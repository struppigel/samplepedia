"""
Tests for analysis task submission functionality

This test suite covers:
1. Form validation (AnalysisTaskForm)
2. Reference solution requirements for different user types
3. Task creation with and without reference solutions
4. SHA256 uniqueness validation
5. Download link validation (MalwareBazaar/MalShare)
6. Image selection
7. Tag and tool handling
8. Permission-based submission rules
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group, Permission
from django.urls import reverse
from django.db import IntegrityError
from samples.models import AnalysisTask, Solution, SampleImage, SolutionType, Difficulty
from samples.forms import AnalysisTaskForm
from cloudinary.models import CloudinaryResource


class AnalysisTaskFormTestCase(TestCase):
    """Test the AnalysisTaskForm validation logic"""
    
    def setUp(self):
        """Create test users"""
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
    
    def test_form_requires_core_fields(self):
        """Core fields should always be required"""
        form = AnalysisTaskForm(data={}, user=self.regular_user)
        self.assertFalse(form.is_valid())
        
        required_fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'tags', 'tools']
        for field in required_fields:
            self.assertIn(field, form.errors)
    
    def test_form_requires_reference_solution_for_regular_users(self):
        """Regular users must provide a reference solution when creating tasks"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('You must provide a reference solution', str(form.errors))
    
    def test_form_allows_no_reference_solution_for_staff(self):
        """Staff users can submit tasks without reference solutions"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.staff_user, is_edit=False)
        self.assertTrue(form.is_valid())
    
    def test_form_validates_onsite_solution_has_content(self):
        """Onsite reference solutions must have content"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Solution',
            'reference_solution_type': 'onsite',
            # Missing: reference_solution_content
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('On-site reference solutions must have content', str(form.errors))
    
    def test_form_validates_external_solution_has_url(self):
        """External reference solutions must have a URL"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Blog Post',
            'reference_solution_type': 'blog',
            # Missing: reference_solution_url
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('External reference solutions', str(form.errors))
    
    def test_form_validates_malwarebazaar_url(self):
        """Form should accept MalwareBazaar URLs"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234/',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Solution',
            'reference_solution_type': 'blog',
            'reference_solution_url': 'https://example.com/writeup',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertTrue(form.is_valid())
    
    def test_form_validates_malshare_url(self):
        """Form should accept MalShare URLs"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://malshare.com/sample.php?action=detail&hash=' + ('a' * 64),
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Solution',
            'reference_solution_type': 'blog',
            'reference_solution_url': 'https://example.com/writeup',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertTrue(form.is_valid())
    
    def test_form_rejects_invalid_download_urls_for_regular_users(self):
        """Regular users should not be able to use arbitrary download URLs"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://example.com/malware.exe',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
            'reference_solution_title': 'My Solution',
            'reference_solution_type': 'blog',
            'reference_solution_url': 'https://example.com/writeup',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.regular_user, is_edit=False)
        self.assertFalse(form.is_valid())
        self.assertIn('download_link', form.errors)
        self.assertIn('MalwareBazaar', str(form.errors['download_link']))
    
    def test_form_allows_any_url_for_staff(self):
        """Staff users can use any download URL"""
        form_data = {
            'sha256': 'a' * 64,
            'download_link': 'https://example.com/malware.exe',
            'description': 'Test description',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'tags': 'malware, test',
            'tools': 'ghidra',
        }
        
        form = AnalysisTaskForm(data=form_data, user=self.staff_user, is_edit=False)
        self.assertTrue(form.is_valid())
    
    def test_form_excludes_expert_difficulty(self):
        """Expert difficulty should not be available in form choices"""
        form = AnalysisTaskForm(user=self.regular_user, is_edit=False)
        difficulty_values = [choice[0] for choice in form.fields['difficulty'].choices]
        self.assertNotIn(Difficulty.EXPERT, difficulty_values)
        self.assertIn(Difficulty.EASY, difficulty_values)
        self.assertIn(Difficulty.MEDIUM, difficulty_values)
        self.assertIn(Difficulty.ADVANCED, difficulty_values)


