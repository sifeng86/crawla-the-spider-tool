import re
from typing import Any, Dict
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


INSPECTOR_STYLE = """
body {
  cursor: crosshair !important;
  scroll-behavior: smooth;
}

[data-crawla-inspector-banner] {
  align-items: center;
  background: rgba(8, 17, 27, 0.92);
  border-bottom: 1px solid rgba(68, 199, 244, 0.35);
  color: #f0f6fc;
  display: flex;
  font: 600 13px/1.4 Arial, sans-serif;
  gap: 10px;
  justify-content: space-between;
  left: 0;
  padding: 10px 14px;
  position: sticky;
  top: 0;
  z-index: 2147483647;
}

[data-crawla-inspector-pill] {
  background: rgba(68, 199, 244, 0.16);
  border: 1px solid rgba(68, 199, 244, 0.34);
  border-radius: 999px;
  color: #d6ecff;
  font-size: 11px;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  text-transform: uppercase;
}

.__crawla_hover {
  outline: 2px dashed rgba(68, 199, 244, 0.95) !important;
  outline-offset: 2px !important;
}

.__crawla_selected {
  outline: 3px solid rgba(46, 160, 67, 0.95) !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 0 3px rgba(46, 160, 67, 0.16) !important;
}
"""


INSPECTOR_SCRIPT = r"""
(function () {
  const HOVER_CLASS = '__crawla_hover';
  const SELECTED_CLASS = '__crawla_selected';
  let hovered = null;
  let selected = null;

  function cssEscapeValue(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return window.CSS.escape(value);
    }
    return String(value).replace(/([ !"#$%&'()*+,./:;<=>?@[\]^`{|}~])/g, '\\$1');
  }

  function buildCssSelector(element) {
    if (!element || element.nodeType !== 1) {
      return '';
    }

    if (element.id) {
      return '#' + cssEscapeValue(element.id);
    }

    const path = [];
    let node = element;
    while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== 'html') {
      let segment = node.tagName.toLowerCase();
      const classNames = Array.from(node.classList || []).filter(Boolean).slice(0, 2);
      if (classNames.length) {
        segment += '.' + classNames.map(cssEscapeValue).join('.');
      }

      if (node.parentElement) {
        const siblings = Array.from(node.parentElement.children).filter((sibling) => sibling.tagName === node.tagName);
        if (siblings.length > 1) {
          segment += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
        }
      }

      path.unshift(segment);
      if (path.length >= 5) {
        break;
      }
      node = node.parentElement;
      if (node && node.id) {
        path.unshift('#' + cssEscapeValue(node.id));
        break;
      }
    }

    return path.join(' > ');
  }

  function buildXPath(element) {
    if (!element || element.nodeType !== 1) {
      return '';
    }
    if (element.id) {
      return '//*[@id="' + String(element.id).replace(/"/g, '\\"') + '"]';
    }

    const segments = [];
    let node = element;
    while (node && node.nodeType === 1) {
      const tagName = node.tagName.toLowerCase();
      let index = 1;
      let sibling = node.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === node.tagName) {
          index += 1;
        }
        sibling = sibling.previousElementSibling;
      }
      segments.unshift(tagName + '[' + index + ']');
      node = node.parentElement;
    }
    return '/' + segments.join('/');
  }

  function truncateText(value, limit) {
    const normalized = String(value || '').replace(/\s+/g, ' ').trim();
    if (!normalized) {
      return '';
    }
    if (normalized.length <= limit) {
      return normalized;
    }
    return normalized.slice(0, limit) + '...';
  }

  function buildAttributeCandidates(element) {
    const attributes = ['data-testid', 'data-test', 'aria-label', 'name', 'href', 'src'];
    return attributes
      .filter((attributeName) => element.hasAttribute(attributeName))
      .map((attributeName) => {
        const rawValue = element.getAttribute(attributeName);
        const value = truncateText(rawValue, 80);
        let selector = '[' + attributeName + '="' + String(rawValue).replace(/"/g, '\\"') + '"]';
        if (attributeName === 'href' && rawValue) {
          selector = element.tagName.toLowerCase() + '[href*="' + String(rawValue).slice(0, 40).replace(/"/g, '\\"') + '"]';
        }
        return {
          kind: 'attribute',
          label: attributeName,
          value: selector,
          preview: value,
        };
      });
  }

  function buildCandidatePayload(element) {
    const text = truncateText(element.innerText || element.textContent || '', 160);
    return {
      source: 'crawla-studio-inspector',
      payload: {
        tag: element.tagName.toLowerCase(),
        text: text,
        html: truncateText(element.outerHTML || '', 220),
        candidates: [
          {
            kind: 'css',
            label: 'CSS selector',
            value: buildCssSelector(element),
            preview: truncateText(buildCssSelector(element), 140),
          },
          {
            kind: 'xpath',
            label: 'XPath',
            value: buildXPath(element),
            preview: truncateText(buildXPath(element), 140),
          }
        ].concat(buildAttributeCandidates(element)).filter((candidate) => candidate.value),
      }
    };
  }

  function markHovered(element) {
    if (hovered && hovered !== selected) {
      hovered.classList.remove(HOVER_CLASS);
    }
    hovered = element;
    if (hovered && hovered !== selected) {
      hovered.classList.add(HOVER_CLASS);
    }
  }

  function selectElement(element) {
    if (selected) {
      selected.classList.remove(SELECTED_CLASS);
    }
    selected = element;
    if (selected) {
      selected.classList.remove(HOVER_CLASS);
      selected.classList.add(SELECTED_CLASS);
      window.parent.postMessage(buildCandidatePayload(selected), '*');
    }
  }

  document.addEventListener('mouseover', function (event) {
    if (!event.target.closest('[data-crawla-inspector-banner]')) {
      markHovered(event.target);
    }
  }, true);

  document.addEventListener('click', function (event) {
    const target = event.target.closest('[data-crawla-inspector-banner]') ? null : event.target;
    if (!target) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    selectElement(target);
  }, true);

  window.parent.postMessage({
    source: 'crawla-studio-inspector',
    payload: {
      ready: true,
      candidates: [],
      text: '',
      html: '',
      tag: '',
    }
  }, '*');
})();
"""


