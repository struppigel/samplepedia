"""
Django signals for the samples app.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django_comments.signals import comment_was_posted
from .models import AnalysisTask, Solution, Notification, NotificationVerb
from .discord_utils import send_in_background, send_sample_notification
from .services.announcements import announce_solution
import logging
import re

logger = logging.getLogger(__name__)

# @username, but not the domain part of an e-mail address
MENTION_RE = re.compile(r'(?<![\w.@])@(\w+)')


@receiver(pre_delete, sender='auth.User')
def clear_user_email_from_comments(sender, instance, **kwargs):
    """
    Clear user email from comments when a user is deleted (GDPR compliance).
    This signal is triggered before user deletion to preserve privacy.
    
    Args:
        sender: The User model class
        instance: The User instance being deleted
        **kwargs: Additional keyword arguments
    """
    from django_comments.models import Comment
    
    # Clear email from all comments by this user
    comments_updated = Comment.objects.filter(user=instance).update(user_email='')
    
    if comments_updated > 0:
        logger.info(f"Cleared email from {comments_updated} comment(s) for user {instance.username}")


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
        # on_commit: the tags and tools are saved by then
        transaction.on_commit(lambda: send_in_background(send_sample_notification, instance))


@receiver(comment_was_posted)
def notify_on_comment(sender, comment, request, **kwargs):
    """
    Notify everyone involved in a task's discussion: @mentioned users, the task
    author, solution authors and earlier commenters. Each gets one notification,
    and the commenter gets none.
    """
    task = comment.content_object
    if not isinstance(task, AnalysisTask) or not comment.user:
        return

    # Import here to avoid circular imports
    from django.contrib.auth.models import User
    from django_comments.models import Comment

    mentioned_ids = set(
        User.objects.filter(username__in=MENTION_RE.findall(comment.comment)).values_list('id', flat=True)
    )
    involved_ids = {task.author_id}
    involved_ids |= set(task.solutions.values_list('author_id', flat=True))
    involved_ids |= set(
        Comment.objects.filter(content_type=comment.content_type, object_pk=comment.object_pk)
        .exclude(pk=comment.pk)
        .values_list('user_id', flat=True)
    )
    recipient_ids = (mentioned_ids | involved_ids) - {None, comment.user_id}

    notifications = []
    for recipient_id in recipient_ids:
        mentioned = recipient_id in mentioned_ids
        notifications.append(Notification(
            recipient_id=recipient_id,
            actor=comment.user,
            verb=NotificationVerb.MENTIONED if mentioned else NotificationVerb.COMMENTED,
            target=task,
            description=f"{comment.user.username} {'mentioned you' if mentioned else 'commented'}",
            data={'sha256': task.sha256[:12]},
        ))
    Notification.objects.bulk_create(notifications)
    logger.info(f"Comment notifications sent to {len(notifications)} user(s) for sample {task.sha256}")


@receiver(post_save, sender=Solution)
def notify_on_solution(sender, instance, created, **kwargs):
    """
    Send a notification when a solution is submitted to an analysis task.
    Notifies the task author (unless they submitted the solution themselves).
    Also sends Discord notification for all new solutions.
    
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
    
    # Announce new solutions on Discord (after transaction commits). Hidden ones wait:
    # the embed links the solution directly, which would defeat the hiding, so
    # manage.py announce_solutions announces them once hidden_until has passed.
    if not instance.is_hidden:
        transaction.on_commit(lambda: send_in_background(announce_solution, instance))
    
    # Send in-app notification to task author (only if different from solution author)
    if task.author and task.author != instance.author:
        # Create notification for the task author
        Notification.objects.create(
            recipient=task.author,
            actor=instance.author,
            verb=NotificationVerb.SUBMITTED_SOLUTION,
            target=task,
            action_object=instance,
            description=f"{instance.author.username} added a solution",
            data={'sha256': task.sha256[:12], 'solution_title': instance.title}
        )
        
        logger.info(f"Solution notification sent to {task.author.username} for sample {task.sha256}")
