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

from django.urls import reverse

from samples.forms import AnalysisTaskForm
from samples.models import AnalysisTask, Article, Difficulty, Platform, Solution, SolutionType
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_article, make_onsite_solution, make_staff, make_task, make_user


def task_form_data(sha256, **fields):
    """Task submission data with a MalwareBazaar download link for the hash"""
    return {
        'sha256': sha256,
        'download_link': f'https://bazaar.abuse.ch/sample/{sha256}/',
        'description': 'Test description',
        'goal': 'Test goal',
        'difficulty': Difficulty.EASY,
        'platform': Platform.WINDOWS,
        'tags': 'malware, test',
        'tools': 'ghidra',
        **fields,
    }


class DraftSelectionFormTestCase(SampleTestCase):
    """Test form validation for draft article selection in task submission"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.draft = make_article(author=cls.user)
        cls.published_article = make_onsite_solution(task=make_task(author=cls.user)).article
        cls.other_draft = make_article()  # owned by another user

    def form(self, **fields):
        return AnalysisTaskForm(data=task_form_data('a' * 64, **fields), user=self.user, is_edit=False)

    def test_form_accepts_valid_draft_article(self):
        """Form should accept a valid unpublished draft owned by the user"""
        form = self.form(reference_draft_article_id=self.draft.id)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        self.assertEqual(form.cleaned_data['_draft_article'], self.draft)

    def test_form_rejects_draft_not_owned_by_user(self):
        """Form should reject draft articles not owned by the submitting user"""
        form = self.form(reference_draft_article_id=self.other_draft.id)
        self.assertFalse(form.is_valid())
        self.assertIn('You can only use your own draft articles', str(form.errors))

    def test_form_rejects_already_published_draft(self):
        """Form should reject draft articles that are already published"""
        form = self.form(reference_draft_article_id=self.published_article.id)
        self.assertFalse(form.is_valid())
        self.assertIn('already published', str(form.errors))

    def test_form_accepts_draft_without_manual_fields(self):
        """Form should not require manual solution fields when draft is provided"""
        form = self.form(reference_draft_article_id=self.draft.id)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_form_requires_reference_when_no_draft(self):
        """Form should require manual reference solution when no draft is provided"""
        form = self.form()
        self.assertFalse(form.is_valid())
        self.assertIn('You must provide a reference solution', str(form.errors))

    def test_form_accepts_manual_solution_without_draft(self):
        """Form should accept manual solution fields when no draft is provided"""
        form = self.form(
            reference_solution_title='My Blog Post',
            reference_solution_type='blog',  # Use string value, not enum
            reference_solution_url='https://example.com/writeup',
        )
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_form_rejects_nonexistent_draft_id(self):
        """Form should reject draft IDs that don't exist"""
        form = self.form(reference_draft_article_id=99999)
        self.assertFalse(form.is_valid())
        self.assertIn('does not exist', str(form.errors))


