"""
Crawla - Main crawler script.
Supports multiple crawling methods: requests, Selenium, Playwright, and LLM.
"""
import requests
import json
import sys
import datetime
import importlib.util
from typing import List, Dict, Any, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

from login.lib.step_helper import StepExecutor
from login.lib.mongo import mongoHelper
from login.lib.stealth import StealthConfig
from login.lib.rate_limiter import rate_limiter
from login.lib.selector_memory import (
    derive_selector_fallback_candidates,
    get_selector_memory_candidates,
    normalize_selector_value,
    record_selector_success,
)


# Connection to mongodb
db = mongoHelper.mongo_conn()

PREVIEW_CACHE_METHODS = {'py_requests', 'py_llm'}
LIVE_BROWSER_METHODS = {'py_selenium', 'py_playwright'}
MAX_SELF_HEAL_HTML_CHARS = 5000


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def build_preview_cache_query(preview_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    query: Dict[str, Any] = {'preview_id': preview_id}
    if user_id:
        query['user_id'] = user_id
    return query


def parse_preview_payload(raw_payload: str) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None


def normalize_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_preview_source(url: str, method: str) -> Optional[str]:
    if method == 'py_llm':
        response = get_page_requests(url)
        if response and response.text:
            return response.text

        return get_page_playwright(url)

    response = get_page_requests(url)
    if not response:
        return None

    return response.text


def get_inspector_source(url: str, method: str) -> Optional[str]:
    if method == 'py_selenium':
        page_source, driver = get_page_selenium(url)
        if not driver:
            return None

        try:
            return page_source
        finally:
            driver.quit()

    if method == 'py_playwright':
        return get_page_playwright(url)

    return get_preview_source(url, method)


def should_use_preview_cache(method: str) -> bool:
    return method in PREVIEW_CACHE_METHODS


def cache_preview_content(preview_id: str, url: str, method: str = 'py_requests', user_id: Optional[str] = None) -> bool:
    page_content = get_preview_source(url, method)
    if not page_content:
        return False

    params = {
        'url': url,
        'preview_id': preview_id,
        'method': method,
        'contents': page_content,
        'created_at': utc_now()
    }
    if user_id:
        params['user_id'] = user_id
    db.preview_contents.update_one(
        build_preview_cache_query(preview_id, user_id),
        {'$set': params},
        upsert=True,
    )
    return True


def load_preview_content(preview_id: str, method: str, user_id: Optional[str] = None) -> Optional[str]:
    if not should_use_preview_cache(method):
        return None

    cached = list(db.preview_contents.find(build_preview_cache_query(preview_id, user_id)).limit(1))
    if not cached:
        return None

    return cached[0].get('contents')


def format_preview_results(results: List[Any]) -> str:
    try:
        return json.dumps(results, ensure_ascii=False)
    except TypeError:
        return str(results)


def build_scheduled_task_query(extra_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    query: Dict[str, Any] = {'schedule_enabled': {'$ne': False}}
    if extra_filters:
        query.update(extra_filters)
    return query


def supports_brotli() -> bool:
    return importlib.util.find_spec('brotli') is not None or importlib.util.find_spec('brotlicffi') is not None


def get_requests_accept_encoding() -> str:
    encodings = ['gzip', 'deflate']
    if supports_brotli():
        encodings.append('br')
    return ', '.join(encodings)


def normalize_step_name(step_name: str) -> str:
    return StepExecutor.LEGACY_STEP_ALIASES.get(step_name, step_name)


def is_self_healable_step(step_name: str) -> bool:
    normalized_name = normalize_step_name(step_name)
    return normalized_name in {'select_one', 'select_all'} or normalized_name.startswith('find_element_by') or normalized_name.startswith('find_elements_by')


def truncate_html_snippet(html: Optional[str]) -> str:
    return (html or '')[:MAX_SELF_HEAL_HTML_CHARS]


def iter_context_candidates(*candidates: Any):
    for candidate in candidates:
        if candidate is None:
            continue

        if isinstance(candidate, list):
            for item in candidate[:3]:
                if item is not None:
                    yield item
            continue

        yield candidate


def build_soup_html_snippet(current: Any) -> str:
    return truncate_html_snippet(str(current))


def build_selenium_html_snippet(current: Any, driver: webdriver.Remote) -> str:
    for candidate in iter_context_candidates(current, driver):
        get_attribute = getattr(candidate, 'get_attribute', None)
        if callable(get_attribute):
            try:
                html = get_attribute('outerHTML') or get_attribute('innerHTML')
                if html:
                    return truncate_html_snippet(html)
            except Exception:
                pass

        page_source = getattr(candidate, 'page_source', None)
        if isinstance(page_source, str) and page_source:
            return truncate_html_snippet(page_source)

    return ''


def build_playwright_html_snippet(current: Any, page: Any) -> str:
    for candidate in iter_context_candidates(current, page):
        content = getattr(candidate, 'content', None)
        if callable(content):
            try:
                html = content()
                if isinstance(html, str) and html:
                    return truncate_html_snippet(html)
            except Exception:
                pass

        evaluate = getattr(candidate, 'evaluate', None)
        if callable(evaluate):
            try:
                html = evaluate('node => node.outerHTML')
                if isinstance(html, str) and html:
                    return truncate_html_snippet(html)
            except Exception:
                pass

    return ''


def basic_result_needs_healing(result: Any) -> bool:
    return result is None or (isinstance(result, list) and len(result) == 0)


def playwright_result_needs_healing(result: Any) -> bool:
    if basic_result_needs_healing(result):
        return True

    count = getattr(result, 'count', None)
    if callable(count):
        try:
            return count() == 0
        except Exception:
            return False

    return False


def append_healing_event(
    healing_context: Optional[Dict[str, Any]],
    strategy: str,
    step_name: str,
    source_param: str,
    resolved_param: str,
):
    if healing_context is None:
        return

    healing_context.setdefault('events', []).append(
        {
            'strategy': strategy,
            'step_name': step_name,
            'source_param': source_param,
            'resolved_param': resolved_param,
        }
    )


def remember_selector_success(
    step_name: str,
    source_param: str,
    resolved_param: str,
    strategy: str,
    healing_context: Optional[Dict[str, Any]] = None,
):
    if healing_context is None:
        return

    record_selector_success(
        healing_context.get('url', ''),
        healing_context.get('method', ''),
        step_name,
        source_param,
        resolved_param,
        strategy=strategy,
        database=healing_context.get('database', db),
    )
    if strategy != 'original':
        append_healing_event(healing_context, strategy, step_name, source_param, resolved_param)


def try_selector_candidate(
    current: Any,
    step_name: str,
    source_param: str,
    candidate_param: str,
    strategy: str,
    execute_step: Callable[[Any, str, str], Any],
    result_needs_healing: Callable[[Any], bool],
    failure_label: str,
    healing_context: Optional[Dict[str, Any]] = None,
) -> Any:
    try:
        candidate_result = execute_step(current, step_name, candidate_param)
    except Exception as candidate_error:
        print(f"{failure_label} {strategy} candidate '{candidate_param}' failed: {candidate_error}")
        return None

    if result_needs_healing(candidate_result):
        print(f"{failure_label} {strategy} candidate '{candidate_param}' still yielded empty.")
        return None

    print(f"{failure_label} recovered via {strategy}: {candidate_param}")
    remember_selector_success(step_name, source_param, candidate_param, strategy, healing_context)
    return candidate_result


def attempt_llm_self_healing(
    current: Any,
    step_name: str,
    param: str,
    execute_step: Callable[[Any, str, str], Any],
    result_needs_healing: Callable[[Any], bool],
    get_html_snippet: Callable[[Any], str],
    failure_message: str,
    failure_label: str,
    healing_context: Optional[Dict[str, Any]] = None,
) -> Any:
    print(f"{failure_message} Attempting LLM Self-Healing...")

    try:
        from login.lib.llm_handler import get_gemini_self_healing

        healed_param = get_gemini_self_healing(step_name, param, get_html_snippet(current))
        if healed_param and healed_param != param:
            print(f"Healed parameter: {healed_param}")
            return try_selector_candidate(
                current,
                step_name,
                param,
                healed_param,
                'llm',
                execute_step,
                result_needs_healing,
                failure_label,
                healing_context,
            )
    except Exception as healing_error:
        print(f"Self-healing failed: {healing_error}")

    return None


def execute_step_with_self_healing(
    current: Any,
    step_name: str,
    param: str,
    execute_step: Callable[[Any, str, str], Any],
    get_html_snippet: Callable[[Any], str],
    result_needs_healing: Callable[[Any], bool],
    failure_label: str,
    healing_context: Optional[Dict[str, Any]] = None,
) -> Any:
    normalized_source_param = normalize_selector_value(param)

    try:
        result = execute_step(current, step_name, param)
    except Exception as original_error:
        healing_message = f"{failure_label} '{step_name}' with '{param}' failed: {original_error}."
        healed_result = None
        attempted_params = {normalized_source_param}

        for strategy, candidates in (
            (
                'memory',
                get_selector_memory_candidates(
                    healing_context.get('url', '') if healing_context else '',
                    healing_context.get('method', '') if healing_context else '',
                    step_name,
                    param,
                    database=healing_context.get('database', db) if healing_context else db,
                ),
            ),
            ('heuristic', derive_selector_fallback_candidates(step_name, param)),
        ):
            for candidate in candidates:
                normalized_candidate = normalize_selector_value(candidate)
                if not normalized_candidate or normalized_candidate in attempted_params:
                    continue
                attempted_params.add(normalized_candidate)
                healed_result = try_selector_candidate(
                    current,
                    step_name,
                    param,
                    candidate,
                    strategy,
                    execute_step,
                    result_needs_healing,
                    failure_label,
                    healing_context,
                )
                if healed_result is not None:
                    return healed_result

        healed_result = attempt_llm_self_healing(
            current,
            step_name,
            param,
            execute_step,
            result_needs_healing,
            get_html_snippet,
            healing_message,
            failure_label,
            healing_context,
        )
        if healed_result is not None:
            return healed_result
        raise

    if result_needs_healing(result):
        attempted_params = {normalized_source_param}
        for strategy, candidates in (
            (
                'memory',
                get_selector_memory_candidates(
                    healing_context.get('url', '') if healing_context else '',
                    healing_context.get('method', '') if healing_context else '',
                    step_name,
                    param,
                    database=healing_context.get('database', db) if healing_context else db,
                ),
            ),
            ('heuristic', derive_selector_fallback_candidates(step_name, param)),
        ):
            for candidate in candidates:
                normalized_candidate = normalize_selector_value(candidate)
                if not normalized_candidate or normalized_candidate in attempted_params:
                    continue
                attempted_params.add(normalized_candidate)
                healed_result = try_selector_candidate(
                    current,
                    step_name,
                    param,
                    candidate,
                    strategy,
                    execute_step,
                    result_needs_healing,
                    failure_label,
                    healing_context,
                )
                if healed_result is not None:
                    return healed_result

        healed_result = attempt_llm_self_healing(
            current,
            step_name,
            param,
            execute_step,
            result_needs_healing,
            get_html_snippet,
            f"{failure_label} '{step_name}' with '{param}' yielded empty.",
            failure_label,
            healing_context,
        )
        if healed_result is not None:
            return healed_result

        return result

    remember_selector_success(step_name, param, param, 'original', healing_context)

    return result


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
        "Accept-Encoding": get_requests_accept_encoding(),
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


def execute_soup_steps(
    soup: BeautifulSoup,
    steps: List[Tuple[str, str]],
    healing_context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
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
                if is_self_healable_step(step_name):
                    new_temp = execute_step_with_self_healing(
                        temp,
                        step_name,
                        param,
                        StepExecutor.execute_soup,
                        build_soup_html_snippet,
                        basic_result_needs_healing,
                        'Step',
                        healing_context,
                    )
                else:
                    new_temp = StepExecutor.execute_soup(temp, step_name, param)
                
                temp = new_temp
                
        except Exception as e:
            print(f"Step failed: {step_name} - {e}")
    
    return results


def execute_selenium_steps(
    driver: webdriver.Remote,
    steps: List[Tuple[str, str]],
    healing_context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
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
                if is_self_healable_step(step_name):
                    result = execute_step_with_self_healing(
                        current,
                        step_name,
                        param,
                        StepExecutor.execute_selenium,
                        lambda context: build_selenium_html_snippet(context, driver),
                        basic_result_needs_healing,
                        'Selenium step',
                        healing_context,
                    )
                else:
                    result = StepExecutor.execute_selenium(current, step_name, param)
                if result is not None:
                    current = result
                    
        except Exception as e:
            print(f"Selenium step failed: {step_name} - {e}")
    
    return results


def execute_playwright_steps(
    page,
    steps: List[Tuple[str, str]],
    healing_context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
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
                if is_self_healable_step(step_name):
                    result = execute_step_with_self_healing(
                        current,
                        step_name,
                        param,
                        StepExecutor.execute_playwright,
                        lambda context: build_playwright_html_snippet(context, page),
                        playwright_result_needs_healing,
                        'Playwright step',
                        healing_context,
                    )
                else:
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
    healing_context = {
        'url': url,
        'method': method,
        'database': db,
        'events': [],
    }
    
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
        
        results = execute_soup_steps(soup, steps, healing_context)
        
    elif method == "py_selenium":
        page_source, driver = get_page_selenium(url)
        if driver:
            try:
                results = execute_selenium_steps(driver, steps, healing_context)
                driver.save_screenshot("screenshot.png")
            finally:
                driver.quit()

    elif method == "py_playwright":
        from login.lib.playwright_helper import PlaywrightHelper

        with PlaywrightHelper(use_stealth=True) as pw:
            pw.goto(url)
            page = pw.get_page()
            results = execute_playwright_steps(page, steps, healing_context)
                
    elif method == "py_llm":
        # LLM method - fetch page and pass to LLM
        page_content = response_cache or get_page_playwright(url)
        if page_content:
            prompt = ""
            if seed.get('args') and len(seed.get('args')) > 0:
                prompt = seed.get('args')[0]
                
            from login.lib.llm_handler import get_gemini_smart_extraction, get_gemini_response
            
            if prompt.strip().startswith('{') and '"type"' in prompt:
                # It's likely a JSON schema
                print(f"Using Smart Data Extraction with schema...")
                res = get_gemini_smart_extraction(prompt, page_content)
            else:
                print(f"Using Standard LLM extraction...")
                res = get_gemini_response(prompt, page_content)
                
            results.append(res)

    if healing_context['events']:
        seed['_healing_events'] = healing_context['events']
    
    return results


def save_results_batch(items_list: List[Dict], mode: str = "normal"):
    """
    Batch insert crawl results to database.
    """
    if mode != "normal" or not items_list:
        return
    
    db.contents.insert_many(items_list)

def prepare_result_item(seed: Dict[str, Any], results: List[Any], mode: str = "normal") -> Optional[Dict]:
    """
    Prepare result item for insertion.
    """
    if mode != "normal":
        return None
        
    items = {
        'contents': results,
        'task_id': seed.get('task_id'),
        'task_name': seed.get('task_name'),
        'noti_email': seed.get('noti_email'),
        'created_at': utc_now(),
        'created_date': str(utc_now().date()),
    }
    
    user_id = seed.get('user_id')
    if user_id and user_id == 'auth0|60f28997680b890068f4bea7':
        items['demo'] = utc_now()
        
    return items


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
        results = db.urls.find(build_scheduled_task_query())
        records = list(results)
        
    elif sys.argv[1] == '--py_requests':
        results = db.urls.find(build_scheduled_task_query({"c_method": "py_requests"}))
        records = list(results)
        
    elif sys.argv[1] == '--py_selenium':
        results = db.urls.find(build_scheduled_task_query({"c_method": "py_selenium"}))
        records = list(results)
        
    elif sys.argv[1] == '--py_playwright':
        results = db.urls.find(build_scheduled_task_query({"c_method": "py_playwright"}))
        records = list(results)
        
    elif sys.argv[1] == '--py_llm':
        results = db.urls.find(build_scheduled_task_query({"c_method": "py_llm"}))
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
        payload = parse_preview_payload(sys.argv[2])
        if payload:
            arg_pid = normalize_optional_text(payload.get('preview_id')) or ''
            arg_url = normalize_optional_text(payload.get('url')) or ''
            arg_method = normalize_optional_text(payload.get('c_method')) or 'py_requests'
            arg_user_id = normalize_optional_text(payload.get('user_id'))
            if not arg_pid or not arg_url:
                sys.exit('Preview parameter format is invalid')
        else:
            arg_items = sys.argv[2].split('_&_', 2)
            if len(arg_items) < 2:
                sys.exit('Preview parameter format is invalid')

            arg_pid, arg_url = arg_items[0], arg_items[1]
            arg_method = arg_items[2] if len(arg_items) == 3 else 'py_requests'
            arg_user_id = None

        if not cache_preview_content(arg_pid, arg_url, arg_method, user_id=arg_user_id):
            sys.exit('Failed to cache preview content')

        sys.exit(0)

    elif sys.argv[1] == '--snapshothtml':
        if len(sys.argv) < 3:
            sys.exit('Snapshot parameter is missing')
        payload = parse_preview_payload(sys.argv[2])
        if not payload:
            sys.exit('Snapshot parameter format is invalid')

        arg_url = normalize_optional_text(payload.get('url')) or ''
        arg_method = normalize_optional_text(payload.get('c_method')) or 'py_requests'
        if not arg_url:
            sys.exit('Snapshot parameter format is invalid')

        snapshot_html = get_inspector_source(arg_url, arg_method)
        if not snapshot_html:
            sys.exit('Failed to build inspector snapshot')

        sys.stdout.write(snapshot_html)
        sys.exit(0)
        
    elif sys.argv[1] == '--preview':
        mode = "preview"
        if len(sys.argv) < 3:
            sys.exit('Preview parameter is missing')
        payload = parse_preview_payload(sys.argv[2])
        if payload:
            arg_pid = normalize_optional_text(payload.get('preview_id')) or ''
            arg_method = normalize_optional_text(payload.get('c_method')) or ''
            arg_url = normalize_optional_text(payload.get('url')) or ''
            arg_steps = payload.get('steps')
            arg_args = payload.get('args')
            arg_user_id = normalize_optional_text(payload.get('user_id'))
            if not arg_pid or not arg_method or not arg_url or not isinstance(arg_steps, list) or not isinstance(arg_args, list):
                sys.exit('Preview parameter format is invalid')
        else:
            arg_items = sys.argv[2].split('_&_', 4)
            if len(arg_items) != 5:
                sys.exit('Preview parameter format is invalid')

            arg_pid, arg_steps_raw, arg_args_raw, arg_method, arg_url = arg_items
            arg_steps = json.loads(arg_steps_raw)
            arg_args = json.loads(arg_args_raw)
            arg_user_id = None

        record = {
            'steps': arg_steps,
            'args': arg_args,
            'c_method': arg_method,
            'task_id': arg_pid,
            'url': arg_url,
            'user_id': arg_user_id,
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
    
    items_to_insert = []
    
    def worker(seed):
        print(f"\n{'='*50}")
        print(f"Processing: {seed.get('task_name', seed.get('task_id', 'Unknown'))}")
        print(f"{'='*50}")
        
        response_cache = None
        if mode == "preview":
            pid = seed.get('task_id')
            response_cache = load_preview_content(pid, seed.get('c_method', 'py_requests'), seed.get('user_id'))
                
        results = process_crawl_task(seed, response_cache)
        print("__&Result&__")
        preview_output = format_preview_results(results) if mode == "preview" else results
        print(f"Final Result: {preview_output}")
        
        return seed, results

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_seed = {executor.submit(worker, seed): seed for seed in records}
        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            try:
                processed_seed, results = future.result()
                item = prepare_result_item(processed_seed, results, mode)
                if item:
                    items_to_insert.append(item)
            except Exception as exc:
                print(f"Task {seed.get('task_id')} generated an exception: {exc}")

    if items_to_insert:
        save_results_batch(items_to_insert, mode)


if __name__ == "__main__":
    main()
