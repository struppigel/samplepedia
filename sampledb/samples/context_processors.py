from django.conf import settings


def impressum_settings(request):
    """Make impressum settings available in all templates."""
    return {
        'settings': {
            'IMPRESSUM_NAME': settings.IMPRESSUM_NAME,
            'IMPRESSUM_ADDRESS_LINE1': settings.IMPRESSUM_ADDRESS_LINE1,
            'IMPRESSUM_ADDRESS_LINE2': settings.IMPRESSUM_ADDRESS_LINE2,
            'IMPRESSUM_PHONE': settings.IMPRESSUM_PHONE,
            'IMPRESSUM_EMAIL': settings.IMPRESSUM_EMAIL,
        }
    }
