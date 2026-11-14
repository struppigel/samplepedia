"""
Tests for account deletion functionality

This test suite covers:
1. Account deletion form validation
2. Password confirmation requirement
3. Acknowledgment checkbox requirement
4. Successful account deletion
5. Cascade deletion of related objects (tasks, solutions, articles, notifications)
6. Comments are preserved but anonymized (user field set to NULL, email cleared)
7. Security: unauthenticated users cannot access deletion page
8. Security: users can only delete their own account
9. Security: last superuser cannot delete their account (prevents lockout)
10. User is logged out after deletion
11. Statistics display (task and solution counts)
12. Redirect behavior after successful deletion
"""

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template import Context, Template
from django.urls import reverse
from django_comments.models import Comment

from samples.forms import DeleteAccountForm
from samples.models import AnalysisTask, Notification, Solution
from samples.tests.base import SampleTestCase
from samples.tests.factories import PASSWORD, make_solution, make_task, make_user

ADMIN_PASSWORD = 'adminpass123'


def make_superuser(username):
    return make_user(username, password=ADMIN_PASSWORD, is_staff=True, is_superuser=True)


class DeleteAccountFormTestCase(SampleTestCase):
    """Test the DeleteAccountForm validation logic"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user(password='correctpassword123')

    def test_form_requires_password(self):
        """Password field is required"""
        form = DeleteAccountForm(user=self.user, data={'confirm_deletion': True})
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_form_requires_confirmation_checkbox(self):
        """Confirmation checkbox is required"""
        form = DeleteAccountForm(user=self.user, data={
            'password': 'correctpassword123',
            'confirm_deletion': False
        })
        self.assertFalse(form.is_valid())
        self.assertIn('confirm_deletion', form.errors)

    def test_form_validates_incorrect_password(self):
        """Form should reject incorrect passwords"""
        form = DeleteAccountForm(user=self.user, data={
            'password': 'wrongpassword',
            'confirm_deletion': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertIn('incorrect', str(form.errors['password']).lower())

    def test_form_validates_correct_password(self):
        """Form should accept correct password with confirmation"""
        form = DeleteAccountForm(user=self.user, data={
            'password': 'correctpassword123',
            'confirm_deletion': True
        })
        self.assertTrue(form.is_valid(), form.errors)


class AccountDeletionViewTestCase(SampleTestCase):
    """Test the delete_account view functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('testuser')

    def test_unauthenticated_user_redirected_to_login(self):
        """Unauthenticated users should be redirected to login"""
        response = self.client.get(reverse('delete_account'))

        self.assertRedirects(response, '/login/?next=/settings/delete-account/', fetch_redirect_response=False)

    def test_authenticated_user_can_access_deletion_page(self):
        """Authenticated users should be able to access the deletion page"""
        self.login_as(self.user)
        response = self.client.get(reverse('delete_account'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'samples/delete_account.html')
        self.assertIn('form', response.context)

    def test_deletion_page_shows_user_statistics(self):
        """Deletion page should show task and solution counts"""
        make_solution(task=make_task(author=self.user))

        self.login_as(self.user)
        response = self.client.get(reverse('delete_account'))

        self.assertEqual(response.context['task_count'], 1)
        self.assertEqual(response.context['solution_count'], 1)

    def test_deletion_with_incorrect_password_fails(self):
        """Account deletion should fail with incorrect password"""
        self.login_as(self.user)

        response = self.client.post(reverse('delete_account'), {
            'password': 'wrongpassword',
            'confirm_deletion': True
        })

        self.assertTrue(User.objects.filter(username='testuser').exists())
        # Form redisplayed with errors
        self.assertEqual(response.status_code, 200)

    def test_deletion_without_confirmation_checkbox_fails(self):
        """Account deletion should fail without confirmation checkbox"""
        self.login_as(self.user)

        response = self.client.post(reverse('delete_account'), {
            'password': PASSWORD,
            'confirm_deletion': False
        })

        self.assertTrue(User.objects.filter(username='testuser').exists())
        # Form redisplayed with errors
        self.assertEqual(response.status_code, 200)


class AccountDeletionCascadeTestCase(SampleTestCase):
    """Test that account deletion properly cascades to related objects"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.other_user = make_user('otheruser')
        cls.task = make_task(author=cls.user, sha256='a' * 64)
        make_solution(task=cls.task)
        Notification.objects.create(
            recipient=cls.user,
            actor=cls.other_user,
            verb='liked',
            target_content_type=ContentType.objects.get_for_model(AnalysisTask),
            target_object_id=cls.task.id
        )

    def comment_on(self, task, text):
        return Comment.objects.create(
            content_type=ContentType.objects.get_for_model(AnalysisTask),
            object_pk=task.id,
            site_id=1,
            user=self.user,
            user_name=self.user.username,
            user_email=self.user.email,
            comment=text
        )

    def render_comment_author(self, comment):
        """Render a comment's author the way the comment templates do"""
        return Template(
            '{% if comment.user %}'
            '<a href="/profile/{{ comment.user.username }}/">{{ comment.user_name }}</a>'
            '{% else %}'
            '<span class="text-muted">Deleted User</span>'
            '{% endif %}'
        ).render(Context({'comment': comment}))

    def test_deletion_removes_user_tasks(self):
        """User's analysis tasks should be deleted"""
        self.assertEqual(AnalysisTask.objects.filter(author=self.user).count(), 1)

        self.user.delete()

        self.assertEqual(AnalysisTask.objects.filter(sha256='a' * 64).count(), 0)

    def test_deletion_removes_user_solutions(self):
        """User's solutions should be deleted"""
        self.assertEqual(Solution.objects.filter(author=self.user).count(), 1)

        self.user.delete()

        self.assertEqual(Solution.objects.count(), 0)

    def test_deletion_removes_user_notifications(self):
        """User's notifications should be deleted"""
        self.assertGreater(Notification.objects.filter(recipient=self.user).count(), 0)
        user_id = self.user.id

        self.user.delete()

        self.assertEqual(Notification.objects.filter(recipient_id=user_id).count(), 0)

    def test_deletion_preserves_comments_but_anonymizes_them(self):
        """User's comments should be preserved but user field set to NULL and displayed as 'Deleted User'"""
        original_email = self.user.email
        comment = self.comment_on(self.task, "This is a test comment")

        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.user_email, original_email)

        self.user.delete()

        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.get(id=comment.id)
        self.assertIsNone(comment.user)
        self.assertEqual(comment.user_email, '')  # Email should be cleared for privacy
        self.assertEqual(comment.comment, "This is a test comment")
        # user_name is preserved in the DB; the template displays "Deleted User"

    def test_deleted_user_comments_display_as_deleted_user(self):
        """Comments from deleted users should display as 'Deleted User' in templates"""
        # A task by the other user, so it survives the deletion
        other_task = make_task(author=self.other_user)
        comment = self.comment_on(other_task, "Test comment from user")
        username = self.user.username

        rendered_before = self.render_comment_author(comment)
        self.assertIn(username, rendered_before)
        self.assertNotIn('Deleted User', rendered_before)

        self.user.delete()

        comment = Comment.objects.get(id=comment.id)
        self.assertIsNone(comment.user)
        rendered_after = self.render_comment_author(comment)
        self.assertIn('Deleted User', rendered_after)
        self.assertNotIn(username, rendered_after)

    def test_deletion_does_not_affect_other_users(self):
        """Other users' data should not be affected"""
        make_task(author=self.other_user, sha256='b' * 64)

        self.user.delete()

        self.assertTrue(User.objects.filter(username='otheruser').exists())
        self.assertTrue(AnalysisTask.objects.filter(sha256='b' * 64).exists())

    def test_user_completely_removed_from_database(self):
        """User record should be completely removed"""
        user_id = self.user.id
        username = self.user.username

        self.user.delete()

        self.assertFalse(User.objects.filter(id=user_id).exists())
        self.assertFalse(User.objects.filter(username=username).exists())


