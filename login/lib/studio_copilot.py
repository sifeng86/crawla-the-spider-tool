import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from login.lib.llm_handler import get_gemini_response
    from login.lib.selector_memory import get_selector_memory_summary
    from login.lib.studio import get_studio_method_catalog
except ModuleNotFoundError:
    from lib.llm_handler import get_gemini_response
    from lib.selector_memory import get_selector_memory_summary
    from lib.studio import get_studio_method_catalog


LIST_HINTS = {'list', 'listing', 'items', 'rows', 'cards', 'articles', 'products', 'entries'}
LINK_HINTS = {'link', 'links', 'href', 'url', 'urls'}
HEADLINE_HINTS = {'title', 'titles', 'headline', 'headlines', 'name', 'names'}
EDITORIAL_HINTS = {'blog', 'blogs', 'article', 'articles', 'news', 'posts', 'changelog'}
CATALOG_HINTS = {'catalog', 'catalogs', 'price', 'prices', 'pricing', 'product', 'products', 'sku'}
MEMORY_ROOT_STEP_PRIORITY = {
    'py_requests': ['select_one'],
    'py_selenium': ['find_element_by_css', 'find_element_by_id', 'find_element_by_class', 'find_element_by_xpath'],
    'py_playwright': ['find_element_by_css', 'find_element_by_id', 'find_element_by_class', 'find_element_by_xpath'],
}
MEMORY_COLLECTION_STEP_PRIORITY = {
    'py_requests': ['select_all'],
    'py_selenium': ['find_elements_by_css', 'find_elements_by_id', 'find_elements_by_class', 'find_elements_by_xpath'],
    'py_playwright': ['find_elements_by_css', 'find_elements_by_id', 'find_elements_by_class', 'find_elements_by_xpath'],
}


def _clean_text(value: Any, default: str = '') -> str:
    if value is None:
        return default

    cleaned = str(value).strip()
    return cleaned or default


def _goal_tokens(goal: str) -> set[str]:
    return {token for token in re.findall(r'[a-z0-9]+', goal.lower()) if token}


def infer_page_family(target_url: str, goal: str = '') -> str:
    parsed = urlparse(target_url)
    hostname = (parsed.hostname or '').lower()
    path = (parsed.path or '').lower()
    tokens = _goal_tokens(goal)

    if 'docs' in hostname or 'docs/' in path or 'wiki' in hostname or 'manual' in hostname:
        return 'docs'
    if tokens & EDITORIAL_HINTS or any(marker in path for marker in ('blog', 'news', 'article', 'changelog')):
        return 'editorial'
    if tokens & CATALOG_HINTS or any(marker in hostname + path for marker in ('shop', 'store', 'product', 'catalog', 'pricing')):
        return 'catalog'
    return 'general'


def _build_root_selector(page_family: str) -> str:
    selectors = {
        'docs': 'main, article, .markdown-body, [role="main"]',
        'editorial': 'main, article, .post, .article-body',
        'catalog': 'main, .product-grid, .catalog, .collection',
        'general': 'main, article, .content, body',
    }
    return selectors.get(page_family, selectors['general'])


def _build_item_selector(page_family: str, wants_links: bool) -> str:
    if page_family == 'docs':
        return 'main a, article a, nav a' if wants_links else 'article, main section, li'
    if page_family == 'editorial':
        return 'article, .post, .article-card, li' if not wants_links else 'article a, .post a, h2 a'
    if page_family == 'catalog':
        return '.product, .card, article, li' if not wants_links else '.product a, .card a, article a'
    return 'article, li, .card, .item' if not wants_links else 'a, article a, .card a'


def _build_llm_goal_prompt(goal: str) -> str:
    if goal.startswith('{') and '"type"' in goal:
        return goal
    return f'Extract the following from the page and return concise structured JSON with stable keys: {goal}'


def _format_task_name(goal: str, page_family: str) -> str:
    goal_words = [word.capitalize() for word in re.findall(r'[A-Za-z0-9]+', goal)[:5]]
    if goal_words:
        return ' '.join(goal_words) + ' Flow'

    family_names = {
        'docs': 'Docs Watcher Flow',
        'editorial': 'Editorial Monitor Flow',
        'catalog': 'Catalog Extractor Flow',
        'general': 'Studio Extraction Flow',
    }
    return family_names.get(page_family, 'Studio Extraction Flow')


def _load_selector_memory_items(target_url: str, method: str, database=None) -> List[Dict[str, Any]]:
    if database is None or method == 'py_llm':
        return []

    summary = get_selector_memory_summary(target_url, method, limit=6, database=database)
    items = summary.get('items') if isinstance(summary, dict) else []
    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def _find_selector_memory_match(memory_items: List[Dict[str, Any]], preferred_steps: List[str]) -> Optional[Dict[str, str]]:
    for step_name in preferred_steps:
        for item in memory_items:
            if _clean_text(item.get('step_name')) != step_name:
                continue

            resolved_param = _clean_text(item.get('resolved_param'))
            if not resolved_param:
                continue

            return {
                'step': step_name,
                'args': resolved_param,
            }

    return None


