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

from django.urls import reverse

from samples.forms import AnalysisTaskForm
from samples.models import AnalysisTask, Difficulty, Platform, Solution
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_staff, make_task, make_user

# A complete new-task submission without a reference solution
FORM_DATA = {
    'sha256': 'a' * 64,
    'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
    'description': 'Test description',
    'goal': 'Test goal',
    'difficulty': Difficulty.EASY,
    'platform': Platform.WINDOWS,
    'tags': 'malware, test',
    'tools': 'ghidra',
}

# A valid external reference solution
BLOG_REFERENCE = {
    'reference_solution_title': 'My Solution',
    'reference_solution_type': 'blog',
    'reference_solution_url': 'https://example.com/writeup',
}


def detail_url(task):
    return reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id})


def edit_url(task):
    return reverse('edit_task', kwargs={'sha256': task.sha256, 'task_id': task.id})


class AnalysisTaskFormTestCase(SampleTestCase):
    """Test the AnalysisTaskForm validation logic"""

    @classmethod
    def setUpTestData(cls):
        cls.regular_user = make_user()
        cls.staff_user = make_staff()

    def make_form(self, user, **fields):
        """A new-task form for FORM_DATA with the given fields added or replaced"""
        return AnalysisTaskForm(data={**FORM_DATA, **fields}, user=user, is_edit=False)

    def test_form_requires_core_fields(self):
        """Core fields should always be required"""
        form = AnalysisTaskForm(data={}, user=self.regular_user)
        self.assertFalse(form.is_valid())

        required_fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'tags', 'tools']
        for field in required_fields:
            self.assertIn(field, form.errors)

    def test_form_requires_reference_solution_for_regular_users(self):
        """Regular users must provide a reference solution when creating tasks"""
        form = self.make_form(self.regular_user)
        self.assertFalse(form.is_valid())
        self.assertIn('You must provide a reference solution', str(form.errors))

    def test_form_allows_no_reference_solution_for_staff(self):
        """Staff users can submit tasks without reference solutions"""
        form = self.make_form(self.staff_user)
        self.assertTrue(form.is_valid())

    def test_form_validates_onsite_solution_has_content(self):
        """Onsite reference solutions must have content"""
        # Missing: reference_solution_content
        form = self.make_form(
            self.regular_user,
            reference_solution_title='My Solution',
            reference_solution_type='onsite',
        )
        self.assertFalse(form.is_valid())
        self.assertIn('On-site reference solutions must have content', str(form.errors))

    def test_form_validates_external_solution_has_url(self):
        """External reference solutions must have a URL"""
        # Missing: reference_solution_url
        form = self.make_form(
            self.regular_user,
            reference_solution_title='My Blog Post',
            reference_solution_type='blog',
        )
        self.assertFalse(form.is_valid())
        self.assertIn('External reference solutions', str(form.errors))

    def test_form_validates_malwarebazaar_url(self):
        """Form should accept MalwareBazaar URLs"""
        form = self.make_form(
            self.regular_user,
            download_link='https://bazaar.abuse.ch/sample/abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234/',
            **BLOG_REFERENCE,
        )
        self.assertTrue(form.is_valid())

    def test_form_validates_malshare_url(self):
        """Form should accept MalShare URLs"""
        form = self.make_form(
            self.regular_user,
            download_link='https://malshare.com/sample.php?action=detail&hash=' + ('a' * 64),
            **BLOG_REFERENCE,
        )
        self.assertTrue(form.is_valid())

    def test_form_validates_malwarebazaar_download_url(self):
        """Form should accept MalwareBazaar download URLs (both /sample/ and /download/ paths)"""
        sha256 = 'c' * 64

        form = self.make_form(
            self.regular_user,
            sha256=sha256,
            download_link=f'https://bazaar.abuse.ch/download/{sha256}',
            **BLOG_REFERENCE,
        )
        self.assertTrue(form.is_valid())

        form = self.make_form(
            self.regular_user,
            sha256=sha256,
            download_link=f'https://bazaar.abuse.ch/sample/{sha256}/',
            **BLOG_REFERENCE,
        )
        self.assertTrue(form.is_valid())

    def test_form_rejects_invalid_download_urls_for_regular_users(self):
        """Regular users should not be able to use arbitrary download URLs"""
        form = self.make_form(
            self.regular_user,
            download_link='https://example.com/malware.exe',
            **BLOG_REFERENCE,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('download_link', form.errors)
        self.assertIn('MalwareBazaar', str(form.errors['download_link']))

    def test_form_allows_any_url_for_staff(self):
        """Staff users can use any download URL"""
        form = self.make_form(self.staff_user, download_link='https://example.com/malware.exe')
        self.assertTrue(form.is_valid())


class TaskSubmissionViewTestCase(SampleTestCase):
    """Test the submit_task view and task creation flow"""

    @classmethod
    def setUpTestData(cls):
        cls.regular_user = make_user()
        cls.staff_user = make_staff()

    def assert_task_created(self, response, sha256):
        """The task exists and the response redirects to its detail page. Returns the task."""
        task = AnalysisTask.objects.filter(sha256=sha256).first()
        self.assertIsNotNone(task, f"Task was not created (response status {response.status_code})")
        self.assertRedirects(response, detail_url(task), fetch_redirect_response=False)
        return task

    def test_submit_task_requires_login(self):
        """Submitting a task should require authentication"""
        response = self.client.get(reverse('submit_task'))
        self.assertRedirects(response, '/login/?next=/submit/', fetch_redirect_response=False)

    def test_submit_task_get_renders_form(self):
        """GET request should render the submission form"""
        self.login_as(self.regular_user)
        response = self.client.get(reverse('submit_task'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/submit_task.html')
        self.assertIn('form', response.context)

    def test_regular_user_can_submit_task_with_reference_solution(self):
        """Regular users should be able to submit tasks with reference solutions"""
        self.login_as(self.regular_user)

        post_data = {
            'sha256': 'b' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/',
            'description': 'Test malware description',
            'goal': 'Find the C2 server',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'ransomware, c2',
            'tools': 'ghidra, x64dbg',
            'reference_solution_title': 'My Writeup',
            'reference_solution_type': 'blog',
            'reference_solution_url': 'https://myblog.com/writeup',
        }

        response = self.client.post(reverse('submit_task'), data=post_data)

        task = self.assert_task_created(response, 'b' * 64)
        self.assertEqual(task.author, self.regular_user)
        self.assertEqual(task.goal, 'Find the C2 server')
        self.assertEqual(task.difficulty, Difficulty.EASY)

        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.title, 'My Writeup')
        self.assertEqual(solution.solution_type, 'blog')
        self.assertEqual(solution.url, 'https://myblog.com/writeup')
        self.assertEqual(solution.author, self.regular_user)

    def test_regular_user_can_submit_task_with_onsite_solution(self):
        """Regular users should be able to submit tasks with onsite solutions"""
        self.login_as(self.regular_user)

        post_data = {
            'sha256': 'c' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/',
            'description': 'Test malware description',
            'goal': 'Find the encryption key',
            'difficulty': Difficulty.MEDIUM,
            'platform': Platform.WINDOWS,
            'tags': 'ransomware, crypto',
            'tools': 'ghidra',
            'reference_solution_title': 'My Analysis',
            'reference_solution_type': 'onsite',
            'reference_solution_content': '# My Analysis\n\nThis is my detailed analysis...',
        }

        response = self.client.post(reverse('submit_task'), data=post_data)

        task = self.assert_task_created(response, 'c' * 64)

        # The text lives in an Article owned by the submitter
        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.solution_type, 'onsite')
        self.assertEqual(solution.article.author, self.regular_user)
        self.assertEqual(solution.article.title, 'My Analysis')
        self.assertIn('This is my detailed analysis', solution.article.content)
        self.assertIsNone(solution.url)  # Onsite solutions don't have URLs

    def test_staff_can_submit_task_without_reference_solution(self):
        """Staff users should be able to submit tasks without reference solutions"""
        self.login_as(self.staff_user)

        post_data = {
            'sha256': 'd' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/',
            'description': 'Test malware description',
            'goal': 'Analyze the malware',
            'difficulty': Difficulty.ADVANCED,
            'platform': Platform.WINDOWS,
            'tags': 'apt, evasion',
            'tools': 'ida, wireshark',
        }

        response = self.client.post(reverse('submit_task'), data=post_data)

        task = self.assert_task_created(response, 'd' * 64)
        self.assertEqual(task.author, self.staff_user)
        self.assertEqual(Solution.objects.filter(analysis_task=task).count(), 0)

    def test_tags_are_normalized_to_lowercase(self):
        """Tags should be converted to lowercase when saving"""
        self.login_as(self.staff_user)

        post_data = {
            'sha256': 'e' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/',
            'description': 'Test',
            'goal': 'Test',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'RaNsOmWaRe, APT, C2',
            'tools': 'Ghidra, IDA',
        }

        response = self.client.post(reverse('submit_task'), data=post_data)

        task = self.assert_task_created(response, 'e' * 64)

        tag_names = [tag.name for tag in task.tags.all()]
        self.assertIn('ransomware', tag_names)
        self.assertIn('apt', tag_names)
        self.assertIn('c2', tag_names)

        tool_names = [tool.name for tool in task.tools.all()]
        self.assertIn('ghidra', tool_names)
        self.assertIn('ida', tool_names)


class TaskEditPermissionTestCase(SampleTestCase):
    """Test edit permissions for analysis tasks"""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.other_user = make_user()
        cls.staff_user = make_staff()
        cls.task = make_task(author=cls.author)

    def test_author_can_edit_own_task(self):
        """Authors should be able to edit their own tasks"""
        self.login_as(self.author)
        response = self.client.get(edit_url(self.task))
        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_edit_task(self):
        """Non-authors should not be able to edit tasks"""
        self.login_as(self.other_user)
        response = self.client.get(edit_url(self.task))
        self.assertRedirects(response, detail_url(self.task), fetch_redirect_response=False)

    def test_staff_can_edit_any_task(self):
        """Staff users should be able to edit any task"""
        self.login_as(self.staff_user)
        response = self.client.get(edit_url(self.task))
        self.assertEqual(response.status_code, 200)

    def test_edit_form_preserves_difficulty(self):
        """Test that edit form preserves the current difficulty value"""
        advanced_task = make_task(author=self.author, difficulty=Difficulty.ADVANCED)
        self.login_as(self.author)

        response = self.client.get(edit_url(advanced_task))

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.instance.difficulty, Difficulty.ADVANCED)
        # The field's initial value is ADVANCED, not the EASY default
        self.assertEqual(form['difficulty'].value(), Difficulty.ADVANCED)
