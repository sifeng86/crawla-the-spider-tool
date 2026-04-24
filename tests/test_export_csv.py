import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_export_csv_module(fake_db):
    sys.modules.pop('export_csv', None)
    with patch('login.lib.mongo.mongoHelper.mongo_conn', return_value=fake_db):
        module = importlib.import_module('export_csv')
        return importlib.reload(module)


class ExportCsvTests(unittest.TestCase):
    def setUp(self):
        fake_db = types.SimpleNamespace(contents=types.SimpleNamespace(find=lambda *args, **kwargs: []))
        self.module = load_export_csv_module(fake_db)

    def test_normalize_csv_contents_keeps_simple_lists_unchanged(self):
        value = ['Crawla Data Extractor']

        self.assertEqual(self.module.normalize_csv_contents(value), value)

    def test_normalize_csv_contents_serializes_structured_results(self):
        value = [{'title': 'Crawla', 'cta': 'Get Started'}]

        self.assertEqual(
            self.module.normalize_csv_contents(value),
            '[{"title": "Crawla", "cta": "Get Started"}]',
        )


if __name__ == '__main__':
    unittest.main()