from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from notifications.models import Notification


@login_required
def notification_list(request):
    """Display all notifications for the logged-in user"""
    notifications = request.user.notifications.all()
    
    return render(request, 'samples/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notification_dropdown(request):
    """AJAX endpoint to fetch recent notifications for dropdown"""
    notifications = request.user.notifications.unread()[:5]
    
    notifications_data = [{
        'id': n.id,
        'description': n.description,
        'timestamp': n.timestamp.isoformat(),
        'url': n.data.get('url', '#') if n.data else '#',
        'sha256': n.data.get('sha256', '') if n.data else '',
    } for n in notifications]
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': request.user.notifications.unread().count()
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
    
    # Redirect to the task detail page
    if notification.action_object:
        return redirect(notification.action_object.get_absolute_url())
    
    return redirect('notification_list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        request.user.notifications.mark_all_as_read()
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
        'unread_count': request.user.notifications.unread().count()
    })
