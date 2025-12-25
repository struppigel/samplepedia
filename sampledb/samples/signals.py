"""
Django signals for the samples app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
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
    if created:
        logger.info(f"New sample created: {instance.sha256}, sending Discord notification")
        try:
            send_sample_notification(instance)
        except Exception as e:
            # Don't fail the save operation if Discord notification fails
            logger.error(f"Failed to send Discord notification for sample {instance.sha256}: {e}")
