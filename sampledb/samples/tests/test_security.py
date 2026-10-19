"""
Security regression tests: response headers, markdown sanitizing, XSS-safe
templates, redirect validation and HTTP method restrictions.
"""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from samples.models import AnalysisTask, Article, Difficulty, Solution, SolutionType
from samples.utils.markdown import render_markdown

XSS_MARKDOWN = (
    '# Heading {: onclick="alert(1)" .evil #sp }\n\n'
    '<script>alert(1)</script>\n\n'
    '<img src="x" onerror="alert(1)">\n\n'
    '[click](javascript:alert(1))\n\n'
    '<a href="https://example.com" onmouseover="alert(1)">hover</a>\n'
)


class RenderMarkdownTestCase(SimpleTestCase):
    """render_markdown must strip active content but keep what the extensions generate."""

    def test_strips_scripts_and_handlers(self):
        html = render_markdown(XSS_MARKDOWN)
        self.assertNotIn('<script', html)
        self.assertNotIn('onclick', html)
        self.assertNotIn('onerror', html)
        self.assertNotIn('onmouseover', html)
        self.assertNotIn('javascript:', html)
        self.assertNotIn('evil', html)
        self.assertNotIn('id="sp"', html)

    def test_keeps_tables_with_alignment(self):
        html = render_markdown('| a | b |\n|:--|--:|\n| 1 | 2 |')
        self.assertIn('<table>', html)
        self.assertIn('<th style="text-align:left">', html)
        self.assertIn('<td style="text-align:right">', html)

    def test_keeps_code_highlighting_classes(self):
        html = render_markdown('```python\nprint("hi")\n```')
        self.assertIn('<pre><code class="language-python">', html)

    def test_keeps_footnotes(self):
        html = render_markdown('Text[^1].\n\n[^1]: Note.')
        self.assertIn('id="fnref:1"', html)
        self.assertIn('class="footnote-ref"', html)
        self.assertIn('href="#fn:1"', html)

    def test_keeps_links_and_images(self):
        html = render_markdown('[l](https://example.com) ![i](https://example.com/a.png)')
        self.assertIn('href="https://example.com"', html)
        self.assertIn('src="https://example.com/a.png"', html)

    def test_empty_input(self):
        self.assertEqual(render_markdown(''), '')
        self.assertEqual(render_markdown(None), '')


class MarkdownRenderPathsTestCase(TestCase):
    """Every view that renders user markdown must sanitize it."""

    def setUp(self):
        self.user = User.objects.create_user(username='author', password='testpass123')
        self.task = AnalysisTask.objects.create(
            sha256='c' * 64,
            goal=XSS_MARKDOWN,
            description=XSS_MARKDOWN,
            difficulty=Difficulty.EASY,
            author=self.user,
        )
        self.article = Article.objects.create(title='Article', content=XSS_MARKDOWN, author=self.user)
        self.solution = Solution.objects.create(
            analysis_task=self.task,
            title='Article',
            solution_type=SolutionType.ONSITE,
            article=self.article,
            author=self.user,
        )
        self.client.login(username='author', password='testpass123')

    def assert_sanitized(self, html):
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('onerror="alert(1)"', html)
        self.assertNotIn('onclick="alert(1)"', html)
        self.assertNotIn('href="javascript:', html)

    def test_task_detail(self):
        response = self.client.get(reverse('sample_detail', args=[self.task.sha256, self.task.id]))
        self.assertEqual(response.status_code, 200)
        self.assert_sanitized(response.content.decode())

    def test_article_view(self):
        # Published articles redirect to the solution view, so render a draft
        draft = Article.objects.create(title='Draft', content=XSS_MARKDOWN, author=self.user)
        response = self.client.get(reverse('article_view', args=[draft.id]))
        self.assertEqual(response.status_code, 200)
        self.assert_sanitized(response.content.decode())

    def test_onsite_solution_view(self):
        response = self.client.get(
            reverse('view_onsite_solution', args=[self.task.sha256, self.task.id, self.solution.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assert_sanitized(response.content.decode())

    def test_markdown_preview_endpoint(self):
        response = self.client.post(reverse('markdown_preview'), {'content': XSS_MARKDOWN})
        self.assertEqual(response.status_code, 200)
        self.assert_sanitized(response.json()['html'])


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
