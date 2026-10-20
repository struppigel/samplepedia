"""
The account and registration pages render their forms through samples/templatetags/form_tags.py:
{% form_field %} (label, widget, errors, help text), {% turnstile %} and {% password_rules %}.
"""
import re
from unittest import mock

from django.contrib.auth.password_validation import password_validators_help_texts
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.utils.http import urlsafe_base64_encode

from samples.tests.base import SampleTestCase
from samples.tests.factories import PASSWORD, make_user


def reset_confirm_url(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return reverse('password_reset_confirm', args=[uid, default_token_generator.make_token(user)])


class FormPageTestCase(SampleTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('formuser')

    def get_reset_confirm_form(self):
        """GET the reset link; Django moves the token into the session and redirects to the form."""
        response = self.client.get(reset_confirm_url(self.user), follow=True)
        self.assertTrue(response.context['validlink'])
        return response

    def widget_tag(self, html, name):
        match = re.search(rf'<(?:input|select|textarea)\b[^>]*\bname="{name}"[^>]*>', html)
        self.assertIsNotNone(match, f'no widget named {name}')
        return match

    def assertField(self, html, name):
        """The field's widget carries a Bootstrap class and has a label pointing at it."""
        tag = self.widget_tag(html, name).group(0)
        self.assertRegex(tag, r'class="[^"]*\b(form-control|form-select|form-check-input)\b')
        self.assertIn(f'for="id_{name}"', html)

    def assertFieldError(self, response, name, message):
        """The error is rendered right after the field's widget and the widget is marked invalid."""
        html = response.content.decode()
        widget = self.widget_tag(html, name)
        self.assertIn('is-invalid', widget.group(0))
        self.assertIn(f'id_{name}_error', widget.group(0))  # aria-describedby

        error = re.search(rf'<div class="invalid-feedback d-block" id="id_{name}_error">(.*?)</div>\s*</div>', html, re.S)
        self.assertIsNotNone(error, f'no error block for {name}')
        self.assertIn(escape(message), error.group(1))
        between = html[widget.end():error.start()]
        self.assertNotRegex(between, r'<(input|select|textarea)\b', 'error is not next to its field')


class FormPagesRenderTestCase(FormPageTestCase):
    """Every page returns 200 with a consistent title and shows its fields."""

    ANONYMOUS_PAGES = [
        ('login', [], 'Login', ['username', 'password']),
        ('register', [], 'Register', ['username', 'email', 'password1', 'password2']),
        ('password_reset', [], 'Reset Password', ['email']),
        ('resend_verification', [], 'Resend Verification Email', ['email']),
        ('password_reset_done', [], 'Password Reset Email Sent', []),
        ('password_reset_complete', [], 'Password Reset Complete', []),
        ('verification_sent', [], 'Verification Email Sent', []),
        ('verify_email', ['invalid', 'invalid-token'], 'Email Verification', []),
        ('password_reset_confirm', ['invalid', 'invalid-token'], 'Set New Password', []),
    ]
    ACCOUNT_PAGES = [
        ('profile_settings', [], 'Profile Settings', []),
        ('change_password', [], 'Change Password', ['current_password', 'new_password1', 'new_password2']),
        ('change_email', [], 'Change Email', ['new_email', 'password']),
        ('delete_account', [], 'Delete Account', ['password', 'confirm_deletion']),
        ('verify_email_change', ['invalid', 'invalid-token'], 'Email Verification', []),
    ]

    def assertPage(self, response, title, fields):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<title>{title} - Samplepedia</title>', html=True)
        html = response.content.decode()
        for name in fields:
            with self.subTest(field=name):
                self.assertField(html, name)

    def test_anonymous_pages(self):
        for url_name, args, title, fields in self.ANONYMOUS_PAGES:
            with self.subTest(page=url_name):
                self.assertPage(self.client.get(reverse(url_name, args=args)), title, fields)

    def test_account_pages(self):
        self.login_as(self.user)
        for url_name, args, title, fields in self.ACCOUNT_PAGES:
            with self.subTest(page=url_name):
                self.assertPage(self.client.get(reverse(url_name, args=args)), title, fields)

    def test_password_reset_confirm_form(self):
        response = self.get_reset_confirm_form()
        self.assertPage(response, 'Set New Password', ['new_password1', 'new_password2'])
        html = response.content.decode()
        self.assertIn('autofocus', self.widget_tag(html, 'new_password1').group(0))
        self.assertContains(response, '<label class="form-label" for="id_new_password2">Confirm New Password</label>', html=True)

    def test_delete_confirmation_is_a_bootstrap_checkbox(self):
        self.login_as(self.user)
        html = self.client.get(reverse('delete_account')).content.decode()
        self.assertRegex(
            html,
            r'<div class="form-check">\s*<input type="checkbox" name="confirm_deletion"[^>]*>\s*'
            r'<label class="form-check-label" for="id_confirm_deletion">',
        )

    def test_custom_labels_and_help_texts(self):
        response = self.client.get(reverse('register'))
        self.assertContains(response, '<label class="form-label" for="id_password2">Confirm Password</label>', html=True)
        self.assertContains(response, "We'll send a verification link to this address.")
        response = self.client.get(reverse('password_reset'))
        self.assertContains(response, '<label class="form-label" for="id_email">Email Address</label>', html=True)
        self.assertContains(response, 'id="id_email_helptext"')


class FormErrorsTestCase(FormPageTestCase):
    """A form posted with errors shows each message next to its field."""

    def test_login(self):
        response = self.client.post(reverse('login'), {'username': 'formuser', 'password': ''})
        self.assertFieldError(response, 'password', 'This field is required.')

    def test_register(self):
        response = self.client.post(reverse('register'), {
            'username': 'newcomer', 'email': 'not-an-email',
            'password1': 'Str0ng-Passw0rd', 'password2': 'different-Passw0rd',
        })
        self.assertFieldError(response, 'email', 'Enter a valid email address.')
        self.assertFieldError(response, 'password2', 'The two password fields didn’t match.')

    def test_password_reset(self):
        response = self.client.post(reverse('password_reset'), {'email': 'not-an-email'})
        self.assertFieldError(response, 'email', 'Enter a valid email address.')
        self.assertContains(response, 'Enter a valid email address.', count=1)

    def test_resend_verification(self):
        response = self.client.post(reverse('resend_verification'), {'email': 'not-an-email'})
        self.assertFieldError(response, 'email', 'Enter a valid email address.')

    def test_password_reset_confirm(self):
        form_url = self.get_reset_confirm_form().redirect_chain[-1][0]
        response = self.client.post(form_url, {'new_password1': 'Str0ng-Passw0rd', 'new_password2': 'other'})
        self.assertFieldError(response, 'new_password2', 'The two password fields didn’t match.')
        self.assertContains(response, 'Please correct the errors below.')

    def test_change_password(self):
        self.login_as(self.user)
        response = self.client.post(reverse('change_password'), {
            'current_password': 'wrong', 'new_password1': 'Str0ng-Passw0rd', 'new_password2': 'Str0ng-Passw0rd',
        })
        self.assertFieldError(response, 'current_password', 'Your current password is incorrect.')

    def test_change_email(self):
        self.login_as(self.user)
        response = self.client.post(reverse('change_email'), {'new_email': 'new@example.org', 'password': 'wrong'})
        self.assertFieldError(response, 'password', 'Your password is incorrect.')

    def test_delete_account(self):
        self.login_as(self.user)
        response = self.client.post(reverse('delete_account'), {'password': PASSWORD})
        self.assertFieldError(
            response, 'confirm_deletion', 'You must confirm that you understand this action is permanent.'
        )


class PasswordRulesTestCase(FormPageTestCase):
    """The password rules come from AUTH_PASSWORD_VALIDATORS, not from hardcoded text."""

    def pages(self):
        yield 'register', self.client.get(reverse('register'))
        yield 'password_reset_confirm', self.get_reset_confirm_form()
        self.login_as(self.user)
        yield 'change_password', self.client.get(reverse('change_password'))

    def test_rules_of_configured_validators_are_shown(self):
        rules = password_validators_help_texts()
        self.assertTrue(rules)
        for page, response in self.pages():
            for rule in rules:
                with self.subTest(page=page, rule=rule):
                    self.assertContains(response, f'<li>{escape(rule)}</li>', html=True)

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    }])
    def test_rules_follow_the_settings(self):
        for page, response in self.pages():
            with self.subTest(page=page):
                self.assertContains(response, 'at least 12 characters')
                self.assertNotContains(response, 'at least 8 characters')
                self.assertNotContains(response, 'commonly used password')


