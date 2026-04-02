"""
Crawla - Main crawler script.
Supports multiple crawling methods: requests, Selenium, Playwright, and LLM.
"""
import requests
import json
import sys
import datetime
from typing import List, Dict, Any, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

from login.lib.step_helper import StepExecutor
from login.lib.mongo import mongoHelper
from login.lib.stealth import StealthConfig
from login.lib.rate_limiter import rate_limiter


# Connection to mongodb
db = mongoHelper.mongo_conn()


def get_page_requests(url: str, use_rate_limit: bool = True) -> Optional[requests.Response]:
    """
    Fetch page using requests library with stealth headers.
    
    Args:
        url: URL to fetch
        use_rate_limit: Apply rate limiting
        
    Returns:
        Response object or None on error
    """
    if use_rate_limit:
        rate_limiter.wait_if_needed(url)
    
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="131"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": StealthConfig.get_random_ua()
    }
    
    try:
        response = requests.get(url=url, headers=headers, timeout=30)
        return response
    except Exception as e:
        print(f"Error fetching URL with requests: {e}")
        return None


def get_page_selenium(url: str, use_rate_limit: bool = True) -> Tuple[Optional[str], Optional[webdriver.Remote]]:
    """
    Fetch page using Selenium with stealth mode.
    
    Args:
        url: URL to fetch
        use_rate_limit: Apply rate limiting
        
    Returns:
        Tuple of (page_source, driver) or (None, None) on error
    """
    if use_rate_limit:
        rate_limiter.wait_if_needed(url)
    
    try:
        options = Options()
        options = StealthConfig.apply_selenium_stealth(options)
        
        driver = webdriver.Remote(
            command_executor='http://chrome:4444/wd/hub',
            options=options
        )
        driver.implicitly_wait(10)
        driver.get(url)
        
        # Apply additional stealth scripts
        StealthConfig.apply_selenium_stealth_scripts(driver)
        
        return driver.page_source, driver
    except Exception as e:
        print(f"Error fetching URL with Selenium: {e}")
        return None, None


def get_page_playwright(url: str, use_rate_limit: bool = True) -> Optional[str]:
    """
    Fetch page using Playwright with stealth mode.
    
    Args:
        url: URL to fetch
        use_rate_limit: Apply rate limiting
        
    Returns:
        Page content or None on error
    """
    if use_rate_limit:
        rate_limiter.wait_if_needed(url)
    
    try:
        from login.lib.playwright_helper import PlaywrightHelper
        
        with PlaywrightHelper(use_stealth=True, use_rate_limit=False) as pw:
            pw.goto(url)
            return pw.get_content()
    except Exception as e:
        print(f"Error fetching URL with Playwright: {e}")
        return None


def execute_soup_steps(soup: BeautifulSoup, steps: List[Tuple[str, str]]) -> List[Any]:
    """
    Execute BeautifulSoup steps safely without exec().
    
    Args:
        soup: BeautifulSoup object
        steps: List of (step_name, param) tuples
        
    Returns:
        List of extracted results
    """
    results = []
    temp = soup
    original = soup
    
    for step_name, param in steps:
        try:
            print(f'Executing step: {step_name} with param: {param}')
            
            if 'ext_str_' in step_name:
                # Extraction step - collect results
                if isinstance(temp, list):
                    item_list = []
                    for item in temp:
                        extracted = StepExecutor.execute_soup(item, step_name, param)
                        if extracted:
                            item_list.append(extracted)
                    results.append(item_list)
                else:
                    extracted = StepExecutor.execute_soup(temp, step_name, param)
                    results.append(extracted)
                # Reset to original after extraction
                temp = original
            else:
                # Navigation step - update temp
                temp = StepExecutor.execute_soup(temp, step_name, param)
                
        except Exception as e:
            print(f"Step failed: {step_name} - {e}")
    
    return results


