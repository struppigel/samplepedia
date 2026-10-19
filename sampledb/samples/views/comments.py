from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_comments.models import Comment
from django_comments.views.comments import post_comment as django_comments_post_comment
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.models import User
from django.db.models import Q
from ..models import AnalysisTask


@login_required
def edit_comment(request, comment_id):
    """Allow users to edit their own comments"""
    comment = get_object_or_404(Comment, pk=comment_id)
    
    # Check if user owns this comment
    if comment.user != request.user:
        return HttpResponseForbidden("You can only edit your own comments.")
    
    if request.method == 'POST':
        new_text = request.POST.get('comment', '').strip()
        if new_text:
            comment.comment = new_text
            comment.save()
            messages.success(request, 'Comment updated successfully.')
            return redirect(comment.content_object.get_absolute_url())
        else:
            messages.error(request, 'Comment cannot be empty.')
    
    return redirect(comment.content_object.get_absolute_url())


@login_required
def delete_comment(request, comment_id):
    """
    Allow users to delete comments if they are:
    - The comment author
    - A staff member
    - The author of the task being commented on
    """
    comment = get_object_or_404(Comment, pk=comment_id)
    
    # Get the analysis task (content object)
    task = comment.content_object
    
    # Check permissions
    can_delete = (
        comment.user == request.user or  # Comment author
        request.user.is_staff or  # Staff member
        (isinstance(task, AnalysisTask) and task.author == request.user)  # Task author
    )
    
    if not can_delete:
        return HttpResponseForbidden("You don't have permission to delete this comment.")
    
    if request.method == 'POST':
        # Get the redirect URL before deleting (with anchor to comments section)
        redirect_url = f"{comment.content_object.get_absolute_url()}#comments-section"
        # Mark as removed (soft delete)
        comment.is_removed = True
        comment.save()
        messages.success(request, 'Comment deleted successfully.')
        return redirect(redirect_url)
    
    # Show confirmation page on GET
    return render(request, 'comments/delete.html', {
        'comment': comment,
        'next': request.GET.get('next', comment.content_object.get_absolute_url())
    })


@require_POST
@login_required
def post_comment(request):
    """Comments require an account; validation and saving are left to django-comments."""
    return django_comments_post_comment(request)


def comment_posted(request):
    """
    django-comments redirects here with ?c=<id> after a successful post.
    Send the author to their new comment, highlighted.
    """
    comment_id = request.GET.get('c', '')
    if not comment_id.isdigit():
        raise Http404
    comment = get_object_or_404(Comment, pk=comment_id, is_removed=False)
    target = comment.content_object
    if target is None:
        raise Http404
    return redirect(f"{target.get_absolute_url()}?highlight=comment-{comment.id}#comment-{comment.id}")


def comments_api_disabled(request, *args, **kwargs):
    raise Http404


@require_GET
@login_required
def search_users(request):
    """
    Search for users by username for @ mentions.
    Returns JSON list of usernames matching the query.
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 1:
        return JsonResponse({'users': []})
    
    # Search for users whose username starts with or contains the query
    users = User.objects.filter(
        Q(username__istartswith=query) | Q(username__icontains=query)
    ).exclude(id=request.user.id).values_list('username', flat=True)[:10]
    
    return JsonResponse({'users': list(users)})
