"""
Tests for shared form rules in samples/forms.py.
"""
from django.urls import reverse

from samples.forms import ArticleForm, ChangeEmailForm, TurnstileUserRegistrationForm
from samples.models import AnalysisTask, Difficulty, Platform
from samples.tests.base import SampleTestCase
from samples.tests.factories import PASSWORD, make_staff, make_user


class EmailRulesTestCase(SampleTestCase):
    def test_registration_rejects_taken_address_in_other_case(self):
        make_user(email='Taken@Example.org')
        form = TurnstileUserRegistrationForm(data={
            'username': 'newbie', 'email': 'taken@example.org',
            'password1': 'a-Long-unusual-pass-42', 'password2': 'a-Long-unusual-pass-42',
        })
        self.assertIn('already registered', str(form.errors['email']))

    def test_change_to_own_address_in_other_case_is_rejected(self):
        user = make_user(email='me@example.org')
        form = ChangeEmailForm(user, data={'new_email': 'ME@example.org', 'password': PASSWORD})
        self.assertIn('already your current email', str(form.errors['new_email']))

    def test_disposable_address_is_rejected(self):
        user = make_user()
        form = ChangeEmailForm(user, data={'new_email': 'x@mailinator.com', 'password': PASSWORD})
        self.assertIn('disposable', str(form.errors['new_email']))


class ArticleFormTestCase(SampleTestCase):
    def test_first_error_is_reported(self):
        form = ArticleForm(data={'title': '  ', 'content': ''})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.first_error(), 'Title is required.')

    def test_whitespace_is_trimmed(self):
        form = ArticleForm(data={'title': ' Title ', 'content': ' Text '})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {'title': 'Title', 'content': 'Text'})


class TaskImageChoiceTestCase(SampleTestCase):
    def test_non_numeric_gallery_id_is_ignored(self):
        """It used to raise a ValueError (500)"""
        self.login_as(make_staff())
        response = self.client.post(reverse('submit_task'), {
            'sha256': 'b' * 64,
            'download_link': 'https://example.com/sample',
            'description': 'd', 'goal': 'g',
            'difficulty': Difficulty.EASY, 'platform': Platform.WINDOWS,
            'tags': 'tag', 'tools': 'tool',
            'image_id': 'not-a-number',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnalysisTask.objects.get(sha256='b' * 64).image)
