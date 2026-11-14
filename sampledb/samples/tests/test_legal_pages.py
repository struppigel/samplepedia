"""
Tests for the bilingual legal pages (impressum, privacy policy) and for the
account e-mail templates that share registration/_email_base.html.

Legal pages: the server renders exactly one language, chosen by ?lang=de|en,
else by the browser's Accept-Language, else English, and links to the other one.
E-mails: plain-text parts are not HTML-escaped; HTML parts are, and keep their links.
"""
import re
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse

from samples.tests.base import SampleTestCase

GERMAN = 'de-DE,de;q=0.9'
ENGLISH = 'en-US,en;q=0.9'


class LegalPagesLanguageTestCase(SampleTestCase):
    # url name: {lang: (text only in that language, <title>)}
    PAGES = {
        'impressum': {
            'de': ('Haftung für Inhalte', 'Impressum - Samplepedia'),
            'en': ('Liability for Content', 'Impressum (Legal Notice) - Samplepedia'),
        },
        'privacy_policy': {
            'de': ('Datenschutz auf einen Blick', 'Datenschutzerklärung - Samplepedia'),
            'en': ('Data Protection at a Glance', 'Privacy Policy - Samplepedia'),
        },
    }
    OTHER = {'de': 'en', 'en': 'de'}

    def get(self, name, accept_language=None, **params):
        headers = {'HTTP_ACCEPT_LANGUAGE': accept_language} if accept_language else {}
        response = self.client.get(reverse(name), params, **headers)
        self.assertEqual(response.status_code, 200)
        return response

    def assertRenderedIn(self, response, name, lang):
        other = self.OTHER[lang]
        marker, title = self.PAGES[name][lang]
        self.assertContains(response, marker)
        self.assertNotContains(response, self.PAGES[name][other][0])
        self.assertContains(response, f'<title>{title}</title>')
        self.assertContains(response, f'class="card-body" lang="{lang}"')
        # The switch links to the other language only
        self.assertContains(response, f'href="?lang={other}"')
        self.assertNotContains(response, f'href="?lang={lang}"')

    def test_lang_parameter_selects_language(self):
        for name in self.PAGES:
            for lang in ('de', 'en'):
                with self.subTest(page=name, lang=lang):
                    self.assertRenderedIn(self.get(name, lang=lang), name, lang)

    def test_lang_parameter_beats_accept_language(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertRenderedIn(self.get(name, GERMAN, lang='en'), name, 'en')
                self.assertRenderedIn(self.get(name, ENGLISH, lang='de'), name, 'de')

    def test_default_follows_accept_language(self):
        cases = [
            (GERMAN, 'de'),
            ('de', 'de'),
            (ENGLISH, 'en'),
            ('fr-FR,fr;q=0.9', 'en'),
            ('fr-FR,de;q=0.8,en;q=0.5', 'de'),  # first of German/English wins
            ('fr-FR,en;q=0.8,de;q=0.5', 'en'),
            (None, 'en'),
        ]
        for name in self.PAGES:
            for header, lang in cases:
                with self.subTest(page=name, accept_language=header):
                    self.assertRenderedIn(self.get(name, header), name, lang)

    def test_unknown_lang_falls_back_to_accept_language(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertRenderedIn(self.get(name, GERMAN, lang='fr'), name, 'de')
                self.assertRenderedIn(self.get(name, lang='fr'), name, 'en')
                self.assertRenderedIn(self.get(name, lang=''), name, 'en')

    def test_response_varies_on_accept_language(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertIn('Accept-Language', self.get(name).headers.get('Vary', ''))

    def test_no_client_side_toggle(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                response = self.get(name)
                self.assertNotContains(response, 'impressum-lang-toggle')
                self.assertNotContains(response, 'content-de')
                self.assertNotContains(response, 'content-en')


ENTITY_RE = re.compile(r'&(#\d+|#x[0-9a-f]+|[a-z]+);', re.I)


class EmailTemplateRenderingTestCase(SimpleTestCase):
    """Render each account e-mail directly, with values that need HTML escaping."""

    USER = SimpleNamespace(username="o'brien&co")
    NEW_EMAIL = "o'brien&co@example.org"
    VERIFICATION_URL = 'https://example.org/verify/MQ/set-token/?next=/a&b'

    def render(self, name, context):
        return (
            render_to_string(f'registration/{name}.html', context),
            render_to_string(f'registration/{name}.txt', context),
        )

    def assertMailParts(self, html, text, url):
        self.assertIsNone(ENTITY_RE.search(text), 'HTML entity in the plain-text part')
        self.assertIn("o'brien&co", text)
        self.assertIn(url, text)
        # HTML part: autoescaped, built on the shared base, with a working button and copy link
        self.assertIn('o&#x27;brien&amp;co', html)
        self.assertIn('class="header', html)
        escaped_url = url.replace('&', '&amp;')
        self.assertIn(f'href="{escaped_url}" class="button"', html)
        self.assertEqual(html.count(escaped_url), 2)

    def test_verification_email(self):
        html, text = self.render('verification_email', {
            'user': self.USER, 'verification_url': self.VERIFICATION_URL,
        })
        self.assertMailParts(html, text, self.VERIFICATION_URL)

    def test_email_change_verification(self):
        html, text = self.render('email_change_verification', {
            'user': self.USER, 'new_email': self.NEW_EMAIL, 'verification_url': self.VERIFICATION_URL,
        })
        self.assertMailParts(html, text, self.VERIFICATION_URL)
        self.assertIn(self.NEW_EMAIL, text)
        self.assertIn('o&#x27;brien&amp;co@example.org', html)

    def test_password_reset_email(self):
        context = {
            'user': self.USER, 'protocol': 'https', 'domain': 'example.org',
            'uid': 'MQ', 'token': 'set-token', 'site_name': 'example.org',
        }
        html, text = self.render('password_reset_email', context)
        url = 'https://example.org' + reverse('password_reset_confirm', kwargs={'uidb64': 'MQ', 'token': 'set-token'})
        self.assertMailParts(html, text, url)
        self.assertIn('header-danger', html)

        subject = render_to_string('registration/password_reset_subject.txt', context)
        self.assertEqual(subject, 'Password Reset Request - Samplepedia')
