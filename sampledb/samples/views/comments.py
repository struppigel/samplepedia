from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_comments.models import Comment
from django_comments.views.comments import CommentPostBadRequest
from django_comments import signals
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.models import User
from django.db.models import Q
from ..models import AnalysisTask
import django_comments
import re


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


@csrf_protect
@require_POST
@login_required
def post_comment(request):
    """
    Custom comment posting view that redirects to the comment with highlight.
    Overrides the default django-comments post view.
    """
    # Get the comment app and form
    comment_app = apps.get_app_config('django_comments_xtd')
    
    # Get data from request
    data = request.POST.copy()
    
    # Get the target object
    try:
        ctype = data.get("content_type")
        object_pk = data.get("object_pk")
        if ctype is None or object_pk is None:
            return CommentPostBadRequest("Missing content_type or object_pk field.")
        
        content_type = ContentType.objects.get_for_id(int(ctype))
        target = content_type.get_object_for_this_type(pk=object_pk)
    except (ValueError, ContentType.DoesNotExist, target.__class__.DoesNotExist):
        return CommentPostBadRequest("Invalid content_type or object_pk")
    
    # Get the comment form
    form_class = django_comments.get_form()
    form = form_class(target, data=data)
    
    # Set user on form for AuthenticatedCommentForm
    if hasattr(form, 'user'):
        form.user = request.user
    
    # Check security and validate
    if not form.is_valid():
        return CommentPostBadRequest("Invalid form data")
    
    # Save the comment
    comment = form.get_comment_object(site_id=django_comments.get_current_site_id(request))
    comment.ip_address = request.META.get("REMOTE_ADDR", None)
    comment.user = request.user
    
    # Save and send signals
    comment.save()
    signals.comment_was_posted.send(
        sender=comment.__class__,
        comment=comment,
        request=request,
    )
    
    # Redirect to the comment with highlight
    if isinstance(target, AnalysisTask):
        redirect_url = f"{target.get_absolute_url()}?highlight=comment-{comment.id}#comment-{comment.id}"
    else:
        redirect_url = target.get_absolute_url()
    
    return HttpResponseRedirect(redirect_url)


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
