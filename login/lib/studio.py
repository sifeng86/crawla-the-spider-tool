from copy import deepcopy
from os import environ as env
from typing import Any, Dict, List

try:
    from login.lib.step_helper import StepExecutor
except ModuleNotFoundError:
    from lib.step_helper import StepExecutor


STUDIO_SCHEMA_VERSION = '2026-04-30'


STEP_DETAILS: Dict[str, Dict[str, str]] = {
    'select_one': {
        'label': 'Select one',
        'group': 'Locate',
        'param_hint': 'CSS selector',
        'description': 'Target a single HTML node from the preview surface.',
    },
    'select_all': {
        'label': 'Select all',
        'group': 'Locate',
        'param_hint': 'CSS selector',
        'description': 'Collect a repeated list before iterating or extracting.',
    },
    'find_element_by_id': {
        'label': 'Find by id',
        'group': 'Locate',
        'param_hint': 'id value',
        'description': 'Anchor into stable containers when the page exposes semantic ids.',
    },
    'find_elements_by_id': {
        'label': 'Find all by id',
        'group': 'Locate',
        'param_hint': 'id value',
        'description': 'Collect multiple nodes sharing a generated identifier pattern.',
    },
    'find_element_by_class': {
        'label': 'Find by class',
        'group': 'Locate',
        'param_hint': 'class name',
        'description': 'Use compact class hooks for stable blocks and cards.',
    },
    'find_elements_by_class': {
        'label': 'Find all by class',
        'group': 'Locate',
        'param_hint': 'class name',
        'description': 'Sweep repeated card grids or article collections.',
    },
    'find_element_by_css': {
        'label': 'Find by CSS',
        'group': 'Locate',
        'param_hint': 'CSS selector',
        'description': 'Use precise selectors for browser runtimes and dynamic apps.',
    },
    'find_elements_by_css': {
        'label': 'Find all by CSS',
        'group': 'Locate',
        'param_hint': 'CSS selector',
        'description': 'Collect repeated browser nodes before drilling into details.',
    },
    'find_element_by_xpath': {
        'label': 'Find by XPath',
        'group': 'Locate',
        'param_hint': 'XPath expression',
        'description': 'Fallback for brittle layouts and deep nested nodes.',
    },
    'click': {
        'label': 'Click',
        'group': 'Action',
        'param_hint': '-',
        'description': 'Trigger navigation, expand accordions, or reveal hidden content.',
    },
    'send_keys': {
        'label': 'Send keys',
        'group': 'Action',
        'param_hint': 'text to type',
        'description': 'Fill search bars, filters, and login forms.',
    },
    'wait_for_visible': {
        'label': 'Wait for visible',
        'group': 'Stability',
        'param_hint': '-',
        'description': 'Pause the run until the browser confirms the node is visible.',
    },
    'ext_str_get_text': {
        'label': 'Get text',
        'group': 'Extract',
        'param_hint': '-',
        'description': 'Capture clean text from the current node.',
    },
    'ext_str_get_attribute': {
        'label': 'Get attribute',
        'group': 'Extract',
        'param_hint': 'attribute name',
        'description': 'Pull href, src, aria labels, or data attributes.',
    },
    'ext_str_get_href': {
        'label': 'Get href',
        'group': 'Extract',
        'param_hint': '-',
        'description': 'Extract link destinations for follow-up detail crawls.',
    },
    'llm_prompt': {
        'label': 'Prompt or JSON schema',
        'group': 'AI',
        'param_hint': 'prompt or JSON schema',
        'description': 'Ask Gemini to extract freeform answers or structured JSON.',
    },
}


def _step_requires_argument(step_name: str) -> bool:
    return STEP_DETAILS.get(step_name, {}).get('param_hint', '-') != '-'


