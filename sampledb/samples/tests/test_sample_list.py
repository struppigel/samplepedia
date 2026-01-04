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

NOTE: This test file doesn't test redirects, but if you add redirect tests in the future:
- Always use fetch_redirect_response=False in assertRedirects() calls
- This ensures compatibility with production settings (DEBUG=False, SECURE_SSL_REDIRECT=True)
- See test_solutions.py for examples of proper redirect testing patterns
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from samples.models import AnalysisTask, Difficulty


class SampleListUnauthenticatedTestCase(TestCase):
    """Test sample list behavior for unauthenticated users"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create some test tasks with different difficulties
        self.task_easy = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Easy malware analysis',
            difficulty=Difficulty.EASY,
            description='Test description easy',
            author=self.user
        )
        self.task_easy.tags.add('ransomware', 'windows')
        
        self.task_medium = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Medium malware analysis',
            difficulty=Difficulty.MEDIUM,
            description='Test description medium',
            author=self.user
        )
        self.task_medium.tags.add('trojan', 'linux')
        
        self.task_advanced = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal='Advanced malware analysis',
            difficulty=Difficulty.ADVANCED,
            description='Test description advanced',
            author=self.user
        )
        self.task_advanced.tags.add('rootkit', 'windows')
        
        self.client = Client()
    
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
        # Search by SHA256
        response = self.client.get(reverse('sample_list') + '?q=aaa')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)
        
        # Verify the search filtered correctly
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)
    
    def test_difficulty_filter_shows_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list when filtering by difficulty"""
        response = self.client.get(reverse('sample_list') + '?difficulty=easy')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)
        
        # Verify the filter worked
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].difficulty, Difficulty.EASY)
    
    def test_tag_filter_shows_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list when filtering by tag"""
        response = self.client.get(reverse('sample_list') + '?tag=windows')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)
        
        # Verify the filter worked (should show 2 tasks tagged with 'windows')
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 2)
    
    def test_multiple_filters_show_list_for_unauthenticated(self):
        """Unauthenticated users should see filtered list with multiple filters"""
        response = self.client.get(reverse('sample_list') + '?difficulty=easy&tag=windows')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)
        
        # Verify combined filters worked
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)


class SampleListAuthenticatedTestCase(TestCase):
    """Test sample list behavior for authenticated users"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        
        # Create test tasks
        self.task1 = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Test task 1',
            difficulty=Difficulty.EASY,
            description='Test description 1',
            author=self.user
        )
        
        self.task2 = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Test task 2',
            difficulty=Difficulty.MEDIUM,
            description='Test description 2',
            author=self.other_user
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_authenticated_user_sees_list_directly(self):
        """Authenticated users should see sample list without any params"""
        response = self.client.get(reverse('sample_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        self.assertIn('page_obj', response.context)
    
    def test_favorites_filter_requires_authentication(self):
        """Favorites filter should work for authenticated users"""
        # Favorite a task
        self.task1.favorited_by.add(self.user)
        
        response = self.client.get(reverse('sample_list') + '?favorites=true')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        
        # Should only show favorited task
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)
    
    def test_authenticated_search_and_filter(self):
        """Authenticated users can search and filter"""
        response = self.client.get(reverse('sample_list') + '?q=aaa&difficulty=easy')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/list.html')
        
        # Verify search and filter worked
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)


class SampleListSortingTestCase(TestCase):
    """Test sample list sorting functionality"""
    
    def setUp(self):
        """Create test data with different attributes"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create tasks with different SHA256s for sorting
        self.task_a = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='AAA task',
            difficulty=Difficulty.ADVANCED,
            description='Test description',
            author=self.user
        )
        
        self.task_b = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='BBB task',
            difficulty=Difficulty.EASY,
            description='Test description',
            author=self.user
        )
        
        self.task_c = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal='CCC task',
            difficulty=Difficulty.MEDIUM,
            description='Test description',
            author=self.user
        )
        
        self.client = Client()
    
    def test_sort_by_sha256_ascending(self):
        """Test sorting by SHA256 ascending"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=sha256')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        # Should be sorted a, b, c
        self.assertEqual(page_obj.object_list[0].sha256, 'a' * 64)
        self.assertEqual(page_obj.object_list[1].sha256, 'b' * 64)
        self.assertEqual(page_obj.object_list[2].sha256, 'c' * 64)
    
    def test_sort_by_sha256_descending(self):
        """Test sorting by SHA256 descending"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=-sha256')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        # Should be sorted c, b, a
        self.assertEqual(page_obj.object_list[0].sha256, 'c' * 64)
        self.assertEqual(page_obj.object_list[1].sha256, 'b' * 64)
        self.assertEqual(page_obj.object_list[2].sha256, 'a' * 64)
    
    def test_sort_by_difficulty(self):
        """Test sorting by difficulty"""
        response = self.client.get(reverse('sample_list') + '?browse=1&sort=difficulty')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        # Should be sorted easy, medium, advanced
        self.assertEqual(page_obj.object_list[0].difficulty, Difficulty.EASY)
        self.assertEqual(page_obj.object_list[1].difficulty, Difficulty.MEDIUM)
        self.assertEqual(page_obj.object_list[2].difficulty, Difficulty.ADVANCED)


class SampleListPaginationTestCase(TestCase):
    """Test sample list pagination"""
    
    def setUp(self):
        """Create enough test data to trigger pagination"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create 30 tasks (pagination is 25 per page)
        for i in range(30):
            AnalysisTask.objects.create(
                sha256=f"{i:064d}",
                goal=f'Test task {i}',
                difficulty=Difficulty.EASY,
                description='Test description',
                author=self.user
            )
        
        self.client = Client()
    
    def test_first_page_has_25_items(self):
        """First page should have 25 items"""
        response = self.client.get(reverse('sample_list') + '?browse=1')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        self.assertEqual(len(page_obj.object_list), 25)
        self.assertEqual(page_obj.paginator.num_pages, 2)
        self.assertTrue(page_obj.has_next())
    
    def test_second_page_has_remaining_items(self):
        """Second page should have remaining 5 items"""
        response = self.client.get(reverse('sample_list') + '?browse=1&page=2')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        self.assertEqual(len(page_obj.object_list), 5)
        self.assertFalse(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())
    
    def test_pagination_preserves_filters(self):
        """Pagination should preserve search/filter parameters"""
        # Add a specific tag to one task
        task = AnalysisTask.objects.first()
        task.tags.add('special')
        
        response = self.client.get(reverse('sample_list') + '?browse=1&tag=special&page=1')
        
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        
        # Should only show the one task with the tag
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj.object_list[0].id, task.id)
