"""
Step helpers for BeautifulSoup, Selenium 4.x, and Playwright.
Provides safe method dispatch without using exec().
"""
from typing import Callable, Dict, Any, List, Optional, Union
from selenium.webdriver.common.by import By


class StepExecutor:
    """
    Safe step execution for web scraping without dangerous exec() calls.
    Supports BeautifulSoup, Selenium 4.x, and Playwright.
    """
    
    # BeautifulSoup step handlers
    SOUP_HANDLERS: Dict[str, Callable] = {
        # Element finding
        'find_element_by_id': lambda e, p: e.find(id=p),
        'find_elements_by_id': lambda e, p: e.find_all(id=p),
        'find_element_by_class': lambda e, p: e.find(class_=p),
        'find_elements_by_class': lambda e, p: e.find_all(class_=p),
        'find_element_by_tag': lambda e, p: e.find(p),
        'find_elements_by_tag': lambda e, p: e.find_all(p),
        'select_one': lambda e, p: e.select_one(p),
        'select_all': lambda e, p: e.select(p),
        # Extraction
        'ext_str_get_text': lambda e, _: e.get_text().strip().replace('\n', ' ') if e else '',
        'ext_str_get_attribute': lambda e, p: e.get(p) if e else None,
        'ext_str_get_href': lambda e, _: e.get('href') if e else None,
        'ext_str_get_src': lambda e, _: e.get('src') if e else None,
    }
    
    # Selenium 4.x step handlers
    SELENIUM_HANDLERS: Dict[str, Callable] = {
        # Element finding - single
        'find_element_by_id': lambda d, p: d.find_element(By.ID, p),
        'find_element_by_class': lambda d, p: d.find_element(By.CLASS_NAME, p),
        'find_element_by_css': lambda d, p: d.find_element(By.CSS_SELECTOR, p),
        'find_element_by_xpath': lambda d, p: d.find_element(By.XPATH, p),
        'find_element_by_tag': lambda d, p: d.find_element(By.TAG_NAME, p),
        'find_element_by_name': lambda d, p: d.find_element(By.NAME, p),
        'find_element_by_link_text': lambda d, p: d.find_element(By.LINK_TEXT, p),
        'find_element_by_partial_link': lambda d, p: d.find_element(By.PARTIAL_LINK_TEXT, p),
        # Element finding - multiple
        'find_elements_by_id': lambda d, p: d.find_elements(By.ID, p),
        'find_elements_by_class': lambda d, p: d.find_elements(By.CLASS_NAME, p),
        'find_elements_by_css': lambda d, p: d.find_elements(By.CSS_SELECTOR, p),
        'find_elements_by_xpath': lambda d, p: d.find_elements(By.XPATH, p),
        'find_elements_by_tag': lambda d, p: d.find_elements(By.TAG_NAME, p),
        'find_elements_by_name': lambda d, p: d.find_elements(By.NAME, p),
        'find_elements_by_link_text': lambda d, p: d.find_elements(By.LINK_TEXT, p),
        'find_elements_by_partial_link': lambda d, p: d.find_elements(By.PARTIAL_LINK_TEXT, p),
        # Actions
        'click': lambda e, _: e.click(),
        'send_keys': lambda e, p: e.send_keys(p),
        'clear': lambda e, _: e.clear(),
        'submit': lambda e, _: e.submit(),
        # Extraction
        'ext_str_get_text': lambda e, _: e.text.strip().replace('\n', ' ') if e else '',
        'ext_str_get_attribute': lambda e, p: e.get_attribute(p) if e else None,
        'ext_str_get_value': lambda e, _: e.get_attribute('value') if e else None,
        'ext_str_get_href': lambda e, _: e.get_attribute('href') if e else None,
        'ext_str_get_src': lambda e, _: e.get_attribute('src') if e else None,
        # Navigation
        'scroll_into_view': lambda e, _: e.location_once_scrolled_into_view,
    }
    
    # Playwright step handlers
    PLAYWRIGHT_HANDLERS: Dict[str, Callable] = {
        # Element finding - single
        'find_element_by_id': lambda p, s: p.locator(f'#{s}').first,
        'find_element_by_class': lambda p, s: p.locator(f'.{s}').first,
        'find_element_by_css': lambda p, s: p.locator(s).first,
        'find_element_by_xpath': lambda p, s: p.locator(f'xpath={s}').first,
        'find_element_by_tag': lambda p, s: p.locator(s).first,
        'find_element_by_text': lambda p, s: p.get_by_text(s).first,
        'find_element_by_role': lambda p, s: p.get_by_role(s).first,
        'find_element_by_placeholder': lambda p, s: p.get_by_placeholder(s).first,
        # Element finding - multiple
        'find_elements_by_id': lambda p, s: p.locator(f'#{s}').all(),
        'find_elements_by_class': lambda p, s: p.locator(f'.{s}').all(),
        'find_elements_by_css': lambda p, s: p.locator(s).all(),
        'find_elements_by_xpath': lambda p, s: p.locator(f'xpath={s}').all(),
        'find_elements_by_tag': lambda p, s: p.locator(s).all(),
        'find_elements_by_text': lambda p, s: p.get_by_text(s).all(),
        # Actions
        'click': lambda e, _: e.click(),
        'send_keys': lambda e, p: e.fill(p),
        'clear': lambda e, _: e.fill(''),
        'hover': lambda e, _: e.hover(),
        'focus': lambda e, _: e.focus(),
        'press': lambda e, p: e.press(p),
        'check': lambda e, _: e.check(),
        'uncheck': lambda e, _: e.uncheck(),
        # Extraction
        'ext_str_get_text': lambda e, _: (e.text_content() or '').strip().replace('\n', ' '),
        'ext_str_get_attribute': lambda e, p: e.get_attribute(p),
        'ext_str_get_value': lambda e, _: e.input_value() if hasattr(e, 'input_value') else e.get_attribute('value'),
        'ext_str_get_href': lambda e, _: e.get_attribute('href'),
        'ext_str_get_src': lambda e, _: e.get_attribute('src'),
        'ext_str_get_inner_html': lambda e, _: e.inner_html(),
        # Wait
        'wait_for_visible': lambda e, _: e.wait_for(state='visible'),
        'wait_for_hidden': lambda e, _: e.wait_for(state='hidden'),
        'wait_for_attached': lambda e, _: e.wait_for(state='attached'),
        # Scroll
        'scroll_into_view': lambda e, _: e.scroll_into_view_if_needed(),
    }
    
    @classmethod
    def execute_soup(cls, element: Any, step_name: str, param: str = '') -> Any:
        """
        Execute a BeautifulSoup step safely.
        
        Args:
            element: BeautifulSoup element or soup object
            step_name: Name of the step to execute
            param: Parameter for the step
            
        Returns:
            Result of the step execution
        """
        handler = cls.SOUP_HANDLERS.get(step_name)
        if not handler:
            raise ValueError(f"Unknown BeautifulSoup step: {step_name}")
        return handler(element, param)
    
    @classmethod
    def execute_selenium(cls, element: Any, step_name: str, param: str = '') -> Any:
        """
        Execute a Selenium step safely.
        
        Args:
            element: Selenium WebDriver or WebElement
            step_name: Name of the step to execute
            param: Parameter for the step
            
        Returns:
            Result of the step execution
        """
        handler = cls.SELENIUM_HANDLERS.get(step_name)
        if not handler:
            raise ValueError(f"Unknown Selenium step: {step_name}")
        return handler(element, param)
    
    @classmethod
    def execute_playwright(cls, element: Any, step_name: str, param: str = '') -> Any:
        """
        Execute a Playwright step safely.
        
        Args:
            element: Playwright Page or Locator
            step_name: Name of the step to execute
            param: Parameter for the step
            
        Returns:
            Result of the step execution
        """
        handler = cls.PLAYWRIGHT_HANDLERS.get(step_name)
        if not handler:
            raise ValueError(f"Unknown Playwright step: {step_name}")
        return handler(element, param)
    
    @classmethod
    def get_available_steps(cls, method: str) -> List[str]:
        """
        Get list of available steps for a method.
        
        Args:
            method: 'soup', 'selenium', or 'playwright'
            
        Returns:
            List of available step names
        """
        handlers_map = {
            'soup': cls.SOUP_HANDLERS,
            'selenium': cls.SELENIUM_HANDLERS,
            'playwright': cls.PLAYWRIGHT_HANDLERS,
        }
        handlers = handlers_map.get(method, {})
        return list(handlers.keys())


