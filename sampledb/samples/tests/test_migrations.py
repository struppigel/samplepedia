"""
Tests for data migrations. The migration functions are called directly with the
current app registry, which still has the fields they touch.
"""
import importlib

from django.apps import apps

from samples.models import Article, Solution, SolutionType
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_onsite_solution, make_solution, make_task

move_content = importlib.import_module('samples.migrations.0019_move_legacy_solution_content')


def legacy_onsite(task, content, title='Legacy'):
    """An on-site solution as the app stored them before Articles existed"""
    return Solution.objects.create(
        analysis_task=task, author=task.author, title=title,
        solution_type=SolutionType.ONSITE, content=content,
    )


class MoveLegacyContentTestCase(SampleTestCase):
    def run_migration(self):
        move_content.move_legacy_content_to_articles(apps, None)

    def test_onsite_without_article_gets_one(self):
        solution = legacy_onsite(make_task(), '# Old text')

        self.run_migration()

        solution.refresh_from_db()
        self.assertEqual(solution.article.content, '# Old text')
        self.assertEqual(solution.article.title, 'Legacy')
        self.assertEqual(solution.article.author, solution.author)
        self.assertEqual(solution.content, '')

    def test_onsite_without_article_or_text_gets_an_empty_article(self):
        solution = legacy_onsite(make_task(), '')

        self.run_migration()

        solution.refresh_from_db()
        self.assertIsNotNone(solution.article)

    def test_duplicate_of_article_text_is_dropped(self):
        solution = make_onsite_solution(content='Same text')
        Solution.objects.filter(pk=solution.pk).update(content='Same text\n')

        self.run_migration()

        solution.refresh_from_db()
        self.assertEqual(solution.content, '')
        self.assertEqual(Article.objects.count(), 1)

    def test_differing_text_is_recovered_as_a_draft(self):
        solution = make_onsite_solution(title='Writeup', content='Current text')
        Solution.objects.filter(pk=solution.pk).update(content='Older text')

        self.run_migration()

        draft = Article.objects.get(title='Writeup (recovered)')
        self.assertEqual(draft.content, 'Older text')
        self.assertEqual(draft.author, solution.author)
        self.assertFalse(draft.is_published())
        solution.refresh_from_db()
        self.assertEqual(solution.article.content, 'Current text')

    def test_text_on_external_solution_is_recovered(self):
        solution = make_solution(title='Blog post')
        Solution.objects.filter(pk=solution.pk).update(content='Notes')

        self.run_migration()

        self.assertTrue(Article.objects.filter(title='Blog post (recovered)', content='Notes').exists())

    def test_recovered_title_fits_the_column(self):
        self.assertEqual(len(move_content.recovered_title('x' * 200)), 200)

    def test_running_twice_changes_nothing(self):
        legacy_onsite(make_task(), 'Text')
        solution = make_onsite_solution(content='A')
        Solution.objects.filter(pk=solution.pk).update(content='B')

        self.run_migration()
        articles = Article.objects.count()
        self.run_migration()

        self.assertEqual(Article.objects.count(), articles)
        self.assertFalse(Solution.objects.exclude(content='').exists())