class TurnstileTestCase(FormPageTestCase):
    """Each protected form renders the challenge, which enables that form's (initially disabled) button."""

    PAGES = [
        ('login', 'login-button', False),
        ('register', 'register-button', False),
        ('password_reset', 'reset-button', False),
        ('resend_verification', 'resend-button', False),
        ('change_password', 'password-button', True),
        ('change_email', 'email-button', True),
        ('delete_account', 'delete-button', True),
    ]

    @mock.patch('turnstile.widgets.ENABLE', True)  # the tests switch Turnstile off
    def test_widget_enables_the_forms_submit_button(self):
        for url_name, button_id, needs_login in self.PAGES:
            with self.subTest(page=url_name):
                if needs_login:
                    self.login_as(self.user)
                html = self.client.get(reverse(url_name)).content.decode()
                widget = re.search(r'<div class="cf-turnstile"[^>]*>', html)
                self.assertIsNotNone(widget)
                self.assertIn('data-callback="spTurnstileSolved"', widget.group(0))
                self.assertIn(f'data-submit-button="{button_id}"', widget.group(0))
                self.assertRegex(html, rf'<button type="submit" id="{button_id}"[^>]*\bdisabled\b')
                # The callback (js/turnstile.js) is defined before the widget loads Turnstile
                script = re.search(r'<script src="[^"]*js/turnstile\.js"></script>', html)
                self.assertIsNotNone(script)
                self.assertLess(script.start(), widget.start())
                self.assertEqual(html.count('js/turnstile.js'), 1)