METHOD_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    'py_requests': {
        'label': 'Requests / BS4',
        'badge': 'Fast lane',
        'summary': 'Best for static pages where speed and throughput matter more than interaction.',
        'preview_mode': 'cached_html',
        'engine_label': 'HTTP + BeautifulSoup',
        'strengths': [
            'Low latency preview caching',
            'Cheap wide crawls and sitemap sweeps',
            'Ideal fallback when browser rendering is unnecessary',
        ],
        'starter_nodes': [
            {
                'id': 'requests-root',
                'title': 'Lock onto the primary content block',
                'step': 'select_one',
                'args': 'main, article, .content',
                'intent': 'Give the flow a stable root before extracting text or links.',
            },
            {
                'id': 'requests-text',
                'title': 'Extract cleaned text',
                'step': 'ext_str_get_text',
                'args': '-',
                'intent': 'Turn the selected node into readable content or feed it into LLM extraction.',
            },
        ],
    },
    'py_selenium': {
        'label': 'Selenium',
        'badge': 'Compatibility',
        'summary': 'Use when a remote Chrome session is enough and you need broad browser automation support.',
        'preview_mode': 'live_browser',
        'engine_label': 'Remote Chrome',
        'strengths': [
            'Handles JS-heavy pages and clicks',
            'Good compatibility fallback beside Playwright',
            'Useful for legacy interaction paths already modelled in the project',
        ],
        'starter_nodes': [
            {
                'id': 'selenium-root',
                'title': 'Focus on the rendered container',
                'step': 'find_element_by_css',
                'args': 'main, [data-testid], .app-shell',
                'intent': 'Attach to the rendered app shell before reading visible text or refining the locator.',
            },
            {
                'id': 'selenium-text',
                'title': 'Read the visible text',
                'step': 'ext_str_get_text',
                'args': '-',
                'intent': 'Confirm the locator chain is valid before adding clicks or form interactions.',
            },
        ],
    },
    'py_playwright': {
        'label': 'Playwright',
        'badge': 'Flagship',
        'summary': 'Primary studio engine for rich locators, stateful flows, and future multi-step sessions.',
        'preview_mode': 'live_browser',
        'engine_label': 'Playwright context',
        'strengths': [
            'Best fit for stateful flows and pagination',
            'Richer locator model for inspector and auto-healing',
            'Fast enough to become the default studio runtime',
        ],
        'starter_nodes': [
            {
                'id': 'playwright-root',
                'title': 'Focus on the primary browser target',
                'step': 'find_element_by_css',
                'args': 'main, article, [data-testid*=item]',
                'intent': 'Attach to a single rendered node before extracting text or branching into stateful flow work.',
            },
            {
                'id': 'playwright-detail',
                'title': 'Capture the visible headline',
                'step': 'ext_str_get_text',
                'args': '-',
                'intent': 'Verify the locator chain before adding stateful navigation primitives.',
            },
        ],
    },
    'py_llm': {
        'label': 'LLM Extraction',
        'badge': 'AI parser',
        'summary': 'Use prompt-driven extraction when the page is noisy, semi-structured, or changes frequently.',
        'preview_mode': 'cached_html',
        'engine_label': 'Gemini planner/extractor',
        'strengths': [
            'Direct prompt-to-answer workflows',
            'JSON schema extraction for structured output',
            'Best partner for self-healing and copilot suggestions',
        ],
        'starter_nodes': [
            {
                'id': 'llm-schema',
                'title': 'Define the output contract',
                'step': 'llm_prompt',
                'args': '{"type":"object","properties":{"title":{"type":"string"}}}',
                'intent': 'Start from the shape of the data, then let Gemini normalize the page into that schema.',
            },
        ],
    },
}


RUN_EVENT_SCHEMA: List[Dict[str, str]] = [
    {'type': 'workspace.ready', 'label': 'Workspace ready', 'level': 'info'},
    {'type': 'preview.cache_requested', 'label': 'Preview cache requested', 'level': 'info'},
    {'type': 'preview.cached', 'label': 'Preview cached', 'level': 'success'},
    {'type': 'flow.node_started', 'label': 'Flow node started', 'level': 'info'},
    {'type': 'flow.node_healed', 'label': 'Flow node healed', 'level': 'warning'},
    {'type': 'flow.node_failed', 'label': 'Flow node failed', 'level': 'danger'},
    {'type': 'run.completed', 'label': 'Run completed', 'level': 'success'},
]


