"""
Markdown editors and browser drafts

This test suite covers:
1. Editor pages render the hooks of static/js/md-editor.js (preview and upload
   URLs, draft name, autosave settings) and load the shared scripts
2. A view that saved what a draft held has the next page clear it
   (<meta name="sp-clear-drafts">, samples/utils/drafts.py, static/js/drafts.js)
3. A rejected submission keeps its drafts
"""
import re

from django.urls import reverse

from samples.models import AnalysisTask, Difficulty, Platform, Solution
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_article, make_onsite_solution, make_staff, make_task, make_user

CLEAR_DRAFTS_RE = re.compile(r'<meta name="sp-clear-drafts" content="([^"]*)">')

NEW_TASK = {
    'sha256': 'c' * 64,
    'download_link': 'https://bazaar.abuse.ch/sample/abcd1234/',
    'description': 'Test description',
    'goal': 'Test goal',
    'difficulty': Difficulty.EASY,
    'platform': Platform.WINDOWS,
    'tags': 'malware',
    'tools': 'ghidra',
}


class EditorTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.task = make_task(author=cls.user)

    def setUp(self):
        self.login_as(self.user)

    def task_url(self, name, **kwargs):
        return reverse(name, kwargs={'sha256': self.task.sha256, 'task_id': self.task.id, **kwargs})

    def cleared_drafts(self, response):
        """The draft names a page tells drafts.js to clear."""
        match = CLEAR_DRAFTS_RE.search(response.content.decode())
        return set(match.group(1).split()) if match else set()

    def assertNothingPending(self):
        """No later page clears drafts either."""
        self.assertEqual(self.cleared_drafts(self.client.get(reverse('article_list'))), set())


class EditorPagesTestCase(EditorTestCase):
    def assertFullEditor(self, response, draft):
        self.assertContains(response, 'data-md-editor data-shortcuts')
        self.assertContains(response, f'data-preview-url="{reverse("markdown_preview")}"')
        self.assertContains(response, f'data-upload-url="{reverse("upload_editor_image")}"')
        self.assertContains(response, f'data-draft="{draft}"')
        self.assertContains(response, 'js/md-editor.js')
        self.assertContains(response, 'malware code directly')
        self.assertNotContains(response, 'editorAPI')

    def test_onsite_editor_for_a_new_solution(self):
        response = self.client.get(self.task_url('onsite_solution_editor'))
        self.assertFullEditor(response, f'onsite-solution:{self.task.id}')
        self.assertContains(response, 'data-autosave="5"')
        self.assertContains(response, 'data-required')
        self.assertContains(response, 'data-md-clear')
        # The editor is the form: its fields post as title and content
        self.assertContains(response, '<form method="post" id="editorForm" novalidate>')
        self.assertContains(response, 'type="submit" form="editorForm"')
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="content"')

    def test_onsite_editor_for_an_existing_solution(self):
        solution = make_onsite_solution(task=self.task, content='Existing writeup')
        response = self.client.get(self.task_url('edit_onsite_solution', solution_id=solution.id))
        self.assertFullEditor(response, f'onsite-solution:{self.task.id}:{solution.id}')
        self.assertContains(response, 'Existing writeup')
        self.assertNotContains(response, 'data-md-clear')

    def test_article_editor(self):
        response = self.client.get(reverse('article_editor'))
        self.assertFullEditor(response, 'article:new')
        self.assertContains(response, 'data-autosave="30"')
        self.assertContains(response, 'data-draft-max-age="24"')
        self.assertContains(response, 'auto-saved every 30 seconds')

        article = make_article(author=self.user)
        response = self.client.get(reverse('article_editor_edit', args=[article.id]))
        self.assertFullEditor(response, f'article:{article.id}')

    def test_markdown_editor(self):
        response = self.client.get(reverse('markdown_editor'))
        self.assertFullEditor(response, 'markdown-editor')
        self.assertContains(response, 'data-draft-restore="silent"')
        self.assertNotContains(response, 'data-required')
        self.assertContains(response, 'js/pages/markdown-editor.js')

    def test_solution_form_tabs_and_draft_picker(self):
        response = self.client.get(self.task_url('create_solution'))
        self.assertContains(response, f'data-md-editor data-preview-url="{reverse("markdown_preview")}"')
        self.assertContains(response, 'data-draft-picker="draftSelectionModal" data-draft-input="id_draft_article_id"')
        self.assertContains(response, f'data-drafts-url="{reverse("get_user_drafts_ajax")}"')
        for script in ['js/md-editor.js', 'js/draft-selection.js', 'js/pages/solution-form.js']:
            self.assertContains(response, script)

    def test_task_form_tabs_and_draft_picker(self):
        response = self.client.get(reverse('submit_task'))
        self.assertContains(response, f'data-md-editor data-preview-url="{reverse("markdown_preview")}"')
        self.assertContains(
            response, 'data-draft-picker="draftSelectionModal" data-draft-input="id_reference_draft_article_id"'
        )
        self.assertContains(response, 'data-restore-draft="true"')
        for script in ['js/md-editor.js', 'js/draft-selection.js', 'js/submit-task-form.js']:
            self.assertContains(response, script)

    def test_rejected_task_form_is_not_restored_from_drafts(self):
        """The page shows what was posted; restoring older draft values would overwrite it."""
        response = self.client.post(reverse('submit_task'), {**NEW_TASK, 'goal': ''})
        self.assertContains(response, 'data-restore-draft="false"')

    def test_rejected_task_form_keeps_reference_content(self):
        response = self.client.post(reverse('submit_task'), {
            **NEW_TASK, 'goal': '', 'reference_solution_content': 'My unsaved writeup',
        })
        self.assertContains(response, 'My unsaved writeup</textarea>')

    def test_publish_modal_urls(self):
        make_article(author=self.user)
        response = self.client.get(reverse('article_list'))
        self.assertContains(response, f'data-search-url="{reverse("search_samples_ajax")}"')
        self.assertContains(response, f'data-publish-url="{reverse("publish_article", args=[0])}"')

    def test_every_page_loads_drafts_js(self):
        response = self.client.get(reverse('sample_list'))
        self.assertContains(response, 'js/drafts.js')
        self.assertNotContains(response, 'draft-storage.js')