class AccountDeletionSecurityTestCase(SampleTestCase):
    """Test security aspects of account deletion"""

    @classmethod
    def setUpTestData(cls):
        cls.user1 = make_user('user1')
        cls.user2 = make_user('user2')

    def test_user_can_only_delete_own_account(self):
        """Users should only be able to delete their own account"""
        self.login_as(self.user1)

        # delete_account takes no user parameter; it always operates on request.user
        response = self.client.get(reverse('delete_account'))
        self.assertEqual(response.status_code, 200)

        form = response.context['form']
        self.assertEqual(form.user, self.user1)
        self.assertTrue(User.objects.filter(username='user2').exists())

    def test_successful_deletion_logs_out_and_redirects(self):
        """A confirmed deletion removes the account, ends the session and goes home"""
        self.login_as(self.user1)

        response = self.client.post(reverse('delete_account'), {
            'password': PASSWORD,
            'confirm_deletion': True,
        })

        self.assertRedirects(response, reverse('sample_list'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='user1').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_deleted_user_cannot_login(self):
        """After deletion, user should not be able to log in"""
        username = self.user1.username

        self.assertTrue(self.client.login(username=username, password=PASSWORD))
        self.client.logout()

        self.user1.delete()

        self.assertFalse(self.client.login(username=username, password=PASSWORD))

    def test_last_superuser_cannot_delete_account(self):
        """Last remaining superuser should not be able to delete their account"""
        superuser = make_superuser('admin')
        self.login_as(superuser)

        response = self.client.post(reverse('delete_account'), {
            'password': ADMIN_PASSWORD,
            'confirm_deletion': True
        })

        self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())
        self.assertRedirects(response, reverse('delete_account'), fetch_redirect_response=False)

        response = self.client.get(response.url)
        messages_list = list(response.context.get('messages', []))
        error_found = any('last superuser' in str(msg).lower() for msg in messages_list)
        self.assertTrue(error_found, "Expected error message about last superuser not found")

    def test_superuser_can_delete_when_others_exist(self):
        """Superuser can delete their account when other superusers exist"""
        self.login_as(make_superuser('admin1'))
        make_superuser('admin2')

        response = self.client.post(reverse('delete_account'), {
            'password': ADMIN_PASSWORD,
            'confirm_deletion': True,
        })

        self.assertRedirects(response, reverse('sample_list'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='admin1').exists())
        self.assertTrue(User.objects.filter(username='admin2', is_superuser=True).exists())

    def test_regular_user_deletion_unaffected_by_superuser_check(self):
        """Regular users should not be affected by superuser check"""
        make_superuser('admin')
        self.login_as(self.user1)

        response = self.client.post(reverse('delete_account'), {
            'password': PASSWORD,
            'confirm_deletion': True,
        })

        self.assertRedirects(response, reverse('sample_list'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='user1').exists())
        self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())


