from django import template

register = template.Library()

@register.inclusion_tag('samples/_user_groups.html')
def display_user_groups(user):
    """
    Display user's groups as badges.
    Shows 'admin' badge for superusers, actual groups, or 'standard member' for users with no groups.
    """
    return {'user': user}
