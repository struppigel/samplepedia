from django import template

register = template.Library()

@register.inclusion_tag('samples/_user_groups.html')
def display_user_groups(user):
    """
    Display user's groups as badges.
    Shows 'admin' badge for superusers, actual groups, or 'standard member' for users with no groups.
    """
    return {'user': user}

@register.inclusion_tag('samples/_difficulty_badge.html')
def difficulty_badge(difficulty, difficulty_display=None):
    """
    Display difficulty as a color-coded badge linking to filtered view.
    """
    if difficulty_display is None:
        difficulty_display = difficulty
    return {
        'difficulty': difficulty,
        'difficulty_display': difficulty_display
    }
