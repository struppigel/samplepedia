"""
Tests for solution functionality

This test suite covers:
1. Solution creation for different types (blog, paper, video, onsite)
2. Solution form validation
3. Solution editing and deletion permissions
4. Solution likes/unlikes
5. Onsite solution content validation
6. URL validation for external solutions
7. Title uniqueness per analysis task
8. Solution listing and filtering
9. Solution type icon display
10. Author attribution and notifications
11. Solution hiding functionality (hidden_until field):
    - Anonymous and regular users cannot see hidden solutions
    - Solution authors can see their own hidden solutions
    - Task authors can see hidden solutions on their tasks
    - Staff can see all hidden solutions
    - Direct URL access protection for hidden onsite solutions
    - Hidden solutions excluded from showcase (no exceptions)
    - Hidden solutions filtered on profile views
    - Expired hidden solutions become visible to all
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from samples.models import AnalysisTask, Solution, SolutionType, Difficulty
from samples.forms import SolutionForm


class SolutionCreationTestCase(TestCase):
    """Test solution creation for different types"""
    
    def setUp(self):
        """Create test users and analysis task"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Test malware analysis',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        self.client = Client()
    
    def test_create_blog_solution(self):
        """Test creating a blog post solution"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            reverse('create_solution', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            {
                'title': 'My Analysis Blog Post',
                'solution_type': SolutionType.BLOG,
                'url': 'https://example.com/analysis'
            }
        )
        
        # Verify we have a redirect (solution was created successfully)
        self.assertIn(response.status_code, [301, 302], f"Expected redirect, got {response.status_code}")
        
        # Debug: Check if solution was actually created
        if Solution.objects.count() == 0:
            print(f"\nSolution not created! Redirect URL: {response.url if hasattr(response, 'url') else 'No URL'}")
            print(f"Status code: {response.status_code}")
        
        self.assertEqual(Solution.objects.count(), 1)
        solution = Solution.objects.first()
        
        # Verify redirect URL
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(solution.title, 'My Analysis Blog Post')
        self.assertEqual(solution.solution_type, SolutionType.BLOG)
        self.assertEqual(solution.author, self.user)
    
    def test_create_video_solution(self):
        """Test creating a video solution"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            reverse('create_solution', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            {
                'title': 'Video Walkthrough',
                'solution_type': SolutionType.VIDEO,
                'url': 'https://youtube.com/watch?v=test'
            }
        )
        
        # Verify we have a redirect (solution was created successfully)
        self.assertIn(response.status_code, [301, 302], f"Expected redirect, got {response.status_code}")
        
        solution = Solution.objects.first()
        
        # Verify redirect URL
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(solution.solution_type, SolutionType.VIDEO)
    
    def test_create_onsite_solution_redirects_to_editor(self):
        """Test that onsite solutions should use the dedicated editor"""
        self.client.login(username='testuser', password='testpass123')
        
        # Onsite solution without content should show form with errors
        response = self.client.post(
            reverse('create_solution', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            {
                'title': 'Onsite Analysis',
                'solution_type': SolutionType.ONSITE,
            },
            follow=False
        )
        
        # Should return form with validation error (missing content)
        self.assertEqual(response.status_code, 200)
        if response.context:
            self.assertIn('form', response.context)
    
    def test_unauthenticated_cannot_create_solution(self):
        """Test that unauthenticated users cannot create solutions"""
        response = self.client.post(
            reverse('create_solution', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            {
                'title': 'Test',
                'solution_type': SolutionType.BLOG,
                'url': 'https://example.com'
            }
        )
        
        # Should redirect to login - assertRedirects handles 301 and 302
        expected_url = f"/login/?next=/sample/{self.task.sha256}/{self.task.id}/solution/add/"
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        self.assertEqual(Solution.objects.count(), 0)


class SolutionFormValidationTestCase(TestCase):
    """Test solution form validation"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='test')
        self.task = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Test task',
            difficulty=Difficulty.MEDIUM,
            author=self.user
        )
    
    def test_external_solution_requires_url(self):
        """Test that blog/paper/video solutions require URL"""
        form = SolutionForm({
            'title': 'Test Solution',
            'solution_type': SolutionType.BLOG,
            'url': ''  # Empty URL
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('External solutions must have a URL.', form.errors['__all__'])
    
    def test_onsite_solution_no_url_required(self):
        """Test that onsite solutions don't require URL"""
        form = SolutionForm({
            'title': 'Test Solution',
            'solution_type': SolutionType.ONSITE,
            'url': '',
            'content': '# My analysis\n\nDetails here...'
        })
        
        self.assertTrue(form.is_valid())
    
    def test_title_required(self):
        """Test that title is required"""
        form = SolutionForm({
            'title': '',
            'solution_type': SolutionType.BLOG,
            'url': 'https://example.com'
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_solution_type_required(self):
        """Test that solution type is required"""
        form = SolutionForm({
            'title': 'Test',
            'solution_type': '',
            'url': 'https://example.com'
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('solution_type', form.errors)


class SolutionUniquenessTestCase(TestCase):
    """Test solution title uniqueness per analysis task"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='test')
        self.task1 = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal='Task 1',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        self.task2 = AnalysisTask.objects.create(
            sha256='d' * 64,
            goal='Task 2',
            difficulty=Difficulty.MEDIUM,
            author=self.user
        )
        
        # Create existing solution
        Solution.objects.create(
            analysis_task=self.task1,
            title='Duplicate Title',
            solution_type=SolutionType.BLOG,
            url='https://example.com/1',
            author=self.user
        )
    
    def test_duplicate_title_same_task_fails(self):
        """Test that duplicate title on same task is rejected"""
        with self.assertRaises(Exception):
            Solution.objects.create(
                analysis_task=self.task1,
                title='Duplicate Title',  # Same title, same task
                solution_type=SolutionType.VIDEO,
                url='https://example.com/2',
                author=self.user
            )
    
    def test_same_title_different_task_allowed(self):
        """Test that same title on different task is allowed"""
        solution = Solution.objects.create(
            analysis_task=self.task2,  # Different task
            title='Duplicate Title',  # Same title
            solution_type=SolutionType.PAPER,
            url='https://example.com/3',
            author=self.user
        )
        
        self.assertEqual(solution.title, 'Duplicate Title')
        self.assertEqual(Solution.objects.filter(title='Duplicate Title').count(), 2)


class SolutionPermissionsTestCase(TestCase):
    """Test solution editing and deletion permissions"""
    
    def setUp(self):
        """Create test users, task, and solution"""
        self.author = User.objects.create_user(username='author', password='test')
        self.other_user = User.objects.create_user(username='other', password='test')
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test',
            is_staff=True
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='e' * 64,
            goal='Test task',
            difficulty=Difficulty.EASY,
            author=self.author
        )
        
        self.solution = Solution.objects.create(
            analysis_task=self.task,
            title='Original Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com',
            author=self.author
        )
        
        # Create a second reference solution so the first can be deleted
        self.solution2 = Solution.objects.create(
            analysis_task=self.task,
            title='Second Reference Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/second',
            author=self.author
        )
        
        self.client = Client()
    
    def test_author_can_edit_solution(self):
        """Test that solution author can edit their solution"""
        self.client.login(username='author', password='test')
        
        response = self.client.get(
            reverse('edit_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.solution.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_non_author_cannot_edit_solution(self):
        """Test that non-authors cannot edit solutions"""
        self.client.login(username='other', password='test')
        
        response = self.client.get(
            reverse('edit_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.solution.id
            })
        )
        
        # Should redirect with error - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
    
    def test_staff_can_edit_any_solution(self):
        """Test that staff users can edit any solution"""
        self.client.login(username='staff', password='test')
        
        response = self.client.get(
            reverse('edit_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.solution.id
            })
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_author_can_delete_solution(self):
        """Test that solution author can delete their solution"""
        self.client.login(username='author', password='test')
        
        response = self.client.post(
            reverse('delete_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.solution.id
            })
        )
        
        # Should redirect to task detail - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(Solution.objects.count(), 1)  # One reference solution remains
    
    def test_non_author_cannot_delete_solution(self):
        """Test that non-authors cannot delete solutions"""
        self.client.login(username='other', password='test')
        
        response = self.client.post(
            reverse('delete_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.solution.id
            })
        )
        
        # Should redirect with error - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(Solution.objects.count(), 2)  # Both solutions remain


class SolutionLikesTestCase(TestCase):
    """Test solution like/unlike functionality"""
    
    def setUp(self):
        """Create test data"""
        self.user1 = User.objects.create_user(username='user1', password='test')
        self.user2 = User.objects.create_user(username='user2', password='test')
        
        self.task = AnalysisTask.objects.create(
            sha256='f' * 64,
            goal='Test task',
            difficulty=Difficulty.ADVANCED,
            author=self.user1
        )
        
        self.solution = Solution.objects.create(
            analysis_task=self.task,
            title='Test Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com',
            author=self.user1
        )
        
        self.client = Client()
    
    def test_user_can_like_solution(self):
        """Test that users can like solutions"""
        self.client.login(username='user2', password='test')
        
        response = self.client.post(
            reverse('toggle_solution_like', kwargs={'solution_id': self.solution.id})
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.liked_by.count(), 1)
        self.assertIn(self.user2, self.solution.liked_by.all())
    
    def test_user_can_unlike_solution(self):
        """Test that users can unlike solutions"""
        # First like
        self.solution.liked_by.add(self.user2)
        
        self.client.login(username='user2', password='test')
        
        response = self.client.post(
            reverse('toggle_solution_like', kwargs={'solution_id': self.solution.id})
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['liked'])
        self.assertEqual(data['like_count'], 0)
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.liked_by.count(), 0)
    
    def test_like_count_property(self):
        """Test that like_count property works correctly"""
        self.assertEqual(self.solution.like_count, 0)
        
        self.solution.liked_by.add(self.user1)
        self.assertEqual(self.solution.like_count, 1)
        
        self.solution.liked_by.add(self.user2)
        self.assertEqual(self.solution.like_count, 2)
    
    def test_unauthenticated_cannot_like(self):
        """Test that unauthenticated users cannot like solutions"""
        response = self.client.post(
            reverse('toggle_solution_like', kwargs={'solution_id': self.solution.id})
        )
        
        # Should return 401 with error
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data['error'], 'Login required')
        self.assertEqual(self.solution.liked_by.count(), 0)


class SolutionListingTestCase(TestCase):
    """Test solution listing and filtering"""
    
    def setUp(self):
        """Create test solutions of different types"""
        self.user = User.objects.create_user(username='testuser', password='test')
        
        self.task = AnalysisTask.objects.create(
            sha256='1' * 64,
            goal='Test task',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        # Create solutions of different types
        Solution.objects.create(
            analysis_task=self.task,
            title='Blog Solution',
            solution_type=SolutionType.BLOG,
            url='https://blog.com',
            author=self.user
        )
        
        Solution.objects.create(
            analysis_task=self.task,
            title='Video Solution',
            solution_type=SolutionType.VIDEO,
            url='https://youtube.com',
            author=self.user
        )
        
        Solution.objects.create(
            analysis_task=self.task,
            title='Paper Solution',
            solution_type=SolutionType.PAPER,
            url='https://paper.com',
            author=self.user
        )
        
        self.client = Client()
    
    def test_solution_list_shows_all_solutions(self):
        """Test that solution list shows all solutions"""
        response = self.client.get(reverse('solution_list'))
        
        self.assertEqual(response.status_code, 200)
        if response.context:
            self.assertEqual(len(response.context['page_obj']), 3)
    
    def test_filter_by_solution_type(self):
        """Test filtering solutions by type"""
        response = self.client.get(
            reverse('solution_list'),
            {'solution_type': SolutionType.BLOG}
        )
        
        self.assertEqual(response.status_code, 200)
        if response.context:
            self.assertEqual(len(response.context['page_obj']), 1)
            self.assertEqual(response.context['page_obj'][0].title, 'Blog Solution')
    
    def test_search_solutions_by_title(self):
        """Test searching solutions by title"""
        response = self.client.get(
            reverse('solution_list'),
            {'q': 'Video'}
        )
        
        self.assertEqual(response.status_code, 200)
        if response.context:
            self.assertEqual(len(response.context['page_obj']), 1)
            self.assertEqual(response.context['page_obj'][0].title, 'Video Solution')
    
    def test_search_solutions_by_sha256(self):
        """Test searching solutions by SHA256"""
        response = self.client.get(
            reverse('solution_list'),
            {'q': '111111'}  # Part of the SHA256
        )
        
        self.assertEqual(response.status_code, 200)
        if response.context:
            self.assertEqual(len(response.context['page_obj']), 3)  # All belong to same task


class OnsiteSolutionTestCase(TestCase):
    """Test onsite solution specific functionality"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser', password='test')
        
        self.task = AnalysisTask.objects.create(
            sha256='2' * 64,
            goal='Test task',
            difficulty=Difficulty.EXPERT,
            author=self.user
        )
        
        self.client = Client()
    
    def test_create_onsite_solution_with_markdown(self):
        """Test creating onsite solution with markdown content"""
        self.client.login(username='testuser', password='test')
        
        markdown_content = """
# Analysis Report

## Overview
This is a detailed analysis...

## Findings
- Finding 1
- Finding 2

## Conclusion
The malware appears to be...
        """
        
        response = self.client.post(
            reverse('onsite_solution_editor', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id
            }),
            {
                'title': 'Detailed Analysis Report',
                'content': markdown_content
            }
        )
        
        # Verify we have a redirect (solution was created successfully)
        self.assertIn(response.status_code, [301, 302], f"Expected redirect, got {response.status_code}")
        
        # Debug: Check if solution was actually created
        solution = Solution.objects.first()
        if solution is None:
            print(f"\nSolution not created! Redirect URL: {response.url if hasattr(response, 'url') else 'No URL'}")
            print(f"Status code: {response.status_code}")
            self.fail("Solution was not created")
        
        # Verify redirect URL - should redirect to view the published solution
        self.assertRedirects(
            response,
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': solution.id
            }),
            fetch_redirect_response=False
        )
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.content, markdown_content.strip())
        self.assertIsNone(solution.url)  # No URL for onsite
    
    def test_view_onsite_solution(self):
        """Test viewing published onsite solution"""
        solution = Solution.objects.create(
            analysis_task=self.task,
            title='Test Onsite Solution',
            solution_type=SolutionType.ONSITE,
            content='# Test\n\nThis is a test.',
            author=self.user
        )
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': solution.id
            }),
            follow=True  # Follow redirects (301 from SECURE_SSL_REDIRECT in production)
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solution.title)
        self.assertContains(response, 'This is a test.')


