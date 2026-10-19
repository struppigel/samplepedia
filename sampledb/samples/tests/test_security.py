"""
Security regression tests: response headers, markdown sanitizing, XSS-safe
templates, redirect validation and HTTP method restrictions.
"""
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django_comments.forms import CommentSecurityForm
from django_comments_xtd.models import XtdComment

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


TEMPLATES_DIR = Path(settings.BASE_DIR) / 'samples' / 'templates'
EVENT_HANDLER_RE = re.compile(r'\son[a-z]+="([^"]*)"')
TEMPLATE_VAR_RE = re.compile(r'\{\{\s*(.*?)\s*\}\}')
# Integer ids are safe in JS; anything else must be escaped for a JS string
SAFE_JS_VAR_RE = re.compile(r'[\w.]+\.(id|pk)|.*\|escapejs')


class InlineHandlerInterpolationTestCase(SimpleTestCase):
    """
    HTML-escaped values are decoded by the browser before an on*= handler runs,
    so a quote in user data would break out of the JS string.
    """

    def test_template_vars_in_event_handlers_are_js_safe(self):
        violations = []
        for template in sorted(TEMPLATES_DIR.rglob('*.html')):
            text = template.read_text(encoding='utf-8')
            for handler in EVENT_HANDLER_RE.findall(text):
                for expr in TEMPLATE_VAR_RE.findall(handler):
                    if not SAFE_JS_VAR_RE.fullmatch(expr):
                        violations.append(f'{template.relative_to(TEMPLATES_DIR)}: {{{{ {expr} }}}}')
        self.assertEqual(violations, [])


class ExternalLinkTestCase(TestCase):
    """A solution URL must not reach a JS context."""

    def test_malicious_solution_url_is_not_interpolated_into_js(self):
        author = User.objects.create_user(username='author', password='testpass123')
        task = AnalysisTask.objects.create(sha256='d' * 64, goal='g', author=author)
        Solution.objects.create(
            analysis_task=task,
            title='Evil',
            solution_type=SolutionType.BLOG,
            url="https://example.com/');alert(1);//",
            author=author,
        )
        html = self.client.get(reverse('sample_detail', args=[task.sha256, task.id])).content.decode()
        self.assertIn('data-external-confirm', html)
        self.assertNotIn('return confirm(', html)


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


# Turnstile would call Cloudflare; its validate() also enforces the required token
skip_turnstile = mock.patch('turnstile.fields.TurnstileField.validate', lambda self, value: None)


@skip_turnstile
class LoginRedirectTestCase(TestCase):
    def setUp(self):
        User.objects.create_user(username='reader', password='testpass123')

    def login(self, **params):
        return self.client.post(reverse('login'), {'username': 'reader', 'password': 'testpass123', **params})

    def test_honours_posted_next(self):
        self.assertRedirects(self.login(next='/courses/'), '/courses/', fetch_redirect_response=False)

    def test_rejects_external_next(self):
        self.assertRedirects(self.login(next='https://evil.example/'), '/', fetch_redirect_response=False)

    def test_rejects_scheme_relative_next(self):
        self.assertRedirects(self.login(next='//evil.example/'), '/', fetch_redirect_response=False)

    def test_external_next_not_rendered_into_form(self):
        response = self.client.get(reverse('login'), {'next': 'https://evil.example/'})
        self.assertNotContains(response, 'evil.example')


