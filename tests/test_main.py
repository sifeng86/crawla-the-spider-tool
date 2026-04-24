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
        self.assertFalse(self.main.should_use_preview_cache('py_selenium'))
        self.assertFalse(self.main.should_use_preview_cache('py_playwright'))
        self.assertFalse(self.main.should_use_preview_cache('py_llm'))

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

    def test_parse_arguments_temphtml_exits_zero_after_successful_cache(self):
        with patch.object(self.main, 'cache_preview_content', return_value=True), \
             patch.object(self.main.sys, 'argv', ['main.py', '--temphtml', 'pid_&_https://example.com']):
            with self.assertRaises(SystemExit) as raised:
                self.main.parse_arguments()

        self.assertEqual(raised.exception.code, 0)


if __name__ == '__main__':
    unittest.main()