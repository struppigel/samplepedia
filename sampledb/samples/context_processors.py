from django.conf import settings
from .models import Notification


def impressum_settings(request):
    """Make impressum settings available in all templates."""
    return {
        'settings': {
            'IMPRESSUM_NAME': settings.IMPRESSUM_NAME,
            'IMPRESSUM_ADDRESS_LINE1': settings.IMPRESSUM_ADDRESS_LINE1,
            'IMPRESSUM_ADDRESS_LINE2': settings.IMPRESSUM_ADDRESS_LINE2,
            'IMPRESSUM_PHONE': settings.IMPRESSUM_PHONE,
            'IMPRESSUM_EMAIL': settings.IMPRESSUM_EMAIL,
            'DISCORD_INVITE_URL': settings.DISCORD_INVITE_URL,
        }
    }


def notification_count(request):
    """Make notification count available in all templates."""
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                recipient=request.user,
                unread=True
            ).count()
        }
    return {
        'unread_notifications_count': 0
    }
