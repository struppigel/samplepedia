from django.conf import settings
from django.shortcuts import get_object_or_404, resolve_url
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ..models import AnalysisTask, Solution
from ..services.likes import toggle_like as toggle


def login_required_response():
    return JsonResponse({'error': 'Login required', 'redirect': resolve_url(settings.LOGIN_URL)}, status=401)


def _toggle_response(request, target):
    if not request.user.is_authenticated:
        return login_required_response()
    liked, like_count = toggle(target, request.user)
    return JsonResponse({'liked': liked, 'like_count': like_count})


@require_POST
def toggle_like(request, sha256, task_id):
    """Toggle favorite for a sample (requires authentication)"""
    return _toggle_response(request, get_object_or_404(AnalysisTask, id=task_id))


@require_POST
def toggle_solution_like(request, solution_id):
    """Toggle like for a solution (requires authentication)"""
    return _toggle_response(request, get_object_or_404(Solution, id=solution_id))
