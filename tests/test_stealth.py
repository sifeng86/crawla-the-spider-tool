import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from login.lib.stealth import StealthConfig


class FakeCdpDriver:
    def __init__(self):
        self.calls = []

    def execute_cdp_cmd(self, command, payload):
        self.calls.append((command, payload))


class FakeScriptDriver:
    def __init__(self):
        self.scripts = []

    def execute_script(self, script):
        self.scripts.append(script)


class StealthTests(unittest.TestCase):
    def test_apply_selenium_stealth_scripts_uses_cdp_when_available(self):
        driver = FakeCdpDriver()

        StealthConfig.apply_selenium_stealth_scripts(driver)

        self.assertEqual(len(driver.calls), 1)
        command, payload = driver.calls[0]
        self.assertEqual(command, 'Page.addScriptToEvaluateOnNewDocument')
        self.assertIn('webdriver', payload['source'])

    def test_apply_selenium_stealth_scripts_falls_back_to_execute_script(self):
        driver = FakeScriptDriver()

        StealthConfig.apply_selenium_stealth_scripts(driver)

        self.assertEqual(len(driver.scripts), 1)
        self.assertIn('navigator', driver.scripts[0])


if __name__ == '__main__':
    unittest.main()