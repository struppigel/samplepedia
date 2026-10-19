"""
Guardrail tests for the front-end design system

This test suite covers:
1. Every {% static %} reference in templates resolves to an existing file
   (hashed static storage turns a missing file into a 500 in production)
2. No !important anywhere in project CSS or inline styles
3. Raw design values (colors, fonts, sizes, radii, shadows, z-index, durations)
   only live in static/css/tokens.css
4. Dark mode is defined only through tokens ([data-bs-theme] selectors)
5. No <style> blocks in templates (except standalone email templates)
6. No AdminLTE / Bootstrap 4 / jQuery leftovers
7. Python design tokens (samples/design_tokens.py) match tokens.css
8. Flash messages, the comments base.html shim, the AJAX difficulty class
   and Discord embed colors use the shared design tokens
"""

import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from samples import design_tokens
from samples.discord_utils import send_sample_notification
from samples.models import AnalysisTask, Difficulty
from samples.templatetags.user_tags import difficulty_badge_class

BASE_DIR = Path(settings.BASE_DIR)
TEMPLATES_DIR = BASE_DIR / 'samples' / 'templates'
CSS_DIR = BASE_DIR / 'static' / 'css'
JS_DIR = BASE_DIR / 'static' / 'js'
TOKENS_CSS = CSS_DIR / 'tokens.css'
BOOTSTRAP_THEME_CSS = CSS_DIR / 'bootstrap-theme.css'

# Standalone HTML emails need inline/embedded styles
EMAIL_TEMPLATES = {
    'registration/password_reset_email.html',
    'registration/verification_email.html',
    'registration/email_change_verification.html',
}

STATIC_TAG_RE = re.compile(r"""{%\s*static\s+['"]([^'"]+)['"]\s*%}""")
STYLE_ATTR_RE = re.compile(r'\sstyle="([^"]*)"')
COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)
DECLARATION_RE = re.compile(r'(?<=[{;])\s*(-?[a-z][a-z-]*)\s*:\s*([^;{}]+)')
VAR_RE = re.compile(r'var\([^()]*\)')
HEX_COLOR_RE = re.compile(r'#[0-9a-fA-F]{3,8}\b')
COLOR_FUNCTION_RE = re.compile(r'\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(([^()]*)\)', re.I)
NAMED_COLOR_RE = re.compile(
    r'\b(white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|silver|gold|'
    r'maroon|navy|teal|olive|lime|aqua|fuchsia|cyan|magenta|brown)\b', re.I
)

# Properties whose values must come from tokens outside tokens.css
TOKEN_ONLY_PROPERTIES = {
    'font-family', 'font-size', 'border-radius', 'box-shadow', 'z-index', 'transition', 'animation',
}
KEYWORDS = {'0', 'none', 'inherit', 'initial', 'unset', 'auto', 'transparent', 'currentcolor'}


def template_files():
    return sorted(TEMPLATES_DIR.rglob('*.html'))


def relative(path):
    return path.relative_to(TEMPLATES_DIR).as_posix()


def project_css_files():
    return sorted(CSS_DIR.rglob('*.css'))


def strip_vars(value):
    """Remove var(...) references (innermost first) so only literal values remain."""
    previous = None
    while previous != value:
        previous = value
        value = VAR_RE.sub('', value)
    return value


def css_declarations(text):
    return DECLARATION_RE.findall(COMMENT_RE.sub('', text))


def raw_color_violations(value):
    literal = strip_vars(value)
    problems = HEX_COLOR_RE.findall(literal) + NAMED_COLOR_RE.findall(literal)
    for name, args in COLOR_FUNCTION_RE.findall(literal):
        if args.strip(' ,/'):
            problems.append(f'{name}({args})')
    return problems


def inline_styles():
    """(template, style value) for every style="" outside the email templates."""
    for path in template_files():
        if relative(path) in EMAIL_TEMPLATES:
            continue
        for style in STYLE_ATTR_RE.findall(path.read_text(encoding='utf-8')):
            # template expressions ({{ }}, {% %}) are data, not design values
            yield relative(path), re.sub(r'{[{%].*?[%}]}', '', style)


class StaticReferencesTestCase(SimpleTestCase):
    """Every {% static %} path used in templates must exist"""

    def test_static_references_resolve(self):
        missing = []
        for path in template_files():
            for ref in STATIC_TAG_RE.findall(path.read_text(encoding='utf-8')):
                if not finders.find(ref):
                    missing.append(f"{relative(path)}: {ref}")
        self.assertEqual(missing, [], "Missing static files:\n" + "\n".join(missing))


