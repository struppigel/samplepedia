import re

from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse

from ..constants import NOTIFICATIONS_PER_PAGE
from ..models import Notification, NotificationVerb

DROPDOWN_SIZE = 5


@login_required
def notification_list(request):
    """Display the logged-in user's notifications, newest first"""
    notifications = Notification.objects.filter(recipient=request.user).select_related('actor')
    page_obj = Paginator(notifications, NOTIFICATIONS_PER_PAGE).get_page(request.GET.get('page'))

    return render(request, 'samples/notifications.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
    })


@login_required
def notification_dropdown(request):
    """AJAX endpoint to fetch recent notifications for dropdown"""
    unread = Notification.objects.filter(recipient=request.user).unread()

    notifications_data = []
    for n in unread[:DROPDOWN_SIZE]:
        url = n.target.get_absolute_url() if n.target else '#'

        # The dropdown is narrow: drop the quoted solution title from the description
        description = n.description
        if n.verb == NotificationVerb.LIKED_SOLUTION:
            description = re.sub(r" '[^']*'", "", description)

        notifications_data.append({
            'id': n.id,
            'verb': n.verb,
            'icon': n.icon,
            'description': description,
            'timestamp': n.timestamp.isoformat(),
            'url': url,
            'read_url': reverse('mark_notification_read', args=[n.id]),
            'sha256': n.data.get('sha256', '') if n.data else '',
        })

    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': unread.count(),
    })


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read and go to what it is about"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )

    notification.mark_as_read()

    if notification.target:
        return redirect(notification.target.get_absolute_url())
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
        'unread_count': Notification.objects.filter(recipient=request.user).unread().count()
    })