# Legacy compatibility - keep the old stepHelper class for backward compatibility
class stepHelper:
    """Legacy step helper for backward compatibility."""
    
    @staticmethod
    def get_soup_steps_helper() -> Dict[str, str]:
        """Get BeautifulSoup step templates (legacy format)."""
        return {
            'find_element_by_id': '.find(id="{param}")',
            'find_elements_by_id': '.find_all(id="{param}")',
            'find_element_by_class': '.find(class_="{param}")',
            'find_elements_by_class': '.find_all(class_="{param}")',
            'select_one': '.select_one("{param}")',
            'select_all': '.select("{param}")',
            'ext_str_get_text': '.get_text()',
        }
    
    @staticmethod
    def get_selenium_steps_helper() -> Dict[str, str]:
        """Get Selenium step templates (legacy format - updated for Selenium 4.x)."""
        return {
            'find_element_by_id': '.find_element(By.ID, "{param}")',
            'find_elements_by_id': '.find_elements(By.ID, "{param}")',
            'find_element_by_class': '.find_element(By.CLASS_NAME, "{param}")',
            'find_elements_by_class': '.find_elements(By.CLASS_NAME, "{param}")',
            'find_element_by_css_selector': '.find_element(By.CSS_SELECTOR, "{param}")',
            'find_elements_by_css_selector': '.find_elements(By.CSS_SELECTOR, "{param}")',
            'find_element_by_xpath': '.find_element(By.XPATH, "{param}")',
            'find_elements_by_xpath': '.find_elements(By.XPATH, "{param}")',
            'click': '.click()',
            'ext_str_get_text': '.text',
            'ext_str_get_attribute': '.get_attribute("{param}")',
        }
    
    @staticmethod
    def get_playwright_steps_helper() -> Dict[str, str]:
        """Get Playwright step templates."""
        return {
            'find_element_by_id': '.locator("#{param}").first',
            'find_elements_by_id': '.locator("#{param}").all()',
            'find_element_by_class': '.locator(".{param}").first',
            'find_elements_by_class': '.locator(".{param}").all()',
            'find_element_by_css': '.locator("{param}").first',
            'find_elements_by_css': '.locator("{param}").all()',
            'click': '.click()',
            'ext_str_get_text': '.text_content()',
            'ext_str_get_attribute': '.get_attribute("{param}")',
        }
