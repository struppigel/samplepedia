"""
Django signals for the samples app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django_comments.signals import comment_was_posted
from .models import AnalysisTask, Solution, Notification
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
    Notifies the task author, solution authors, and previous commenters (unless they posted this comment).
    Avoids duplicate notifications.
    
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
    
    # Check if user is authenticated
    if not comment.user:
        return
    
    # Import here to avoid circular imports
    from django.contrib.auth.models import User
    from django_comments.models import Comment
    
    # Collect all users to notify (avoiding duplicates)
    recipients = set()
    
    # Add task author
    if content_object.author and content_object.author != comment.user:
        recipients.add(content_object.author)
    
    # Add solution authors for this task
    solution_authors = content_object.solutions.values_list('author', flat=True).distinct()
    for author_id in solution_authors:
        if author_id and author_id != comment.user.id:
            try:
                author = User.objects.get(id=author_id)
                recipients.add(author)
            except User.DoesNotExist:
                continue
    
    # Add previous commenters on this task
    previous_comments = Comment.objects.filter(
        content_type=comment.content_type,
        object_pk=comment.object_pk
    ).exclude(id=comment.id).values_list('user_id', flat=True).distinct()
    
    for user_id in previous_comments:
        if user_id and user_id != comment.user.id:
            try:
                user = User.objects.get(id=user_id)
                recipients.add(user)
            except User.DoesNotExist:
                continue
    
    # Create notifications for all recipients
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            actor=comment.user,
            verb='commented',
            target=content_object,
            description=f"{comment.user.username} commented",
            data={'sha256': content_object.sha256[:12]}
        )
        logger.info(f"Comment notification sent to {recipient.username} for sample {content_object.sha256}")


@receiver(post_save, sender=Solution)
def notify_on_solution(sender, instance, created, **kwargs):
    """
    Send a notification when a solution is submitted to an analysis task.
    Notifies the task author (unless they submitted the solution themselves).
    
    Args:
        sender: The Solution model class
        instance: The Solution instance that was saved
        created: Boolean; True if a new record was created
        **kwargs: Additional keyword arguments
    """
    # Only notify on new solution creation, not updates
    if not created:
        return
    
    # Get the analysis task
    task = instance.analysis_task
    
    # Don't notify if the solution author is the same as the task author
    if not task.author or task.author == instance.author:
        return
    
    # Create notification for the task author
    Notification.objects.create(
        recipient=task.author,
        actor=instance.author,
        verb='submitted a solution',
        target=task,
        action_object=instance,
        description=f"{instance.author.username} added a solution",
        data={'sha256': task.sha256[:12], 'solution_title': instance.title}
    )
    
    logger.info(f"Solution notification sent to {task.author.username} for sample {task.sha256}")
