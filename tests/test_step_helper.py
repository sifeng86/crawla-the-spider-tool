import sys
import unittest
from pathlib import Path

from selenium.webdriver.common.by import By


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from login.lib.step_helper import StepExecutor


class FakeSeleniumElement:
    def __init__(self):
        self.calls = []

    def find_element(self, by, value):
        self.calls.append(('find_element', by, value))
        return 'single'


class FakeLocator:
    def __init__(self, selector):
        self.selector = selector
        self.first = ('first', selector)


class FakePlaywrightPage:
    def locator(self, selector):
        return FakeLocator(selector)


class StepHelperTests(unittest.TestCase):
    def test_execute_selenium_accepts_legacy_css_selector_name(self):
        element = FakeSeleniumElement()

        result = StepExecutor.execute_selenium(element, 'find_element_by_css_selector', '.price')

        self.assertEqual(result, 'single')
        self.assertEqual(element.calls, [('find_element', By.CSS_SELECTOR, '.price')])

    def test_execute_playwright_accepts_legacy_css_selector_name(self):
        page = FakePlaywrightPage()

        result = StepExecutor.execute_playwright(page, 'find_element_by_css_selector', '.price')

        self.assertEqual(result, ('first', '.price'))


if __name__ == '__main__':
    unittest.main()