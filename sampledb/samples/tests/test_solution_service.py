"""
Tests for samples/services/solutions.py, the one place solutions are created.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.urls import reverse

from samples.models import Article, Solution, SolutionType
from samples.services.solutions import (
    create_solution, hidden_until_from_weeks, publish_draft, update_onsite_solution,
)
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_article, make_onsite_solution, make_solution, make_task, make_user


class CreateSolutionTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task = make_task()
        cls.author = make_user()

    def test_onsite_text_goes_into_a_new_article(self):
        solution = create_solution(
            task=self.task, author=self.author, solution_type=SolutionType.ONSITE,
            title='Writeup', content='# Text',
        )
        self.assertEqual(solution.article.content, '# Text')
        self.assertEqual(solution.article.title, 'Writeup')
        self.assertEqual(solution.article.author, self.author)
        self.assertIsNone(solution.url)

    def test_external_solution_keeps_url_and_has_no_article(self):
        solution = create_solution(
            task=self.task, author=self.author, solution_type=SolutionType.BLOG,
            title='Blog', url='https://example.com/post',
        )
        self.assertEqual(solution.url, 'https://example.com/post')
        self.assertIsNone(solution.article)

    def test_publishing_a_draft_takes_its_title(self):
        draft = make_article(author=self.author, title='Draft title')
        solution = publish_draft(article=draft, task=self.task, author=self.author)
        self.assertEqual(solution.title, 'Draft title')
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.article, draft)

    def test_cannot_publish_someone_elses_draft(self):
        draft = make_article(author=make_user())
        with self.assertRaises(ValidationError):
            publish_draft(article=draft, task=self.task, author=self.author)
        self.assertFalse(Solution.objects.exists())

    def test_cannot_publish_a_published_article(self):
        published = make_onsite_solution(author=self.author).article
        with self.assertRaises(ValidationError):
            publish_draft(article=published, task=self.task, author=self.author)

    def test_duplicate_title_is_a_title_error_and_creates_nothing(self):
        make_solution(task=self.task, title='Taken')
        with self.assertRaises(ValidationError) as raised:
            create_solution(
                task=self.task, author=self.author, solution_type=SolutionType.ONSITE,
                title='Taken', content='text',
            )
        self.assertIn('title', raised.exception.message_dict)
        self.assertEqual(Article.objects.count(), 0)


class UpdateOnsiteSolutionTestCase(SampleTestCase):
    def test_rename_into_taken_title_fails(self):
        task = make_task()
        make_solution(task=task, title='Taken')
        solution = make_onsite_solution(task=task, title='Mine')
        with self.assertRaises(ValidationError):
            update_onsite_solution(solution, title='Taken', content='x')

    def test_keeps_own_title(self):
        solution = make_onsite_solution(title='Mine', content='old')
        update_onsite_solution(solution, title='Mine', content='new')
        solution.article.refresh_from_db()
        self.assertEqual(solution.article.content, 'new')


class HiddenUntilTestCase(SampleTestCase):
    def test_weeks(self):
        now = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(hidden_until_from_weeks(2, now=now), now + timedelta(weeks=2))
        self.assertEqual(hidden_until_from_weeks('3', now=now), now + timedelta(weeks=3))

    def test_not_hidden(self):
        self.assertIsNone(hidden_until_from_weeks(0))
        self.assertIsNone(hidden_until_from_weeks(None))


class CreateSolutionViewTestCase(SampleTestCase):
    def test_someone_elses_draft_is_a_form_error(self):
        task = make_task()
        user = make_user()
        foreign_draft = make_article(author=make_user())
        self.login_as(user)

        response = self.client.post(reverse('create_solution', args=[task.sha256, task.id]), {
            'solution_type': SolutionType.ONSITE, 'draft_article_id': foreign_draft.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You can only publish your own drafts.')
        self.assertFalse(Solution.objects.exists())

    def test_external_solution_cannot_become_onsite(self):
        solution = make_solution()
        self.login_as(solution.author)
        url = reverse('edit_solution', args=[solution.analysis_task.sha256, solution.analysis_task.id, solution.id])

        response = self.client.post(url, {'title': solution.title, 'solution_type': SolutionType.ONSITE, 'content': 'x'})

        self.assertEqual(response.status_code, 200)
        solution.refresh_from_db()
        self.assertEqual(solution.solution_type, SolutionType.BLOG)