def execute_selenium_steps(driver: webdriver.Remote, steps: List[Tuple[str, str]]) -> List[Any]:
    """
    Execute Selenium steps safely without exec().
    
    Args:
        driver: Selenium WebDriver
        steps: List of (step_name, param) tuples
        
    Returns:
        List of extracted results
    """
    results = []
    current = driver
    
    for step_name, param in steps:
        try:
            print(f'Executing Selenium step: {step_name} with param: {param}')
            
            if 'ext_str_' in step_name:
                # Extraction step
                if isinstance(current, list):
                    item_list = []
                    for item in current:
                        extracted = StepExecutor.execute_selenium(item, step_name, param)
                        if extracted:
                            item_list.append(extracted)
                    results.append(item_list)
                else:
                    extracted = StepExecutor.execute_selenium(current, step_name, param)
                    results.append(extracted)
                # Reset to driver after extraction
                current = driver
            else:
                # Navigation/action step
                result = StepExecutor.execute_selenium(current, step_name, param)
                if result is not None:
                    current = result
                    
        except Exception as e:
            print(f"Selenium step failed: {step_name} - {e}")
    
    return results


def execute_playwright_steps(page, steps: List[Tuple[str, str]]) -> List[Any]:
    """
    Execute Playwright steps safely without exec().
    
    Args:
        page: Playwright Page object
        steps: List of (step_name, param) tuples
        
    Returns:
        List of extracted results
    """
    results = []
    current = page
    
    for step_name, param in steps:
        try:
            print(f'Executing Playwright step: {step_name} with param: {param}')
            
            if 'ext_str_' in step_name:
                # Extraction step
                if isinstance(current, list):
                    item_list = []
                    for item in current:
                        extracted = StepExecutor.execute_playwright(item, step_name, param)
                        if extracted:
                            item_list.append(extracted)
                    results.append(item_list)
                else:
                    extracted = StepExecutor.execute_playwright(current, step_name, param)
                    results.append(extracted)
                # Reset to page after extraction
                current = page
            else:
                # Navigation/action step
                result = StepExecutor.execute_playwright(current, step_name, param)
                if result is not None:
                    current = result
                    
        except Exception as e:
            print(f"Playwright step failed: {step_name} - {e}")
    
    return results


def process_crawl_task(seed: Dict[str, Any], response_cache: Optional[str] = None) -> List[Any]:
    """
    Process a single crawl task.
    
    Args:
        seed: Task configuration from database
        response_cache: Pre-cached response content
        
    Returns:
        List of extracted results
    """
    results = []
    method = seed.get('c_method', 'py_requests')
    url = seed.get('url', '')
    steps = list(zip(seed.get('steps', []), seed.get('args', [])))
    
    print(f"Processing task with method: {method}, URL: {url}")
    
    if method == "py_requests":
        if response_cache:
            soup = BeautifulSoup(response_cache, 'html.parser')
        else:
            response = get_page_requests(url)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
            else:
                return results
        
        results = execute_soup_steps(soup, steps)
        
    elif method == "py_selenium":
        page_source, driver = get_page_selenium(url)
        
        if driver:
            try:
                if response_cache:
                    # Use cached content for soup-based extraction
                    soup = BeautifulSoup(response_cache, 'html.parser')
                    results = execute_soup_steps(soup, steps)
                else:
                    results = execute_selenium_steps(driver, steps)
                    driver.save_screenshot("screenshot.png")
            finally:
                driver.quit()
                
    elif method == "py_playwright":
        from login.lib.playwright_helper import PlaywrightHelper
        
        with PlaywrightHelper(use_stealth=True) as pw:
            pw.goto(url)
            page = pw.get_page()
            
            if response_cache:
                soup = BeautifulSoup(response_cache, 'html.parser')
                results = execute_soup_steps(soup, steps)
            else:
                results = execute_playwright_steps(page, steps)
                
    elif method == "py_llm":
        # LLM method - fetch page and pass to LLM
        page_content = get_page_playwright(url)
        if page_content:
            results.append(page_content)
    
    return results


def save_results(seed: Dict[str, Any], results: List[Any], mode: str = "normal"):
    """
    Save crawl results to database.
    
    Args:
        seed: Task configuration
        results: Extracted results
        mode: Operation mode
    """
    if mode != "normal":
        return
    
    items = {
        'contents': results,
        'task_id': seed.get('task_id'),
        'task_name': seed.get('task_name'),
        'noti_email': seed.get('noti_email'),
        'created_at': datetime.datetime.utcnow(),
        'created_date': str(datetime.datetime.utcnow().date()),
    }
    
    user_id = seed.get('user_id')
    if user_id and user_id == 'auth0|60f28997680b890068f4bea7':
        items['demo'] = datetime.datetime.utcnow()
    
    db.contents.insert_one(items)