class NoImportantTestCase(SimpleTestCase):
    """Styles win by load order and specificity, never by !important"""

    def test_no_important_in_css(self):
        offenders = [
            path.name for path in project_css_files()
            if '!important' in COMMENT_RE.sub('', path.read_text(encoding='utf-8'))
        ]
        self.assertEqual(offenders, [])

    def test_no_important_in_inline_styles(self):
        offenders = [f"{name}: {style}" for name, style in inline_styles() if '!important' in style]
        self.assertEqual(offenders, [])


class TokensOnlyTestCase(SimpleTestCase):
    """Raw design values live in tokens.css; everything else uses var(--sp-*)"""

    def test_no_raw_colors_outside_tokens(self):
        offenders = []
        for path in project_css_files():
            if path == TOKENS_CSS:
                continue
            for prop, value in css_declarations(path.read_text(encoding='utf-8')):
                for problem in raw_color_violations(value):
                    offenders.append(f"{path.name}: {prop}: {value.strip()} ({problem})")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_no_raw_colors_in_inline_styles(self):
        offenders = [
            f"{name}: {style}" for name, style in inline_styles()
            if raw_color_violations(style)
        ]
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_token_only_properties(self):
        offenders = []
        for path in project_css_files():
            if path == TOKENS_CSS:
                continue
            for prop, value in css_declarations(path.read_text(encoding='utf-8')):
                if prop not in TOKEN_ONLY_PROPERTIES:
                    continue
                literal = strip_vars(value).replace('calc(', '(').strip(' ()*-,')
                if prop in ('transition', 'animation'):
                    # property names and easing keywords are fine, raw durations are not
                    if re.search(r'\d', literal):
                        offenders.append(f"{path.name}: {prop}: {value.strip()}")
                elif literal and literal.lower() not in KEYWORDS:
                    offenders.append(f"{path.name}: {prop}: {value.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_inline_styles_have_no_design_values(self):
        design_props = TOKEN_ONLY_PROPERTIES | {'color', 'background', 'background-color', 'border-color'}
        offenders = []
        for name, style in inline_styles():
            for declaration in style.split(';'):
                prop = declaration.split(':', 1)[0].strip().lower()
                if prop in design_props:
                    offenders.append(f"{name}: {declaration.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))


class DarkModeTestCase(SimpleTestCase):
    """Dark mode is token redefinition only"""

    def test_theme_selector_only_in_token_files(self):
        allowed = {TOKENS_CSS, BOOTSTRAP_THEME_CSS}
        offenders = [
            path.name for path in project_css_files()
            if path not in allowed and '[data-bs-theme' in COMMENT_RE.sub('', path.read_text(encoding='utf-8'))
        ]
        self.assertEqual(offenders, [])

    def test_tokens_define_dark_theme(self):
        self.assertIn('[data-bs-theme="dark"]', TOKENS_CSS.read_text(encoding='utf-8'))


class TemplateStyleBlocksTestCase(SimpleTestCase):
    """Page styles belong in static/css, not in templates"""

    def test_no_style_blocks(self):
        offenders = [
            relative(path) for path in template_files()
            if relative(path) not in EMAIL_TEMPLATES and '<style' in path.read_text(encoding='utf-8')
        ]
        self.assertEqual(offenders, [])


class LegacyFrameworkTestCase(SimpleTestCase):
    """No AdminLTE, Bootstrap 4 or jQuery leftovers (e.g. after merging an old branch)"""

    LEGACY_PATTERNS = [
        (r'adminlte\.min|adminlte/', 'AdminLTE asset'),
        (r'\$\(|jQuery', 'jQuery'),
        (r'\.modal\(', 'jQuery modal API'),
        (r'data-(toggle|target|dismiss)=', 'Bootstrap 4 data attribute'),
        (r'(?<![\w-])(ml|mr|pl|pr)-(sm-|md-|lg-|xl-)?(\d|auto)(?![\w-])', 'Bootstrap 4 spacing class'),
        (r'(?<![\w-])(float|text)-(sm-|md-|lg-|xl-)?(left|right)(?![\w-])', 'Bootstrap 4 direction class'),
        (r'(?<![\w-])(badge-pill|form-group|form-inline|custom-control|custom-select|'
         r'embed-responsive[\w-]*|font-weight-\w+|no-gutters|sr-only)(?![\w-])', 'Bootstrap 4 class'),
        (r'class="close"', 'Bootstrap 4 close button'),
        (r'(?<![\w-])(text-dark|content-header|content-wrapper|main-header|main-footer|'
         r'navbar-badge|dropdown-menu-lg|bg-gradient-\w+|card-primary)(?![\w-])', 'AdminLTE/Bootstrap 4 class'),
        (r'(?<![\w-])(markdown-preview-content|markdown-content|article-content)(?![\w-])', 'old markdown class'),
        (r'--(primary-red|form-border|body-color|text-primary|text-color|accent-red)\b', 'old CSS variable'),
        (r'(?<![\w-])dark-mode(?![\w-])', 'old .dark-mode class'),
    ]

    def files(self):
        yield from (p for p in template_files() if relative(p) not in EMAIL_TEMPLATES)
        yield from sorted(JS_DIR.glob('*.js'))
        yield BASE_DIR / 'samples' / 'forms.py'

    def test_no_legacy_framework_usage(self):
        offenders = []
        for path in self.files():
            text = path.read_text(encoding='utf-8')
            for pattern, label in self.LEGACY_PATTERNS:
                for match in re.finditer(pattern, text):
                    line = text.count('\n', 0, match.start()) + 1
                    offenders.append(f"{path.name}:{line} {label}: {match.group(0)}")
        self.assertEqual(offenders, [], "\n".join(offenders))


class DesignTokensSyncTestCase(SimpleTestCase):
    """samples/design_tokens.py mirrors the matching tokens in tokens.css"""

    def root_tokens(self):
        text = COMMENT_RE.sub('', TOKENS_CSS.read_text(encoding='utf-8'))
        root_block = re.search(r':root\s*{(.*?)}', text, re.S).group(1)
        return dict(re.findall(r'--sp-([\w-]+)\s*:\s*([^;]+);', root_block))

    def test_difficulty_colors_match_tokens(self):
        tokens = self.root_tokens()
        for level, color in design_tokens.DIFFICULTY_COLORS.items():
            self.assertEqual(tokens[f'difficulty-{level}'].strip().lower(), color.lower(), level)
        self.assertEqual(
            tokens['difficulty-unknown'].strip().lower(),
            design_tokens.DIFFICULTY_FALLBACK_COLOR.lower(),
        )

    def test_event_colors_match_tokens(self):
        tokens = self.root_tokens()
        self.assertEqual(tokens['success'].strip().lower(), design_tokens.SUCCESS_COLOR.lower())
        self.assertEqual(tokens['danger'].strip().lower(), design_tokens.DANGER_COLOR.lower())

    def test_every_difficulty_has_color_and_badge_class(self):
        components = (CSS_DIR / 'components.css').read_text(encoding='utf-8')
        for level in Difficulty.values:
            self.assertIn(level, design_tokens.DIFFICULTY_COLORS)
            self.assertIn(f'.badge-difficulty-{level}', components)

    def test_difficulty_badge_class(self):
        self.assertEqual(difficulty_badge_class('easy'), 'badge-difficulty-easy')
        self.assertEqual(difficulty_badge_class('nonsense'), 'badge-difficulty-unknown')

    def test_difficulty_embed_color(self):
        self.assertEqual(design_tokens.difficulty_embed_color('easy'), 0x17a2b8)
        self.assertEqual(design_tokens.difficulty_embed_color('nonsense'), 0x6c757d)


class DesignIntegrationTestCase(TestCase):
    """Server-side pieces of the design system work end to end"""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='testpass123')
        self.other = User.objects.create_user(username='other', password='testpass123')
        self.task = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Find the C2 address',
            difficulty=Difficulty.EASY,
            description='Test description',
            author=self.owner,
        )
        self.client = Client()

    def test_error_message_rendered_once_as_danger_alert(self):
        self.client.login(username='other', password='testpass123')
        response = self.client.get(
            reverse('edit_task', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True,
        )
        content = response.content.decode()
        self.assertEqual(content.count('You do not have permission to edit this task.'), 1)
        self.assertIn('alert alert-danger', content)

    def test_comments_base_shim_renders_site_layout(self):
        # django_comments_xtd templates extend "base.html"
        response = self.client.get(reverse('comments-flag-done'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'app-navbar')
        self.assertContains(response, 'class="page-title"')

    def test_search_samples_ajax_returns_difficulty_class(self):
        self.client.login(username='owner', password='testpass123')
        response = self.client.get(reverse('search_samples_ajax'), {'q': 'C2 address'})
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['difficulty_class'], 'badge-difficulty-easy')

    @override_settings(DISCORD_WEBHOOK_EASY='https://discord.invalid/webhook')
    def test_discord_embed_uses_difficulty_palette(self):
        with mock.patch('samples.discord_utils.requests.post') as post:
            send_sample_notification(self.task)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['embeds'][0]['color'], 0x17a2b8)
