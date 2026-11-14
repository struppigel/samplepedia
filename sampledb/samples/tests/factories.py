"""
Test data factories.

Each helper saves a valid object with sensible defaults; pass keyword arguments
to override any model field. Related objects are created on demand, so
make_solution() alone yields a user, a task and a solution.
"""
import itertools

from django.contrib.auth.models import User

from samples.models import AnalysisTask, Article, Difficulty, Solution, SolutionType

PASSWORD = 'testpass123'

_sequence = itertools.count(1)


def make_user(username=None, *, password=PASSWORD, email=None, **fields):
    username = username or f'user{next(_sequence)}'
    if email is None:
        email = f'{username}@example.com'
    return User.objects.create_user(username=username, password=password, email=email, **fields)


def make_staff(username=None, **fields):
    return make_user(username, is_staff=True, **fields)


def make_task(*, author=None, sha256=None, goal='Analyze the sample', difficulty=Difficulty.EASY,
              send_discord_notification=False, **fields):
    """A task with a unique valid SHA256. Discord announcements are off unless asked for."""
    return AnalysisTask.objects.create(
        sha256=sha256 or f'{next(_sequence):064x}',
        goal=goal,
        difficulty=difficulty,
        author=author or make_user(),
        send_discord_notification=send_discord_notification,
        **fields,
    )


def make_article(*, author=None, title=None, content='Article content', **fields):
    """A draft article (not attached to a solution)."""
    return Article.objects.create(
        author=author or make_user(),
        title=title or f'Article {next(_sequence)}',
        content=content,
        **fields,
    )


def make_solution(*, task=None, author=None, title=None, solution_type=SolutionType.BLOG,
                  url='https://example.com/solution', **fields):
    """An external solution. The author defaults to the task author (a reference solution)."""
    task = task or make_task()
    return Solution.objects.create(
        analysis_task=task,
        author=author or task.author,
        title=title or f'Solution {next(_sequence)}',
        solution_type=solution_type,
        url=url,
        **fields,
    )


def make_onsite_solution(*, task=None, author=None, title=None, content='Solution content', **fields):
    """An onsite solution backed by an Article, like the views create them."""
    task = task or make_task()
    author = author or task.author
    title = title or f'Onsite solution {next(_sequence)}'
    article = make_article(author=author, title=title, content=content)
    return Solution.objects.create(
        analysis_task=task,
        author=author,
        title=title,
        solution_type=SolutionType.ONSITE,
        article=article,
        url='',
        **fields,
    )