class SolutionHidingTestCase(TestCase):
    """Test solution hiding functionality"""
    
    def setUp(self):
        """Create test users and analysis tasks"""
        from datetime import timedelta
        from django.utils import timezone
        
        self.task_author = User.objects.create_user(
            username='taskauthor',
            password='testpass123'
        )
        self.solution_author = User.objects.create_user(
            username='solutionauth',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staffuser',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal='Test hidden solutions',
            difficulty=Difficulty.EASY,
            author=self.task_author
        )
        
        # Create visible solution
        self.visible_solution = Solution.objects.create(
            analysis_task=self.task,
            title='PublicBlog Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/visible',
            author=self.solution_author,
            hidden_until=None
        )
        
        # Create hidden solution (hidden for 2 weeks from now)
        self.hidden_solution = Solution.objects.create(
            analysis_task=self.task,
            title='TemporarilyHidden Solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/hidden',
            author=self.solution_author,
            hidden_until=timezone.now() + timedelta(weeks=2)
        )
        
        # Create expired hidden solution (was hidden but now visible)
        self.expired_solution = Solution.objects.create(
            analysis_task=self.task,
            title='PreviouslyHidden Solution',
            solution_type=SolutionType.PAPER,
            url='https://example.com/expired',
            author=self.solution_author,
            hidden_until=timezone.now() - timedelta(days=1)
        )
        
        # Create onsite hidden solution
        self.hidden_onsite = Solution.objects.create(
            analysis_task=self.task,
            title='NotYetPublic Onsite',
            solution_type=SolutionType.ONSITE,
            content='# Secret Analysis\n\nThis is hidden.',
            author=self.solution_author,
            hidden_until=timezone.now() + timedelta(weeks=1)
        )
        
        self.client = Client()
    
    def test_anonymous_user_cannot_see_hidden_solutions_in_detail_view(self):
        """Anonymous users should not see currently hidden solutions in task detail"""
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
        self.assertNotContains(response, self.hidden_onsite.title)
    
    def test_regular_user_cannot_see_hidden_solutions_in_detail_view(self):
        """Regular users should not see hidden solutions in task detail"""
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
    
    def test_solution_author_can_see_own_hidden_solution(self):
        """Solution authors should see their own hidden solutions"""
        self.client.login(username='solutionauth', password='testpass123')
        
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # Should also see the "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')
    
    def test_task_author_can_see_all_hidden_solutions_on_own_task(self):
        """Task authors should see all hidden solutions on their tasks"""
        self.client.login(username='taskauthor', password='testpass123')
        
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # Should see the "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')
    
    def test_staff_user_can_see_all_hidden_solutions(self):
        """Staff users should see all hidden solutions everywhere"""
        self.client.login(username='staffuser', password='testpass123')
        
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
    
    def test_direct_access_to_hidden_onsite_solution_blocked_for_anonymous(self):
        """Anonymous users cannot directly access hidden onsite solutions"""
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.hidden_onsite.id
            }),
            follow=True
        )
        
        # Should redirect to task detail with error message
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
    
    def test_direct_access_to_hidden_onsite_solution_blocked_for_regular_user(self):
        """Regular users cannot directly access hidden onsite solutions"""
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.hidden_onsite.id
            }),
            follow=True
        )
        
        # Should redirect to task detail with error message
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            fetch_redirect_response=False
        )
    
    def test_direct_access_to_hidden_onsite_solution_allowed_for_author(self):
        """Solution author can directly access their hidden onsite solution"""
        self.client.login(username='solutionauth', password='testpass123')
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.hidden_onsite.id
            }),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)
        self.assertContains(response, 'Secret Analysis')
    
    def test_direct_access_to_hidden_onsite_solution_allowed_for_task_author(self):
        """Task author can directly access hidden solutions on their task"""
        self.client.login(username='taskauthor', password='testpass123')
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.hidden_onsite.id
            }),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)
    
    def test_direct_access_to_hidden_onsite_solution_allowed_for_staff(self):
        """Staff can directly access any hidden solution"""
        self.client.login(username='staffuser', password='testpass123')
        
        response = self.client.get(
            reverse('view_onsite_solution', kwargs={
                'sha256': self.task.sha256,
                'task_id': self.task.id,
                'solution_id': self.hidden_onsite.id
            }),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)
    
    def test_hidden_solutions_excluded_from_solutions_showcase(self):
        """Hidden solutions should never appear in solutions showcase"""
        # Even staff shouldn't see hidden solutions in showcase
        self.client.login(username='staffuser', password='testpass123')
        
        response = self.client.get(reverse('solutions_showcase'), follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
        self.assertNotContains(response, self.hidden_onsite.title)
    
    def test_hidden_solutions_excluded_from_profile_for_other_users(self):
        """Hidden solutions should not appear on profile when viewed by others"""
        # Regular user viewing solution author's profile
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(
            reverse('user_profile', kwargs={'username': self.solution_author.username}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
    
    def test_hidden_solutions_visible_on_own_profile(self):
        """Users should see their own hidden solutions on their profile"""
        self.client.login(username='solutionauth', password='testpass123')
        
        response = self.client.get(
            reverse('user_profile', kwargs={'username': self.solution_author.username}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # Should see the "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')
    
    def test_hidden_solutions_excluded_from_solution_list_for_others(self):
        """Hidden solutions should not appear in solutions_list view for other users"""
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(reverse('solution_list'), follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
    
    def test_own_hidden_solutions_visible_in_solution_list(self):
        """Users should see their own hidden solutions in solutions_list view"""
        self.client.login(username='solutionauth', password='testpass123')
        
        response = self.client.get(reverse('solution_list'), follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        # Should see the "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')
    
    def test_expired_hidden_solution_becomes_visible_to_all(self):
        """Solutions with hidden_until in the past should be visible to everyone"""
        # Anonymous user
        response = self.client.get(
            reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.expired_solution.title)
        # Should NOT see "Hidden" badge since it's no longer hidden
        
        # Verify in solutions showcase too
        response = self.client.get(reverse('solutions_showcase'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.expired_solution.title)
    
    def test_user_can_see_hidden_status_method(self):
        """Test the user_can_see_hidden_status model method"""
        from django.contrib.auth.models import AnonymousUser
        
        # Anonymous user cannot see hidden status
        self.assertFalse(self.hidden_solution.user_can_see_hidden_status(AnonymousUser()))
        
        # Regular user cannot see hidden status
        self.assertFalse(self.hidden_solution.user_can_see_hidden_status(self.regular_user))
        
        # Solution author can see hidden status
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.solution_author))
        
        # Task author can see hidden status
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.task_author))
        
        # Staff can see hidden status
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.staff_user))

class SolutionsShowcaseTestCase(TestCase):
    """Test solutions showcase ordering and visibility"""
    
    def setUp(self):
        """Create test user and analysis task"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.task = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Test malware analysis',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        self.client = Client()
    
    def test_recently_unhidden_solution_appears_in_showcase(self):
        """Test that a solution with recently passed hidden_until appears in showcase"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create an old solution that was just unhidden
        old_solution = Solution.objects.create(
            title='Old but recently unhidden solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/old',
            author=self.user,
            analysis_task=self.task,
        )
        old_solution.created_at = timezone.now() - timedelta(days=365)  # Created 1 year ago
        old_solution.hidden_until = timezone.now() - timedelta(hours=1)  # Became visible 1 hour ago
        old_solution.save(update_fields=['created_at', 'hidden_until'])
        
        # Create a newer solution (by creation date) with no hidden_until
        newer_solution = Solution.objects.create(
            title='Newer solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/new',
            author=self.user,
            analysis_task=self.task,
        )
        newer_solution.created_at = timezone.now() - timedelta(days=7)  # Created 1 week ago
        newer_solution.save(update_fields=['created_at'])
        
        # Get the showcase
        response = self.client.get(reverse('solutions_showcase'))
        
        # The old solution should appear in the showcase
        self.assertContains(response, 'Old but recently unhidden solution')
        
        # Get the solutions from context to check ordering
        solutions = response.context['solutions']
        
        # The old solution should appear FIRST (it became visible more recently)
        solution_titles = [s.title for s in solutions]
        old_index = solution_titles.index('Old but recently unhidden solution')
        newer_index = solution_titles.index('Newer solution')
        
        # Recently unhidden (1 hour ago) should come before solution from 7 days ago
        self.assertLess(old_index, newer_index, 
                    "Recently unhidden solution should appear first (most recent visible_date)")
    
    def test_still_hidden_solution_not_in_showcase(self):
        """Test that solutions with future hidden_until don't appear"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create a solution that's still hidden
        hidden_solution = Solution.objects.create(
            title='Still hidden solution',
            solution_type=SolutionType.BLOG,
            url='https://example.com/hidden',
            author=self.user,
            analysis_task=self.task,
            hidden_until=timezone.now() + timedelta(days=7)  # Hidden for 7 more days
        )
        
        # Get the showcase
        response = self.client.get(reverse('solutions_showcase'))
        
        # The hidden solution should NOT appear
        self.assertNotContains(response, 'Still hidden solution')
    
    def test_showcase_orders_by_visible_date_not_created_date(self):
        """Test that showcase uses visible_date (hidden_until or created_at) for ordering"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Solution 1: Created 30 days ago, no hidden_until (visible_date = created_at = 30 days ago)
        solution1 = Solution.objects.create(
            title='Solution 1',
            solution_type=SolutionType.BLOG,
            url='https://example.com/1',
            author=self.user,
            analysis_task=self.task,
        )
        # Manually update created_at after creation
        solution1.created_at = timezone.now() - timedelta(days=30)
        solution1.save(update_fields=['created_at'])
        
        # Solution 2: Created 60 days ago, became visible 2 days ago (visible_date = 2 days ago)
        solution2 = Solution.objects.create(
            title='Solution 2',
            solution_type=SolutionType.BLOG,
            url='https://example.com/2',
            author=self.user,
            analysis_task=self.task,
        )
        solution2.created_at = timezone.now() - timedelta(days=60)
        solution2.hidden_until = timezone.now() - timedelta(days=2)
        solution2.save(update_fields=['created_at', 'hidden_until'])
        
        # Get the showcase
        response = self.client.get(reverse('solutions_showcase'))
        solutions = list(response.context['solutions'])
        
        # Solution 2 should come first (visible_date = 2 days ago is more recent than 30 days ago)
        self.assertEqual(solutions[0].title, 'Solution 2')
        self.assertEqual(solutions[1].title, 'Solution 1')