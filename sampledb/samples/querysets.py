"""
Query rules shared by views and template tags: who may see hidden solutions,
reference-solution bookkeeping, and the annotations list pages render, so a
page costs a fixed number of queries instead of a few per row.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Case, CharField, Count, Exists, F, IntegerField, OuterRef, Q, QuerySet, Subquery, Value, When,
)
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone


def difficulty_order(field='difficulty'):
    """Sort key that orders difficulties as declared (easy first, expert last)."""
    from .models import Difficulty
    return Case(
        *[When(**{field: value}, then=Value(position)) for position, value in enumerate(Difficulty.values)],
        output_field=IntegerField(),
    )


def public_solution_q(prefix=''):
    """Solutions that were never hidden or whose hidden period is over."""
    return Q(**{f'{prefix}hidden_until__isnull': True}) | Q(**{f'{prefix}hidden_until__lte': timezone.now()})


class SolutionQuerySet(QuerySet):
    def publicly_visible(self):
        return self.filter(public_solution_q())

    def visible_to(self, user):
        """Hidden solutions are shown only to staff, their author and the task author."""
        if not user.is_authenticated:
            return self.publicly_visible()
        if user.is_staff:
            return self
        return self.filter(public_solution_q() | Q(author=user) | Q(analysis_task__author=user))

    def reference(self):
        """Reference solutions: written by the task's own author."""
        return self.filter(author=F('analysis_task__author'))

    def with_reference_count(self):
        """Annotate reference_count: the task's reference solutions, hidden ones included."""
        from .models import Solution
        references = (
            Solution.objects
            .filter(analysis_task=OuterRef('analysis_task'), author=OuterRef('analysis_task__author'))
            .order_by().values('analysis_task')
            .annotate(count=Count('pk')).values('count')
        )
        return self.annotate(reference_count=Coalesce(Subquery(references, output_field=IntegerField()), 0))

    def for_listing(self):
        """Related rows and like counts that solution lists render."""
        return self.select_related('analysis_task__author', 'author', 'article').annotate(
            like_count_annotated=Count('liked_by', distinct=True),
        )


class AnalysisTaskQuerySet(QuerySet):
    def for_listing(self):
        """
        Favorite, public-solution and comment counts plus one has_<type>_solution
        flag per solution type, for task lists and their sorting.
        """
        from django_comments.models import Comment
        from .models import Solution, SolutionType

        comments = (
            Comment.objects
            .filter(
                content_type=ContentType.objects.get_for_model(self.model),
                object_pk=Cast(OuterRef('pk'), output_field=CharField()),
                is_public=True,
                is_removed=False,
            )
            .order_by().values('object_pk')
            .annotate(count=Count('pk')).values('count')
        )
        type_flags = {
            f'has_{solution_type}_solution': Exists(
                Solution.objects.publicly_visible().filter(analysis_task=OuterRef('pk'), solution_type=solution_type)
            )
            for solution_type in SolutionType.values
        }
        return self.select_related('author').annotate(
            # distinct: the two joins would otherwise multiply each other's counts
            favorite_count_annotated=Count('favorited_by', distinct=True),
            solution_count_annotated=Count('solutions', filter=public_solution_q('solutions__'), distinct=True),
            comment_count_annotated=Coalesce(Subquery(comments, output_field=IntegerField()), 0),
            **type_flags,
        )
