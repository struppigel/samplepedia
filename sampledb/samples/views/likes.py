from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..models import AnalysisTask, Solution, Notification


def toggle_like(request, sha256, task_id):
    """Toggle favorite for a sample (requires authentication)"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Login required',
            'redirect': '/login/'
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
        
        # Delete all like notifications for this task
        content_type = ContentType.objects.get_for_model(AnalysisTask)
        Notification.objects.filter(
            recipient=sample.author,
            verb='liked',
            target_content_type=content_type,
            target_object_id=sample.id
        ).delete()
        
    else:
        # Add to favorites - CREATE/UPDATE notification
        sample.favorited_by.add(request.user)
        user_has_favorited = True
        
        # Check if there's already a like notification for this task
        content_type = ContentType.objects.get_for_model(AnalysisTask)
        existing_notification = Notification.objects.filter(
            recipient=sample.author,
            verb='liked',
            target_content_type=content_type,
            target_object_id=sample.id,
            unread=True
        ).first()
        
        if existing_notification:
            # Update existing notification with aggregated count
            like_count = sample.favorite_count
            other_likers = sample.favorited_by.exclude(id=request.user.id)
            
            if other_likers.count() == 0:
                # Only this user liked it
                description = f"{request.user.username} liked your sample"
            elif other_likers.count() == 1:
                # Two people total
                other_user = other_likers.first()
                description = f"{request.user.username} and {other_user.username} liked your sample"
            else:
                # Multiple people
                count = other_likers.count()
                description = f"{request.user.username} and {count} others liked your sample"
            
            existing_notification.description = description
            existing_notification.actor = request.user  # Update to most recent liker
            existing_notification.data = {'sha256': sample.sha256[:12]}
            existing_notification.timestamp = timezone.now()
            existing_notification.save()
        else:
            # Create new notification
            Notification.objects.create(
                recipient=sample.author,
                actor=request.user,
                verb='liked',
                target=sample,
                description=f"{request.user.username} liked your sample",
                data={'sha256': sample.sha256[:12]}
            )
    
    # Return JSON response for AJAX
    return JsonResponse({
        'liked': user_has_favorited,
        'like_count': sample.favorite_count
    })


def toggle_solution_like(request, solution_id):
    """Toggle like for a solution (requires authentication)"""
    TITLE_MAX_LENGTH = 60
    
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Login required',
            'redirect': '/accounts/login/'
        }, status=401)
    
    solution = get_object_or_404(Solution, id=solution_id)
    
    # Skip self-notifications
    if request.user == solution.author:
        if solution.liked_by.filter(id=request.user.id).exists():
            solution.liked_by.remove(request.user)
            user_has_liked = False
        else:
            solution.liked_by.add(request.user)
            user_has_liked = True
        
        return JsonResponse({
            'liked': user_has_liked,
            'like_count': solution.like_count
        })
    
    if solution.liked_by.filter(id=request.user.id).exists():
        # Remove from likes - DELETE notification
        solution.liked_by.remove(request.user)
        user_has_liked = False
        
        # Delete all like notifications for this solution
        content_type = ContentType.objects.get_for_model(Solution)
        Notification.objects.filter(
            recipient=solution.author,
            verb='liked_solution',
            target_content_type=content_type,
            target_object_id=solution.id
        ).delete()
        
    else:
        # Add to likes - CREATE/UPDATE notification
        solution.liked_by.add(request.user)
        user_has_liked = True
        
        # Check if there's already a like notification for this solution
        content_type = ContentType.objects.get_for_model(Solution)
        existing_notification = Notification.objects.filter(
            recipient=solution.author,
            verb='liked_solution',
            target_content_type=content_type,
            target_object_id=solution.id,
            unread=True
        ).first()
        
        if existing_notification:
            # Update existing notification with aggregated count
            like_count = solution.like_count
            other_likers = solution.liked_by.exclude(id=request.user.id)
            
            if other_likers.count() == 0:
                # Only this user liked it
                title = solution.title[:TITLE_MAX_LENGTH] + '...' if len(solution.title) > TITLE_MAX_LENGTH else solution.title
                description = f"{request.user.username} liked your solution '{title}'"
            elif other_likers.count() == 1:
                # Two people total
                other_user = other_likers.first()
                title = solution.title[:TITLE_MAX_LENGTH] + '...' if len(solution.title) > TITLE_MAX_LENGTH else solution.title
                description = f"{request.user.username} and {other_user.username} liked your solution '{title}'"
            else:
                # Multiple people
                count = other_likers.count()
                title = solution.title[:TITLE_MAX_LENGTH] + '...' if len(solution.title) > TITLE_MAX_LENGTH else solution.title
                description = f"{request.user.username} and {count} others liked your solution '{title}'"
            
            existing_notification.description = description
            existing_notification.actor = request.user  # Update to most recent liker
            existing_notification.data = {'solution_title': solution.title[:TITLE_MAX_LENGTH]}
            existing_notification.timestamp = timezone.now()
            existing_notification.save()
        else:
            # Create new notification
            title = solution.title[:TITLE_MAX_LENGTH] + '...' if len(solution.title) > TITLE_MAX_LENGTH else solution.title
            Notification.objects.create(
                recipient=solution.author,
                actor=request.user,
                verb='liked_solution',
                target=solution,
                description=f"{request.user.username} liked your solution '{title}'",
                data={'solution_title': solution.title[:TITLE_MAX_LENGTH]}
            )
    
    # Return JSON response for AJAX
    return JsonResponse({
        'liked': user_has_liked,
        'like_count': solution.like_count
    })
