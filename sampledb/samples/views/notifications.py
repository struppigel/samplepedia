from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Notification


@login_required
def notification_list(request):
    """Display all notifications for the logged-in user"""
    notifications = Notification.objects.filter(recipient=request.user)
    
    return render(request, 'samples/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notification_dropdown(request):
    """AJAX endpoint to fetch recent notifications for dropdown"""
    notifications = Notification.objects.filter(
        recipient=request.user,
        unread=True
    )[:5]
    
    notifications_data = []
    for n in notifications:
        # Determine URL based on target type
        url = '#'
        if n.target:
            if hasattr(n.target, 'get_absolute_url'):
                url = n.target.get_absolute_url()
            elif n.verb == 'liked_solution' and hasattr(n.target, 'analysis_task'):
                # For solution notifications, link to the sample detail page
                url = n.target.analysis_task.get_absolute_url()
        
        # For solution like notifications, remove the title from description for dropdown
        description = n.description
        if n.verb == 'liked_solution' and "'" in description:
            # Strip everything between quotes to remove the title
            # e.g., "user liked your solution 'Title'" -> "user liked your solution"
            import re
            description = re.sub(r" '[^']*'", "", description)
        
        notifications_data.append({
            'id': n.id,
            'verb': n.verb,
            'description': description,
            'timestamp': n.timestamp.isoformat(),
            'url': url,
            'sha256': n.data.get('sha256', '') if n.data else '',
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': Notification.objects.filter(recipient=request.user, unread=True).count()
    })


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read and redirect to target"""
    notification = get_object_or_404(
        Notification, 
        id=notification_id, 
        recipient=request.user
    )
    
    notification.mark_as_read()
    
    # Redirect to the appropriate page based on target type
    if notification.target:
        if hasattr(notification.target, 'get_absolute_url'):
            return redirect(notification.target.get_absolute_url())
        elif notification.verb == 'liked_solution' and hasattr(notification.target, 'analysis_task'):
            # For solution notifications, redirect to the sample detail page with solution ID
            url = notification.target.analysis_task.get_absolute_url()
            return redirect(f"{url}?highlight_solution={notification.target.id}")
    
    return redirect('notification_list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user).mark_all_as_read()
    return redirect('notification_list')


@login_required
def delete_notification(request, notification_id):
    """Delete a notification"""
    if request.method == 'POST':
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            recipient=request.user
        )
        notification.delete()
    
    return redirect('notification_list')


@login_required
def unread_count(request):
    """AJAX endpoint for polling unread notification count"""
    return JsonResponse({
        'unread_count': Notification.objects.filter(recipient=request.user, unread=True).count()
    })
