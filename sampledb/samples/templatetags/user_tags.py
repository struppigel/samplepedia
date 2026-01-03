from django import template

register = template.Library()

@register.inclusion_tag('samples/_user_groups.html')
def display_user_groups(user):
    """
    Display user's groups as badges.
    Shows 'admin' badge for superusers, actual groups, or 'standard member' for users with no groups.
    """
    return {'user': user}

@register.inclusion_tag('samples/_rank_medal.html')
def rank_medal(rank, size='normal'):
    """
    Display ranking medal badge for top 3 users, or rank number for others.
    Shows gold (#1), silver (#2), or bronze (#3) medal badges.
    
    Args:
        rank: The user's rank position
        size: 'normal' (1.1em) or 'small' (0.85em) for different display contexts
    """
    return {'rank': rank, 'size': size}

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

@register.filter
def difficulty_badge_class(difficulty):
    """
    Return the Bootstrap badge class for a difficulty level.
    This is the single source of truth for difficulty badge colors.
    
    Returns a string like "badge-info" ready to use in badge class attribute.
    """
    badge_classes = {
        'easy': 'badge-info',
        'medium': 'badge-warning',
        'advanced': 'badge-danger',
        'expert': 'badge-dark',
    }
    return badge_classes.get(difficulty, 'badge-secondary')

@register.filter
def solution_icon(solution_type):
    """
    Return the Font Awesome icon and color classes for a solution type.
    Returns a string like "fa-book text-info" ready to use in class attribute.
    
    For unknown solution types, returns a generic link icon as fallback.
    """
    icons = {
        'blog': 'fa-book text-info',
        'paper': 'fa-file-alt text-secondary',
        'video': 'fa-video text-danger',
        'onsite': 'fa-file-alt text-success',
    }
    return icons.get(solution_type, 'fa-link text-primary')

@register.inclusion_tag('samples/_solution_icons.html')
def solution_icons(task):
    """
    Display solution type icons for an analysis task.
    Shows one icon per solution type (blog, paper, video, onsite).
    Dynamically detects all solution types present.
    """
    from collections import Counter
    
    solutions = task.solutions.all()
    total_count = solutions.count()
    
    # Get all solution types present (ordered by the keys in solution_icon for consistency)
    solution_types_present = []
    if total_count > 0:
        type_counts = Counter(solutions.values_list('solution_type', flat=True))
        # Order by the keys in solution_icon filter for consistent display
        icon_order = ['blog', 'paper', 'video', 'onsite']
        solution_types_present = [st for st in icon_order if st in type_counts]
    
    return {
        'solution_types': solution_types_present,
        'has_any': bool(solution_types_present),
        'total_count': total_count
    }

@register.inclusion_tag('samples/_solution_like_button.html')
def solution_like_button(solution, is_liked_or_set):
    """
    Display a like button with count for a solution.
    
    Args:
        solution: The Solution object
        is_liked_or_set: Either a boolean indicating if liked, or a set of liked IDs to check against
    """
    # Determine if the solution is liked
    if isinstance(is_liked_or_set, bool):
        is_liked = is_liked_or_set
    else:
        # Assume it's a set of IDs
        is_liked = solution.id in is_liked_or_set
    
    return {
        'solution_id': solution.id,
        'like_count': solution.like_count,
        'is_liked': is_liked
    }