class TaskFormDraftTestCase(EditorTestCase):
    def test_submitted_task_clears_the_task_form(self):
        self.login_as(make_staff())
        response = self.client.post(reverse('submit_task'), NEW_TASK, follow=True)
        self.assertRedirects(response, AnalysisTask.objects.get(sha256=NEW_TASK['sha256']).get_absolute_url())
        self.assertEqual(self.cleared_drafts(response), {'task-form'})
        self.assertNothingPending()

    def test_published_reference_draft_is_cleared_too(self):
        draft = make_article(author=self.user)
        response = self.client.post(
            reverse('submit_task'), {**NEW_TASK, 'reference_draft_article_id': draft.id}, follow=True,
        )
        self.assertEqual(self.cleared_drafts(response), {'task-form', f'article:{draft.id}'})

    def test_rejected_task_keeps_the_task_form(self):
        response = self.client.post(reverse('submit_task'), NEW_TASK)  # no reference solution
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You must provide a reference solution')
        self.assertEqual(self.cleared_drafts(response), set())
        self.assertNothingPending()


class OnsiteSolutionDraftTestCase(EditorTestCase):
    def test_new_solution_clears_its_draft(self):
        response = self.client.post(
            self.task_url('onsite_solution_editor'), {'title': 'Writeup', 'content': 'Text'}, follow=True,
        )
        solution = Solution.objects.get(title='Writeup')
        self.assertRedirects(response, self.task_url('view_onsite_solution', solution_id=solution.id))
        self.assertEqual(self.cleared_drafts(response), {f'onsite-solution:{self.task.id}'})
        self.assertNothingPending()

    def test_edited_solution_clears_its_draft(self):
        solution = make_onsite_solution(task=self.task)
        response = self.client.post(
            self.task_url('edit_onsite_solution', solution_id=solution.id),
            {'title': solution.title, 'content': 'New text'}, follow=True,
        )
        self.assertEqual(self.cleared_drafts(response), {f'onsite-solution:{self.task.id}:{solution.id}'})

    def test_rejected_solution_keeps_its_draft(self):
        response = self.client.post(self.task_url('onsite_solution_editor'), {'title': 'Writeup', 'content': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cleared_drafts(response), set())
        self.assertContains(response, f'data-draft="onsite-solution:{self.task.id}"')
        self.assertNothingPending()

    def test_solution_from_draft_article_clears_the_article_draft(self):
        draft = make_article(author=self.user)
        response = self.client.post(
            self.task_url('create_solution'), {'solution_type': 'onsite', 'draft_article_id': draft.id}, follow=True,
        )
        self.assertEqual(self.cleared_drafts(response), {f'article:{draft.id}'})


class ArticleDraftTestCase(EditorTestCase):
    def test_new_article_clears_its_draft(self):
        response = self.client.post(reverse('article_editor'), {'title': 'Notes', 'content': 'Text'}, follow=True)
        self.assertEqual(self.cleared_drafts(response), {'article:new'})
        self.assertNothingPending()

    def test_edited_article_clears_its_draft(self):
        article = make_article(author=self.user)
        response = self.client.post(
            reverse('article_editor_edit', args=[article.id]), {'title': 'Notes', 'content': 'New'}, follow=True,
        )
        self.assertEqual(self.cleared_drafts(response), {f'article:{article.id}'})

    def test_rejected_article_keeps_its_draft(self):
        response = self.client.post(reverse('article_editor'), {'title': '', 'content': 'Text'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cleared_drafts(response), set())
        self.assertNothingPending()

    def test_published_article_clears_its_draft(self):
        article = make_article(author=self.user)
        response = self.client.post(reverse('publish_article', args=[article.id]), {'sample_id': self.task.id})
        self.assertTrue(response.json()['success'])
        # The page the publish modal goes to next
        response = self.client.get(response.json()['redirect_url'])
        self.assertEqual(self.cleared_drafts(response), {f'article:{article.id}'})

    def test_attached_article_clears_its_draft(self):
        article = make_article(author=self.user)
        response = self.client.post(self.task_url('attach_draft_to_sample'), {'article_id': article.id})
        self.assertTrue(response.json()['success'])
        response = self.client.get(self.task_url('sample_detail'))
        self.assertEqual(self.cleared_drafts(response), {f'article:{article.id}'})
