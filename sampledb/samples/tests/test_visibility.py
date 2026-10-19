"""
Tests for the shared visibility and permission rules (samples/querysets.py and
the Solution model): who sees hidden solutions on every page that lists them,
who may edit or delete, and that list pages cost a fixed number of queries.
"""
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from samples.models import AnalysisTask, Solution
from samples.tests.base import SampleTestCase
from samples.tests.factories import (
    make_article, make_onsite_solution, make_solution, make_staff, make_task, make_user,
)


def hidden():
    return timezone.now() + timedelta(weeks=2)


class VisibilityMatrixTestCase(SampleTestCase):
    """A hidden solution is visible to staff, its author and the task author; nobody else."""

    @classmethod
    def setUpTestData(cls):
        cls.task_author = make_user('taskauthor')
        cls.solution_author = make_user('solver')
        cls.other = make_user('other')
        cls.staff = make_staff('moderator')
        cls.task = make_task(author=cls.task_author)
        make_solution(task=cls.task, title='Reference Writeup')
        cls.hidden_solution = make_onsite_solution(
            task=cls.task, author=cls.solution_author, title='Secret Writeup', hidden_until=hidden(),
        )
        cls.privileged = {'solver': cls.solution_author, 'taskauthor': cls.task_author, 'moderator': cls.staff}

    def viewers(self):
        """(name, user or None for anonymous, may see hidden)"""
        yield 'anonymous', None, False
        yield 'other', self.other, False
        for name, user in self.privileged.items():
            yield name, user, True

    def get_as(self, user, url, **params):
        self.client.logout()
        if user:
            self.login_as(user)
        return self.client.get(url, params)

    def assert_matrix(self, url, **params):
        for name, user, may_see in self.viewers():
            with self.subTest(viewer=name):
                response = self.get_as(user, url, **params)
                self.assertEqual(response.status_code, 200)
                if may_see:
                    self.assertContains(response, 'Secret Writeup')
                    self.assertContains(response, 'fa-eye-slash')  # "Hidden" badge
                else:
                    self.assertNotContains(response, 'Secret Writeup')
                self.assertContains(response, 'Reference Writeup')

    def test_task_detail(self):
        self.assert_matrix(self.task.get_absolute_url())

    def test_solution_list(self):
        self.assert_matrix(reverse('solution_list'))

    def test_profile(self):
        url = reverse('user_profile', args=['solver'])
        for name, user, may_see in self.viewers():
            if user is None:
                continue  # profiles require login
            with self.subTest(viewer=name):
                response = self.get_as(user, url)
                if may_see:
                    self.assertContains(response, 'Secret Writeup')
                else:
                    self.assertNotContains(response, 'Secret Writeup')

    def test_showcase_never_shows_hidden(self):
        for name, user, _ in self.viewers():
            with self.subTest(viewer=name):
                response = self.get_as(user, reverse('solutions_showcase'))
                self.assertNotContains(response, 'Secret Writeup')

    def test_onsite_view(self):
        url = self.hidden_solution.get_absolute_url()
        for name, user, may_see in self.viewers():
            with self.subTest(viewer=name):
                response = self.get_as(user, url)
                self.assertEqual(response.status_code, 200 if may_see else 302)

    def test_task_list_counts_only_public_solutions(self):
        task = AnalysisTask.objects.for_listing().get(pk=self.task.pk)
        self.assertEqual(task.solution_count_annotated, 1)
        self.assertTrue(task.has_blog_solution)
        self.assertFalse(task.has_onsite_solution)

    def test_queryset_and_instance_rules_agree(self):
        for name, user, may_see in self.viewers():
            user = user or AnonymousUser()
            with self.subTest(viewer=name):
                in_queryset = Solution.objects.visible_to(user).filter(pk=self.hidden_solution.pk).exists()
                self.assertEqual(in_queryset, may_see)
                self.assertEqual(self.hidden_solution.user_can_view(user), may_see)

    def test_expired_hidden_solution_is_public(self):
        self.hidden_solution.hidden_until = timezone.now() - timedelta(days=1)
        self.hidden_solution.save()
        response = self.get_as(None, self.task.get_absolute_url())
        self.assertContains(response, 'Secret Writeup')
        self.assertNotContains(response, 'fa-eye-slash')


class DeletePermissionTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task = make_task()
        cls.reference = make_solution(task=cls.task)
        cls.community = make_solution(task=cls.task, author=make_user())
        cls.staff = make_staff()

    def test_last_reference_is_locked(self):
        self.assertTrue(self.reference.is_last_reference())
        self.assertFalse(self.reference.user_can_delete(self.staff))
        make_solution(task=self.task)  # a second reference solution
        self.assertFalse(self.reference.is_last_reference())

    def test_hidden_references_still_count(self):
        make_solution(task=self.task, hidden_until=hidden())
        self.assertFalse(self.reference.is_last_reference())

    def test_annotation_matches_query(self):
        annotated = Solution.objects.with_reference_count().get(pk=self.reference.pk)
        self.assertEqual(annotated.reference_count, 1)
        self.assertTrue(annotated.is_last_reference())

    def test_community_solution_deletable_by_author_and_staff(self):
        self.assertTrue(self.community.user_can_delete(self.community.author))
        self.assertTrue(self.community.user_can_delete(self.staff))
        self.assertFalse(self.community.user_can_delete(self.task.author))

    def test_staff_sees_delete_button(self):
        self.login_as(self.staff)
        response = self.client.get(self.task.get_absolute_url())
        self.assertContains(response, f"confirmDelete('{self.community.id}'")
        self.assertNotContains(response, f"confirmDelete('{self.reference.id}'")
        self.assertContains(response, 'Cannot delete the last reference solution')

    def test_staff_can_delete_community_solution(self):
        self.login_as(self.staff)
        url = reverse('delete_solution', args=[self.task.sha256, self.task.id, self.community.id])
        self.client.post(url)
        self.assertFalse(Solution.objects.filter(pk=self.community.pk).exists())


class ListCountsTestCase(SampleTestCase):
    def test_favorite_and_solution_counts_do_not_multiply(self):
        """Counting two joined relations in one query needs distinct=True"""
        task = make_task()
        task.favorited_by.add(*(make_user() for _ in range(3)))
        make_solution(task=task)
        make_solution(task=task, author=make_user())

        annotated = AnalysisTask.objects.for_listing().get(pk=task.pk)
        self.assertEqual(annotated.favorite_count_annotated, 3)
        self.assertEqual(annotated.solution_count_annotated, 2)


class QueryCountTestCase(SampleTestCase):
    """List pages must not issue queries per row."""

    @classmethod
    def setUpTestData(cls):
        cls.viewer = make_staff()

    def add_rows(self, count, author):
        for _ in range(count):
            task = make_task(author=author)
            task.favorited_by.add(self.viewer)
            make_solution(task=task)
            make_onsite_solution(task=task)
            make_solution(task=task, author=make_user(), hidden_until=hidden())

    def queries_for(self, url):
        self.login_as(self.viewer)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def assert_constant(self, url, author):
        self.add_rows(3, author)
        few = self.queries_for(url)
        self.add_rows(7, author)
        many = self.queries_for(url)
        self.assertEqual(few, many, f'{url}: {few} queries for 3 rows, {many} for 10')

    def test_task_list(self):
        self.assert_constant(reverse('sample_list') + '?browse=1', make_user())

    def test_solution_list(self):
        self.assert_constant(reverse('solution_list'), make_user())

    def test_showcase(self):
        self.assert_constant(reverse('solutions_showcase'), make_user())

    def test_profile(self):
        author = make_user('prolific')
        self.assert_constant(reverse('user_profile', args=['prolific']), author)

    def test_article_list(self):
        def add_articles(count):
            for _ in range(count):
                make_onsite_solution(author=self.viewer)
                make_article(author=self.viewer)

        self.login_as(self.viewer)
        add_articles(3)
        few = self.queries_for(reverse('article_list'))
        add_articles(7)
        many = self.queries_for(reverse('article_list'))
        self.assertEqual(few, many)
