import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGIN_DIR = ROOT / 'login'
for path in (ROOT, LOGIN_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from lib.studio_inspector import build_inspector_document, build_inspector_response


class StudioInspectorTests(unittest.TestCase):
    def test_build_inspector_document_sanitizes_and_injects_helper(self):
        document = build_inspector_document(
            'https://example.com/docs',
            '<html><head><script>alert(1)</script></head><body><a href="/docs" onclick="evil()">Docs</a></body></html>',
            'Cached HTML preview',
        )

        self.assertIn('Click any element to generate selector candidates for Studio.', document)
        self.assertIn('window.parent.postMessage', document)
        self.assertIn('<base href="https://example.com/docs"', document)
        self.assertNotIn('alert(1)', document)
        self.assertNotIn('onclick=', document)

    def test_build_inspector_response_marks_browser_snapshot_mode(self):
        response = build_inspector_response(
            'studio-preview',
            'py_playwright',
            '<html><body><h1>Docs</h1></body></html>',
            'https://example.com/docs',
        )

        self.assertEqual(response['preview_id'], 'studio-preview')
        self.assertEqual(response['source_mode'], 'http_snapshot')
        self.assertIn('HTTP snapshot', response['note'])
        self.assertIn('Docs', response['html'])


if __name__ == '__main__':
    unittest.main()