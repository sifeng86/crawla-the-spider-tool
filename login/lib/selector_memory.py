import datetime
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:
    from login.lib.mongo import mongoHelper
except ModuleNotFoundError:
    from lib.mongo import mongoHelper


NTH_PATTERN = re.compile(r':nth-(?:child|of-type)\(\d+\)')
ID_LITERAL_PATTERN = re.compile(r'#([A-Za-z][\w:-]*)')
XPATH_ID_PATTERN = re.compile(r'@id="([^"]+)"')
XPATH_CLASS_PATTERN = re.compile(r'@class="([^"]+)"')


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def normalize_selector_domain(url: str) -> str:
    hostname = urlparse(url or '').hostname or ''
    return hostname.lower()


def normalize_selector_value(value: Any) -> str:
    return str(value or '').strip()


def get_selector_memory_collection(database=None):
    if database is not None:
        return database.selector_memory
    return mongoHelper.mongo_conn().selector_memory


def _unique_ordered(values: Iterable[str]) -> List[str]:
    unique_values: List[str] = []
    for value in values:
        normalized = normalize_selector_value(value)
        if normalized and normalized not in unique_values:
            unique_values.append(normalized)
    return unique_values


def _derive_css_fallbacks(param: str) -> List[str]:
    candidates: List[str] = []
    normalized = normalize_selector_value(param)
    if not normalized:
        return candidates

    collapsed = NTH_PATTERN.sub('', normalized).strip()
    if collapsed and collapsed != normalized:
        candidates.append(collapsed)

    segments = [segment.strip() for segment in collapsed.split('>') if segment.strip()]
    if len(segments) > 1:
        candidates.append(segments[-1])
        if len(segments) > 2:
            candidates.append(' > '.join(segments[-2:]))

    if ' ' in collapsed:
        tokens = [token.strip() for token in collapsed.split(' ') if token.strip()]
        if tokens:
            candidates.append(tokens[-1])

    id_match = ID_LITERAL_PATTERN.search(collapsed)
    if id_match:
        identifier = id_match.group(1)
        candidates.append('#' + identifier)

    class_candidates = [piece for piece in collapsed.split('.') if piece]
    if len(class_candidates) > 1:
        candidates.append('.' + class_candidates[-1].split(':')[0])

    return _unique_ordered(candidates)


def _derive_id_fallbacks(param: str) -> List[str]:
    normalized = normalize_selector_value(param)
    if normalized.startswith('#'):
        return [normalized[1:]]
    return []


def _derive_class_fallbacks(param: str) -> List[str]:
    normalized = normalize_selector_value(param)
    if normalized.startswith('.'):
        normalized = normalized[1:]
    tokens = [token for token in re.split(r'[\s.]+', normalized) if token]
    if not tokens:
        return []
    return _unique_ordered([tokens[0], tokens[-1]])


def _derive_xpath_fallbacks(param: str) -> List[str]:
    normalized = normalize_selector_value(param)
    candidates: List[str] = []

    id_match = XPATH_ID_PATTERN.search(normalized)
    if id_match:
        identifier = id_match.group(1)
        candidates.append(f'//*[contains(@id, "{identifier}")]')

    class_match = XPATH_CLASS_PATTERN.search(normalized)
    if class_match:
        class_tokens = [token for token in class_match.group(1).split() if token]
        if class_tokens:
            candidates.append(f'//*[contains(@class, "{class_tokens[0]}")]')

    collapsed = normalized.replace('/html/body/', '//')
    if collapsed != normalized:
        candidates.append(collapsed)

    return _unique_ordered(candidates)


def derive_selector_fallback_candidates(step_name: str, param: str) -> List[str]:
    normalized = normalize_selector_value(param)
    if not normalized or normalized == '-':
        return []

    if step_name in {'select_one', 'select_all', 'find_element_by_css', 'find_elements_by_css'}:
        return _derive_css_fallbacks(normalized)
    if step_name in {'find_element_by_id', 'find_elements_by_id'}:
        return _derive_id_fallbacks(normalized)
    if step_name in {'find_element_by_class', 'find_elements_by_class'}:
        return _derive_class_fallbacks(normalized)
    if step_name in {'find_element_by_xpath', 'find_elements_by_xpath'}:
        return _derive_xpath_fallbacks(normalized)

    return []


def record_selector_success(
    url: str,
    method: str,
    step_name: str,
    source_param: str,
    resolved_param: str,
    strategy: str = 'original',
    database=None,
):
    domain = normalize_selector_domain(url)
    source_value = normalize_selector_value(source_param)
    resolved_value = normalize_selector_value(resolved_param)

    if not domain or not method or not step_name or not source_value or not resolved_value:
        return

    collection = get_selector_memory_collection(database)
    now = utc_now()
    collection.update_one(
        {
            'domain': domain,
            'method': method,
            'step_name': step_name,
            'source_param': source_value,
            'resolved_param': resolved_value,
        },
        {
            '$set': {
                'strategy': strategy,
                'last_seen_at': now,
            },
            '$setOnInsert': {
                'created_at': now,
            },
            '$inc': {
                'success_count': 1,
            },
        },
        upsert=True,
    )


def _fetch_selector_documents(query: Dict[str, Any], limit: int, database=None) -> List[Dict[str, Any]]:
    collection = get_selector_memory_collection(database)
    cursor = collection.find(query).sort([('success_count', -1), ('last_seen_at', -1)]).limit(limit)
    return list(cursor)


def get_selector_memory_candidates(
    url: str,
    method: str,
    step_name: str,
    source_param: str,
    limit: int = 5,
    database=None,
) -> List[str]:
    domain = normalize_selector_domain(url)
    source_value = normalize_selector_value(source_param)
    if not domain or not method or not step_name or not source_value:
        return []

    exact_matches = _fetch_selector_documents(
        {
            'domain': domain,
            'method': method,
            'step_name': step_name,
            'source_param': source_value,
        },
        limit,
        database=database,
    )
    general_matches = _fetch_selector_documents(
        {
            'domain': domain,
            'method': method,
            'step_name': step_name,
        },
        limit,
        database=database,
    )

    ordered_candidates = []
    for document in exact_matches + general_matches:
        candidate = normalize_selector_value(document.get('resolved_param'))
        if candidate and candidate != source_value:
            ordered_candidates.append(candidate)

    return _unique_ordered(ordered_candidates)[:limit]


def get_selector_memory_summary(url: str, method: str, limit: int = 8, database=None) -> Dict[str, Any]:
    domain = normalize_selector_domain(url)
    if not domain or not method:
        return {
            'domain': domain,
            'items': [],
        }

    rows = _fetch_selector_documents(
        {
            'domain': domain,
            'method': method,
        },
        limit,
        database=database,
    )

    items = []
    for row in rows:
        last_seen_at = row.get('last_seen_at')
        items.append(
            {
                'step_name': row.get('step_name', ''),
                'source_param': row.get('source_param', ''),
                'resolved_param': row.get('resolved_param', ''),
                'strategy': row.get('strategy', 'original'),
                'success_count': int(row.get('success_count', 0) or 0),
                'last_seen_at': last_seen_at.isoformat() if hasattr(last_seen_at, 'isoformat') else str(last_seen_at or ''),
            }
        )

    return {
        'domain': domain,
        'items': items,
    }