def _env_flag(name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def is_studio_enabled() -> bool:
    return _env_flag('CRAWLA_STUDIO_ENABLED', default=True)


def get_studio_feature_flags() -> Dict[str, bool]:
    return {
        'workspace_shell': True,
        'visual_inspector': _env_flag('CRAWLA_STUDIO_INSPECTOR_ENABLED', default=True),
        'ai_copilot': _env_flag('CRAWLA_STUDIO_COPILOT_ENABLED', default=True),
        'run_debugger': _env_flag('CRAWLA_STUDIO_DEBUGGER_ENABLED', default=False),
    }


def _method_runtime(method: str) -> str:
    runtime_map = {
        'py_requests': 'soup',
        'py_selenium': 'selenium',
        'py_playwright': 'playwright',
    }
    return runtime_map.get(method, '')


def _build_step_cards(method: str) -> List[Dict[str, str]]:
    if method == 'py_llm':
                llm_step = deepcopy(STEP_DETAILS['llm_prompt'])
                llm_step['step'] = 'llm_prompt'
                return [llm_step]

    runtime = _method_runtime(method)
    steps = []
    for step_name in StepExecutor.get_available_steps(runtime):
        if step_name in STEP_DETAILS:
            details = deepcopy(STEP_DETAILS[step_name])
            details['step'] = step_name
            steps.append(details)

    unique_steps = {step['step']: step for step in steps}
    return list(unique_steps.values())


def get_studio_method_catalog() -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {}
    for method, method_def in METHOD_DEFINITIONS.items():
        entry = deepcopy(method_def)
        entry['step_cards'] = _build_step_cards(method)
        catalog[method] = entry
    return catalog


def _clean_text(value: Any, default: str = '') -> str:
    if value is None:
        return default

    cleaned = str(value).strip()
    return cleaned or default


def _normalize_studio_node(node: Dict[str, Any], index: int, allowed_steps: set[str]) -> Dict[str, str]:
    if not isinstance(node, dict):
        raise ValueError(f'Flow node {index + 1} must be an object')

    step = _clean_text(node.get('step'))
    if step not in allowed_steps:
        raise ValueError(f'Flow node {index + 1} uses an unsupported step for the selected method')

    step_defaults = STEP_DETAILS.get(step, {})
    args = _clean_text(node.get('args'), default='-')
    if _step_requires_argument(step) and args == '-':
        raise ValueError(f'Flow node {index + 1} requires an argument for {step}')

    return {
        'id': _clean_text(node.get('id'), default=f'node-{index + 1}'),
        'title': _clean_text(node.get('title'), default=step_defaults.get('label', f'Node {index + 1}')),
        'step': step,
        'args': args,
        'intent': _clean_text(node.get('intent'), default=step_defaults.get('description', '')),
    }


def validate_studio_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('Missing studio payload')

    workspace = payload.get('workspace') if isinstance(payload.get('workspace'), dict) else {}
    catalog = get_studio_method_catalog()

    task_name = _clean_text(payload.get('task_name') or workspace.get('title'), default='Untitled Studio Flow')
    target_url = _clean_text(payload.get('url') or workspace.get('target_url'))
    if not target_url.startswith(('http://', 'https://')):
        raise ValueError('Target URL must start with http:// or https://')

    notification_email = _clean_text(payload.get('noti_email') or workspace.get('notification_email'))
    if '@' not in notification_email:
        raise ValueError('Notification email is required')

    crawl_method = _clean_text(payload.get('c_method') or payload.get('selected_method'))
    if crawl_method not in catalog:
        raise ValueError('Unsupported crawl method')

    raw_nodes = payload.get('nodes')
    if raw_nodes is None:
        flow = payload.get('flow') if isinstance(payload.get('flow'), dict) else {}
        raw_nodes = flow.get('nodes')

    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError('At least one flow node is required')

    allowed_steps = {card['step'] for card in catalog[crawl_method]['step_cards']}
    normalized_nodes = [
        _normalize_studio_node(node, index, allowed_steps)
        for index, node in enumerate(raw_nodes)
    ]

    return {
        'draft_id': _clean_text(payload.get('draft_id') or payload.get('preview_id')),
        'task_name': task_name,
        'url': target_url,
        'noti_email': notification_email,
        'c_method': crawl_method,
        'nodes': normalized_nodes,
        'steps': [node['step'] for node in normalized_nodes],
        'args': [node['args'] for node in normalized_nodes],
    }


def build_studio_state(userinfo: Dict[str, Any], studio_token: str) -> Dict[str, Any]:
    catalog = get_studio_method_catalog()
    selected_method = 'py_playwright'
    starter_nodes = deepcopy(catalog[selected_method]['starter_nodes'])
    feature_flags = get_studio_feature_flags()

    feature_panels = [
        {
            'key': 'workspace_shell',
            'label': 'Studio shell',
            'status': 'ready',
            'description': 'Route, workspace layout, draft schema, and method catalog are live.',
        },
        {
            'key': 'visual_inspector',
            'label': 'Visual inspector',
            'status': 'next' if not feature_flags['visual_inspector'] else 'ready',
            'description': 'Element picking and selector generation will attach to preview mode in the next slice.',
        },
        {
            'key': 'ai_copilot',
            'label': 'AI copilot',
            'status': 'next' if not feature_flags['ai_copilot'] else 'ready',
            'description': 'Prompt-to-flow planning will build on the same draft schema rendered in this workspace.',
        },
        {
            'key': 'run_debugger',
            'label': 'Run debugger',
            'status': 'next' if not feature_flags['run_debugger'] else 'ready',
            'description': 'Timeline, healing traces, and node screenshots will bind to the run event ledger.',
        },
    ]

    return {
        'schema_version': STUDIO_SCHEMA_VERSION,
        'draft_id': studio_token,
        'selected_method': selected_method,
        'workspace': {
            'title': 'Untitled Studio Flow',
            'subtitle': 'Start from a target URL, then layer selectors, actions, and AI planning on top.',
            'operator': userinfo.get('name', 'Unknown operator'),
            'notification_email': userinfo.get('email', ''),
            'target_url': '',
            'mode': 'draft',
            'stability_goal': 'High first-run success rate',
        },
        'preview': {
            'preview_id': studio_token,
            'status': 'idle',
            'headline': 'Preview stage is waiting for a target URL',
            'detail': 'This panel will host cached HTML for Requests/LLM and live browser mirrors for Selenium/Playwright.',
            'last_result': '',
            'preview_mode': catalog[selected_method]['preview_mode'],
        },
        'inspector': {
            'status': 'idle',
            'source_mode': 'on_demand',
            'source_note': 'Load an inspector snapshot to pick elements and apply selectors to the active flow node.',
            'selected_node_index': 0,
            'selection': None,
        },
        'healing': {
            'memory_status': 'idle',
            'memory_note': 'Run previews or successful crawls to build selector memory for this domain.',
            'memory_items': [],
        },
        'copilot': {
            'status': 'idle',
            'goal': '',
            'source': 'template',
            'note': 'Describe the data you want and Copilot will draft a flow for the currently selected runtime.',
            'suggestion': None,
        },
        'flow': {
            'shape': 'linear-blueprint',
            'nodes': starter_nodes,
        },
        'run': {
            'status': 'draft',
            'event_schema': deepcopy(RUN_EVENT_SCHEMA),
            'events': [
                {
                    'type': 'workspace.ready',
                    'title': 'Studio workspace primed',
                    'detail': 'Draft schema, method matrix, and event ledger are attached to this session.',
                    'level': 'info',
                },
                {
                    'type': 'preview.cache_requested',
                    'title': 'Preview wiring is ready',
                    'detail': 'The workspace is pointing at the existing preview pipeline and can evolve without replacing /contents.',
                    'level': 'info',
                },
            ],
        },
        'templates': [
            {
                'title': 'Docs index watcher',
                'description': 'Track article titles, last-updated markers, and outbound doc links.',
            },
            {
                'title': 'Catalog card extractor',
                'description': 'Model list pages first, then branch into detail pages once stateful flow lands.',
            },
            {
                'title': 'Schema-driven summarizer',
                'description': 'Combine cached HTML preview with LLM extraction for fast structured output.',
            },
        ],
        'feature_flags': feature_flags,
        'feature_panels': feature_panels,
    }