class TaskSubmissionWithDraftTestCase(SampleTestCase):
    """Test task submission view with draft article selection"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.draft = make_article(author=cls.user)

    def setUp(self):
        self.login_as(self.user)

    def test_submit_task_with_draft_creates_solution(self):
        """Submitting a task with a draft should create a solution with the draft attached"""
        response = self.client.post(reverse('submit_task'), task_form_data(
            'c' * 64,
            description='Malware sample analysis task',
            goal='Identify the malware family and IOCs',
            difficulty=Difficulty.MEDIUM,
            tags='ransomware, windows',
            tools='ghidra, x64dbg',
            reference_draft_article_id=self.draft.id,
        ))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AnalysisTask.objects.count(), 1)
        task = AnalysisTask.objects.first()
        self.assertEqual(task.sha256, 'c' * 64)
        self.assertEqual(task.author, self.user)

        self.assertEqual(Solution.objects.count(), 1)
        solution = Solution.objects.first()
        self.assertEqual(solution.title, self.draft.title)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.article, self.draft)
        self.assertEqual(solution.author, self.user)
        self.assertEqual(solution.analysis_task, task)

        self.draft.refresh_from_db()
        self.assertTrue(self.draft.is_published())

    def test_submit_task_with_draft_redirects_to_detail(self):
        """After submitting with draft, should redirect to task detail page"""
        response = self.client.post(reverse('submit_task'), task_form_data(
            'd' * 64, tags='test', tools='ida', reference_draft_article_id=self.draft.id,
        ))

        task = AnalysisTask.objects.first()
        expected_url = reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id})
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_draft_cannot_be_published_twice(self):
        """A draft that's already published cannot be used again"""
        response_1 = self.client.post(reverse('submit_task'), task_form_data(
            'e' * 64,
            description='First task',
            goal='First goal',
            tags='test',
            tools='ida',
            reference_draft_article_id=self.draft.id,
        ))
        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)

        response_2 = self.client.post(reverse('submit_task'), task_form_data(
            '0' * 64,
            description='Second task',
            goal='Second goal',
            difficulty=Difficulty.MEDIUM,
            platform=Platform.LINUX,
            tags='test2',
            tools='ghidra',
            reference_draft_article_id=self.draft.id,
        ))

        # Form redisplayed with a validation error
        self.assertEqual(response_2.status_code, 200)
        self.assertContains(response_2, 'already published')
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)

    def test_submit_task_with_manual_solution_still_works(self):
        """Traditional manual solution submission should still work"""
        response = self.client.post(reverse('submit_task'), task_form_data(
            'f' * 64,
            description='Test task',
            difficulty=Difficulty.ADVANCED,
            tags='test',
            tools='radare2',
            reference_solution_title='My Blog Post',
            reference_solution_type='blog',  # Use string value, not enum
            reference_solution_url='https://myblog.com/analysis',
        ))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AnalysisTask.objects.count(), 1)
        self.assertEqual(Solution.objects.count(), 1)

        solution = Solution.objects.first()
        self.assertEqual(solution.title, 'My Blog Post')
        self.assertEqual(solution.solution_type, SolutionType.BLOG)
        self.assertEqual(solution.url, 'https://myblog.com/analysis')
        self.assertIsNone(solution.article)