STYLE_IMPORT_RE = re.compile(r'@import\s+(?:url\([^)]*\)|[^;]+);?', re.IGNORECASE)
STYLE_URL_RE = re.compile(r'url\((?P<value>.*?)\)', re.IGNORECASE)
MAX_STYLESHEET_LINKS = 8
MAX_STYLESHEET_BYTES = 500_000


def _remove_dangerous_attributes(soup: BeautifulSoup):
    for tag in soup.find_all(True):
        attributes = dict(tag.attrs)
        for attr_name in attributes:
            normalized_name = attr_name.lower()
            if normalized_name.startswith('on') or normalized_name in {'srcdoc'}:
                del tag.attrs[attr_name]


def _normalize_resource_url(base_url: str, value: str) -> str:
    normalized = str(value or '').strip()
    if not normalized or normalized.startswith(('#', 'data:', 'javascript:', 'mailto:', 'tel:')):
        return normalized
    return urljoin(base_url, normalized)


def _normalize_srcset(base_url: str, value: str) -> str:
    normalized_candidates = []
    for candidate in str(value or '').split(','):
        chunk = candidate.strip()
        if not chunk:
            continue
        parts = chunk.split()
        resource_url = _normalize_resource_url(base_url, parts[0])
        descriptor = ' '.join(parts[1:])
        normalized_candidates.append(resource_url + (' ' + descriptor if descriptor else ''))
    return ', '.join(normalized_candidates)


def _rewrite_relative_resource_urls(soup: BeautifulSoup, base_url: str):
    for tag in soup.find_all(True):
        for attr_name in ('href', 'src', 'poster', 'action'):
            if tag.has_attr(attr_name):
                tag[attr_name] = _normalize_resource_url(base_url, tag.get(attr_name))
        if tag.has_attr('srcset'):
            tag['srcset'] = _normalize_srcset(base_url, tag.get('srcset'))


def _sanitize_embedded_styles(soup: BeautifulSoup):
    for style_tag in list(soup.find_all('style')):
        stylesheet = style_tag.string if style_tag.string is not None else style_tag.get_text()
        sanitized = STYLE_IMPORT_RE.sub('', str(stylesheet or ''))
        if sanitized.strip():
            style_tag.string = sanitized
        else:
            style_tag.decompose()


def _is_stylesheet_link(tag: Any) -> bool:
  rel_values = tag.get('rel') or []
  if isinstance(rel_values, str):
    rel_values = rel_values.split()
  normalized = {str(value).strip().lower() for value in rel_values if str(value).strip()}
  return 'stylesheet' in normalized and bool(tag.get('href'))


def _fetch_stylesheet_text(stylesheet_url: str) -> str:
  normalized_url = str(stylesheet_url or '').strip()
  if not normalized_url.startswith(('http://', 'https://')):
    return ''

  request = Request(
    normalized_url,
    headers={
      'User-Agent': 'Mozilla/5.0 (compatible; CrawlaStudioInspector/1.0)',
      'Accept': 'text/css,*/*;q=0.1',
    },
  )
  try:
    with urlopen(request, timeout=5) as response:
      payload = response.read(MAX_STYLESHEET_BYTES + 1)
      if len(payload) > MAX_STYLESHEET_BYTES:
        return ''
      charset = response.headers.get_content_charset() or 'utf-8'
  except Exception:
    return ''

  try:
    return payload.decode(charset, errors='replace')
  except LookupError:
    return payload.decode('utf-8', errors='replace')


