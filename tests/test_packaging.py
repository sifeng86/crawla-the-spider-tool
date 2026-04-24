import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class PackagingTests(unittest.TestCase):
    def test_startup_script_uses_lf_line_endings(self):
        content = (ROOT / 'startup.sh').read_bytes()

        self.assertNotIn(b'\r\n', content)
        self.assertTrue(content.startswith(b'#!/bin/bash\n'))

    def test_dockerfile_runs_as_non_root_user(self):
        content = (ROOT / 'Dockerfile').read_text(encoding='utf-8')

        self.assertIn('USER crawla', content)

    def test_dockerfile_uses_shared_playwright_browser_path(self):
        content = (ROOT / 'Dockerfile').read_text(encoding='utf-8')

        self.assertIn('ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright', content)


if __name__ == '__main__':
    unittest.main()