class ArticleListButtonStatesTestCase(SampleTestCase):
    """Test article list view button states and last reference protection"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

        # The task's only reference solution
        cls.task = make_task(author=cls.user, sha256='1' * 64)
        cls.article_last_ref = make_onsite_solution(task=cls.task).article

        # A task with two reference solutions, so neither is the last one
        task2 = make_task(author=cls.user)
        cls.solution_multi_ref_1 = make_onsite_solution(task=task2)
        cls.solution_multi_ref_2 = make_onsite_solution(task=task2)
        cls.article_multi_ref_1 = cls.solution_multi_ref_1.article

    def setUp(self):
        self.login_as(self.user)

    def test_article_list_shows_task_column_for_published(self):
        """Article list should show task SHA256 link for published articles"""
        response = self.client.get(reverse('article_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.task.sha256[:8])
        self.assertContains(response, reverse('sample_detail', kwargs={
            'sha256': self.task.sha256,
            'task_id': self.task.id
        }))

    def test_last_reference_buttons_are_disabled(self):
        """Unpublish and delete buttons should be disabled for last reference solutions"""
        response = self.client.get(reverse('article_list'))

        self.assertEqual(response.status_code, 200)
        # Disabled buttons are muted text with a lock icon
        content = response.content.decode('utf-8')
        self.assertIn('fa-lock', content)
        self.assertIn('text-muted', content)
        self.assertIn('Cannot unpublish the last reference solution', content)
        self.assertIn('Cannot delete the last reference solution', content)

    def test_multi_reference_buttons_are_enabled(self):
        """Unpublish and delete buttons should be enabled for non-last reference solutions"""
        response = self.client.get(reverse('article_list'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('text-warning', content)  # Unpublish button
        self.assertIn('text-danger', content)   # Delete button
        self.assertIn('fa-undo', content)       # Unpublish icon (enabled)
        self.assertIn('fa-trash', content)      # Delete icon (enabled)

    def test_cannot_unpublish_last_reference_via_post(self):
        """Attempting to unpublish the last reference should fail"""
        response = self.client.post(reverse('article_unpublish', kwargs={'article_id': self.article_last_ref.id}))

        # Redirects back to the article list
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Solution.objects.filter(article=self.article_last_ref).exists())
        self.article_last_ref.refresh_from_db()
        self.assertTrue(self.article_last_ref.is_published())

    def test_cannot_delete_last_reference_via_post(self):
        """Attempting to delete article with last reference should fail"""
        response = self.client.post(reverse('article_delete', kwargs={'article_id': self.article_last_ref.id}))

        # Redirects back to the article list
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Article.objects.filter(id=self.article_last_ref.id).exists())
        self.assertTrue(Solution.objects.filter(article=self.article_last_ref).exists())

    def test_can_unpublish_non_last_reference(self):
        """Should be able to unpublish article when task has multiple solutions"""
        unpublish_url = reverse('article_unpublish', kwargs={'article_id': self.article_multi_ref_1.id})

        response = self.client.post(unpublish_url, {'solution_id': self.solution_multi_ref_1.id})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Solution.objects.filter(id=self.solution_multi_ref_1.id).exists())
        self.assertTrue(Solution.objects.filter(id=self.solution_multi_ref_2.id).exists())
        self.article_multi_ref_1.refresh_from_db()
        self.assertFalse(self.article_multi_ref_1.is_published())


class DraftPublishingIntegrationTestCase(SampleTestCase):
    """Integration tests for the full draft publishing workflow"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.login_as(self.user)

    def test_full_workflow_create_draft_to_publish(self):
        """Test complete workflow: create draft -> submit task with draft -> verify solution"""
        draft = make_article(
            author=self.user,
            title='Complete Malware Analysis',
            content='# Introduction\n\nThis is my complete analysis...',
        )
        self.assertFalse(draft.is_published())
        self.assertEqual(draft.view_count, 0)

        response = self.client.post(reverse('submit_task'), task_form_data(
            '3' * 64,
            description='Emotet banking trojan sample',
            goal='Analyze C2 communication and identify IOCs',
            difficulty=Difficulty.EXPERT,
            tags='emotet, banking, trojan',
            tools='ghidra, wireshark, procmon',
            reference_draft_article_id=draft.id,
        ))
        self.assertEqual(response.status_code, 302)

        task = AnalysisTask.objects.get(sha256='3' * 64)
        self.assertEqual(task.goal, 'Analyze C2 communication and identify IOCs')
        self.assertEqual(task.difficulty, Difficulty.EXPERT)
        self.assertEqual(task.author, self.user)

        solution = Solution.objects.get(analysis_task=task)
        self.assertEqual(solution.title, draft.title)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertEqual(solution.article, draft)
        self.assertEqual(solution.author, self.user)

        draft.refresh_from_db()
        self.assertTrue(draft.is_published())
        self.assertEqual(draft.solution, solution)

        # The task detail page lists the solution
        response = self.client.get(reverse('sample_detail', kwargs={'sha256': task.sha256, 'task_id': task.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, draft.title)

        # The solution itself can be viewed
        response = self.client.get(reverse('view_onsite_solution', kwargs={
            'sha256': task.sha256,
            'task_id': task.id,
            'solution_id': solution.id
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, draft.title)
        self.assertContains(response, 'complete analysis')

    def test_draft_appears_in_ajax_endpoint(self):
        """Test that unpublished drafts appear in the AJAX endpoint"""
        make_article(author=self.user, title='Unpublished Draft 1')
        make_article(author=self.user, title='Unpublished Draft 2')
        make_onsite_solution(task=make_task(author=self.user), title='Published Article')

        response = self.client.get(reverse('get_user_drafts_ajax'))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data['results']), 2)
        draft_titles = [d['title'] for d in data['results']]
        self.assertIn('Unpublished Draft 1', draft_titles)
        self.assertIn('Unpublished Draft 2', draft_titles)
        self.assertNotIn('Published Article', draft_titles)

    def test_staff_can_submit_without_draft_or_manual_solution(self):
        """Staff users should be able to submit tasks without any reference solution"""
        staff_user = make_staff()
        self.login_as(staff_user)

        response = self.client.post(reverse('submit_task'), task_form_data(
            '5' * 64,
            download_link='https://example.com/malware.exe',  # Staff can use any URL
            description='Staff submitted task',
            goal='No solution required',
            difficulty=Difficulty.MEDIUM,
            tags='test',
            tools='ida',
        ))
        self.assertEqual(response.status_code, 302)

        task = AnalysisTask.objects.get(sha256='5' * 64)
        self.assertEqual(task.author, staff_user)
        self.assertEqual(Solution.objects.filter(analysis_task=task).count(), 0)
