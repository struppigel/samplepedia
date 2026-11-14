"""
User scores. Every like (favorite) a user's tasks and solutions receive is
worth DIFFICULTY_POINTS of the task's difficulty. Scores, like breakdowns and
counts are computed as annotations in one query, so the ranking and profile
pages don't loop over users, tasks and solutions.
"""
from django.contrib.auth.models import User
from django.db.models import Count, ExpressionWrapper, F, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from .models import DIFFICULTY_POINTS, AnalysisTask, Difficulty, Solution

TaskFavorite = AnalysisTask.favorited_by.through
SolutionLike = Solution.liked_by.through


def _count_per_user(queryset, user_field):
    """Correlated COUNT of `queryset` rows whose `user_field` is the outer user."""
    counts = (
        queryset.filter(**{user_field: OuterRef('pk')})
        .order_by().values(user_field)
        .annotate(count=Count('pk')).values('count')
    )
    return Coalesce(Subquery(counts, output_field=IntegerField()), 0)


def like_fields():
    """Names of the per-difficulty like annotations, e.g. task_likes_easy."""
    return [f'{kind}_likes_{difficulty}' for kind in ('task', 'solution') for difficulty in Difficulty.values]


def annotate_scores(users):
    """
    Annotate users with task_likes_<difficulty>, solution_likes_<difficulty>,
    score, task_count and solution_count.
    """
    likes = {}
    for difficulty in Difficulty.values:
        likes[f'task_likes_{difficulty}'] = _count_per_user(
            TaskFavorite.objects.filter(analysistask__difficulty=difficulty), 'analysistask__author',
        )
        likes[f'solution_likes_{difficulty}'] = _count_per_user(
            SolutionLike.objects.filter(solution__analysis_task__difficulty=difficulty), 'solution__author',
        )
    score = sum(
        (F(f'task_likes_{difficulty}') + F(f'solution_likes_{difficulty}')) * DIFFICULTY_POINTS[difficulty]
        for difficulty in Difficulty.values
    )
    return users.annotate(**likes).annotate(
        score=ExpressionWrapper(score, output_field=IntegerField()),
        task_count=_count_per_user(AnalysisTask.objects.all(), 'author'),
        solution_count=_count_per_user(Solution.objects.all(), 'author'),
    )


def ranked_users():
    """Users with a positive score, best first; ties go to the earlier account."""
    return annotate_scores(User.objects.all()).filter(score__gt=0).order_by('-score', 'pk')


def scored_user(user):
    """The user annotated by annotate_scores()."""
    return annotate_scores(User.objects.filter(pk=user.pk)).get()


def rank_of(scored):
    """1-based position of an annotated user in ranked_users(), or None without a score."""
    if scored.score <= 0:
        return None
    ahead = Q(score__gt=scored.score) | Q(score=scored.score, pk__lt=scored.pk)
    return ranked_users().filter(ahead).count() + 1
