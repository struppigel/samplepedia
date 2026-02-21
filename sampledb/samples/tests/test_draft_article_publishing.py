"""
Tests for draft article selection and publishing functionality

This test suite covers:
1. Form validation for draft selection in task submission
2. Task submission with draft article as reference solution
3. Draft ownership and published status validation
4. Article list view button states (enabled/disabled)
5. Prevention of unpublishing/deleting last reference solution
6. Full integration flow: create draft -> submit task -> verify solution
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group, Permission
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from samples.models import AnalysisTask, Solution, Article, SolutionType, Difficulty, Platform
from samples.forms import AnalysisTaskForm


class DraftSelectionFormTestCase(TestCase):
    """Test form validation for draft article selection in task submission"""
    
    def setUp(self):
        """Create test users and draft articles"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@test.com',
            password='testpass123'
        )
        
        # Create unpublished draft for user
        self.draft = Article.objects.create(
            title='My Draft Article',
            content='# Draft Content\n\nThis is a draft.',
            author=self.user
        )
        
        # Create published article (attached to a solution)
        self.published_article = Article.objects.create(
            title='Published Article',
            content='# Published Content',
            author=self.user
        )
        
        # Create a task and solution to mark article as published
        task = AnalysisTask.objects.create(
            sha256='b' * 64,
            goal='Test task',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        Solution.objects.create(
            title='Published Article',
            solution_type=SolutionType.ONSITE,
            author=self.user,
            analysis_task=task,
            article=self.published_article
        )
        
        # Create draft for other user
        self.other_draft = Article.objects.create(
            title='Other User Draft',
            content='# Other Content',
            author=self.other_user
        )
    
    def test_form_accepts_valid_draft_article(self):
        """Form should accept a valid unpublished draft owned by the user"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_draft_article_id': self.draft.id,
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        self.assertEqual(form.cleaned_data['_draft_article'], self.draft)
    
    def test_form_rejects_draft_not_owned_by_user(self):
        """Form should reject draft articles not owned by the submitting user"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_draft_article_id': self.other_draft.id,  # Other user's draft
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('You can only use your own draft articles', str(form.errors))
    
    def test_form_rejects_already_published_draft(self):
        """Form should reject draft articles that are already published"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_draft_article_id': self.published_article.id,
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('already published', str(form.errors))
    
    def test_form_accepts_draft_without_manual_fields(self):
        """Form should not require manual solution fields when draft is provided"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_draft_article_id': self.draft.id,
            # No reference_solution_title, reference_solution_type, etc.
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
    
    def test_form_requires_reference_when_no_draft(self):
        """Form should require manual reference solution when no draft is provided"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            # No reference_draft_article_id and no manual solution fields
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('You must provide a reference solution', str(form.errors))
    
    def test_form_accepts_manual_solution_without_draft(self):
        """Form should accept manual solution fields when no draft is provided"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Blog Post',
            'reference_solution_type': 'blog',  # Use string value, not enum
            'reference_solution_url': 'https://example.com/writeup',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
    
    def test_form_rejects_nonexistent_draft_id(self):
        """Form should reject draft IDs that don't exist"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('a' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_draft_article_id': 99999,  # Non-existent ID
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('does not exist', str(form.errors))


class TaskSubmissionWithDraftTestCase(TestCase):
    """Test task submission view with draft article selection"""
    
    def setUp(self):
        """Create test users and draft articles"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.draft = Article.objects.create(
            title='My Analysis Writeup',
            content='# Detailed Analysis\n\nThis is my analysis content.',
            author=self.user
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_submit_task_with_draft_creates_solution(self):
        """Submitting a task with a draft should create a solution with the draft attached"""
        form_data = {
            'sha256': 'c' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('c' * 64) + '/',
            'description': 'Malware sample analysis task',
            'goal': 'Identify the malware family and IOCs',
            'difficulty': Difficulty.MEDIUM,
            'platform': Platform.WINDOWS,
            'tags': 'ransomware, windows',
            'tools': 'ghidra, x64dbg',
            'reference_draft_article_id': self.draft.id,
        }
        
        response = self.client.post(reverse('submit_task'), form_data)
        
        # Verify redirect (task was created)
        self.assertEqual(response.status_code, 302)
        
        # Verify task was created
        self.assertEqual(AnalysisTask.objects.count(), 1)
        task = AnalysisTask.objects.first()
        self.assertEqual(task.sha256, 'c' * 64)
        self.assertEqual(task.author, self.user)
        
        # Verify solution was created with draft attached
        self.assertEqual(Solution.objects.count(), 1)
        solution = Solution.objects.first()
        self.assertEqual(solution.title, self.draft.title)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.article, self.draft)
        self.assertEqual(solution.author, self.user)
        self.assertEqual(solution.analysis_task, task)
        
        # Verify draft is now marked as published
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.is_published())
    
    def test_submit_task_with_draft_redirects_to_detail(self):
        """After submitting with draft, should redirect to task detail page"""
        form_data = {
            'sha256': 'd' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('d' * 64) + '/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ida',
            'reference_draft_article_id': self.draft.id,
        }
        
        response = self.client.post(reverse('submit_task'), form_data)
        
        task = AnalysisTask.objects.first()
        expected_url = reverse('sample_detail', kwargs={
            'sha256': task.sha256,
            'task_id': task.id
        })
        
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
    
    def test_draft_cannot_be_published_twice(self):
        """A draft that's already published cannot be used again"""
        # First submission
        form_data_1 = {
            'sha256': 'e' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('e' * 64) + '/',
            'description': 'First task',
            'goal': 'First goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ida',
            'reference_draft_article_id': self.draft.id,
        }
        
        response_1 = self.client.post(reverse('submit_task'), form_data_1)
        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)
        
        # Attempt second submission with same draft
        form_data_2 = {
            'sha256': '0' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('0' * 64) + '/',
            'description': 'Second task',
            'goal': 'Second goal',
            'difficulty': Difficulty.MEDIUM,
            'platform': Platform.LINUX,
            'tags': 'test2',
            'tools': 'ghidra',
            'reference_draft_article_id': self.draft.id,  # Same draft
        }
        
        response_2 = self.client.post(reverse('submit_task'), form_data_2)
        
        # Should fail validation
        self.assertEqual(response_2.status_code, 200)  # Form redisplayed
        self.assertContains(response_2, 'already published')
        
        # No new task or solution created
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)
    
    def test_submit_task_with_manual_solution_still_works(self):
        """Traditional manual solution submission should still work"""
        form_data = {
            'sha256': 'f' * 64,  # Use 'f' instead of 'g' (g is not a hex digit)
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('f' * 64) + '/',
            'description': 'Test task',
            'goal': 'Test goal',
            'difficulty': Difficulty.ADVANCED,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'radare2',
            'reference_solution_title': 'My Blog Post',
            'reference_solution_type': 'blog',  # Use string value, not enum
            'reference_solution_url': 'https://myblog.com/analysis',
        }
        
        response = self.client.post(reverse('submit_task'), form_data)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)
        
        solution = Solution.objects.first()
        self.assertEqual(solution.title, 'My Blog Post')
        self.assertEqual(solution.solution_type, SolutionType.BLOG)
        self.assertEqual(solution.url, 'https://myblog.com/analysis')
        self.assertIsNone(solution.article)  # No article attached


