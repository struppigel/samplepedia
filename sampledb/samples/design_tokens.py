"""
Design tokens needed outside the browser (e.g. Discord embed colors).

The single source of truth for the site's design is static/css/tokens.css.
The values here mirror the matching --sp-* custom properties there;
samples/tests/test_design_system.py fails if the two drift apart.
"""

# Mirrors --sp-difficulty-<level> in tokens.css
DIFFICULTY_COLORS = {
    'easy': '#17a2b8',
    'medium': '#ffa726',
    'advanced': '#ef5350',
    'expert': '#111111',
}

# Mirrors --sp-difficulty-unknown in tokens.css
DIFFICULTY_FALLBACK_COLOR = '#6c757d'

# Mirror --sp-success / --sp-danger in tokens.css
SUCCESS_COLOR = '#28a745'
DANGER_COLOR = '#dc3545'


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
