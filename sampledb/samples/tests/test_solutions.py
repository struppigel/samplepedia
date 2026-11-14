"""
Tests for solution functionality

This test suite covers:
1. Solution creation for different types (blog, paper, video, onsite)
2. Solution creation with draft articles (publishing existing drafts)
3. Solution form validation
4. Solution editing and deletion permissions
5. Solution likes/unlikes
6. Onsite solution content validation
7. URL validation for external solutions
8. Title uniqueness per analysis task
9. Solution listing and filtering
10. Solution type icon display
11. Author attribution and notifications
12. Draft article publishing workflow (draft vs manual content)
13. Solution hiding functionality (hidden_until field):
    - Anonymous and regular users cannot see hidden solutions
    - Solution authors can see their own hidden solutions
    - Task authors can see hidden solutions on their tasks
    - Staff can see all hidden solutions
    - Direct URL access protection for hidden onsite solutions
    - Hidden solutions excluded from showcase (no exceptions)
    - Hidden solutions filtered on profile views
    - Expired hidden solutions become visible to all
"""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from samples.forms import SolutionForm
from samples.models import Article, Solution, SolutionType
from samples.tests.base import SampleTestCase
from samples.tests.factories import (
    make_article, make_onsite_solution, make_solution, make_staff, make_task, make_user,
)


class SolutionTestCase(SampleTestCase):
    """Shared URL helpers for the views of self.task"""

    def task_url(self, name, **kwargs):
        return reverse(name, kwargs={'sha256': self.task.sha256, 'task_id': self.task.id, **kwargs})

    def detail_url(self):
        return self.task_url('sample_detail')

    def create_url(self):
        return self.task_url('create_solution')

    def solution_url(self, solution):
        return self.task_url('view_onsite_solution', solution_id=solution.id)


