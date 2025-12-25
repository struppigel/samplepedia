"""
Django signals for the samples app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Sample
from .discord_utils import send_sample_notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Sample)
def notify_discord_on_new_sample(sender, instance, created, **kwargs):
    """
    Send a Discord notification when a new sample is created.
    
    Args:
        sender: The Sample model class
        instance: The actual Sample instance being saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    if created and instance.send_discord_notification:
        logger.info(f"New sample created: {instance.sha256}, scheduling Discord notification")
        # Use on_commit to ensure m2m relationships (tags/tools) are saved before notification
        transaction.on_commit(lambda: _send_notification(instance))


def _send_notification(instance):
    """Helper function to send notification after transaction commits."""
    try:
        send_sample_notification(instance)
    except Exception as e:
        # Don't fail if Discord notification fails
        logger.error(f"Failed to send Discord notification for sample {instance.sha256}: {e}")
