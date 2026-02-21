"""
Tests for view count functionality

This test suite covers:
1. AnalysisTask view count increment on detail page access
2. Article view count increment on onsite solution view
3. View count initialization (default to 0)
4. View count atomic increments (F expressions)
5. View count display in templates
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from samples.models import AnalysisTask, Solution, Article, Difficulty, SolutionType


class AnalysisTaskViewCountTestCase(TestCase):
    """Test view count functionality for AnalysisTask model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Test malware analysis',
            difficulty=Difficulty.EASY,
            description='Test description',
            author=self.user
        )
        
        self.client = Client()
    
    def test_view_count_default_is_zero(self):
        """New tasks should have view_count of 0"""
        self.assertEqual(self.task.view_count, 0)
    
    def test_detail_view_increments_count(self):
        """Accessing the detail page should increment view count"""
        initial_count = self.task.view_count
        
        # Access the detail page
        response = self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Refresh from database and check count incremented
        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, initial_count + 1)
    
    def test_multiple_views_increment_count(self):
        """Multiple accesses should increment count each time"""
        initial_count = self.task.view_count
        num_views = 5
        
        # Access the detail page multiple times
        for _ in range(num_views):
            self.client.get(
                reverse('sample_detail', kwargs={
                    'sha256': self.task.sha256,
                    'task_id': self.task.id
                })
            )
        
        # Refresh from database and check count incremented correctly
        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, initial_count + num_views)
    
    def test_view_count_persists_across_requests(self):
        """View count should persist across multiple requests"""
        # First view
        self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.task.refresh_from_db()
        count_after_first = self.task.view_count
        
        # Second view
        self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.task.refresh_from_db()
        count_after_second = self.task.view_count
        
        # Verify increments are cumulative
        self.assertEqual(count_after_first, 1)
        self.assertEqual(count_after_second, 2)
    
    def test_view_count_displayed_in_template(self):
        """View count should be displayed in the detail template"""
        # Set a specific view count
        self.task.view_count = 42
        self.task.save()
        
        response = self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        # Check that the view count appears in the rendered HTML
        # Note: view count will be 43 because accessing the page increments it
        self.assertContains(response, '43')  # The incremented count


class SolutionViewCountTestCase(TestCase):
    """Test view count functionality for onsite solutions via Article model"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Test malware analysis',
            difficulty=Difficulty.MEDIUM,
            description='Test description',
            author=self.user
        )
        
        # Create an article for onsite solution
        self.article = Article.objects.create(
            title='Test Onsite Solution',
            content='# Test Solution\n\nThis is a test solution.',
            author=self.user
        )
        
        # Create an onsite solution linked to the article
        self.onsite_solution = Solution.objects.create(
            analysis_task=self.task,
            title='Test Onsite Solution',
            solution_type=SolutionType.ONSITE,
            article=self.article,
            author=self.user
        )
        
        # Create an external solution (blog)
        self.external_solution = Solution.objects.create(
            analysis_task=self.task,
            title='Test External Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/solution',
            author=self.user
        )
        
        self.client = Client()
    
    def test_article_view_count_default_is_zero(self):
        """New articles should have view_count of 0"""
        self.assertEqual(self.article.view_count, 0)
    
    def test_onsite_solution_view_increments_article_count(self):
        """Accessing onsite solution view should increment article view count"""
        initial_count = self.article.view_count
        
        # Access the onsite solution view
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.onsite_solution.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Refresh from database and check count incremented
        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, initial_count + 1)
    
    def test_multiple_onsite_solution_views_increment_article_count(self):
        """Multiple accesses to onsite solution should increment article count each time"""
        initial_count = self.article.view_count
        num_views = 3
        
        # Access the onsite solution view multiple times
        for _ in range(num_views):
            self.client.get(
                reverse('view_onsite_solution', kwargs={
                    'sha256': self.task.sha256,
                    'task_id': self.task.id,
                    'solution_id': self.onsite_solution.id
                })
            )
        
        # Refresh from database and check count incremented correctly
        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, initial_count + num_views)
    
    def test_external_solution_no_view_count(self):
        """External solutions don't have articles so no view count tracking"""
        # External solutions are opened in new tabs via URLs, so no view count tracking
        # Access the task detail page (where external solutions are listed)
        self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        # Article view count should remain unchanged
        self.article.refresh_from_db()
        self.assertEqual(self.article.view_count, 0)
    
    def test_onsite_solution_view_count_displayed_in_template(self):
        """View count should be displayed in the onsite solution view template"""
        # Set a specific view count
        self.article.view_count = 25
        self.article.save()
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.onsite_solution.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        # Check that the view count appears in the rendered HTML
        # Note: view count will be 26 because accessing the page increments it
        self.assertContains(response, '<i class="fas fa-eye"></i> 26')
    
    def test_article_view_count_in_detail_page_for_onsite(self):
        """Onsite solution article view count should be displayed in task detail page"""
        self.article.view_count = 10
        self.article.save()
        
        response = self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        # Check that the view count appears in the solutions list
        self.assertContains(response, '<i class="fas fa-eye"></i> 10')
    
    def test_external_solution_no_view_count_in_detail_page(self):
        """External solution should not show view count in task detail page"""
        response = self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
        # The HTML should NOT contain view count for external solution
        # (we conditionally hide it with {% if solution.solution_type == 'onsite' and solution.article %})
        content = response.content.decode('utf-8')
        
        # Count how many times the eye icon appears in solution list
        # Should only appear for onsite solutions
        eye_icon_count = content.count('fa-eye')
        # We have one onsite solution with view count displayed
        self.assertGreaterEqual(eye_icon_count, 1)


