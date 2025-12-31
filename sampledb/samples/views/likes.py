from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from notifications.signals import notify

from ..models import AnalysisTask


def toggle_like(request, sha256, task_id):
    """Toggle favorite for a sample (requires authentication)"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Login required',
            'redirect': '/accounts/login/'
        }, status=401)
    
    sample = get_object_or_404(AnalysisTask, id=task_id)
    
    # Skip self-notifications
    if request.user == sample.author:
        if sample.favorited_by.filter(id=request.user.id).exists():
            sample.favorited_by.remove(request.user)
            user_has_favorited = False
        else:
            sample.favorited_by.add(request.user)
            user_has_favorited = True
        
        return JsonResponse({
            'liked': user_has_favorited,
            'like_count': sample.favorite_count
        })
    
    if sample.favorited_by.filter(id=request.user.id).exists():
        # Remove from favorites - DELETE notification
        sample.favorited_by.remove(request.user)
        user_has_favorited = False
        
        # Delete all like notifications for this user and task
        sample.author.notifications.filter(
            verb='liked',
            action_object_object_id=str(sample.id),
            action_object_content_type__model='analysistask'
        ).delete()
        
    else:
        # Add to favorites - CREATE/UPDATE notification
        sample.favorited_by.add(request.user)
        user_has_favorited = True
        
        # Check if there's already a like notification for this task
        existing_notification = sample.author.notifications.filter(
            verb='liked',
            action_object_object_id=str(sample.id),
            action_object_content_type__model='analysistask',
            unread=True
        ).first()
        
        if existing_notification:
            # Update existing notification with aggregated count
            like_count = sample.favorite_count
            other_likers = sample.favorited_by.exclude(id=request.user.id)
            
            if other_likers.count() == 0:
                # Only this user liked it
                description = f"{request.user.username} liked your task"
            elif other_likers.count() == 1:
                # Two people total
                other_user = other_likers.first()
                description = f"{request.user.username} and {other_user.username} liked your task"
            else:
                # Multiple people
                count = other_likers.count()
                description = f"{request.user.username} and {count} others liked your task"
            
            existing_notification.description = description
            existing_notification.actor = request.user  # Update to most recent liker
            existing_notification.data = {'sha256': sample.sha256[:12]}
            existing_notification.save()
        else:
            # Create new notification
            notify.send(
                sender=request.user,
                recipient=sample.author,
                verb='liked',
                action_object=sample,
                description=f"{request.user.username} liked your task",
                data={'sha256': sample.sha256[:12]}
            )
    
    # Return JSON response for AJAX
    return JsonResponse({
        'liked': user_has_favorited,
        'like_count': sample.favorite_count
    })