class SolutionCreationTestCase(SolutionTestCase):
    """Test solution creation for different types"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.task = make_task(author=cls.user)

    def test_create_blog_solution(self):
        """Test creating a blog post solution"""
        self.login_as(self.user)

        response = self.client.post(self.create_url(), {
            'title': 'My Analysis Blog Post',
            'solution_type': SolutionType.BLOG,
            'url': 'https://example.com/analysis',
        })

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.assertEqual(Solution.objects.count(), 1)
        solution = Solution.objects.first()
        self.assertEqual(solution.title, 'My Analysis Blog Post')
        self.assertEqual(solution.solution_type, SolutionType.BLOG)
        self.assertEqual(solution.author, self.user)

    def test_create_video_solution(self):
        """Test creating a video solution"""
        self.login_as(self.user)

        response = self.client.post(self.create_url(), {
            'title': 'Video Walkthrough',
            'solution_type': SolutionType.VIDEO,
            'url': 'https://youtube.com/watch?v=test',
        })

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        solution = Solution.objects.first()
        self.assertEqual(solution.solution_type, SolutionType.VIDEO)

    def test_onsite_solution_without_content_redisplays_form(self):
        """An onsite solution needs content or a draft; otherwise the form comes back with errors"""
        self.login_as(self.user)

        response = self.client.post(self.create_url(), {
            'title': 'Onsite Analysis',
            'solution_type': SolutionType.ONSITE,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(Solution.objects.exists())

    def test_unauthenticated_cannot_create_solution(self):
        """Test that unauthenticated users cannot create solutions"""
        response = self.client.post(self.create_url(), {
            'title': 'Test',
            'solution_type': SolutionType.BLOG,
            'url': 'https://example.com',
        })

        expected_url = f"/login/?next=/sample/{self.task.sha256}/{self.task.id}/solution/add/"
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        self.assertEqual(Solution.objects.count(), 0)

    def test_create_onsite_solution_with_draft_article(self):
        """Test publishing a draft article as a solution"""
        self.login_as(self.user)
        draft = make_article(author=self.user, title='My Draft Analysis')

        response = self.client.post(self.create_url(), {
            'solution_type': SolutionType.ONSITE,
            'draft_article_id': draft.id,
        })

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        solution = Solution.objects.first()
        self.assertIsNotNone(solution)
        self.assertEqual(solution.title, 'My Draft Analysis')
        self.assertEqual(solution.article, draft)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        self.assertTrue(draft.is_published())

    def test_create_onsite_solution_by_writing_new(self):
        """Test creating onsite solution creates an Article internally"""
        self.login_as(self.user)

        response = self.client.post(self.create_url(), {
            'title': 'New Analysis',
            'solution_type': SolutionType.ONSITE,
            'content': '# New Content\n\nWritten directly...',
        })

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        solution = Solution.objects.first()
        self.assertIsNotNone(solution)
        self.assertEqual(solution.title, 'New Analysis')
        self.assertIsNotNone(solution.article)
        self.assertEqual(solution.article.title, 'New Analysis')
        self.assertEqual(solution.article.content, '# New Content\n\nWritten directly...')
        self.assertEqual(Article.objects.count(), 1)

    def test_cannot_provide_both_draft_and_content(self):
        """Test validation error when providing both draft and manual content"""
        self.login_as(self.user)
        draft = make_article(author=self.user)

        response = self.client.post(self.create_url(), {
            'title': 'Test',
            'solution_type': SolutionType.ONSITE,
            'draft_article_id': draft.id,
            'content': 'Manual content',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Solution.objects.count(), 0)

    def test_title_not_required_when_publishing_draft(self):
        """Test that title field is not required when publishing a draft"""
        self.login_as(self.user)
        draft = make_article(author=self.user, title='Draft Title')

        # No title provided, so the draft's title is used
        response = self.client.post(self.create_url(), {
            'solution_type': SolutionType.ONSITE,
            'draft_article_id': draft.id,
        })

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        solution = Solution.objects.first()
        self.assertIsNotNone(solution)
        self.assertEqual(solution.title, 'Draft Title')


class SolutionFormValidationTestCase(SampleTestCase):
    """Test solution form validation"""

    def test_external_solution_requires_url(self):
        """Test that blog/paper/video solutions require URL"""
        form = SolutionForm({
            'title': 'Test Solution',
            'solution_type': SolutionType.BLOG,
            'url': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('External solutions must have a URL.', form.errors['__all__'])

    def test_onsite_solution_no_url_required(self):
        """Test that onsite solutions don't require URL"""
        form = SolutionForm({
            'title': 'Test Solution',
            'solution_type': SolutionType.ONSITE,
            'url': '',
            'content': '# My analysis\n\nDetails here...',
        })

        self.assertTrue(form.is_valid())

    def test_title_required(self):
        """Test that title is required"""
        form = SolutionForm({
            'title': '',
            'solution_type': SolutionType.BLOG,
            'url': 'https://example.com',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_solution_type_required(self):
        """Test that solution type is required"""
        form = SolutionForm({
            'title': 'Test',
            'solution_type': '',
            'url': 'https://example.com',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('solution_type', form.errors)


class SolutionUniquenessTestCase(SampleTestCase):
    """Test solution title uniqueness per analysis task"""

    @classmethod
    def setUpTestData(cls):
        cls.task1 = make_task()
        cls.task2 = make_task()
        make_solution(task=cls.task1, title='Duplicate Title')

    def test_duplicate_title_same_task_fails(self):
        """Test that duplicate title on same task is rejected"""
        with self.assertRaises(IntegrityError):
            # Same title, same task; only the type differs
            make_solution(task=self.task1, title='Duplicate Title', solution_type=SolutionType.VIDEO)

    def test_same_title_different_task_allowed(self):
        """Test that same title on different task is allowed"""
        solution = make_solution(task=self.task2, title='Duplicate Title')

        self.assertEqual(solution.title, 'Duplicate Title')
        self.assertEqual(Solution.objects.filter(title='Duplicate Title').count(), 2)


class SolutionPermissionsTestCase(SolutionTestCase):
    """Test solution editing and deletion permissions"""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user()
        cls.other_user = make_user()
        cls.staff_user = make_staff()
        cls.task = make_task(author=cls.author)
        cls.solution = make_solution(task=cls.task)
        # A second reference solution so the first can be deleted
        make_solution(task=cls.task)

    def edit_url(self):
        return self.task_url('edit_solution', solution_id=self.solution.id)

    def delete_url(self):
        return self.task_url('delete_solution', solution_id=self.solution.id)

    def test_author_can_edit_solution(self):
        """Test that solution author can edit their solution"""
        self.login_as(self.author)

        response = self.client.get(self.edit_url())

        self.assertEqual(response.status_code, 200)

    def test_non_author_cannot_edit_solution(self):
        """Test that non-authors cannot edit solutions"""
        self.login_as(self.other_user)

        response = self.client.get(self.edit_url())

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)

    def test_staff_can_edit_any_solution(self):
        """Test that staff users can edit any solution"""
        self.login_as(self.staff_user)

        response = self.client.get(self.edit_url())

        self.assertEqual(response.status_code, 200)

    def test_author_can_delete_solution(self):
        """Test that solution author can delete their solution"""
        self.login_as(self.author)

        response = self.client.post(self.delete_url())

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.assertEqual(Solution.objects.count(), 1)  # One reference solution remains

    def test_non_author_cannot_delete_solution(self):
        """Test that non-authors cannot delete solutions"""
        self.login_as(self.other_user)

        response = self.client.post(self.delete_url())

        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.assertEqual(Solution.objects.count(), 2)  # Both solutions remain


class SolutionLikesTestCase(SampleTestCase):
    """Test solution like/unlike functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.user1 = make_user()
        cls.user2 = make_user()
        cls.solution = make_solution(task=make_task(author=cls.user1))

    def like_url(self):
        return reverse('toggle_solution_like', kwargs={'solution_id': self.solution.id})

    def test_user_can_like_solution(self):
        """Test that users can like solutions"""
        self.login_as(self.user2)

        response = self.client.post(self.like_url())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.liked_by.count(), 1)
        self.assertIn(self.user2, self.solution.liked_by.all())

    def test_user_can_unlike_solution(self):
        """Test that users can unlike solutions"""
        self.solution.liked_by.add(self.user2)
        self.login_as(self.user2)

        response = self.client.post(self.like_url())

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
        response = self.client.post(self.like_url())

        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data['error'], 'Login required')
        self.assertEqual(self.solution.liked_by.count(), 0)


class SolutionListingTestCase(SampleTestCase):
    """Test solution listing and filtering"""

    @classmethod
    def setUpTestData(cls):
        task = make_task(sha256='1' * 64)
        make_solution(task=task, title='Blog Solution', solution_type=SolutionType.BLOG)
        make_solution(task=task, title='Video Solution', solution_type=SolutionType.VIDEO)
        make_solution(task=task, title='Paper Solution', solution_type=SolutionType.PAPER)

    def test_solution_list_shows_all_solutions(self):
        """Test that solution list shows all solutions"""
        response = self.client.get(reverse('solution_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_filter_by_solution_type(self):
        """Test filtering solutions by type"""
        response = self.client.get(reverse('solution_list'), {'solution_type': SolutionType.BLOG})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].title, 'Blog Solution')

    def test_search_solutions_by_title(self):
        """Test searching solutions by title"""
        response = self.client.get(reverse('solution_list'), {'q': 'Video'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].title, 'Video Solution')

    def test_search_solutions_by_sha256(self):
        """Test searching solutions by SHA256"""
        response = self.client.get(reverse('solution_list'), {'q': '111111'})  # Part of the task's SHA256

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 3)  # All belong to same task


class OnsiteSolutionTestCase(SolutionTestCase):
    """Test onsite solution specific functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.task = make_task(author=cls.user)

    def test_create_onsite_solution_with_markdown(self):
        """Test creating onsite solution with markdown content"""
        self.login_as(self.user)

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

        response = self.client.post(self.task_url('onsite_solution_editor'), {
            'title': 'Detailed Analysis Report',
            'content': markdown_content,
        })

        solution = Solution.objects.first()
        self.assertIsNotNone(solution, "Solution was not created")
        # Should redirect to view the published solution
        self.assertRedirects(response, self.solution_url(solution), fetch_redirect_response=False)
        self.assertEqual(solution.solution_type, SolutionType.ONSITE)
        # Content is now stored in the Article model
        self.assertIsNotNone(solution.article, "Article was not created")
        self.assertEqual(solution.article.content, markdown_content.strip())
        self.assertIsNone(solution.url)  # No URL for onsite

    def test_view_onsite_solution(self):
        """Test viewing published onsite solution"""
        solution = make_onsite_solution(
            task=self.task,
            title='Test Onsite Solution',
            content='# Test\n\nThis is a test.',
        )

        response = self.client.get(self.solution_url(solution))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solution.title)
        self.assertContains(response, 'This is a test.')


class SolutionHidingTestCase(SolutionTestCase):
    """Test solution hiding functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.task_author = make_user()
        cls.solution_author = make_user()
        cls.staff_user = make_staff()
        cls.regular_user = make_user()
        cls.task = make_task(author=cls.task_author)

        now = timezone.now()
        cls.visible_solution = make_solution(
            task=cls.task, author=cls.solution_author, title='PublicBlog Solution',
        )
        cls.hidden_solution = make_solution(
            task=cls.task, author=cls.solution_author, title='TemporarilyHidden Solution',
            hidden_until=now + timedelta(weeks=2),
        )
        # Was hidden, but the hiding period is over
        cls.expired_solution = make_solution(
            task=cls.task, author=cls.solution_author, title='PreviouslyHidden Solution',
            hidden_until=now - timedelta(days=1),
        )
        cls.hidden_onsite = make_onsite_solution(
            task=cls.task,
            author=cls.solution_author,
            title='NotYetPublic Onsite',
            content='# Secret Analysis\n\nThis is hidden.',
            hidden_until=now + timedelta(weeks=1),
        )

    def profile_url(self):
        return reverse('user_profile', kwargs={'username': self.solution_author.username})

    def test_anonymous_user_cannot_see_hidden_solutions_in_detail_view(self):
        """Anonymous users should not see currently hidden solutions in task detail"""
        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
        self.assertNotContains(response, self.hidden_onsite.title)

    def test_regular_user_cannot_see_hidden_solutions_in_detail_view(self):
        """Regular users should not see hidden solutions in task detail"""
        self.login_as(self.regular_user)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)

    def test_solution_author_can_see_own_hidden_solution(self):
        """Solution authors should see their own hidden solutions"""
        self.login_as(self.solution_author)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')

    def test_task_author_can_see_all_hidden_solutions_on_own_task(self):
        """Task authors should see all hidden solutions on their tasks"""
        self.login_as(self.task_author)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')

    def test_staff_user_can_see_all_hidden_solutions(self):
        """Staff users should see all hidden solutions everywhere"""
        self.login_as(self.staff_user)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)

    def test_direct_access_to_hidden_onsite_solution_blocked_for_anonymous(self):
        """Anonymous users cannot directly access hidden onsite solutions"""
        response = self.client.get(self.solution_url(self.hidden_onsite))

        # Redirected to the task detail page (which must load) with an error message
        self.assertRedirects(response, self.detail_url())

    def test_direct_access_to_hidden_onsite_solution_blocked_for_regular_user(self):
        """Regular users cannot directly access hidden onsite solutions"""
        self.login_as(self.regular_user)

        response = self.client.get(self.solution_url(self.hidden_onsite))

        # Redirected to the task detail page (which must load) with an error message
        self.assertRedirects(response, self.detail_url())

    def test_direct_access_to_hidden_onsite_solution_allowed_for_author(self):
        """Solution author can directly access their hidden onsite solution"""
        self.login_as(self.solution_author)

        response = self.client.get(self.solution_url(self.hidden_onsite))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)
        self.assertContains(response, 'Secret Analysis')

    def test_direct_access_to_hidden_onsite_solution_allowed_for_task_author(self):
        """Task author can directly access hidden solutions on their task"""
        self.login_as(self.task_author)

        response = self.client.get(self.solution_url(self.hidden_onsite))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)

    def test_direct_access_to_hidden_onsite_solution_allowed_for_staff(self):
        """Staff can directly access any hidden solution"""
        self.login_as(self.staff_user)

        response = self.client.get(self.solution_url(self.hidden_onsite))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.hidden_onsite.title)

    def test_hidden_solutions_excluded_from_solutions_showcase(self):
        """Hidden solutions should never appear in solutions showcase"""
        # Even staff shouldn't see hidden solutions in showcase
        self.login_as(self.staff_user)

        response = self.client.get(reverse('solutions_showcase'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)
        self.assertNotContains(response, self.hidden_onsite.title)

    def test_hidden_solutions_excluded_from_profile_for_other_users(self):
        """Hidden solutions should not appear on profile when viewed by others"""
        self.login_as(self.regular_user)

        response = self.client.get(self.profile_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)

    def test_hidden_solutions_visible_on_own_profile(self):
        """Users should see their own hidden solutions on their profile"""
        self.login_as(self.solution_author)

        response = self.client.get(self.profile_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        self.assertContains(response, self.hidden_onsite.title)
        # "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')

    def test_hidden_solutions_excluded_from_solution_list_for_others(self):
        """Hidden solutions should not appear in solutions_list view for other users"""
        self.login_as(self.regular_user)

        response = self.client.get(reverse('solution_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertNotContains(response, self.hidden_solution.title)

    def test_own_hidden_solutions_visible_in_solution_list(self):
        """Users should see their own hidden solutions in solutions_list view"""
        self.login_as(self.solution_author)

        response = self.client.get(reverse('solution_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.visible_solution.title)
        self.assertContains(response, self.hidden_solution.title)
        # "Hidden" badge
        self.assertContains(response, 'fa-eye-slash')

    def test_expired_hidden_solution_becomes_visible_to_all(self):
        """Solutions with hidden_until in the past should be visible to everyone"""
        # Anonymous user
        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.expired_solution.title)
        self.assertNotContains(response, 'fa-eye-slash')  # No "Hidden" badge

        response = self.client.get(reverse('solutions_showcase'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.expired_solution.title)

    def test_user_can_see_hidden_status_method(self):
        """Test the user_can_see_hidden_status model method"""
        self.assertFalse(self.hidden_solution.user_can_see_hidden_status(AnonymousUser()))
        self.assertFalse(self.hidden_solution.user_can_see_hidden_status(self.regular_user))
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.solution_author))
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.task_author))
        self.assertTrue(self.hidden_solution.user_can_see_hidden_status(self.staff_user))


class SolutionsShowcaseTestCase(SampleTestCase):
    """Test solutions showcase ordering and visibility"""

    @classmethod
    def setUpTestData(cls):
        cls.task = make_task()

    def test_recently_unhidden_solution_appears_in_showcase(self):
        """Test that a solution with recently passed hidden_until appears in showcase"""
        # Created a year ago, but only became visible an hour ago
        old_solution = make_solution(task=self.task, title='Old but recently unhidden solution')
        old_solution.created_at = timezone.now() - timedelta(days=365)
        old_solution.hidden_until = timezone.now() - timedelta(hours=1)
        old_solution.save(update_fields=['created_at', 'hidden_until'])

        # Newer by creation date (a week ago), never hidden
        newer_solution = make_solution(task=self.task, title='Newer solution')
        newer_solution.created_at = timezone.now() - timedelta(days=7)
        newer_solution.save(update_fields=['created_at'])

        response = self.client.get(reverse('solutions_showcase'))

        self.assertContains(response, 'Old but recently unhidden solution')

        solution_titles = [s.title for s in response.context['solutions']]
        old_index = solution_titles.index('Old but recently unhidden solution')
        newer_index = solution_titles.index('Newer solution')

        # Recently unhidden (1 hour ago) should come before solution from 7 days ago
        self.assertLess(old_index, newer_index,
                        "Recently unhidden solution should appear first (most recent visible_date)")

    def test_still_hidden_solution_not_in_showcase(self):
        """Test that solutions with future hidden_until don't appear"""
        make_solution(
            task=self.task, title='Still hidden solution',
            hidden_until=timezone.now() + timedelta(days=7),
        )

        response = self.client.get(reverse('solutions_showcase'))

        self.assertNotContains(response, 'Still hidden solution')

    def test_showcase_orders_by_visible_date_not_created_date(self):
        """Test that showcase uses visible_date (hidden_until or created_at) for ordering"""
        # Solution 1: created 30 days ago, never hidden (visible_date = 30 days ago)
        solution1 = make_solution(task=self.task, title='Solution 1')
        solution1.created_at = timezone.now() - timedelta(days=30)
        solution1.save(update_fields=['created_at'])

        # Solution 2: created 60 days ago, became visible 2 days ago (visible_date = 2 days ago)
        solution2 = make_solution(task=self.task, title='Solution 2')
        solution2.created_at = timezone.now() - timedelta(days=60)
        solution2.hidden_until = timezone.now() - timedelta(days=2)
        solution2.save(update_fields=['created_at', 'hidden_until'])

        response = self.client.get(reverse('solutions_showcase'))
        solutions = list(response.context['solutions'])

        # visible_date 2 days ago is more recent than 30 days ago
        self.assertEqual(solutions[0].title, 'Solution 2')
        self.assertEqual(solutions[1].title, 'Solution 1')
