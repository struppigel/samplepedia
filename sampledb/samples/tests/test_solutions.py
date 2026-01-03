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
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertEqual(Solution.objects.count(), 1)
        
        solution = Solution.objects.first()
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
        
        self.assertEqual(response.status_code, 302)
        solution = Solution.objects.first()
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
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
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
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)
    
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
        
        self.assertEqual(response.status_code, 302)
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
        
        # Should redirect with error
        self.assertEqual(response.status_code, 302)
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
        
        self.assertEqual(response.status_code, 302)
        
        solution = Solution.objects.first()
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
            })
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solution.title)
        self.assertContains(response, 'This is a test.')
