"""
Design tokens needed outside the browser (e.g. Discord embed colors).

They are read from static/css/tokens.css, the single source of truth for the
site's design, when this module is imported; nothing here is copied by hand.
"""
import re
from functools import lru_cache
from pathlib import Path

from .models import Difficulty

TOKENS_CSS = Path(__file__).resolve().parent.parent / 'static' / 'css' / 'tokens.css'

_COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)
_ROOT_RE = re.compile(r':root\s*\{(.*?)\}', re.S)
_TOKEN_RE = re.compile(r'--sp-([\w-]+)\s*:\s*([^;]+);')
_VAR_RE = re.compile(r'var\(--sp-([\w-]+)\)')


@lru_cache(maxsize=None)
def light_tokens():
    """The light theme's --sp-* values (from :root), with var() references resolved."""
    text = _COMMENT_RE.sub('', TOKENS_CSS.read_text(encoding='utf-8'))
    raw = {}
    for block in _ROOT_RE.findall(text):
        raw.update((name, value.strip()) for name, value in _TOKEN_RE.findall(block))

    def resolve(value, depth=0):
        if depth > 10:
            return value
        return _VAR_RE.sub(lambda m: resolve(raw[m.group(1)], depth + 1), value)

    return {name: resolve(value) for name, value in raw.items()}


_tokens = light_tokens()

# --sp-difficulty-<level> and the badge color for unknown levels
DIFFICULTY_COLORS = {level: _tokens[f'difficulty-{level}'] for level in Difficulty.values}
DIFFICULTY_FALLBACK_COLOR = _tokens['difficulty-unknown']

# --sp-success / --sp-danger
SUCCESS_COLOR = _tokens['success']
DANGER_COLOR = _tokens['danger']


def difficulty_css_class(difficulty):
    """CSS class for a difficulty badge, e.g. 'badge-difficulty-easy' (styled in components.css)."""
    if difficulty in DIFFICULTY_COLORS:
        return f'badge-difficulty-{difficulty}'
    return 'badge-difficulty-unknown'


def hex_to_int(color):
    """'#17a2b8' -> 0x17a2b8, the integer color format Discord embeds expect."""
    return int(color.lstrip('#'), 16)


def difficulty_embed_color(difficulty):
    """Discord embed color for a difficulty level."""
    return hex_to_int(DIFFICULTY_COLORS.get(difficulty, DIFFICULTY_FALLBACK_COLOR))
