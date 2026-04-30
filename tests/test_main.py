import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_main_module(fake_db):
    sys.modules.pop('main', None)
    with patch('login.lib.mongo.mongoHelper.mongo_conn', return_value=fake_db):
        module = importlib.import_module('main')
        return importlib.reload(module)


class MainModuleTests(unittest.TestCase):
    def setUp(self):
        self.fake_db = types.SimpleNamespace(
            preview_contents=MagicMock(),
            contents=MagicMock(),
            urls=MagicMock(),
        )
        self.main = load_main_module(self.fake_db)

    def test_should_use_preview_cache_only_for_requests(self):
        self.assertTrue(self.main.should_use_preview_cache('py_requests'))
        self.assertTrue(self.main.should_use_preview_cache('py_llm'))
        self.assertFalse(self.main.should_use_preview_cache('py_selenium'))
        self.assertFalse(self.main.should_use_preview_cache('py_playwright'))

    def test_get_requests_accept_encoding_defaults_without_brotli(self):
        with patch.object(self.main, 'supports_brotli', return_value=False):
            self.assertEqual(self.main.get_requests_accept_encoding(), 'gzip, deflate')

    def test_get_requests_accept_encoding_includes_brotli_when_supported(self):
        with patch.object(self.main, 'supports_brotli', return_value=True):
            self.assertEqual(self.main.get_requests_accept_encoding(), 'gzip, deflate, br')

    def test_cache_preview_content_prefers_requests_for_llm(self):
        response = types.SimpleNamespace(text='<html>fast-preview</html>')

        with patch.object(self.main, 'get_page_requests', return_value=response), \
             patch.object(self.main, 'get_page_playwright') as get_page_playwright:
            result = self.main.cache_preview_content('pid-llm', 'https://example.com', 'py_llm')

        self.assertTrue(result)
        get_page_playwright.assert_not_called()
        self.fake_db.preview_contents.update_one.assert_called_once_with(
            {'preview_id': 'pid-llm'},
            {
                '$set': {
                    'url': 'https://example.com',
                    'preview_id': 'pid-llm',
                    'method': 'py_llm',
                    'contents': '<html>fast-preview</html>',
                    'created_at': ANY,
                }
            },
            upsert=True,
        )

    def test_cache_preview_content_falls_back_to_playwright_for_llm(self):
        with patch.object(self.main, 'get_page_requests', return_value=None), \
             patch.object(self.main, 'get_page_playwright', return_value='<html>rendered</html>'):
            result = self.main.cache_preview_content('pid-llm-fallback', 'https://example.com', 'py_llm')

        self.assertTrue(result)
        self.fake_db.preview_contents.update_one.assert_called_once_with(
            {'preview_id': 'pid-llm-fallback'},
            {
                '$set': {
                    'url': 'https://example.com',
                    'preview_id': 'pid-llm-fallback',
                    'method': 'py_llm',
                    'contents': '<html>rendered</html>',
                    'created_at': ANY,
                }
            },
            upsert=True,
        )

    def test_cache_preview_content_upserts_latest_html(self):
        response = types.SimpleNamespace(text='<html>fresh</html>')

        with patch.object(self.main, 'get_page_requests', return_value=response):
            result = self.main.cache_preview_content('pid-1', 'https://example.com')

        self.assertTrue(result)
        self.fake_db.preview_contents.update_one.assert_called_once_with(
            {'preview_id': 'pid-1'},
            {
                '$set': {
                    'url': 'https://example.com',
                    'preview_id': 'pid-1',
                    'method': 'py_requests',
                    'contents': '<html>fresh</html>',
                    'created_at': ANY,
                }
            },
            upsert=True,
        )

    def test_load_preview_content_skips_non_requests_methods(self):
        self.assertIsNone(self.main.load_preview_content('pid-2', 'py_selenium'))
        self.fake_db.preview_contents.find.assert_not_called()

    def test_load_preview_content_returns_cached_html_for_requests(self):
        cursor = MagicMock()
        cursor.limit.return_value = [{'contents': '<html>cached</html>'}]
        self.fake_db.preview_contents.find.return_value = cursor

        content = self.main.load_preview_content('pid-3', 'py_requests')

        self.assertEqual(content, '<html>cached</html>')
        self.fake_db.preview_contents.find.assert_called_once_with({'preview_id': 'pid-3'})

    def test_process_crawl_task_ignores_cached_html_for_selenium(self):
        driver = MagicMock()
        seed = {
            'c_method': 'py_selenium',
            'url': 'https://example.com',
            'steps': ['find_element_by_css_selector'],
            'args': ['.price'],
        }

        with patch.object(self.main, 'get_page_selenium', return_value=('<html>live</html>', driver)), \
             patch.object(self.main, 'execute_selenium_steps', return_value=['ok']) as execute_selenium_steps, \
             patch.object(self.main, 'execute_soup_steps', return_value=['cached']) as execute_soup_steps:
            result = self.main.process_crawl_task(seed, response_cache='<html>cached</html>')

        self.assertEqual(result, ['ok'])
        execute_soup_steps.assert_not_called()
        execute_selenium_steps.assert_called_once_with(
            driver,
            [('find_element_by_css_selector', '.price')],
        )
        driver.save_screenshot.assert_called_once_with('screenshot.png')
        driver.quit.assert_called_once()

    def test_process_crawl_task_ignores_cached_html_for_playwright(self):
        seed = {
            'c_method': 'py_playwright',
            'url': 'https://example.com',
            'steps': ['find_element_by_css_selector'],
            'args': ['.price'],
        }

        helper_instance = MagicMock()
        helper_instance.__enter__.return_value = helper_instance
        helper_instance.get_page.return_value = 'page'

        with patch('login.lib.playwright_helper.PlaywrightHelper', return_value=helper_instance), \
             patch.object(self.main, 'execute_playwright_steps', return_value=['ok']) as execute_playwright_steps, \
             patch.object(self.main, 'execute_soup_steps', return_value=['cached']) as execute_soup_steps:
            result = self.main.process_crawl_task(seed, response_cache='<html>cached</html>')

        self.assertEqual(result, ['ok'])
        execute_soup_steps.assert_not_called()
        helper_instance.goto.assert_called_once_with('https://example.com')
        execute_playwright_steps.assert_called_once_with('page', [('find_element_by_css_selector', '.price')])

    def test_process_crawl_task_uses_cached_html_for_llm_preview(self):
        seed = {
            'c_method': 'py_llm',
            'url': 'https://example.com',
            'args': ['What is the title?'],
        }

        with patch.object(self.main, 'get_page_playwright') as get_page_playwright, \
             patch('login.lib.llm_handler.get_gemini_response', return_value='Crawla Title'):
            result = self.main.process_crawl_task(seed, response_cache='<html>cached llm</html>')

        self.assertEqual(result, ['Crawla Title'])
        get_page_playwright.assert_not_called()

    def test_process_crawl_task_returns_structured_json_for_smart_extraction(self):
        seed = {
            'c_method': 'py_llm',
            'url': 'https://example.com',
            'args': ['{"type":"object"}'],
        }

        with patch('login.lib.llm_handler.get_gemini_smart_extraction', return_value={'title': 'Crawla'}):
            result = self.main.process_crawl_task(seed, response_cache='<html>cached llm</html>')

        self.assertEqual(result, [{'title': 'Crawla'}])

    def test_execute_soup_steps_attempts_llm_self_healing(self):
        soup = object()
        healed_node = object()

        def execute_soup_side_effect(current, step_name, param):
            if step_name == 'select_one' and param == '.broken-title':
                return None
            if step_name == 'select_one' and param == 'h3':
                return healed_node
            if step_name == 'ext_str_get_text' and current is healed_node:
                return 'Crawla Data Extractor'
            return None

        with patch.object(self.main.StepExecutor, 'execute_soup', side_effect=execute_soup_side_effect), \
             patch('login.lib.llm_handler.get_gemini_self_healing', return_value='h3'):
            result = self.main.execute_soup_steps(soup, [('select_one', '.broken-title'), ('ext_str_get_text', '-')])

        self.assertEqual(result, ['Crawla Data Extractor'])

    def test_execute_selenium_steps_attempts_llm_self_healing(self):
        driver = MagicMock()
        driver.page_source = '<html><h3>Crawla Data Extractor</h3></html>'
        healed_node = object()

        def execute_selenium_side_effect(current, step_name, param):
            if step_name == 'find_element_by_css' and param == '.broken-title':
                raise ValueError('not found')
            if step_name == 'find_element_by_css' and param == 'h3':
                return healed_node
            if step_name == 'ext_str_get_text' and current is healed_node:
                return 'Crawla Data Extractor'
            return None

        with patch.object(self.main.StepExecutor, 'execute_selenium', side_effect=execute_selenium_side_effect), \
             patch('login.lib.llm_handler.get_gemini_self_healing', return_value='h3'):
            result = self.main.execute_selenium_steps(driver, [('find_element_by_css', '.broken-title'), ('ext_str_get_text', '-')])

        self.assertEqual(result, ['Crawla Data Extractor'])

    def test_execute_playwright_steps_attempts_llm_self_healing(self):
        page = MagicMock()
        page.content.return_value = '<html><h3>Crawla Data Extractor</h3></html>'
        broken_locator = MagicMock()
        broken_locator.count.return_value = 0
        healed_locator = MagicMock()
        healed_locator.count.return_value = 1

        def execute_playwright_side_effect(current, step_name, param):
            if step_name == 'find_element_by_css' and param == '.broken-title':
                return broken_locator
            if step_name == 'find_element_by_css' and param == 'h3':
                return healed_locator
            if step_name == 'ext_str_get_text' and current is healed_locator:
                return 'Crawla Data Extractor'
            return None

        with patch.object(self.main.StepExecutor, 'execute_playwright', side_effect=execute_playwright_side_effect), \
             patch('login.lib.llm_handler.get_gemini_self_healing', return_value='h3'):
            result = self.main.execute_playwright_steps(page, [('find_element_by_css', '.broken-title'), ('ext_str_get_text', '-')])

        self.assertEqual(result, ['Crawla Data Extractor'])

    def test_format_preview_results_uses_json(self):
        result = self.main.format_preview_results([{'title': 'Crawla'}])

        self.assertEqual(result, '[{"title": "Crawla"}]')

    def test_parse_arguments_temphtml_exits_zero_after_successful_cache(self):
        with patch.object(self.main, 'cache_preview_content', return_value=True), \
             patch.object(self.main.sys, 'argv', ['main.py', '--temphtml', 'pid_&_https://example.com']):
            with self.assertRaises(SystemExit) as raised:
                self.main.parse_arguments()

        self.assertEqual(raised.exception.code, 0)

    def test_parse_arguments_temphtml_supports_optional_method(self):
        with patch.object(self.main, 'cache_preview_content', return_value=True) as cache_preview_content, \
             patch.object(self.main.sys, 'argv', ['main.py', '--temphtml', 'pid_&_https://example.com_&_py_llm']):
            with self.assertRaises(SystemExit) as raised:
                self.main.parse_arguments()

        self.assertEqual(raised.exception.code, 0)
        cache_preview_content.assert_called_once_with('pid', 'https://example.com', 'py_llm')


if __name__ == '__main__':
    unittest.main()