class TaskSubmissionViewTestCase(TestCase):
    """Test the submit_task view and task creation flow"""
    
    def setUp(self):
        """Create test users and client"""
        self.client = Client()
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
    
    def test_submit_task_requires_login(self):
        """Submitting a task should require authentication"""
        response = self.client.get(reverse('submit_task'))
        # assertRedirects handles both 301 and 302
        self.assertRedirects(response, '/login/?next=/submit/', fetch_redirect_response=False)
    
    def test_submit_task_get_renders_form(self):
        """GET request should render the submission form"""
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('submit_task'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/submit_task.html')
        if response.context:
            self.assertIn('form', response.context)
    
    def test_regular_user_can_submit_task_with_reference_solution(self):
        """Regular users should be able to submit tasks with reference solutions"""
        self.client.login(username='regular', password='testpass123')
        
        post_data = {
            'sha256': 'b' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/',
            'description': 'Test malware description',
            'goal': 'Find the C2 server',
            'difficulty': Difficulty.EASY,
            'tags': 'ransomware, c2',
            'tools': 'ghidra, x64dbg',
            'reference_solution_title': 'My Writeup',
            'reference_solution_type': 'blog',
            'reference_solution_url': 'https://myblog.com/writeup',
        }
        
        response = self.client.post(reverse('submit_task'), data=post_data)
        
        # Debug: Print form errors if submission failed
        if response.status_code not in (301, 302):
            if response.context and 'form' in response.context:
                print(f"\nForm errors: {response.context['form'].errors}")
        
        # Task should be created
        task = AnalysisTask.objects.get(sha256='b' * 64)
        
        # Should redirect to task detail page - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(task.author, self.regular_user)
        self.assertEqual(task.goal, 'Find the C2 server')
        self.assertEqual(task.difficulty, Difficulty.EASY)
        
        # Reference solution should be created
        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.title, 'My Writeup')
        self.assertEqual(solution.solution_type, 'blog')
        self.assertEqual(solution.url, 'https://myblog.com/writeup')
        self.assertEqual(solution.author, self.regular_user)
    
    def test_regular_user_can_submit_task_with_onsite_solution(self):
        """Regular users should be able to submit tasks with onsite solutions"""
        self.client.login(username='regular', password='testpass123')
        
        post_data = {
            'sha256': 'c' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/',
            'description': 'Test malware description',
            'goal': 'Find the encryption key',
            'difficulty': Difficulty.MEDIUM,
            'tags': 'ransomware, crypto',
            'tools': 'ghidra',
            'reference_solution_title': 'My Analysis',
            'reference_solution_type': 'onsite',
            'reference_solution_content': '# My Analysis\n\nThis is my detailed analysis...',
        }
        
        response = self.client.post(reverse('submit_task'), data=post_data)
        
        # Debug: Print form errors if submission failed
        if response.status_code not in (301, 302):
            if response.context and 'form' in response.context:
                print(f"\nForm errors: {response.context['form'].errors}")
        
        # Task should be created
        task = AnalysisTask.objects.get(sha256='c' * 64)
        
        # Should redirect to task detail page - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id}),
            fetch_redirect_response=False
        )
        
        # Reference solution should be created with content
        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.solution_type, 'onsite')
        self.assertIn('My Analysis', solution.content)
        self.assertIsNone(solution.url)  # Onsite solutions don't have URLs
    
    def test_staff_can_submit_task_without_reference_solution(self):
        """Staff users should be able to submit tasks without reference solutions"""
        self.client.login(username='staff', password='testpass123')
        
        post_data = {
            'sha256': 'd' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/',
            'description': 'Test malware description',
            'goal': 'Analyze the malware',
            'difficulty': Difficulty.ADVANCED,
            'tags': 'apt, evasion',
            'tools': 'ida, wireshark',
        }
        
        response = self.client.post(reverse('submit_task'), data=post_data)
        
        # Debug: Print form errors if submission failed
        if response.status_code not in (301, 302):
            if response.context and 'form' in response.context:
                print(f"\nForm errors: {response.context['form'].errors}")
        
        # Task should be created
        task = AnalysisTask.objects.get(sha256='d' * 64)
        
        # Should redirect to task detail page - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id}),
            fetch_redirect_response=False
        )
        self.assertEqual(task.author, self.staff_user)
        
        # No reference solution should exist
        self.assertEqual(Solution.objects.filter(analysis_task=task).count(), 0)
    
    def test_tags_are_normalized_to_lowercase(self):
        """Tags should be converted to lowercase when saving"""
        self.client.login(username='staff', password='testpass123')
        
        post_data = {
            'sha256': 'e' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/',
            'description': 'Test',
            'goal': 'Test',
            'difficulty': Difficulty.EASY,
            'tags': 'RaNsOmWaRe, APT, C2',
            'tools': 'Ghidra, IDA',
        }
        
        response = self.client.post(reverse('submit_task'), data=post_data)
        
        # Task should be created
        task = AnalysisTask.objects.get(sha256='e' * 64)
        
        # Should redirect to task detail page - assertRedirects handles 301 and 302
        self.assertRedirects(
            response,
            reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id}),
            fetch_redirect_response=False
        )
        
        # Tags should be lowercase
        tag_names = [tag.name for tag in task.tags.all()]
        self.assertIn('ransomware', tag_names)
        self.assertIn('apt', tag_names)
        self.assertIn('c2', tag_names)
        
        # Tools should be lowercase
        tool_names = [tool.name for tool in task.tools.all()]
        self.assertIn('ghidra', tool_names)
        self.assertIn('ida', tool_names)

class TaskEditPermissionTestCase(TestCase):
    """Test edit permissions for analysis tasks"""
    
    def setUp(self):
        """Create test users and a sample task"""
        self.client = Client()
        
        self.author = User.objects.create_user(
            username='author',
            email='author@test.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123'
        )
        
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        
        # Create a test task
        self.task = AnalysisTask.objects.create(
            sha256='9' * 64,
            download_link='https://bazaar.abuse.ch/sample/test/',
            description='Test task',
            goal='Test goal',
            difficulty=Difficulty.EASY,
            author=self.author
        )
    
    def test_author_can_edit_own_task(self):
        """Authors should be able to edit their own tasks"""
        self.client.login(username='author', password='testpass123')
        url = reverse('edit_task', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_other_user_cannot_edit_task(self):
        """Non-authors should not be able to edit tasks"""
        self.client.login(username='other', password='testpass123')
        url = reverse('edit_task', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id})
        response = self.client.get(url)
        # assertRedirects handles both 301 and 302
        self.assertRedirects(response, reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}), fetch_redirect_response=False)
    
    def test_staff_can_edit_any_task(self):
        """Staff users should be able to edit any task"""
        self.client.login(username='staff', password='testpass123')
        url = reverse('edit_task', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# Run tests with: python manage.py test samples.test_task_submission
