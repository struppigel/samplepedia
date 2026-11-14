"""
Pages hand their scripts data through markup: URLs come from {% url %} in data-* attributes
(js/utils.js, js/app.js, js/comments.js, js/pages/*), never from inline scripts or handlers.
Also covers the |mention_links filter that links @mentions in comments on the server.
"""
import django_comments
from django.contrib.contenttypes.models import ContentType
from django.template import Context, Template
from django.urls import reverse

from samples.models import AnalysisTask, Notification, NotificationVerb
from samples.templatetags.comment_tags import mention_links, mentioned_users
from samples.tests.base import SampleTestCase
from samples.tests.factories import (
    make_article, make_onsite_solution, make_solution, make_staff, make_task, make_user,
)
from samples.tests.frontend_rules import EVENT_ATTR_RE, INLINE_SCRIPT_RE


def make_comment(task, user, text):
    return django_comments.get_model().objects.create(
        content_type=ContentType.objects.get_for_model(AnalysisTask),
        object_pk=task.id,
        user=user,
        user_name=user.username,
        user_email=user.email,
        comment=text,
        site_id=1,
    )


class MentionLinksTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice')
        cls.bob = make_user('bob')

    def profile_link(self, username):
        return f'<a href="{reverse("user_profile", args=[username])}" class="mention-link">@{username}</a>'

    def test_links_existing_users(self):
        html = mention_links('Thanks @alice and @bob!')
        self.assertIn(self.profile_link('alice'), html)
        self.assertIn(self.profile_link('bob'), html)

    def test_unknown_names_stay_text(self):
        html = mention_links('Hi @nobody')
        self.assertEqual(html, '<p>Hi @nobody</p>')

    def test_email_addresses_are_not_mentions(self):
        html = mention_links('Write to someone@alice or me.@bob')
        self.assertNotIn('<a', html)
        self.assertIn('someone@alice', html)

    def test_escapes_html(self):
        html = mention_links('<script>alert("x")</script> @alice <b>bold</b>')
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>', html)
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', html)
        self.assertIn(self.profile_link('alice'), html)

    def test_keeps_linebreaks(self):
        self.assertEqual(mention_links('one\ntwo @alice\n\nthree'),
                         f'<p>one<br>two {self.profile_link("alice")}</p>\n\n<p>three</p>')

    def test_uses_the_known_usernames_without_a_query(self):
        with self.assertNumQueries(0):
            html = mention_links('@alice @bob', frozenset({'alice'}))
        self.assertIn(self.profile_link('alice'), html)
        self.assertNotIn(self.profile_link('bob'), html)

    def test_mentioned_users_needs_one_query_for_a_list(self):
        task = make_task()
        comments = [make_comment(task, self.alice, text) for text in ('@bob', '@alice @ghost', 'x@alice')]
        with self.assertNumQueries(1):
            self.assertEqual(mentioned_users(comments), {'alice', 'bob'})

    def test_template_usage(self):
        task = make_task()
        comments = [make_comment(task, self.bob, 'Hey @alice')]
        html = Template(
            '{% load comment_tags %}{% mentioned_users comments as known %}'
            '{% for c in comments %}{{ c.comment|mention_links:known }}{% endfor %}'
        ).render(Context({'comments': comments}))
        self.assertEqual(html, f'<p>Hey {self.profile_link("alice")}</p>')


