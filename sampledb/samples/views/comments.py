from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_comments.models import Comment
from django.http import HttpResponseForbidden
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
        # Get the redirect URL before deleting
        redirect_url = comment.content_object.get_absolute_url()
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
