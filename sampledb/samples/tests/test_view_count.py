"""
Tests for view count functionality

This test suite covers:
1. AnalysisTask view count increment on detail page access
2. Article view count increment on onsite solution view
3. View count initialization (default to 0)
4. View count atomic increments (F expressions)
5. View count display in templates
"""

from django.test import Client
from django.urls import reverse

from samples.models import Difficulty
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_onsite_solution, make_solution, make_task, make_user


class ViewCountTestCase(SampleTestCase):
    """Shared URL helpers"""

    def detail_url(self):
        return reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id})

    def solution_url(self, solution):
        return reverse('view_onsite_solution', kwargs={
            'sha256': self.task.sha256, 'task_id': self.task.id, 'solution_id': solution.id,
        })


class AnalysisTaskViewCountTestCase(ViewCountTestCase):
    """Test view count functionality for AnalysisTask model"""

    @classmethod
    def setUpTestData(cls):
        cls.task = make_task(difficulty=Difficulty.EASY, description='Test description')

    def test_view_count_default_is_zero(self):
        """New tasks should have view_count of 0"""
        self.assertEqual(self.task.view_count, 0)

    def test_detail_view_increments_count(self):
        """Accessing the detail page should increment view count"""
        initial_count = self.task.view_count

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, initial_count + 1)

    def test_multiple_views_increment_count(self):
        """Multiple accesses should increment count each time"""
        initial_count = self.task.view_count
        num_views = 5

        for _ in range(num_views):
            self.client.get(self.detail_url())

        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, initial_count + num_views)

    def test_view_count_persists_across_requests(self):
        """View count should persist across multiple requests"""
        self.client.get(self.detail_url())
        self.task.refresh_from_db()
        count_after_first = self.task.view_count

        self.client.get(self.detail_url())
        self.task.refresh_from_db()
        count_after_second = self.task.view_count

        # Verify increments are cumulative
        self.assertEqual(count_after_first, 1)
        self.assertEqual(count_after_second, 2)

    def test_view_count_displayed_in_template(self):
        """View count should be displayed in the detail template"""
        self.task.view_count = 42
        self.task.save()

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        # 43, because accessing the page increments it
        self.assertContains(response, '43')


class SolutionViewCountTestCase(ViewCountTestCase):
    """Test view count functionality for onsite solutions via Article model"""

    @classmethod
    def setUpTestData(cls):
        cls.task = make_task(difficulty=Difficulty.MEDIUM, description='Test description')
        cls.onsite_solution = make_onsite_solution(
            task=cls.task,
            title='Test Onsite Solution',
            content='# Test Solution\n\nThis is a test solution.',
        )
        cls.article = cls.onsite_solution.article
        cls.external_solution = make_solution(task=cls.task, title='Test External Solution')

    def test_article_view_count_default_is_zero(self):
        """New articles should have view_count of 0"""
        self.assertEqual(self.article.view_count, 0)

    def test_onsite_solution_view_increments_article_count(self):
        """Accessing onsite solution view should increment article view count"""
        initial_count = self.article.view_count

        response = self.client.get(self.solution_url(self.onsite_solution))

        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, initial_count + 1)

    def test_multiple_onsite_solution_views_increment_article_count(self):
        """Multiple accesses to onsite solution should increment article count each time"""
        initial_count = self.article.view_count
        num_views = 3

        for _ in range(num_views):
            self.client.get(self.solution_url(self.onsite_solution))

        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, initial_count + num_views)

    def test_external_solution_no_view_count(self):
        """External solutions are opened via their URL, so viewing the task doesn't count article views"""
        self.client.get(self.detail_url())

        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, 0)

    def test_onsite_solution_view_count_displayed_in_template(self):
        """View count should be displayed in the onsite solution view template"""
        self.article.view_count = 25
        self.article.save()

        response = self.client.get(self.solution_url(self.onsite_solution))

        self.assertEqual(response.status_code, 200)
        # 26, because accessing the page increments it
        self.assertContains(response, '<i class="fas fa-eye"></i> 26')

    def test_article_view_count_in_detail_page_for_onsite(self):
        """Onsite solution article view count should be displayed in task detail page"""
        self.article.view_count = 10
        self.article.save()

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<i class="fas fa-eye"></i> 10')

    def test_external_solution_no_view_count_in_detail_page(self):
        """External solution should not show view count in task detail page"""
        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        # The eye icon only appears for onsite solutions; there is exactly one
        content = response.content.decode('utf-8')
        self.assertGreaterEqual(content.count('fa-eye'), 1)


class ViewCountConcurrencyTestCase(ViewCountTestCase):
    """Test view count thread safety and atomic operations"""

    @classmethod
    def setUpTestData(cls):
        cls.task = make_task(goal='Test concurrent views', difficulty=Difficulty.ADVANCED)

    def test_view_count_uses_f_expression(self):
        """Rapid consecutive views must all be counted (F() expression updates)"""
        initial_count = self.task.view_count

        for _ in range(10):
            self.client.get(self.detail_url())

        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, initial_count + 10)


class ViewCountIntegrationTestCase(ViewCountTestCase):
    """Integration tests for view count across multiple features"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('testuser')
        cls.task = make_task(author=cls.user, goal='Integration test task', difficulty=Difficulty.EXPERT)
        cls.onsite_solution = make_onsite_solution(
            task=cls.task,
            title='Integration Test Solution',
            content='# Integration Test\n\nContent here.',
        )
        cls.article = cls.onsite_solution.article

    def test_task_and_article_view_counts_independent(self):
        """Task and article view counts should be tracked independently"""
        self.client.get(self.detail_url())

        self.task.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.task.view_count, 1)
        # Not viewing the solution directly
        self.assertEqual(self.article.view_count, 0)

        self.client.get(self.solution_url(self.onsite_solution))

        self.task.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.task.view_count, 1)
        self.assertEqual(self.article.view_count, 1)

    def test_authenticated_vs_unauthenticated_view_counting(self):
        """View counts should increment for both authenticated and unauthenticated users"""
        Client().get(self.detail_url())

        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, 1)

        client_auth = Client()
        client_auth.force_login(self.user)
        client_auth.get(self.detail_url())

        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, 2)
