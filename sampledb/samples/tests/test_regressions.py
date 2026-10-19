"""
Regression tests for bugs found in the 2026-10 review: duplicate solution
titles, hidden-solution leaks, the article delete button and editor
re-renders that dropped the user's input.
"""
from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from samples.models import Article, Solution, SolutionType
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_article, make_onsite_solution, make_solution, make_staff, make_task


class RegressionTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task = make_task()
        cls.author = cls.task.author
        cls.staff = make_staff()
        cls.existing = make_solution(task=cls.task, title='Taken')

    def setUp(self):
        self.login_as(self.author)

    def task_url(self, name, **kwargs):
        return reverse(name, kwargs={'sha256': self.task.sha256, 'task_id': self.task.id, **kwargs})


class DuplicateSolutionTitleTestCase(RegressionTestCase):
    """unique_together(title, analysis_task) used to surface as a 500."""

    def test_create_external_solution(self):
        response = self.client.post(self.task_url('create_solution'), {
            'title': 'Taken', 'solution_type': SolutionType.BLOG, 'url': 'https://example.org/',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already has a solution titled')
        self.assertEqual(Solution.objects.count(), 1)

    def test_create_onsite_solution(self):
        response = self.client.post(self.task_url('create_solution'), {
            'title': 'Taken', 'solution_type': SolutionType.ONSITE, 'content': 'text',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Solution.objects.count(), 1)

    def test_create_from_draft_with_taken_title(self):
        draft = make_article(title='Taken', author=self.author)
        response = self.client.post(self.task_url('create_solution'), {
            'solution_type': SolutionType.ONSITE, 'draft_article_id': draft.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Solution.objects.count(), 1)

    def test_edit_into_taken_title(self):
        other = make_solution(task=self.task, title='Other')
        response = self.client.post(self.task_url('edit_solution', solution_id=other.id), {
            'title': 'Taken', 'solution_type': SolutionType.BLOG, 'url': 'https://example.org/',
        })
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        self.assertEqual(other.title, 'Other')

    def test_edit_keeping_own_title(self):
        response = self.client.post(self.task_url('edit_solution', solution_id=self.existing.id), {
            'title': 'Taken', 'solution_type': SolutionType.BLOG, 'url': 'https://example.net/',
        })
        self.assertEqual(response.status_code, 302)

    def test_onsite_editor(self):
        response = self.client.post(self.task_url('onsite_solution_editor'), {'title': 'Taken', 'content': 'text'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Solution.objects.count(), 1)

    def test_publish_article(self):
        draft = make_article(title='Taken', author=self.author)
        response = self.client.post(reverse('publish_article', args=[draft.id]), {'sample_id': self.task.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('already has a solution titled', response.json()['error'])

    def test_attach_draft(self):
        draft = make_article(title='Taken', author=self.author)
        response = self.client.post(self.task_url('attach_draft_to_sample'), {'article_id': draft.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Solution.objects.count(), 1)


class HiddenSolutionTestCase(RegressionTestCase):
    def create_hidden_onsite(self):
        return make_onsite_solution(task=self.task, hidden_until=timezone.now() + timedelta(weeks=2))

    def test_blocked_view_does_not_count(self):
        solution = self.create_hidden_onsite()
        self.client.logout()
        response = self.client.get(self.task_url('view_onsite_solution', solution_id=solution.id))
        self.assertEqual(response.status_code, 302)
        solution.article.refresh_from_db()
        self.assertEqual(solution.article.view_count, 0)

    @mock.patch('samples.signals.send_solution_notification')
    def test_hidden_solution_is_not_announced(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            self.create_hidden_onsite()
        send.assert_not_called()

    @mock.patch('samples.signals.send_solution_notification')
    def test_visible_solution_is_announced(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            make_solution(task=self.task)
        send.assert_called_once()


class EditorReRenderTestCase(RegressionTestCase):
    """Validation errors must not empty the editor."""

    def test_onsite_editor_keeps_title(self):
        response = self.client.post(self.task_url('onsite_solution_editor'), {'title': 'My unsaved title', 'content': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My unsaved title')

    def test_article_editor_keeps_content(self):
        response = self.client.post(reverse('article_editor'), {'title': '', 'content': 'My unsaved content'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My unsaved content')


class ArticleViewDeleteTestCase(RegressionTestCase):
    def test_delete_button_posts(self):
        draft = make_article(author=self.author)
        response = self.client.get(reverse('article_view', args=[draft.id]))
        self.assertContains(response, f'<form method="post" action="{reverse("article_delete", args=[draft.id])}"')
        self.client.post(reverse('article_delete', args=[draft.id]), {'next': reverse('article_list')})
        self.assertFalse(Article.objects.filter(id=draft.id).exists())


class LegacyOnsiteEditTestCase(RegressionTestCase):
    def test_staff_edit_keeps_solution_author_as_article_author(self):
        legacy = Solution.objects.create(
            analysis_task=self.task, title='Legacy', solution_type=SolutionType.ONSITE,
            content='old', author=self.author,
        )
        self.login_as(self.staff)
        self.client.post(self.task_url('edit_onsite_solution', solution_id=legacy.id), {'title': 'Legacy', 'content': 'new'})
        legacy.refresh_from_db()
        self.assertEqual(legacy.article.author, self.author)