def parse_arguments() -> Tuple[str, Optional[str], List[Dict]]:
    """
    Parse command line arguments.
    
    Returns:
        Tuple of (mode, extra_arg, records)
    """
    if len(sys.argv) <= 1:
        sys.exit('No parameters provided')
    
    mode = "normal"
    records = []
    
    if sys.argv[1] == '--all':
        results = db.urls.find()
        records = list(results)
        
    elif sys.argv[1] == '--py_requests':
        results = db.urls.find({"c_method": "py_requests"})
        records = list(results)
        
    elif sys.argv[1] == '--py_selenium':
        results = db.urls.find({"c_method": "py_selenium"})
        records = list(results)
        
    elif sys.argv[1] == '--py_playwright':
        results = db.urls.find({"c_method": "py_playwright"})
        records = list(results)
        
    elif sys.argv[1] == '--py_llm':
        results = db.urls.find({"c_method": "py_llm"})
        records = list(results)
        
    elif sys.argv[1] == '--user':
        if len(sys.argv) < 3:
            sys.exit('User parameter is missing')
        user_id = sys.argv[2]
        results = db.urls.find({"user_id": user_id}).sort("_id", -1).limit(1)
        records = list(results)
        
    elif sys.argv[1] == '--task':
        if len(sys.argv) < 3:
            sys.exit('Task parameter is missing')
        task_id = sys.argv[2]
        results = db.urls.find({"task_id": task_id}).sort("_id", -1).limit(1)
        records = list(results)
        
    elif sys.argv[1] == '--temphtml':
        mode = "temphtml"
        if len(sys.argv) < 3:
            sys.exit('Preview parameter is missing')
        arg_pid, arg_url = sys.argv[2].split('_&_')
        
        results = db.preview_contents.find({"preview_id": arg_pid}).sort("_id", -1).limit(1)
        existing = list(results)
        
        if len(existing) == 0:
            response = get_page_requests(arg_url)
            if response:
                params = {
                    'url': arg_url,
                    'preview_id': arg_pid,
                    'contents': response.text,
                    'created_at': datetime.datetime.utcnow()
                }
                db.preview_contents.insert_one(params)
        else:
            sys.exit('Contents cache existed!')
        sys.exit('temphtml ended')
        
    elif sys.argv[1] == '--preview':
        mode = "preview"
        if len(sys.argv) < 3:
            sys.exit('Preview parameter is missing')
        
        arg_items = sys.argv[2].split('_&_')
        if len(arg_items) != 5:
            sys.exit('Preview parameter format is invalid')
        
        arg_pid, arg_steps, arg_args, arg_method, arg_url = arg_items
        
        results = db.preview_contents.find({"preview_id": arg_pid}).sort("_id", -1).limit(1)
        cached = list(results)
        
        response_content = cached[0]['contents'] if cached else None
        
        record = {
            'steps': json.loads(arg_steps),
            'args': json.loads(arg_args),
            'c_method': arg_method,
            'task_id': arg_pid,
            'url': arg_url,
        }
        records = [record]
        
    else:
        sys.exit('Unknown command')
    
    if len(records) == 0:
        sys.exit('No data to crawl')
    
    return mode, None, records


def main():
    """Main entry point."""
    mode, _, records = parse_arguments()
    
    for seed in records:
        print(f"\n{'='*50}")
        print(f"Processing: {seed.get('task_name', seed.get('task_id', 'Unknown'))}")
        print(f"{'='*50}")
        
        # Check for cached preview content
        response_cache = None
        if mode == "preview":
            pid = seed.get('task_id')
            cached = list(db.preview_contents.find({"preview_id": pid}).limit(1))
            if cached:
                response_cache = cached[0].get('contents')
        
        # Process the crawl task
        results = process_crawl_task(seed, response_cache)
        
        # Save results
        save_results(seed, results, mode)
        
        # Output results
        print("__&Result&__")
        print(f"Final Result: {results}")


if __name__ == "__main__":
    main()
