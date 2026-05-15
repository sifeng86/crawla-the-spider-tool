"""
Playwright helper for fast, stealth web scraping.
2-3x faster than Selenium with better anti-detection.
"""
from typing import Optional, List, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from .stealth import StealthConfig
from .rate_limiter import rate_limiter


class PlaywrightHelper:
    """
    Helper class for Playwright-based web scraping with stealth mode.
    """
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        use_stealth: bool = True,
        use_rate_limit: bool = True
    ):
        """
        Initialize Playwright helper.
        
        Args:
            headless: Run browser in headless mode
            timeout: Default timeout in milliseconds
            use_stealth: Apply anti-detection measures
            use_rate_limit: Apply rate limiting
        """
        self.headless = headless
        self.timeout = timeout
        self.use_stealth = use_stealth
        self.use_rate_limit = use_rate_limit
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
    
    def start(self):
        """Start the Playwright browser."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        if self.use_stealth:
            self._context = StealthConfig.get_playwright_stealth_context(self._browser)
        else:
            self._context = self._browser.new_context()
        
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        
        if self.use_stealth:
            StealthConfig.apply_playwright_stealth_scripts(self._page)
    
    def stop(self):
        """Stop the Playwright browser and clean up."""
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
    
    def get_page(self) -> Optional[Page]:
        """Get the current page instance."""
        return self._page
    
    def goto(self, url: str, wait_until: str = 'networkidle') -> bool:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            wait_until: When to consider navigation done
                       ('load', 'domcontentloaded', 'networkidle')
        
        Returns:
            True if navigation successful
        """
        if self.use_rate_limit:
            rate_limiter.wait_if_needed(url)
        
        try:
            self._page.goto(url, wait_until=wait_until, timeout=self.timeout)
            return True
        except Exception as e:
            print(f"Navigation error: {e}")
            return False
    
    def get_content(self) -> str:
        """Get the page HTML content."""
        return self._page.content()
    
    def get_text(self) -> str:
        """Get all text content from the page."""
        return self._page.inner_text('body')
    
    def screenshot(self, path: str = 'screenshot.png', full_page: bool = False):
        """Take a screenshot of the page."""
        self._page.screenshot(path=path, full_page=full_page)
    
    # Element finding methods
    def find_element(self, selector: str):
        """Find a single element by CSS selector."""
        return self._page.locator(selector).first
    
    def find_elements(self, selector: str) -> List:
        """Find all elements matching CSS selector."""
        return self._page.locator(selector).all()
    
    def find_by_xpath(self, xpath: str):
        """Find element by XPath."""
        return self._page.locator(f'xpath={xpath}').first
    
    def find_all_by_xpath(self, xpath: str) -> List:
        """Find all elements by XPath."""
        return self._page.locator(f'xpath={xpath}').all()
    
    def find_by_text(self, text: str, exact: bool = False):
        """Find element containing text."""
        if exact:
            return self._page.get_by_text(text, exact=True).first
        return self._page.get_by_text(text).first
    
    # Action methods
    def click(self, selector: str):
        """Click an element."""
        self._page.click(selector)
    
    def fill(self, selector: str, value: str):
        """Fill a form field."""
        self._page.fill(selector, value)
    
    def type_text(self, selector: str, text: str, delay: int = 50):
        """Type text with human-like delay."""
        self._page.type(selector, text, delay=delay)
    
    def hover(self, selector: str):
        """Hover over an element."""
        self._page.hover(selector)
    
    def scroll_to(self, selector: str):
        """Scroll element into view."""
        self._page.locator(selector).scroll_into_view_if_needed()
    
    def scroll_page(self, direction: str = 'down', amount: int = 500):
        """Scroll the page."""
        if direction == 'down':
            self._page.mouse.wheel(0, amount)
        elif direction == 'up':
            self._page.mouse.wheel(0, -amount)
    
    # Wait methods
    def wait_for_selector(self, selector: str, state: str = 'visible', timeout: int = None):
        """
        Wait for an element.
        
        Args:
            selector: CSS selector
            state: 'attached', 'detached', 'visible', 'hidden'
            timeout: Custom timeout in ms
        """
        self._page.wait_for_selector(selector, state=state, timeout=timeout or self.timeout)
    
    def wait_for_load_state(self, state: str = 'networkidle'):
        """Wait for page load state."""
        self._page.wait_for_load_state(state)
    
    def wait_for_timeout(self, ms: int):
        """Wait for specified milliseconds."""
        self._page.wait_for_timeout(ms)
    
    # Extraction methods
    def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get element attribute value."""
        element = self._page.locator(selector).first
        return element.get_attribute(attribute)
    
    def get_text_content(self, selector: str) -> str:
        """Get text content of an element."""
        return self._page.locator(selector).first.text_content() or ''
    
    def get_all_text_contents(self, selector: str) -> List[str]:
        """Get text content of all matching elements."""
        return self._page.locator(selector).all_text_contents()
    
    def evaluate(self, expression: str) -> Any:
        """Execute JavaScript in the page context."""
        return self._page.evaluate(expression)


def get_page_content(url: str, timeout: int = 30000, use_stealth: bool = True) -> str:
    """
    Quick function to get page content with stealth mode.
    
    Args:
        url: URL to fetch
        timeout: Timeout in milliseconds
        use_stealth: Apply anti-detection measures
    
    Returns:
        Page HTML content
    """
    with PlaywrightHelper(timeout=timeout, use_stealth=use_stealth) as pw:
        pw.goto(url)
        return pw.get_content()
