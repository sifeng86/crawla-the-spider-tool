"""
Anti-detection stealth configuration for web crawlers.
Helps prevent websites from detecting automation.
"""
import random
from typing import List, Optional


class StealthConfig:
    """Anti-detection configuration for Selenium and Playwright crawlers."""

    SELENIUM_STEALTH_SCRIPT = '''
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    '''
    
    # Modern user agents (updated January 2025)
    USER_AGENTS: List[str] = [
        # Chrome on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        # Chrome on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        # Firefox on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
        # Firefox on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0',
        # Safari on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
        # Edge on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    ]
    
    # Common viewport sizes
    VIEWPORTS = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1536, 'height': 864},
        {'width': 1440, 'height': 900},
        {'width': 1280, 'height': 720},
    ]
    
    # Common locales
    LOCALES = ['en-US', 'en-GB', 'en-CA', 'en-AU']
    
    # Common timezones
    TIMEZONES = [
        'America/New_York',
        'America/Los_Angeles',
        'America/Chicago',
        'Europe/London',
        'Asia/Hong_Kong',
    ]
    
    @classmethod
    def get_random_ua(cls) -> str:
        """Get a random user agent string."""
        return random.choice(cls.USER_AGENTS)
    
    @classmethod
    def get_random_viewport(cls) -> dict:
        """Get a random viewport size."""
        return random.choice(cls.VIEWPORTS)
    
    @classmethod
    def get_random_locale(cls) -> str:
        """Get a random locale."""
        return random.choice(cls.LOCALES)
    
    @classmethod
    def get_random_timezone(cls) -> str:
        """Get a random timezone."""
        return random.choice(cls.TIMEZONES)
    
    @classmethod
    def apply_selenium_stealth(cls, options, user_agent: Optional[str] = None):
        """
        Apply stealth settings to Selenium ChromeOptions.
        
        Args:
            options: selenium.webdriver.chrome.options.Options instance
            user_agent: Optional custom user agent, random if not provided
        
        Returns:
            Modified options object
        """
        ua = user_agent or cls.get_random_ua()
        viewport = cls.get_random_viewport()
        
        # Basic options
        options.add_argument(f'user-agent={ua}')
        options.add_argument(f'--window-size={viewport["width"]},{viewport["height"]}')
        options.add_argument('--headless=new')  # New headless mode (less detectable)
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Anti-detection arguments
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-running-insecure-content')
        
        # Experimental options to hide automation
        options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Preferences to appear more human
        prefs = {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False,
            'profile.default_content_setting_values.notifications': 2,
        }
        options.add_experimental_option('prefs', prefs)
        
        return options
    
    @classmethod
    def apply_selenium_stealth_scripts(cls, driver):
        """
        Execute JavaScript to further hide automation signals.
        Call this after page load.
        
        Args:
            driver: Selenium WebDriver instance
        """
        if hasattr(driver, 'execute_cdp_cmd'):
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': cls.SELENIUM_STEALTH_SCRIPT
            })
            return

        if hasattr(driver, 'execute_script'):
            driver.execute_script(cls.SELENIUM_STEALTH_SCRIPT)

    
    @classmethod
    def get_playwright_stealth_context(cls, browser, user_agent: Optional[str] = None):
        """
        Create a stealth browser context for Playwright.
        
        Args:
            browser: Playwright browser instance
            user_agent: Optional custom user agent, random if not provided
        
        Returns:
            BrowserContext with stealth settings
        """
        ua = user_agent or cls.get_random_ua()
        viewport = cls.get_random_viewport()
        locale = cls.get_random_locale()
        timezone = cls.get_random_timezone()
        
        context = browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale=locale,
            timezone_id=timezone,
            color_scheme='light',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': f'{locale},en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
        )
        
        return context
    
    @classmethod
    def apply_playwright_stealth_scripts(cls, page):
        """
        Add stealth scripts to Playwright page.
        Call this before navigation.
        
        Args:
            page: Playwright page instance
        """
        page.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ];
                    plugins.item = (i) => plugins[i];
                    plugins.namedItem = (name) => plugins.find(p => p.name === name);
                    plugins.refresh = () => {};
                    return plugins;
                }
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Mock chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)
