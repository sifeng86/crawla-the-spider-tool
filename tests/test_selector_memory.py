import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
LOGIN_DIR = ROOT / 'login'
for path in (ROOT, LOGIN_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from lib import selector_memory


class SelectorMemoryTests(unittest.TestCase):
    def test_derive_css_fallback_candidates_shortens_selector(self):
        candidates = selector_memory.derive_selector_fallback_candidates(
            'find_element_by_css',
            'main > div.card:nth-child(3) > h3.title',
        )

        self.assertIn('main > div.card > h3.title', candidates)
        self.assertIn('h3.title', candidates)

    def test_get_selector_memory_candidates_prefers_exact_then_general(self):
        with patch.object(
            selector_memory,
            '_fetch_selector_documents',
            side_effect=[
                [
                    {'resolved_param': 'h3'},
                    {'resolved_param': '.docs-heading'},
                ],
                [
                    {'resolved_param': 'h3'},
                    {'resolved_param': 'main h1'},
                ],
            ],
        ):
            candidates = selector_memory.get_selector_memory_candidates(
                'https://docs.github.com/en',
                'py_requests',
                'select_one',
                '.broken-title',
            )

        self.assertEqual(candidates, ['h3', '.docs-heading', 'main h1'])

    def test_record_selector_success_upserts_counter(self):
        collection = MagicMock()
        database = types.SimpleNamespace(selector_memory=collection)

        selector_memory.record_selector_success(
            'https://docs.github.com/en',
            'py_requests',
            'select_one',
            '.broken-title',
            'h3',
            strategy='memory',
            database=database,
        )

        collection.update_one.assert_called_once()
        args, kwargs = collection.update_one.call_args
        self.assertEqual(args[0]['domain'], 'docs.github.com')
        self.assertEqual(args[0]['resolved_param'], 'h3')
        self.assertEqual(args[1]['$set']['strategy'], 'memory')
        self.assertEqual(kwargs['upsert'], True)


if __name__ == '__main__':
    unittest.main()