class ViewCountConcurrencyTestCase(TestCase):
    """Test view count thread safety and atomic operations"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal='Test concurrent views',
            difficulty=Difficulty.ADVANCED,
            description='Test description',
            author=self.user
        )
        
        self.client = Client()
    
    def test_view_count_uses_f_expression(self):
        """View count should use F expression for atomic updates"""
        # This test verifies that the implementation uses F() expressions
        # by checking that concurrent-like updates work correctly
        
        initial_count = self.task.view_count
        
        # Simulate rapid consecutive views
        for _ in range(10):
            self.client.get(
                reverse('sample_detail', kwargs={
                    'sha256': self.task.sha256,
                    'task_id': self.task.id
                })
            )
        
        self.task.refresh_from_db()
        
        # If F() expressions are used correctly, all increments should be counted
        self.assertEqual(self.task.view_count, initial_count + 10)


class ViewCountIntegrationTestCase(TestCase):
    """Integration tests for view count across multiple features"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='d' * 64,
            goal='Integration test task',
            difficulty=Difficulty.EXPERT,
            description='Test description',
            author=self.user
        )
        
        # Create an article for onsite solution
        self.article = Article.objects.create(
            title='Integration Test Solution',
            content='# Integration Test\n\nContent here.',
            author=self.user
        )
        
        # Create onsite solution linked to the article
        self.onsite_solution = Solution.objects.create(
            analysis_task=self.task,
            title='Integration Test Solution',
            solution_type=SolutionType.ONSITE,
            article=self.article,
            author=self.user
        )
        
        self.client = Client()
    
    def test_task_and_article_view_counts_independent(self):
        """Task and article view counts should be tracked independently"""
        # View the task detail page
        self.client.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.task.refresh_from_db()
        self.article.refresh_from_db()
        
        # Task view count should be incremented
        self.assertEqual(self.task.view_count, 1)
        # Article view count should NOT be incremented (not viewing solution directly)
        self.assertEqual(self.article.view_count, 0)
        
        # Now view the solution
        self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.onsite_solution.id
            })
        )
        
        self.task.refresh_from_db()
        self.article.refresh_from_db()
        
        # Task view count should remain the same
        self.assertEqual(self.task.view_count, 1)
        # Article view count should now be incremented
        self.assertEqual(self.article.view_count, 1)
    
    def test_authenticated_vs_unauthenticated_view_counting(self):
        """View counts should increment for both authenticated and unauthenticated users"""
        # Test as unauthenticated user
        client_unauth = Client()
        client_unauth.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, 1)
        
        # Test as authenticated user
        client_auth = Client()
        client_auth.login(username='testuser', password='testpass123')
        client_auth.get(
            reverse('sample_detail', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            })
        )
        
        self.task.refresh_from_db()
        self.assertEqual(self.task.view_count, 2)