def _rewrite_stylesheet_resource_urls(stylesheet: str, stylesheet_url: str) -> str:
  def replace_url(match: re.Match[str]) -> str:
    raw_value = (match.group('value') or '').strip()
    quote = ''
    if raw_value[:1] in {'\"', "'"} and raw_value[-1:] == raw_value[:1]:
      quote = raw_value[:1]
      raw_value = raw_value[1:-1].strip()

    if not raw_value:
      return 'url()'
    if raw_value.lower().startswith('javascript:'):
      return 'url()'

    normalized = _normalize_resource_url(stylesheet_url, raw_value)
    if not normalized:
      return 'url()'
    wrapper = quote or '"'
    return f'url({wrapper}{normalized}{wrapper})'

  return STYLE_URL_RE.sub(replace_url, stylesheet)


def _sanitize_stylesheet_text(stylesheet: str, stylesheet_url: str) -> str:
  sanitized = STYLE_IMPORT_RE.sub('', str(stylesheet or ''))
  return _rewrite_stylesheet_resource_urls(sanitized, stylesheet_url)


def _collect_linked_stylesheets(soup: BeautifulSoup, base_url: str):
  collected_stylesheets = []
  stylesheet_links = [tag for tag in soup.find_all('link') if _is_stylesheet_link(tag)]
  for link_tag in stylesheet_links[:MAX_STYLESHEET_LINKS]:
    stylesheet_url = _normalize_resource_url(base_url, link_tag.get('href'))
    stylesheet_text = _fetch_stylesheet_text(stylesheet_url)
    if not stylesheet_text:
      continue

    sanitized_stylesheet = _sanitize_stylesheet_text(stylesheet_text, stylesheet_url)
    if sanitized_stylesheet.strip():
      collected_stylesheets.append(sanitized_stylesheet)

  return collected_stylesheets


def build_inspector_document(url: str, html: str, note: str) -> str:
  soup = BeautifulSoup(html or '<html><body></body></html>', 'html.parser')
  linked_stylesheets = _collect_linked_stylesheets(soup, url)

  for tag in soup.find_all(['script', 'noscript', 'iframe', 'object', 'embed', 'link']):
    tag.decompose()

  for tag in soup.find_all('meta'):
    if str(tag.get('http-equiv', '')).lower() == 'refresh':
      tag.decompose()

  _remove_dangerous_attributes(soup)
  _sanitize_embedded_styles(soup)
  _rewrite_relative_resource_urls(soup, url)

  if soup.html is None:
    html_tag = soup.new_tag('html')
    html_tag.extend(soup.contents)
    soup.clear()
    soup.append(html_tag)

  if soup.head is None:
    soup.html.insert(0, soup.new_tag('head'))
  if soup.body is None:
    body_tag = soup.new_tag('body')
    for child in list(soup.html.contents):
      if child is soup.head:
        continue
      body_tag.append(child.extract())
    soup.html.append(body_tag)

  for stylesheet in linked_stylesheets:
    external_style_tag = soup.new_tag('style')
    external_style_tag.string = stylesheet
    soup.head.append(external_style_tag)

  style_tag = soup.new_tag('style')
  style_tag.string = INSPECTOR_STYLE
  soup.head.append(style_tag)

  banner = soup.new_tag('div')
  banner['data-crawla-inspector-banner'] = 'true'
  banner.append('Click any element to generate selector candidates for Studio.')
  pill = soup.new_tag('span')
  pill['data-crawla-inspector-pill'] = 'true'
  pill.string = note
  banner.append(pill)
  soup.body.insert(0, banner)

  script_tag = soup.new_tag('script')
  script_tag.string = INSPECTOR_SCRIPT
  soup.body.append(script_tag)
  return str(soup)


def build_inspector_response(preview_id: str, selected_method: str, html: str, url: str) -> Dict[str, Any]:
  source_mode = 'cached_html' if selected_method in {'py_requests', 'py_llm'} else 'browser_snapshot'
  note = 'Cached HTML preview' if source_mode == 'cached_html' else 'Browser-rendered DOM snapshot'
  return {
    'preview_id': preview_id,
    'source_mode': source_mode,
    'note': note,
    'html': build_inspector_document(url, html, note),
  }