class PageHooksTestCase(SampleTestCase):
    """The data-* hooks carry the URLs the scripts call"""

    @classmethod
    def setUpTestData(cls):
        cls.author = make_user('author')
        cls.commenter = make_user('commenter')
        cls.task = make_task(author=cls.author)
        cls.reference = make_solution(task=cls.task)
        cls.community = make_solution(task=cls.task, author=cls.commenter)
        cls.comment = make_comment(cls.task, cls.commenter, 'Nice one @author, see me@author.org')

    def get_detail(self, user):
        self.login_as(user)
        response = self.client.get(self.task.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return response

    def assertNoInlineScripts(self, response):
        html = response.content.decode()
        self.assertEqual(INLINE_SCRIPT_RE.findall(html), [])
        self.assertEqual(EVENT_ATTR_RE.findall(html), [])

    def test_detail_solution_buttons(self):
        response = self.get_detail(self.commenter)
        delete_url = reverse('delete_solution', args=[self.task.sha256, self.task.id, self.community.id])
        self.assertContains(response, f'data-post-url="{delete_url}"')
        self.assertContains(response, f'data-post-next="{self.task.get_absolute_url()}"')
        self.assertContains(response, f'data-confirm="Are you sure you want to delete &quot;{self.community.title}&quot;?')
        self.assertContains(response, f'data-like-url="{reverse("toggle_solution_like", args=[self.community.id])}"')
        self.assertContains(response, f'data-like-url="{reverse("toggle_like", args=[self.task.sha256, self.task.id])}"')
        attach_url = reverse('attach_draft_to_sample', args=[self.task.sha256, self.task.id])
        self.assertContains(response, f'data-attach-draft-url="{attach_url}"')
        self.assertContains(response, f'data-back-url="{reverse("sample_list")}"')
        self.assertContains(response, 'data-scroll-to="comments-section"')

    def test_detail_page_scripts_are_static_files(self):
        response = self.get_detail(self.commenter)
        self.assertNoInlineScripts(response)
        self.assertContains(response, 'js/draft-selection.js"></script>')
        self.assertContains(response, 'js/pages/sample-detail.js"></script>')

    def test_comment_author_gets_edit_and_delete(self):
        response = self.get_detail(self.commenter)
        self.assertContains(response, f'data-post-url="{reverse("delete_comment", args=[self.comment.id])}"')
        self.assertContains(response, 'data-comment-edit')
        self.assertContains(response, 'data-comment-cancel')
        self.assertContains(response, f'action="{reverse("comments-xtd-edit", args=[self.comment.id])}"')
        self.assertContains(response, f'id="edit-form-{self.comment.id}" hidden')
        # The edit form and the new-comment form both autocomplete mentions
        self.assertContains(response, f'data-mention-search-url="{reverse("search_users")}"', count=2)

    def test_task_author_can_only_delete_comments(self):
        response = self.get_detail(self.author)
        self.assertContains(response, f'data-post-url="{reverse("delete_comment", args=[self.comment.id])}"')
        self.assertNotContains(response, 'data-comment-edit')

    def test_comment_mentions_are_linked(self):
        response = self.get_detail(self.author)
        profile = reverse('user_profile', args=['author'])
        self.assertContains(response, f'<a href="{profile}" class="mention-link">@author</a>', count=1)
        self.assertContains(response, 'see me@author.org')

    def test_task_list_filter_bar(self):
        self.login_as(self.commenter)
        response = self.client.get(reverse('sample_list'), {'browse': 'true'})
        self.assertNoInlineScripts(response)
        self.assertContains(response, 'data-autosubmit', count=3)
        self.assertContains(response, 'data-favorites-toggle')
        self.assertContains(response, 'id="submitTaskBtn" data-clears-drafts="task-form"')
        self.assertContains(response, f'data-like-url="{reverse("toggle_like", args=[self.task.sha256, self.task.id])}"')

    def test_article_list_buttons(self):
        draft = make_article(author=self.commenter)
        published = make_onsite_solution(task=self.task, author=self.commenter)
        self.login_as(self.commenter)
        response = self.client.get(reverse('article_list'))
        self.assertNoInlineScripts(response)
        self.assertContains(response, f'data-publish-article="{draft.id}"')
        self.assertContains(response, f'data-post-url="{reverse("article_delete", args=[draft.id])}"')
        self.assertContains(response, f'data-post-url="{reverse("article_unpublish", args=[published.article.id])}"')
        self.assertContains(response, f'data-post-url="{reverse("article_delete", args=[published.article.id])}"')
        self.assertContains(response, 'js/pages/articles.js"></script>')

    def test_article_view_publish_button(self):
        draft = make_article(author=self.commenter)
        self.login_as(self.commenter)
        response = self.client.get(reverse('article_view', args=[draft.id]))
        self.assertNoInlineScripts(response)
        self.assertContains(response, f'data-publish-article="{draft.id}"')

    def test_onsite_solution_back_link(self):
        solution = make_onsite_solution(task=self.task, author=self.commenter)
        self.login_as(self.commenter)
        response = self.client.get(reverse('view_onsite_solution', args=[self.task.sha256, self.task.id, solution.id]))
        self.assertNoInlineScripts(response)
        self.assertContains(response, f'<a href="{self.task.get_absolute_url()}" class="btn-back')

    def test_profile_and_notifications_confirm_through_markup(self):
        Notification.objects.create(recipient=self.commenter, actor=self.author, verb=NotificationVerb.COMMENTED,
                                    target=self.task, description='commented')
        self.login_as(self.commenter)
        for url in (reverse('user_profile', args=['commenter']), reverse('notification_list')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNoInlineScripts(response)
                self.assertContains(response, 'data-confirm="')

    def test_notification_dropdown_sends_read_urls(self):
        notification = Notification.objects.create(
            recipient=self.commenter, actor=self.author, verb=NotificationVerb.COMMENTED,
            target=self.task, description='commented')
        self.login_as(self.commenter)
        data = self.client.get(reverse('notification_dropdown')).json()
        self.assertEqual(data['notifications'][0]['read_url'],
                         reverse('mark_notification_read', args=[notification.id]))

    def test_staff_sees_comment_delete(self):
        response = self.get_detail(make_staff())
        self.assertContains(response, f'data-post-url="{reverse("delete_comment", args=[self.comment.id])}"')