def _selector_memory_note(memory_items: List[Dict[str, Any]]) -> str:
    if not memory_items:
        return ''

    hit_count = len(memory_items)
    label = 'selector-memory hit' if hit_count == 1 else 'selector-memory hits'
    return f' Copilot also grounded the draft with {hit_count} {label} from this domain.'


def _allowed_step_map(method: str) -> Dict[str, Dict[str, str]]:
    catalog = get_studio_method_catalog()
    return {step['step']: step for step in catalog[method]['step_cards']}


def _normalize_nodes(method: str, raw_nodes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    allowed_steps = _allowed_step_map(method)
    nodes: List[Dict[str, str]] = []
    for index, node in enumerate(raw_nodes or []):
        if not isinstance(node, dict):
            continue

        step = _clean_text(node.get('step'))
        if step not in allowed_steps:
            continue

        args = _clean_text(node.get('args'), default='-')
        if allowed_steps[step].get('param_hint', '-') != '-' and args == '-':
            continue

        step_meta = allowed_steps[step]
        nodes.append(
            {
                'id': _clean_text(node.get('id'), default=f'copilot-node-{index + 1}'),
                'title': _clean_text(node.get('title'), default=step_meta.get('label', f'Node {index + 1}')),
                'step': step,
                'args': args,
                'intent': _clean_text(node.get('intent'), default=step_meta.get('description', '')),
            }
        )

    return nodes


def _build_template_nodes(
    method: str,
    goal: str,
    page_family: str,
    selector_memory_items: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    goal_tokens = _goal_tokens(goal)
    wants_list = bool(goal_tokens & LIST_HINTS or goal_tokens & LINK_HINTS)
    wants_links = bool(goal_tokens & LINK_HINTS)
    wants_headlines = bool(goal_tokens & HEADLINE_HINTS) or page_family in {'docs', 'editorial'}
    selector_memory_items = selector_memory_items or []

    if method == 'py_llm':
        return [
            {
                'id': 'copilot-llm-prompt',
                'title': 'Extract requested data with AI',
                'step': 'llm_prompt',
                'args': _build_llm_goal_prompt(goal),
                'intent': 'Let Gemini convert the preview surface into the requested answer shape.',
            }
        ]

    locate_step = 'select_one' if method == 'py_requests' else 'find_element_by_css'
    collect_step = 'select_all' if method == 'py_requests' else 'find_elements_by_css'
    root_selector = _build_root_selector(page_family)
    item_selector = _build_item_selector(page_family, wants_links)
    root_memory_match = _find_selector_memory_match(selector_memory_items, MEMORY_ROOT_STEP_PRIORITY.get(method, []))
    collect_memory_match = _find_selector_memory_match(selector_memory_items, MEMORY_COLLECTION_STEP_PRIORITY.get(method, []))

    nodes: List[Dict[str, str]] = [
        {
            'id': 'copilot-root',
            'title': 'Reuse the last stable root selector' if root_memory_match else 'Anchor the main content surface',
            'step': root_memory_match['step'] if root_memory_match else locate_step,
            'args': root_memory_match['args'] if root_memory_match else root_selector,
            'intent': 'Start from a selector that already succeeded on this domain.' if root_memory_match else 'Give the run a stable root container before collecting items or reading text.',
        }
    ]

    if wants_list or wants_links:
        nodes.append(
            {
                'id': 'copilot-collect',
                'title': 'Reuse repeated targets from selector memory' if collect_memory_match else 'Collect repeated targets',
                'step': collect_memory_match['step'] if collect_memory_match else collect_step,
                'args': collect_memory_match['args'] if collect_memory_match else item_selector,
                'intent': 'Reuse a repeated selector that already worked on this domain.' if collect_memory_match else 'Sweep the repeated targets that likely contain the requested titles, links, or cards.',
            }
        )

    if wants_links:
        nodes.append(
            {
                'id': 'copilot-href',
                'title': 'Capture the destination link',
                'step': 'ext_str_get_href',
                'args': '-',
                'intent': 'Extract the outbound URL that matches the requested link-oriented goal.',
            }
        )
    else:
        nodes.append(
            {
                'id': 'copilot-text',
                'title': 'Read visible text',
                'step': 'ext_str_get_text',
                'args': '-',
                'intent': 'Capture the text payload requested in the goal before refining further.',
            }
        )

    if wants_headlines and not wants_links and len(nodes) < 4:
        nodes.append(
            {
                'id': 'copilot-attribute',
                'title': 'Optionally capture a stable label',
                'step': 'ext_str_get_attribute',
                'args': 'aria-label',
                'intent': 'Pull a stable attribute when the visible title may vary across cards or navigation targets.',
            }
        )

    return nodes[:4]


def _build_template_rationale(
    goal: str,
    page_family: str,
    method: str,
    selector_memory_items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    selector_memory_items = selector_memory_items or []

    if method == 'py_llm':
        return 'Copilot used a prompt-first fallback so the AI runtime can shape the answer directly from preview HTML.' + _selector_memory_note(selector_memory_items)
    if page_family == 'docs':
        return 'Copilot biased the flow toward docs-style layouts with a stable main/article root and selector-friendly repeated targets.' + _selector_memory_note(selector_memory_items)
    if page_family == 'catalog':
        return 'Copilot biased the flow toward card grids and product-like targets so list extraction can scale into detail crawls later.' + _selector_memory_note(selector_memory_items)
    if page_family == 'editorial':
        return 'Copilot biased the flow toward article blocks and headline-friendly selectors for content monitoring workflows.' + _selector_memory_note(selector_memory_items)
    return 'Copilot built a conservative selector-first flow that can be refined in the inspector before you save the task.' + _selector_memory_note(selector_memory_items)


def _build_llm_prompt(
    goal: str,
    target_url: str,
    method: str,
    current_nodes: Optional[List[Dict[str, Any]]] = None,
    selector_memory_items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    catalog = get_studio_method_catalog()[method]
    allowed_steps = [
        {
            'step': step['step'],
            'label': step['label'],
            'param_hint': step['param_hint'],
            'description': step['description'],
        }
        for step in catalog['step_cards']
    ]
    current_snapshot = [
        {
            'title': _clean_text(node.get('title')),
            'step': _clean_text(node.get('step')),
            'args': _clean_text(node.get('args')),
        }
        for node in (current_nodes or [])
        if isinstance(node, dict)
    ][:4]
    selector_memory_snapshot = [
        {
            'step_name': _clean_text(item.get('step_name')),
            'resolved_param': _clean_text(item.get('resolved_param')),
            'success_count': int(item.get('success_count', 0) or 0),
            'strategy': _clean_text(item.get('strategy'), default='memory'),
        }
        for item in (selector_memory_items or [])
        if _clean_text(item.get('step_name')) and _clean_text(item.get('resolved_param'))
    ][:5]

    return json.dumps(
        {
            'role': 'studio-flow-planner',
            'instructions': [
                'Return only valid JSON.',
                'Use 1 to 4 nodes.',
                'Choose step names only from allowed_steps.',
                'For steps that require arguments, provide a concrete argument and never use -.',
                'For steps that do not require arguments, use -.',
                'If the method is py_llm, you must use only llm_prompt.',
                'Prefer selector_memory candidates when they align with the goal and current runtime.',
            ],
            'response_schema': {
                'task_name': 'short task name',
                'rationale': 'one concise sentence',
                'nodes': [
                    {
                        'title': 'node title',
                        'step': 'allowed step name',
                        'args': 'step argument or -',
                        'intent': 'why this node exists',
                    }
                ],
            },
            'target_url': target_url,
            'method': method,
            'goal': goal,
            'current_nodes': current_snapshot,
            'selector_memory': selector_memory_snapshot,
            'allowed_steps': allowed_steps,
        },
        ensure_ascii=True,
    )


def _parse_llm_plan(result: str) -> Optional[Dict[str, Any]]:
    cleaned = _clean_text(result)
    if not cleaned or cleaned.startswith('LLM Error:'):
        return None

    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def suggest_studio_copilot_plan(
    goal: str,
    target_url: str,
    method: str,
    current_nodes: Optional[List[Dict[str, Any]]] = None,
    database=None,
) -> Dict[str, Any]:
    goal = _clean_text(goal)
    target_url = _clean_text(target_url)
    method = _clean_text(method)

    if not goal:
        raise ValueError('Copilot goal is required')
    if not target_url.startswith(('http://', 'https://')):
        raise ValueError('Target URL must start with http:// or https://')

    catalog = get_studio_method_catalog()
    if method not in catalog:
        raise ValueError('Unsupported crawl method')

    page_family = infer_page_family(target_url, goal)
    selector_memory_items = _load_selector_memory_items(target_url, method, database=database)
    task_name = _format_task_name(goal, page_family)
    nodes = _normalize_nodes(method, _build_template_nodes(method, goal, page_family, selector_memory_items=selector_memory_items))
    rationale = _build_template_rationale(goal, page_family, method, selector_memory_items=selector_memory_items)
    source = 'template'

    llm_plan = _parse_llm_plan(
        get_gemini_response(
            _build_llm_prompt(
                goal,
                target_url,
                method,
                current_nodes=current_nodes,
                selector_memory_items=selector_memory_items,
            )
        )
    )
    if llm_plan:
        llm_nodes = _normalize_nodes(method, llm_plan.get('nodes') if isinstance(llm_plan.get('nodes'), list) else [])
        if llm_nodes:
            source = 'llm'
            task_name = _clean_text(llm_plan.get('task_name'), default=task_name)
            rationale = _clean_text(
                llm_plan.get('rationale'),
                default='Gemini proposed a studio starter flow for the requested goal.',
            ) + _selector_memory_note(selector_memory_items)
            nodes = llm_nodes

    return {
        'goal': goal,
        'source': source,
        'headline': f'Copilot drafted a {page_family} flow for {catalog[method]["label"]}',
        'task_name': task_name,
        'rationale': rationale,
        'memory_hits': len(selector_memory_items),
        'nodes': nodes,
    }