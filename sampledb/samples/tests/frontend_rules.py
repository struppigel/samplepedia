"""
Static checks for the front end, shared by test_frontend.py and usable from the
command line while refactoring:

    python samples/tests/frontend_rules.py [path-substring ...]

Each check yields (relative path, line, message).
"""
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / 'samples' / 'templates'
JS_DIR = BASE_DIR / 'static' / 'js'

# HTML e-mails are standalone documents, not pages of the site
EMAIL_TEMPLATES = {'registration/_email_base.html'}

INLINE_SCRIPT_RE = re.compile(r'<script\b(?![^>]*\bsrc=)(?![^>]*type="application/(?:ld\+)?json")[^>]*>', re.I)
EVENT_ATTR_RE = re.compile(r'\son[a-z]+\s*=\s*["\']', re.I)
# Absolute app paths written into JS instead of coming from {% url %} via data-* attributes
HARDCODED_URL_RE = re.compile(r"""[`'"]/(sample|solution|comments|notifications|ajax|articles|markdown-preview|upload-editor-image|profile|login)\b""")
COOKIE_RE = re.compile(r'document\.cookie')
STYLE_DISPLAY_RE = re.compile(r'\.style\.display\b')


def line_of(text, index):
    return text.count('\n', 0, index) + 1


def templates():
    for path in sorted(TEMPLATES_DIR.rglob('*.html')):
        relative = path.relative_to(TEMPLATES_DIR).as_posix()
        if relative not in EMAIL_TEMPLATES:
            yield relative, path.read_text(encoding='utf-8')


def scripts():
    for path in sorted(JS_DIR.rglob('*.js')):
        yield 'static/js/' + path.relative_to(JS_DIR).as_posix(), path.read_text(encoding='utf-8')


def inline_scripts():
    for name, text in templates():
        for match in INLINE_SCRIPT_RE.finditer(text):
            yield name, line_of(text, match.start()), 'inline <script> (move it to static/js)'


def inline_event_handlers():
    for name, text in [*templates(), *scripts()]:
        for match in EVENT_ATTR_RE.finditer(text):
            yield name, line_of(text, match.start()), f'inline handler {match.group(0).strip()} (use addEventListener)'


def hardcoded_urls():
    for name, text in scripts():
        for match in HARDCODED_URL_RE.finditer(text):
            yield name, line_of(text, match.start()), f'hardcoded URL {match.group(0)} (pass it with a data-* attribute)'


def cookie_parsing():
    for name, text in scripts():
        if name == 'static/js/utils.js':
            continue
        for match in COOKIE_RE.finditer(text):
            yield name, line_of(text, match.start()), 'document.cookie (use sp.csrfToken())'


def display_toggling():
    for name, text in scripts():
        for match in STYLE_DISPLAY_RE.finditer(text):
            yield name, line_of(text, match.start()), '.style.display (use sp.show() / the hidden attribute)'


CHECKS = [inline_scripts, inline_event_handlers, hardcoded_urls, cookie_parsing, display_toggling]


if __name__ == '__main__':
    filters = sys.argv[1:]
    count = 0
    for check in CHECKS:
        for name, line, message in check():
            if not filters or any(f in name for f in filters):
                print(f'{name}:{line}: {message}')
                count += 1
    print(f'{count} finding(s)')
