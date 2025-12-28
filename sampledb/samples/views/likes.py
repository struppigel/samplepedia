from django.shortcuts import get_object_or_404
from django.http import JsonResponse

from ..models import AnalysisTask


def toggle_like(request, sha256, task_id):
    """Toggle favorite for a sample (requires authentication)"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Login required',
            'redirect': '/accounts/login/'
        }, status=401)
    
    sample = get_object_or_404(AnalysisTask, id=task_id)
    
    if sample.favorited_by.filter(id=request.user.id).exists():
        # Remove from favorites
        sample.favorited_by.remove(request.user)
        user_has_favorited = False
    else:
        # Add to favorites
        sample.favorited_by.add(request.user)
        user_has_favorited = True
    
    # Return JSON response for AJAX
    return JsonResponse({
        'liked': user_has_favorited,
        'like_count': sample.favorite_count
    })