class AccountDeletionIntegrationTestCase(SampleTestCase):
    """Integration tests for the complete deletion workflow"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('integrationuser')
        for sha256 in ('a' * 64, 'b' * 64):
            make_solution(task=make_task(author=cls.user, sha256=sha256))

    def test_statistics_accurately_reflect_user_content(self):
        """Statistics page should show accurate counts"""
        self.login_as(self.user)

        response = self.client.get(reverse('delete_account'))

        self.assertEqual(response.context['task_count'], 2)
        self.assertEqual(response.context['solution_count'], 2)

    def test_deletion_removes_all_user_content(self):
        """Complete deletion should remove all related content"""
        self.assertEqual(AnalysisTask.objects.filter(author=self.user).count(), 2)
        self.assertEqual(Solution.objects.filter(author=self.user).count(), 2)

        self.user.delete()

        self.assertEqual(AnalysisTask.objects.filter(sha256='a' * 64).count(), 0)
        self.assertEqual(AnalysisTask.objects.filter(sha256='b' * 64).count(), 0)
        self.assertEqual(Solution.objects.count(), 0)
        self.assertFalse(User.objects.filter(username='integrationuser').exists())

    def test_form_displays_correct_warning_information(self):
        """Deletion form should display appropriate warnings"""
        self.login_as(self.user)

        response = self.client.get(reverse('delete_account'))

        self.assertContains(response, 'permanent')
        self.assertContains(response, 'cannot be undone')
        self.assertContains(response, '2 analysis task')
        self.assertContains(response, '2 solution')
