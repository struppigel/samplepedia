"""
Tests for sample list view functionality

This test suite covers:
1. Landing page display for unauthenticated users
2. Sample list display for authenticated users
3. Search/filter functionality for unauthenticated users (regression test)
4. Browse parameter behavior
5. Filtering by difficulty, tags, SHA256
6. Favorites filtering
7. Sorting functionality
8. Pagination
"""

from django.urls import reverse

from samples.models import AnalysisTask, Difficulty
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_task, make_user


class SampleListUnauthenticatedTestCase(SampleTestCase):
    """Test sample list behavior for unauthenticated users"""

    @classmethod
    def setUpTestData(cls):
        cls.task_easy = make_task(sha256='a' * 64, difficulty=Difficulty.EASY)
        cls.task_easy.tags.add('ransomware', 'windows')

        cls.task_medium = make_task(sha256='b' * 64, difficulty=Difficulty.MEDIUM)
        cls.task_medium.tags.add('trojan', 'linux')

        cls.task_advanced = make_task(sha256='c' * 64, difficulty=Difficulty.ADVANCED)
        cls.task_advanced.tags.add('rootkit', 'windows')

    def test_landing_page_for_unauthenticated_without_params(self):
        """Unauthenticated users should see landing page when accessing root without params"""
        response = self.client.get(reverse('sample_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/landing.html')

    def test_browse_param_shows_list(self):
        """Unauthenticated users should see sample list with browse param"""
        response = self.client.get(reverse('sample_list') + '?browse=1')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

    def test_search_shows_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list when searching (regression test)"""
        response = self.client.get(reverse('sample_list') + '?q=aaa')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)

    def test_difficulty_filter_shows_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list when filtering by difficulty"""
        response = self.client.get(reverse('sample_list') + '?difficulty=easy')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].difficulty, Difficulty.EASY)

    def test_tag_filter_shows_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list when filtering by tag"""
        response = self.client.get(reverse('sample_list') + '?tag=windows')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

        # Two tasks are tagged 'windows'
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 2)

    def test_multiple_filters_show_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list with multiple filters"""
        response = self.client.get(reverse('sample_list') + '?difficulty=easy&tag=windows')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)


class SampleListAuthenticatedTestCase(SampleTestCase):
    """Test sample list behavior for authenticated users"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.task1 = make_task(author=cls.user, sha256='a' * 64, difficulty=Difficulty.EASY)
        cls.task2 = make_task(sha256='b' * 64, difficulty=Difficulty.MEDIUM)

    def setUp(self):
        self.login_as(self.user)

    def test_authenticated_user_sees_list_directly(self):
        """Authenticated users should see sample list without any params"""
        response = self.client.get(reverse('sample_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)

    def test_favorites_filter_requires_authentication(self):
        """Favorites filter should work for authenticated users"""
        self.task1.favorited_by.add(self.user)

        response = self.client.get(reverse('sample_list') + '?favorites=true')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')

        # Should only show the favorited task
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)

    def test_authenticated_search_and_filter(self):
        """Authenticated users can search and filter"""
        response = self.client.get(reverse('sample_list') + '?q=aaa&difficulty=easy')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')

        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)


class SampleListSortingTestCase(SampleTestCase):
    """Test sample list sorting functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.task_a = make_task(sha256='a' * 64, goal='AAA task', difficulty=Difficulty.ADVANCED)
        cls.task_b = make_task(sha256='b' * 64, goal='BBB task', difficulty=Difficulty.EASY)
        cls.task_c = make_task(sha256='c' * 64, goal='CCC task', difficulty=Difficulty.MEDIUM)

    def test_sort_by_sha256_ascending(self):
        """Test sorting by SHA256 ascending"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=sha256')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)
        self.assertEqual(page_obj.object_list[1].sha256, 'b' * 64)
        self.assertEqual(page_obj.object_list[2].sha256, 'c' * 64)

    def test_sort_by_sha256_descending(self):
        """Test sorting by SHA256 descending"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=-sha256')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        self.assertEqual(page_obj.object_list[0].sha256, 'c' * 64)
        self.assertEqual(page_obj.object_list[1].sha256, 'b' * 64)
        self.assertEqual(page_obj.object_list[2].sha256, 'a' * 64)

    def test_sort_by_difficulty(self):
        """Test sorting by difficulty"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=difficulty')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        self.assertEqual(page_obj.object_list[0].difficulty, Difficulty.EASY)
        self.assertEqual(page_obj.object_list[1].difficulty, Difficulty.MEDIUM)
        self.assertEqual(page_obj.object_list[2].difficulty, Difficulty.ADVANCED)


class SampleListPaginationTestCase(SampleTestCase):
    """Test sample list pagination"""

    @classmethod
    def setUpTestData(cls):
        # Enough tasks for more than one page
        author = make_user()
        for i in range(30):
            make_task(author=author, sha256=f"{i:064d}", goal=f'Test task {i}', difficulty=Difficulty.EASY)

    def test_first_page_has_17_items(self):
        """First page should have 17 items which is the current pagination limit"""
        response = self.client.get(reverse('sample_list') + '?browse=1')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        self.assertEqual(len(page_obj.object_list), 17)
        self.assertTrue(page_obj.paginator.num_pages >= 2)
        self.assertTrue(page_obj.has_next())

    def test_second_page_has_remaining_items(self):
        """Second page holds the tasks that didn't fit on the first"""
        response = self.client.get(reverse('sample_list') + '?browse=1&page=2')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        self.assertEqual(len(page_obj.object_list), page_obj.paginator.count - page_obj.paginator.per_page)
        self.assertTrue(page_obj.has_previous())

    def test_pagination_preserves_filters(self):
        """Pagination should preserve search/filter parameters"""
        task = AnalysisTask.objects.first()
        task.tags.add('special')

        response = self.client.get(reverse('sample_list') + '?browse=1&tag=special&page=1')

        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']

        # Only the one tagged task
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].id, task.id)
