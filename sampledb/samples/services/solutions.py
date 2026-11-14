"""
Creating and editing solutions.

Every view that adds a solution goes through create_solution(), so on-site
solutions always get an Article and titles stay unique per task. Errors are
raised as ValidationError for the caller to show on its form or response.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Article, Solution, SolutionType


def hidden_until_from_weeks(weeks, now=None):
    """End of a 'hide for N weeks' period, or None when the solution isn't hidden."""
    if not weeks:
        return None
    return (now or timezone.now()) + timedelta(weeks=int(weeks))


def _check_title_free(task, title, exclude_pk=None):
    if Solution.title_taken(task, title, exclude_pk=exclude_pk):
        raise ValidationError({'title': f'This task already has a solution titled "{title}".'})


def _check_publishable(article, author):
    if article.author_id != author.id:
        raise ValidationError('You can only publish your own drafts.')
    if article.is_published():
        raise ValidationError('This article is already published.')


@transaction.atomic
def create_solution(*, task, author, solution_type, title='', url='', content='', article=None,
                    hidden_until=None):
    """
    Add a solution to a task.

    On-site solutions are backed by an Article: pass a draft `article` to
    publish it (the solution takes its title), or `content` to write a new one.
    External solutions (blog, paper, video) need a `url`.
    """
    if article is not None:
        solution_type = SolutionType.ONSITE
        _check_publishable(article, author)
        title = article.title
    _check_title_free(task, title)

    if solution_type == SolutionType.ONSITE:
        if article is None:
            article = Article.objects.create(author=author, title=title, content=content)
        url = None
    return Solution.objects.create(
        analysis_task=task,
        author=author,
        title=title,
        solution_type=solution_type,
        url=url,
        article=article,
        hidden_until=hidden_until,
    )


def publish_draft(*, article, task, author, hidden_until=None):
    """Publish a draft article as an on-site solution of `task`."""
    return create_solution(
        task=task, author=author, solution_type=SolutionType.ONSITE, article=article, hidden_until=hidden_until,
    )


@transaction.atomic
def update_onsite_solution(solution, *, title, content):
    """
    Change an on-site solution's title and text. The article keeps its author,
    so a staff member editing it doesn't take it over.
    """
    _check_title_free(solution.analysis_task, title, exclude_pk=solution.pk)
    article = solution.article
    article.title = title
    article.content = content
    article.save()
    solution.title = title
    solution.save(update_fields=['title'])
    return solution
