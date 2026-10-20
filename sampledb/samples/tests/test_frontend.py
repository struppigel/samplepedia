"""
Front-end guardrails (rules in samples/tests/frontend_rules.py):

1. No inline <script> blocks in templates (JSON data blocks excepted)
2. No inline on*= event handlers or javascript: URLs, in templates or in HTML built by JavaScript
3. No app URLs hardcoded in JavaScript (templates pass them via data-* attributes)
4. No hand-parsed cookies outside utils.js (use sp.csrfToken())
5. No .style.display toggling (use sp.show() / the hidden attribute)

Together they let the Content-Security-Policy forbid inline scripts and handlers.
"""
from django.test import SimpleTestCase

from samples.tests import frontend_rules


class FrontendRulesTestCase(SimpleTestCase):
    def assertNoFindings(self, check):
        findings = [f'{name}:{line}: {message}' for name, line, message in check()]
        self.assertEqual(findings, [], '\n'.join(findings))

    def test_no_inline_scripts(self):
        self.assertNoFindings(frontend_rules.inline_scripts)

    def test_no_inline_event_handlers(self):
        self.assertNoFindings(frontend_rules.inline_event_handlers)

    def test_no_javascript_urls(self):
        self.assertNoFindings(frontend_rules.javascript_urls)

    def test_no_hardcoded_urls_in_js(self):
        self.assertNoFindings(frontend_rules.hardcoded_urls)

    def test_no_cookie_parsing_outside_utils(self):
        self.assertNoFindings(frontend_rules.cookie_parsing)

    def test_no_display_toggling(self):
        self.assertNoFindings(frontend_rules.display_toggling)
