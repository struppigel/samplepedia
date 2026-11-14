"""
Markdown rendering for user content.

Python-Markdown passes raw HTML through and attr_list lets authors put any
attribute (including on* handlers) on block elements, so the output is
sanitized with an allowlist before it reaches a template.
"""
import re

import nh3
from django.utils.safestring import SafeString, mark_safe
from markdownx.utils import markdownify

ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'dd', 'del', 'details', 'div',
    'dl', 'dt', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins',
    'kbd', 'li', 'mark', 'ol', 'p', 'pre', 's', 'span', 'strong', 'sub', 'summary',
    'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'ul',
}

ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'class'},
    'abbr': {'title'},
    'code': {'class'},
    'div': {'class'},
    'img': {'src', 'alt', 'title', 'width', 'height'},
    'li': {'id'},
    'ol': {'start'},
    'sup': {'id'},
    'td': {'style'},
    'th': {'style'},
}

# Classes and ids the markdown extensions generate (fenced_code, footnotes)
ALLOWED_CLASS_RE = re.compile(r'(language-[\w+#-]+|footnote|footnote-ref|footnote-backref)')
ALLOWED_ID_RE = re.compile(r'fn(ref)?:\d+')


def _filter_attribute(tag, attribute, value):
    if attribute == 'class':
        classes = [c for c in value.split() if ALLOWED_CLASS_RE.fullmatch(c)]
        return ' '.join(classes) or None
    if attribute == 'id':
        return value if ALLOWED_ID_RE.fullmatch(value) else None
    return value


def sanitize_html(html):
    """Strip everything from rendered markdown that isn't on the allowlist."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_filter_attribute,
        filter_style_properties={'text-align'},
        url_schemes={'http', 'https', 'mailto'},
    )


def render_markdown(text) -> SafeString:
    """Render user-supplied markdown to sanitized HTML that is safe to output."""
    if not text:
        return mark_safe('')
    return mark_safe(sanitize_html(markdownify(text)))