class ArticleListButtonStatesTestCase(TestCase):
    """Test article list view button states and last reference protection"""
    
    def setUp(self):
        """Create test users, tasks, and articles"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # Create task
        self.task = AnalysisTask.objects.create(
            sha256='1' * 64,
            goal='Test task',
            difficulty=Difficulty.MEDIUM,
            author=self.user
        )
        
        # Create article with only one solution (last reference)
        self.article_last_ref = Article.objects.create(
            title='Only Solution',
            content='# Content',
            author=self.user
        )
        self.solution_last_ref = Solution.objects.create(
            title='Only Solution',
            solution_type=SolutionType.ONSITE,
            author=self.user,
            analysis_task=self.task,
            article=self.article_last_ref
        )
        
        # Create second task with multiple solutions (not last reference)
        task2 = AnalysisTask.objects.create(
            sha256='2' * 64,
            goal='Second task',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        # First article/solution for task2
        self.article_multi_ref_1 = Article.objects.create(
            title='Solution 1',
            content='# Content 1',
            author=self.user
        )
        self.solution_multi_ref_1 = Solution.objects.create(
            title='Solution 1',
            solution_type=SolutionType.ONSITE,
            author=self.user,
            analysis_task=task2,
            article=self.article_multi_ref_1
        )
        
        # Second article/solution for task2 
        self.article_multi_ref_2 = Article.objects.create(
            title='Solution 2',
            content='# Content 2',
            author=self.user
        )
        self.solution_multi_ref_2 = Solution.objects.create(
            title='Solution 2',
            solution_type=SolutionType.ONSITE,
            author=self.user,
            analysis_task=task2,
            article=self.article_multi_ref_2
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_article_list_shows_task_column_for_published(self):
        """Article list should show task SHA256 link for published articles"""
        response = self.client.get(reverse('article_list'))
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain SHA256 link for published article
        self.assertContains(response, self.task.sha256[:8])  # First 8 chars
        self.assertContains(response, reverse('sample_detail', kwargs={
            'sha256': self.task.sha256,
            'task_id': self.task.id
        }))
    
    def test_last_reference_buttons_are_disabled(self):
        """Unpublish and delete buttons should be disabled for last reference solutions"""
        response = self.client.get(reverse('article_list'))
        
        self.assertEqual(response.status_code, 200)
        
        # Check for disabled button indicators (muted text with lock icon)
        content = response.content.decode('utf-8')
        
        # Should contain lock icon for disabled buttons
        self.assertIn('fa-lock', content)
        self.assertIn('text-muted', content)
        self.assertIn('Cannot unpublish the last reference solution', content)
        self.assertIn('Cannot delete the last reference solution', content)
    
    def test_multi_reference_buttons_are_enabled(self):
        """Unpublish and delete buttons should be enabled for non-last reference solutions"""
        response = self.client.get(reverse('article_list'))
        
        self.assertEqual(response.status_code, 200)
        
        # Check for enabled button styles (colored btn-link)
        content = response.content.decode('utf-8')
        
        # Should contain colored action buttons (not all disabled)
        self.assertIn('text-warning', content)  # Unpublish button
        self.assertIn('text-danger', content)   # Delete button
        self.assertIn('fa-undo', content)       # Unpublish icon (enabled)
        self.assertIn('fa-trash', content)      # Delete icon (enabled)
    
    def test_cannot_unpublish_last_reference_via_post(self):
        """Attempting to unpublish the last reference should fail"""
        unpublish_url = reverse('article_unpublish', kwargs={
            'article_id': self.article_last_ref.id
        })
        
        response = self.client.post(unpublish_url)
        
        # Should redirect back to article list
        self.assertEqual(response.status_code, 302)
        
        # Solution should still exist
        self.assertTrue(
            Solution.objects.filter(article=self.article_last_ref).exists()
        )
        
        # Article should still be published
        self.article_last_ref.refresh_from_db()
        self.assertTrue(self.article_last_ref.is_published())
    
    def test_cannot_delete_last_reference_via_post(self):
        """Attempting to delete article with last reference should fail"""
        delete_url = reverse('article_delete', kwargs={
            'article_id': self.article_last_ref.id
        })
        
        response = self.client.post(delete_url)
        
        # Should redirect back to article list
        self.assertEqual(response.status_code, 302)
        
        # Article should still exist
        self.assertTrue(Article.objects.filter(id=self.article_last_ref.id).exists())
        
        # Solution should still exist
        self.assertTrue(
            Solution.objects.filter(article=self.article_last_ref).exists()
        )
    
    def test_can_unpublish_non_last_reference(self):
        """Should be able to unpublish article when task has multiple solutions"""
        # Unpublish first article from task2 (which has 2 solutions)
        unpublish_url = reverse('article_unpublish', kwargs={
            'article_id': self.article_multi_ref_1.id
        })
        
        response = self.client.post(unpublish_url, {
            'solution_id': self.solution_multi_ref_1.id
        })
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # First solution should be deleted
        self.assertFalse(
            Solution.objects.filter(id=self.solution_multi_ref_1.id).exists()
        )
        
        # Second solution should still exist
        self.assertTrue(
            Solution.objects.filter(id=self.solution_multi_ref_2.id).exists()
        )
        
        # First article should no longer be published
        self.article_multi_ref_1.refresh_from_db()
        self.assertFalse(self.article_multi_ref_1.is_published())


class DraftPublishingIntegrationTestCase(TestCase):
    """Integration tests for the full draft publishing workflow"""
    
    def setUp(self):
        """Create test user"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_full_workflow_create_draft_to_publish(self):
        """Test complete workflow: create draft -> submit task with draft -> verify solution"""
        
        # Step 1: Create a draft article
        draft = Article.objects.create(
            title='Complete Malware Analysis',
            content='# Introduction\n\nThis is my complete analysis...',
            author=self.user
        )
        
        self.assertFalse(draft.is_published())
        self.assertEqual(draft.view_count, 0)
        
        # Step 2: Submit a new task with the draft as reference
        task_data = {
            'sha256': '3' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/' + ('3' * 64) + '/',
            'description': 'Emotet banking trojan sample',
            'goal': 'Analyze C2 communication and identify IOCs',
            'difficulty': Difficulty.EXPERT,
            'platform': Platform.WINDOWS,
            'tags': 'emotet, banking, trojan',
            'tools': 'ghidra, wireshark, procmon',
            'reference_draft_article_id': draft.id,
        }
        
        response = self.client.post(reverse('submit_task'), task_data)
        self.assertEqual(response.status_code, 302)
        
        # Step 3: Verify task was created
        task = AnalysisTask.objects.get(sha256='3' * 64)
        self.assertEqual(task.goal, 'Analyze C2 communication and identify IOCs')
        self.assertEqual(task.difficulty, Difficulty.EXPERT)
        self.assertEqual(task.author, self.user)
        
        # Step 4: Verify solution was created and linked to draft
        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.title, draft.title)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.article, draft)
        self.assertEqual(solution.author, self.user)
        
        # Step 5: Verify draft is now published
        draft.refresh_from_db()
        self.assertTrue(draft.is_published())
        self.assertEqual(draft.solution, solution)
        
        # Step 6: Verify task detail page shows the solution
        detail_url = reverse('sample_detail', kwargs={
            'sha256': task.sha256,
            'task_id': task.id
        })
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, draft.title)
        
        # Step 7: Verify solution can be viewed
        solution_url = reverse('view_onsite_solution', kwargs={
            'sha256': task.sha256,
            'task_id': task.id,
            'solution_id': solution.id
        })
        response = self.client.get(solution_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, draft.title)
        self.assertContains(response, 'complete analysis')  # Check for content (lowercase)
    
    def test_draft_appears_in_ajax_endpoint(self):
        """Test that unpublished drafts appear in the AJAX endpoint"""
        # Create draft
        draft1 = Article.objects.create(
            title='Unpublished Draft 1',
            content='Content 1',
            author=self.user
        )
        draft2 = Article.objects.create(
            title='Unpublished Draft 2',
            content='Content 2',
            author=self.user
        )
        
        # Create published article
        published = Article.objects.create(
            title='Published Article',
            content='Content',
            author=self.user
        )
        task = AnalysisTask.objects.create(
            sha256='4' * 64,
            goal='Test',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        Solution.objects.create(
            title='Published Article',
            solution_type=SolutionType.ONSITE,
            author=self.user,
            analysis_task=task,
            article=published
        )
        
        # Call AJAX endpoint
        response = self.client.get(reverse('get_user_drafts_ajax'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data['results']), 2)
        
        # Verify draft titles are in response
        draft_titles = [d['title'] for d in data['results']]
        self.assertIn('Unpublished Draft 1', draft_titles)
        self.assertIn('Unpublished Draft 2', draft_titles)
        self.assertNotIn('Published Article', draft_titles)
    
    def test_staff_can_submit_without_draft_or_manual_solution(self):
        """Staff users should be able to submit tasks without any reference solution"""
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        
        self.client.login(username='staffuser', password='testpass123')
        
        task_data = {
            'sha256': '5' * 64,
            'download_link': 'https://example.com/malware.exe',  # Staff can use any URL
            'description': 'Staff submitted task',
            'goal': 'No solution required',
            'difficulty': Difficulty.MEDIUM,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ida',
            # No reference_draft_article_id
            # No reference_solution_title, etc.
        }
        
        response = self.client.post(reverse('submit_task'), task_data)
        self.assertEqual(response.status_code, 302)
        
        # Task created
        task = AnalysisTask.objects.get(sha256='5' * 64)
        self.assertEqual(task.author, staff_user)
        
        # No solution created
        self.assertEqual(Solution.objects.filter(analysis_task=task).count(), 0)
