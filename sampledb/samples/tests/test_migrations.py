"""
Tests for data migrations, run with the real migration machinery: migrate back
to the state before the migration, create rows with the historical models,
migrate forward and check the result.
"""
import importlib

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

move_content = importlib.import_module('samples.migrations.0019_move_legacy_solution_content')

BEFORE = [('samples', '0018_remove_solution_idx_solution_view_count_and_more')]
AFTER = [('samples', '0019_move_legacy_solution_content')]


def migrate(targets):
    """Migrate to `targets` and return the historical apps at that state."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class MoveLegacyContentMigrationTestCase(TransactionTestCase):
    """0019 moves Solution.content into Articles before 0021 drops the column."""

    def setUp(self):
        self.latest = MigrationExecutor(connection).loader.graph.leaf_nodes('samples')
        self.addCleanup(migrate, self.latest)
        apps = migrate(BEFORE)
        User = apps.get_model('auth', 'User')
        Task = apps.get_model('samples', 'AnalysisTask')
        Solution = apps.get_model('samples', 'Solution')
        Article = apps.get_model('samples', 'Article')

        self.author = User.objects.create(username='author')
        task = Task.objects.create(sha256='a' * 64, goal='g', author=self.author)

        def solution(title, solution_type='onsite', content='', article=None):
            return Solution.objects.create(
                analysis_task=task, title=title, solution_type=solution_type,
                content=content, article=article, author=self.author,
            ).pk

        def article(title, content):
            return Article.objects.create(title=title, content=content, author=self.author)

        self.ids = {
            'legacy': solution('Legacy', content='# Old text'),
            'empty': solution('Empty'),
            'duplicate': solution('Same', content='Same text\n', article=article('Same', 'Same text')),
            'differs': solution('Writeup', content='Older text', article=article('Writeup', 'Current text')),
            'external': solution('Blog post', solution_type='blog', content='Notes'),
        }

    def test_legacy_content_moves_into_articles(self):
        apps = migrate(AFTER)
        Solution = apps.get_model('samples', 'Solution')
        Article = apps.get_model('samples', 'Article')
        solution = {name: Solution.objects.select_related('article').get(pk=pk) for name, pk in self.ids.items()}

        self.assertFalse(Solution.objects.exclude(content='').exists())
        # An on-site solution without an Article gets one holding its text, owned by its author
        self.assertEqual(solution['legacy'].article.content, '# Old text')
        self.assertEqual(solution['legacy'].article.title, 'Legacy')
        self.assertEqual(solution['legacy'].article.author_id, self.author.pk)
        # ... even when there was no text
        self.assertIsNotNone(solution['empty'].article)
        # Text that only repeats the Article is dropped
        self.assertFalse(Article.objects.filter(title='Same (recovered)').exists())
        # Text that differs, or sits on an external solution, is kept as an unpublished draft
        recovered = Article.objects.get(title='Writeup (recovered)')
        self.assertEqual(recovered.content, 'Older text')
        self.assertFalse(Solution.objects.filter(article=recovered).exists())
        self.assertEqual(solution['differs'].article.content, 'Current text')
        self.assertTrue(Article.objects.filter(title='Blog post (recovered)', content='Notes').exists())

        # Running it again changes nothing
        count = Article.objects.count()
        move_content.move_legacy_content_to_articles(apps, None)
        self.assertEqual(Article.objects.count(), count)


class RecoveredTitleTestCase(SimpleTestCase):
    def test_fits_the_article_title_column(self):
        self.assertEqual(len(move_content.recovered_title('x' * 200)), 200)
        self.assertEqual(move_content.recovered_title('Short'), 'Short (recovered)')
