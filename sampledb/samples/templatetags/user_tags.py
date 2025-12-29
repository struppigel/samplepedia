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

@register.inclusion_tag('samples/_favorite_button.html')
def favorite_button(task, is_liked_or_set):
    """
    Display a favorite/like button with count for an analysis task.
    
    Args:
        task: The AnalysisTask object
        is_liked_or_set: Either a boolean indicating if liked, or a set of favorited IDs to check against
    """
    # Determine if the task is liked
    if isinstance(is_liked_or_set, bool):
        is_liked = is_liked_or_set
    else:
        # Assume it's a set of IDs
        is_liked = task.id in is_liked_or_set
    
    return {
        'task_id': task.id,
        'sha256': task.sha256,
        'favorite_count': task.favorite_count,
        'is_liked': is_liked
    }

@register.filter
def is_in(value, container):
    """
    Check if a value is in a container (e.g., list, set).
    Usage: {% if task.id|is_in:user_favorited_ids %}
    """
    return value in container
