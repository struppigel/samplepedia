"""
Tests for account e-mails (samples/services/emails.py): registration
verification, resending it, password reset and e-mail change.
"""
import re

from django.contrib.auth.models import User
from django.core import mail
from django.urls import resolve, reverse

from samples.tests.base import SampleTestCase
from samples.tests.factories import PASSWORD, make_user

LINK_RE = re.compile(r'https?://testserver(/\S+?/)\s')


def link_in(message):
    return LINK_RE.search(message.body).group(1)


class RegistrationEmailTestCase(SampleTestCase):
    def test_registration_sends_a_working_verification_link(self):
        response = self.client.post(reverse('register'), {
            'username': 'newbie',
            'email': 'newbie@example.org',
            'password1': 'a-Long-unusual-pass-42',
            'password2': 'a-Long-unusual-pass-42',
        })
        self.assertRedirects(response, reverse('verification_sent'), fetch_redirect_response=False)
        self.assertFalse(User.objects.get(username='newbie').is_active)

        (message,) = mail.outbox
        self.assertEqual(message.to, ['newbie@example.org'])
        self.assertEqual(message.alternatives[0][1], 'text/html')
        path = link_in(message)
        self.assertEqual(resolve(path).url_name, 'verify_email')

        self.client.get(path)
        self.assertTrue(User.objects.get(username='newbie').is_active)


class ResendVerificationTestCase(SampleTestCase):
    MESSAGE = 'If an unverified account exists with this email, a verification link has been sent.'

    def resend(self, email):
        return self.client.post(reverse('resend_verification'), {'email': email}, follow=True)

    def test_unverified_account_gets_a_new_link(self):
        make_user(email='waiting@example.org', is_active=False)
        self.assertContains(self.resend('waiting@example.org'), self.MESSAGE)
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_and_unknown_addresses_look_the_same(self):
        make_user(email='done@example.org')
        for email in ('done@example.org', 'nobody@example.org'):
            with self.subTest(email=email):
                self.assertContains(self.resend(email), self.MESSAGE)
        self.assertEqual(mail.outbox, [])


class PasswordResetTestCase(SampleTestCase):
    def reset(self, email):
        return self.client.post(reverse('password_reset'), {'email': email})

    def test_reset_link_works(self):
        user = make_user(email='me@example.org')
        response = self.reset('me@example.org')
        self.assertRedirects(response, reverse('password_reset_done'), fetch_redirect_response=False)

        (message,) = mail.outbox
        self.assertEqual(message.subject, 'Password Reset Request - Samplepedia')
        path = link_in(message)
        self.assertEqual(resolve(path).url_name, 'password_reset_confirm')

        # The confirm view swaps the token into the session and redirects to a set-password form
        form_url = self.client.get(path).url
        self.client.post(form_url, {'new_password1': 'Another-pass-123', 'new_password2': 'Another-pass-123'})
        user.refresh_from_db()
        self.assertTrue(user.check_password('Another-pass-123'))

    def test_shared_address_does_not_crash(self):
        make_user(email='shared@example.org')
        make_user(email='shared@example.org')
        self.reset('shared@example.org')
        self.assertEqual(len(mail.outbox), 2)

    def test_unknown_address_sends_nothing(self):
        response = self.reset('nobody@example.org')
        self.assertRedirects(response, reverse('password_reset_done'), fetch_redirect_response=False)
        self.assertEqual(mail.outbox, [])


class ChangeEmailTestCase(SampleTestCase):
    def test_new_address_must_confirm_before_the_change(self):
        user = make_user(email='old@example.org')
        self.login_as(user)

        self.client.post(reverse('change_email'), {'new_email': 'new@example.org', 'password': PASSWORD})

        (message,) = mail.outbox
        self.assertEqual(message.to, ['new@example.org'])
        user.refresh_from_db()
        self.assertEqual(user.email, 'old@example.org')

        path = link_in(message)
        self.assertEqual(resolve(path).url_name, 'verify_email_change')
        self.client.get(path)
        user.refresh_from_db()
        self.assertEqual(user.email, 'new@example.org')
