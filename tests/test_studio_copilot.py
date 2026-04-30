import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LOGIN_DIR = ROOT / 'login'
for path in (ROOT, LOGIN_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from lib.studio_copilot import suggest_studio_copilot_plan


class StudioCopilotTests(unittest.TestCase):
    def test_suggest_studio_copilot_plan_falls_back_to_template_when_llm_unavailable(self):
        with patch('lib.studio_copilot.get_gemini_response', return_value='LLM Error: Google API key not configured'):
            result = suggest_studio_copilot_plan(
                'Collect article titles and links',
                'https://docs.github.com/en',
                'py_requests',
            )

        self.assertEqual(result['source'], 'template')
        self.assertEqual(result['nodes'][0]['step'], 'select_one')
        self.assertEqual(result['nodes'][1]['step'], 'select_all')
        self.assertEqual(result['nodes'][2]['step'], 'ext_str_get_href')
        self.assertEqual(result['memory_hits'], 0)

    def test_suggest_studio_copilot_plan_reuses_selector_memory_for_template_fallback(self):
        database = object()
        with patch('lib.studio_copilot.get_gemini_response', return_value='LLM Error: Google API key not configured'), \
             patch(
                 'lib.studio_copilot.get_selector_memory_summary',
                 return_value={
                     'items': [
                         {
                             'step_name': 'select_one',
                             'resolved_param': 'main .doc-content',
                             'success_count': 4,
                             'strategy': 'memory',
                         },
                         {
                             'step_name': 'select_all',
                             'resolved_param': 'main a',
                             'success_count': 3,
                             'strategy': 'memory',
                         },
                     ],
                 },
             ) as get_selector_memory_summary:
            result = suggest_studio_copilot_plan(
                'Collect article titles and links',
                'https://docs.github.com/en',
                'py_requests',
                database=database,
            )

        self.assertEqual(result['source'], 'template')
        self.assertEqual(result['memory_hits'], 2)
        self.assertEqual(result['nodes'][0]['args'], 'main .doc-content')
        self.assertEqual(result['nodes'][1]['args'], 'main a')
        self.assertIn('selector-memory hits', result['rationale'])
        get_selector_memory_summary.assert_called_once_with(
            'https://docs.github.com/en',
            'py_requests',
            limit=6,
            database=database,
        )

    def test_suggest_studio_copilot_plan_includes_selector_memory_in_llm_prompt(self):
        database = object()
        with patch(
            'lib.studio_copilot.get_selector_memory_summary',
            return_value={
                'items': [
                    {
                        'step_name': 'select_one',
                        'resolved_param': 'main .doc-content',
                        'success_count': 4,
                        'strategy': 'memory',
                    }
                ],
            },
        ), patch('lib.studio_copilot.get_gemini_response', return_value='LLM Error: Google API key not configured') as get_gemini_response:
            suggest_studio_copilot_plan(
                'Collect article titles',
                'https://docs.github.com/en',
                'py_requests',
                database=database,
            )

        llm_prompt = get_gemini_response.call_args[0][0]
        self.assertIn('"selector_memory"', llm_prompt)
        self.assertIn('main .doc-content', llm_prompt)

    def test_suggest_studio_copilot_plan_uses_llm_plan_when_valid(self):
        with patch(
            'lib.studio_copilot.get_gemini_response',
            return_value='{"task_name":"Docs Link Flow","rationale":"Use repeated anchors for docs navigation.","nodes":[{"title":"Collect links","step":"select_all","args":"main a","intent":"Gather the docs links."},{"title":"Read href","step":"ext_str_get_href","args":"-","intent":"Extract the href values."}]}',
        ):
            result = suggest_studio_copilot_plan(
                'Collect docs links',
                'https://docs.github.com/en',
                'py_requests',
            )

        self.assertEqual(result['source'], 'llm')
        self.assertEqual(result['task_name'], 'Docs Link Flow')
        self.assertEqual(result['memory_hits'], 0)
        self.assertEqual(result['nodes'][0]['step'], 'select_all')
        self.assertEqual(result['nodes'][1]['step'], 'ext_str_get_href')

    def test_suggest_studio_copilot_plan_builds_llm_prompt_node_for_llm_method(self):
        with patch('lib.studio_copilot.get_gemini_response', return_value='LLM Error: Google API key not configured'):
            result = suggest_studio_copilot_plan(
                'Extract the hero title and summary as JSON',
                'https://example.com',
                'py_llm',
            )

        self.assertEqual(result['nodes'][0]['step'], 'llm_prompt')
        self.assertIn('Extract the following from the page', result['nodes'][0]['args'])
        self.assertEqual(result['memory_hits'], 0)


if __name__ == '__main__':
    unittest.main()