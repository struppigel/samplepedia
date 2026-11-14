"""
Move text still stored in the deprecated Solution.content field into Articles,
so a later migration can drop the column without losing anything.

- An on-site solution without an Article gets one holding its text.
- Text that differs from the solution's Article (or sits on an external
  solution) is kept as an unpublished draft for the author, titled
  "<title> (recovered)".
- Afterwards Solution.content is empty everywhere. Running it again changes nothing.
"""
from django.db import migrations
from django.db.models import Q

RECOVERED_SUFFIX = ' (recovered)'
ARTICLE_TITLE_MAX_LENGTH = 200


def recovered_title(title):
    return title[:ARTICLE_TITLE_MAX_LENGTH - len(RECOVERED_SUFFIX)] + RECOVERED_SUFFIX


def move_legacy_content_to_articles(apps, schema_editor):
    Solution = apps.get_model('samples', 'Solution')
    Article = apps.get_model('samples', 'Article')

    needs_work = Solution.objects.filter(
        Q(content__gt='') | Q(solution_type='onsite', article__isnull=True)
    ).select_related('article')
    for solution in needs_work.iterator():
        content = solution.content or ''
        if solution.solution_type == 'onsite' and solution.article_id is None:
            solution.article = Article.objects.create(
                author_id=solution.author_id, title=solution.title, content=content,
            )
        elif content.strip() and (solution.article_id is None or content.strip() != solution.article.content.strip()):
            Article.objects.create(
                author_id=solution.author_id, title=recovered_title(solution.title), content=content,
            )
        solution.content = ''
        solution.save(update_fields=['content', 'article'])


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0018_remove_solution_idx_solution_view_count_and_more'),
    ]

    operations = [
        migrations.RunPython(move_legacy_content_to_articles, migrations.RunPython.noop),
    ]
