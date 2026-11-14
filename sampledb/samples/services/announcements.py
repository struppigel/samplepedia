"""
Discord announcements for solutions: exactly one per solution, when it becomes
publicly visible.

Visible solutions are announced right after they are created (signals.py).
Hidden ones wait until hidden_until has passed; manage.py announce_solutions,
run hourly by a Railway cron service, picks them up. Both paths go through
announce_solution, whose claim on discord_announced_at keeps them from posting
the same solution twice.
"""
from datetime import timedelta

from django.db.models.functions import Coalesce
from django.utils import timezone

from ..discord_utils import send_solution_notification
from ..models import Solution

# Solutions that became visible longer ago than this are no longer announced,
# so a stopped cron job or a long Discord outage doesn't end in a flood of old posts
DEFAULT_MAX_AGE = timedelta(days=7)


def announce_solution(solution):
    """Post the solution to Discord unless it was already announced. Returns whether it was posted."""
    claimed = Solution.objects.filter(pk=solution.pk, discord_announced_at__isnull=True).update(
        discord_announced_at=timezone.now(),
    )
    if not claimed:
        return False
    if send_solution_notification(solution):
        return True
    # Not posted (Discord down or no webhook): release the claim so the next run retries
    Solution.objects.filter(pk=solution.pk).update(discord_announced_at=None)
    return False


def due_solutions(now=None, max_age=DEFAULT_MAX_AGE):
    """Publicly visible solutions that still wait for their announcement, oldest first."""
    now = now or timezone.now()
    return (
        Solution.objects.publicly_visible()
        .filter(discord_announced_at__isnull=True)
        .alias(visible_since=Coalesce('hidden_until', 'created_at'))
        .filter(visible_since__gte=now - max_age)
        .select_related('analysis_task', 'author')
        .order_by('visible_since')
    )
