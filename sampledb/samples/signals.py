"""
Django signals for the samples app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django_comments.signals import comment_was_posted
from .models import AnalysisTask, Notification
from .discord_utils import send_sample_notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AnalysisTask)
def notify_discord_on_new_sample(sender, instance, created, **kwargs):
    """
    Send a Discord notification when a new sample is created.
    
    Args:
        sender: The AnalysisTask model class
        instance: The actual AnalysisTask instance being saved
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


@receiver(comment_was_posted)
def notify_on_comment(sender, comment, request, **kwargs):
    """
    Send a notification when a comment is posted on an analysis task.
    Notifies the task author (unless they commented on their own task).
    
    Args:
        sender: The comment model class
        comment: The comment instance that was posted
        request: The HTTP request object
        **kwargs: Additional keyword arguments
    """
    # Get the object that was commented on
    content_object = comment.content_object
    
    # Only process comments on AnalysisTask objects
    if not isinstance(content_object, AnalysisTask):
        return
    
    # Don't notify if user comments on their own task
    if comment.user == content_object.author:
        return
    
    # Check if user is authenticated
    if not comment.user:
        return
    
    # Create notification
    Notification.objects.create(
        recipient=content_object.author,
        actor=comment.user,
        verb='commented',
        target=content_object,
        description=f"{comment.user.username} commented on your sample",
        data={'sha256': content_object.sha256[:12]}
    )
    
    logger.info(f"Comment notification sent to {content_object.author.username} for sample {content_object.sha256}")
