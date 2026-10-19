"""
Security regression tests: response headers, markdown sanitizing, XSS-safe
templates, redirect validation and HTTP method restrictions.
"""
from django.test import TestCase


class SecurityHeadersTestCase(TestCase):
    """The CSP header must restrict who may frame the site."""

    def test_frame_ancestors_restricted(self):
        response = self.client.get('/impressum/')
        policy = response.headers.get('Content-Security-Policy', '')
        self.assertIn("frame-ancestors 'self' https://malwareanalysis-for-hedgehogs.learnworlds.com", policy)
        self.assertIn("object-src 'none'", policy)

    def test_no_default_src_blocking_cdns(self):
        # A default-src would block the CDN assets until a full policy exists
        response = self.client.get('/impressum/')
        self.assertNotIn('default-src', response.headers.get('Content-Security-Policy', ''))
