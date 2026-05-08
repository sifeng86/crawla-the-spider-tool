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

    def test_templates_do_not_load_jquery_from_unapproved_host(self):
        templates = [
            ROOT / 'login' / 'templates' / 'home.html',
            ROOT / 'login' / 'templates' / 'dashboard.html',
            ROOT / 'login' / 'templates' / 'add_contents.html',
        ]

        for template_path in templates:
            content = template_path.read_text(encoding='utf-8')
            self.assertNotIn('code.jquery.com', content, msg=str(template_path))

        add_contents = templates[-1].read_text(encoding='utf-8')
        self.assertIn('https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js', add_contents)

    def test_primary_web_templates_use_brand_mark_component(self):
        templates = [
            ROOT / 'login' / 'templates' / 'home.html',
            ROOT / 'login' / 'templates' / 'add_contents.html',
            ROOT / 'login' / 'templates' / 'studio.html',
        ]

        for template_path in templates:
            content = template_path.read_text(encoding='utf-8')
            self.assertIn('crawla-mark', content, msg=str(template_path))
            self.assertNotIn('header-logo.png', content, msg=str(template_path))

    def test_shared_app_css_does_not_import_google_fonts(self):
        content = (ROOT / 'login' / 'public' / 'app.css').read_text(encoding='utf-8')

        self.assertNotIn('fonts.googleapis.com', content)

    def test_fontawesome_links_use_expected_sri(self):
        expected_integrity = 'sha384-wESLQ85D6gbsF459vf1CiZ2+rr+CsxRY0RpiF1tLlQpDnAgg6rwdsUF1+Ics2bni'
        templates = [
            ROOT / 'login' / 'templates' / 'home.html',
            ROOT / 'login' / 'templates' / 'dashboard.html',
            ROOT / 'login' / 'templates' / 'add_contents.html',
        ]

        for template_path in templates:
            content = template_path.read_text(encoding='utf-8')
            self.assertIn(expected_integrity, content, msg=str(template_path))

        studio = (ROOT / 'login' / 'templates' / 'studio.html').read_text(encoding='utf-8')
        self.assertNotIn('@fortawesome/fontawesome-free@5.15.3/css/fontawesome.min.css', studio)

    def test_classic_templates_load_fontawesome_solid_icons(self):
        templates = [
            ROOT / 'login' / 'templates' / 'home.html',
            ROOT / 'login' / 'templates' / 'dashboard.html',
            ROOT / 'login' / 'templates' / 'add_contents.html',
        ]

        for template_path in templates:
            content = template_path.read_text(encoding='utf-8')
            self.assertIn('@fortawesome/fontawesome-free@5.15.3/css/solid.min.css', content, msg=str(template_path))

    def test_studio_template_surfaces_checklists_and_button_guards(self):
        content = (ROOT / 'login' / 'templates' / 'studio.html').read_text(encoding='utf-8')

        self.assertIn('studio-method-list-compact', content)
        self.assertIn('studio-preview-meta-row', content)
        self.assertIn('Optional tools', content)
        self.assertIn('setGuardedButtonState', content)
        self.assertIn('renderActionAvailability', content)
        self.assertIn('renderHelperPanels', content)
        self.assertIn('studio-helper-grid-stacked', content)
        self.assertIn('studio-action-card', content)
        self.assertIn('studio-tip', content)
        self.assertIn('getPreviewDependencySnapshot', content)
        self.assertIn('getPreviewStaleReason', content)
        self.assertIn('last_attempt_signature', content)
        self.assertIn('studio-toggle-copilot-panel', content)
        self.assertIn('studio-toggle-inspector-panel', content)

    def test_studio_flow_editor_protects_form_controls_from_card_click_rerenders(self):
        content = (ROOT / 'login' / 'templates' / 'studio.html').read_text(encoding='utf-8')

        self.assertIn("flowList.addEventListener('focusin'", content)
        self.assertIn("input, select, textarea, button, a, label", content)


if __name__ == '__main__':
    unittest.main()