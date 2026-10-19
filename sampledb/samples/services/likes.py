"""
Liking tasks (favorites) and solutions.

The owner keeps one unread, aggregated notification per liked object
("alice and 2 others liked your sample"). Unliking updates it rather than
deleting it, so the other likers stay in it; it disappears once nobody
else likes the object anymore.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..models import AnalysisTask, Notification, NotificationVerb

TITLE_MAX_LENGTH = 60


def _truncate(title):
    return title[:TITLE_MAX_LENGTH] + '...' if len(title) > TITLE_MAX_LENGTH else title


def _like_details(target):
    """(likers relation, notification verb, what was liked, notification data)"""
    if isinstance(target, AnalysisTask):
        return target.favorited_by, NotificationVerb.LIKED_TASK, 'your sample', {'sha256': target.sha256[:12]}
    return (
        target.liked_by,
        NotificationVerb.LIKED_SOLUTION,
        f"your solution '{_truncate(target.title)}'",
        {'solution_title': target.title[:TITLE_MAX_LENGTH]},
    )


def toggle_like(target, user):
    """Like or unlike an AnalysisTask or Solution. Returns (liked, like_count)."""
    likers, *_ = _like_details(target)
    liked = not likers.filter(pk=user.pk).exists()
    if liked:
        likers.add(user)
    else:
        likers.remove(user)
    if user != target.author:
        _sync_like_notification(target, latest_liker=user if liked else None)
    return liked, likers.count()


def _sync_like_notification(target, latest_liker):
    likers, verb, subject, data = _like_details(target)
    # Through-table ids grow with each like, so the newest liker comes first
    through = likers.through
    others = list(
        through.objects
        .filter(**{target._meta.model_name: target})
        .exclude(user=target.author)
        .order_by('-id')
        .values_list('user__username', 'user_id')
    )
    notifications = Notification.objects.filter(
        recipient=target.author,
        verb=verb,
        target_content_type=ContentType.objects.get_for_model(target),
        target_object_id=target.pk,
    )
    existing = notifications.unread().first()

    if not others:
        notifications.unread().delete()
        return
    if latest_liker is None and existing is None:
        return  # an unlike doesn't create a notification

    (actor_name, actor_id), rest = others[0], others[1:]
    if not rest:
        description = f"{actor_name} liked {subject}"
    elif len(rest) == 1:
        description = f"{actor_name} and {rest[0][0]} liked {subject}"
    else:
        description = f"{actor_name} and {len(rest)} others liked {subject}"

    if existing is None:
        Notification.objects.create(
            recipient=target.author, actor_id=actor_id, verb=verb, target=target,
            description=description, data=data,
        )
        return
    existing.actor_id = actor_id
    existing.description = description
    existing.data = data
    if latest_liker is not None:
        existing.timestamp = timezone.now()
    existing.save()