class NextRedirectTestCase(TestCase):
    """Views that redirect to 'next' or the Referer must stay on this site."""

    def setUp(self):
        self.author = User.objects.create_user(username='author', password='testpass123')
        User.objects.create_user(username='other', password='testpass123')
        self.task = AnalysisTask.objects.create(sha256='f' * 64, goal='g', author=self.author)
        self.solution = Solution.objects.create(
            analysis_task=self.task, title='Ref', solution_type=SolutionType.BLOG,
            url='https://example.com/', author=self.author,
        )
        self.url = reverse('delete_solution', args=[self.task.sha256, self.task.id, self.solution.id])
        self.detail_url = reverse('sample_detail', args=[self.task.sha256, self.task.id])
        # A user who may not delete gets an error message and a redirect
        self.client.login(username='other', password='testpass123')

    def test_external_next_falls_back(self):
        response = self.client.post(self.url, {'next': 'https://evil.example/'})
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)

    def test_external_referer_falls_back(self):
        response = self.client.post(self.url, HTTP_REFERER='https://evil.example/')
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)

    def test_internal_next_is_followed(self):
        response = self.client.post(self.url, {'next': '/courses/'})
        self.assertRedirects(response, '/courses/', fetch_redirect_response=False)

    def test_article_delete_rejects_external_next(self):
        article = Article.objects.create(title='A', content='c', author=self.author)
        response = self.client.post(reverse('article_delete', args=[article.id]), {'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('article_list'), fetch_redirect_response=False)


class LikeEndpointTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author', password='testpass123')
        self.task = AnalysisTask.objects.create(sha256='1' * 64, goal='g', author=self.author)
        self.solution = Solution.objects.create(
            analysis_task=self.task, title='S', solution_type=SolutionType.BLOG,
            url='https://example.com/', author=self.author,
        )
        self.task_like_url = reverse('toggle_like', args=[self.task.sha256, self.task.id])
        self.solution_like_url = reverse('toggle_solution_like', args=[self.solution.id])

    def test_get_does_not_change_state(self):
        self.client.login(username='author', password='testpass123')
        self.assertEqual(self.client.get(self.task_like_url).status_code, 405)
        self.assertEqual(self.client.get(self.solution_like_url).status_code, 405)
        self.assertEqual(self.task.favorited_by.count(), 0)
        self.assertEqual(self.solution.liked_by.count(), 0)

    def test_anonymous_gets_real_login_url(self):
        for url in (self.task_like_url, self.solution_like_url):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['redirect'], settings.LOGIN_URL)


class CommentPostingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='commenter', password='testpass123')
        self.task = AnalysisTask.objects.create(sha256='2' * 64, goal='g', author=self.user)

    def comment_data(self, text):
        return {**CommentSecurityForm(self.task).generate_security_data(), 'comment': text, 'reply_to': 0}

    def test_anonymous_post_is_rejected(self):
        response = self.client.post(reverse('comments-post-comment'), self.comment_data('spam'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response['Location'])
        self.assertEqual(XtdComment.objects.count(), 0)

    def test_comment_api_is_disabled(self):
        response = self.client.post('/comments/api/comment/', {**self.comment_data('spam'), 'name': 'x', 'email': 'x@x.com'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(XtdComment.objects.count(), 0)

    def test_author_lands_on_highlighted_comment(self):
        self.client.login(username='commenter', password='testpass123')
        response = self.client.post(reverse('comments-post-comment'), self.comment_data('hello'), follow=True)
        comment = XtdComment.objects.get()
        self.assertEqual(comment.user, self.user)
        expected = f'{self.task.get_absolute_url()}?highlight=comment-{comment.id}'
        self.assertEqual(response.redirect_chain[-1][0], f'{expected}#comment-{comment.id}')

    def test_posted_with_bad_id_is_404(self):
        self.assertEqual(self.client.get(reverse('comments-comment-done'), {'c': 'abc'}).status_code, 404)


class EditorImageUploadTestCase(TestCase):
    def test_upload_error_does_not_leak_details(self):
        User.objects.create_user(username='writer', password='testpass123')
        self.client.login(username='writer', password='testpass123')
        image = SimpleUploadedFile('a.png', b'\x89PNG', content_type='image/png')
        with mock.patch('samples.views.solutions.EditorImage.objects.create', side_effect=Exception('api_secret=xyz')):
            with self.assertLogs('samples.views.solutions', level='ERROR'):
                response = self.client.post(reverse('upload_editor_image'), {'image': image})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('api_secret', response.content.decode())
