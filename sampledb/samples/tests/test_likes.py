"""
Tests for liking tasks and solutions (samples/services/likes.py) and the
aggregated like notifications, plus notification icons and pagination.
"""
from django.urls import reverse

from samples.models import Notification, NotificationVerb
from samples.services.likes import toggle_like
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_solution, make_task, make_user


class LikeNotificationTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user('owner')
        cls.task = make_task(author=cls.owner)
        cls.alice, cls.bob, cls.carol = make_user('alice'), make_user('bob'), make_user('carol')

    def notification(self):
        return Notification.objects.get(recipient=self.owner, verb=NotificationVerb.LIKED_TASK)

    def test_first_like_notifies_owner(self):
        liked, count = toggle_like(self.task, self.alice)
        self.assertEqual((liked, count), (True, 1))
        self.assertEqual(self.notification().description, 'alice liked your sample')
        self.assertEqual(self.notification().actor, self.alice)

    def test_likes_aggregate_into_one_notification(self):
        toggle_like(self.task, self.alice)
        toggle_like(self.task, self.bob)
        self.assertEqual(self.notification().description, 'bob and alice liked your sample')
        toggle_like(self.task, self.carol)
        self.assertEqual(self.notification().description, 'carol and 2 others liked your sample')
        self.assertEqual(self.notification().actor, self.carol)

    def test_unlike_keeps_the_other_likers(self):
        for user in (self.alice, self.bob, self.carol):
            toggle_like(self.task, user)

        liked, count = toggle_like(self.task, self.carol)

        self.assertEqual((liked, count), (False, 2))
        self.assertEqual(self.notification().description, 'bob and alice liked your sample')
        self.assertEqual(self.notification().actor, self.bob)

    def test_last_unlike_removes_the_notification(self):
        toggle_like(self.task, self.alice)
        toggle_like(self.task, self.alice)
        self.assertFalse(Notification.objects.exists())

    def test_read_notifications_are_left_alone(self):
        toggle_like(self.task, self.alice)
        self.notification().mark_as_read()

        toggle_like(self.task, self.bob)

        notifications = Notification.objects.filter(recipient=self.owner).order_by('timestamp')
        self.assertEqual([n.unread for n in notifications], [False, True])
        toggle_like(self.task, self.bob)
        toggle_like(self.task, self.alice)
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)  # the read one

    def test_liking_your_own_task_does_not_notify(self):
        liked, _ = toggle_like(self.task, self.owner)
        self.assertTrue(liked)
        self.assertFalse(Notification.objects.exists())

    def test_own_like_is_not_counted_in_the_description(self):
        toggle_like(self.task, self.owner)
        toggle_like(self.task, self.alice)
        self.assertEqual(self.notification().description, 'alice liked your sample')

    def test_solution_like_mentions_the_title(self):
        solution = make_solution(task=self.task, title='A' * 80)
        toggle_like(solution, self.alice)
        notification = Notification.objects.get(verb=NotificationVerb.LIKED_SOLUTION)
        self.assertEqual(notification.description, f"alice liked your solution '{'A' * 60}...'")


class LikeEndpointTestCase(SampleTestCase):
    def test_endpoints_return_state_and_count(self):
        solution = make_solution()
        task = solution.analysis_task
        self.login_as(make_user())

        response = self.client.post(reverse('toggle_like', args=[task.sha256, task.id]))
        self.assertEqual(response.json(), {'liked': True, 'like_count': 1})

        response = self.client.post(reverse('toggle_solution_like', args=[solution.id]))
        self.assertEqual(response.json(), {'liked': True, 'like_count': 1})


class NotificationViewsTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user()
        cls.solution = make_solution(author=cls.owner)

    def setUp(self):
        self.login_as(self.owner)

    def notify(self, verb, target=None, count=1):
        for _ in range(count):
            Notification.objects.create(
                recipient=self.owner, actor=make_user(), verb=verb,
                target=target or self.solution.analysis_task, description=f'{verb} happened',
            )

    def test_every_verb_has_an_icon(self):
        for verb in NotificationVerb.values:
            self.assertNotIn('fa-bell', Notification(verb=verb).icon, verb)

    def test_page_and_dropdown_use_the_same_icon(self):
        self.notify(NotificationVerb.MENTIONED)
        page = self.client.get(reverse('notification_list'))
        dropdown = self.client.get(reverse('notification_dropdown')).json()
        self.assertContains(page, 'fas fa-at')
        self.assertEqual(dropdown['notifications'][0]['icon'], 'fas fa-at text-info')

    def test_list_is_paginated(self):
        self.notify(NotificationVerb.COMMENTED, count=30)
        first = self.client.get(reverse('notification_list'))
        self.assertEqual(len(first.context['page_obj']), 25)
        self.assertContains(first, '?page=2')
        second = self.client.get(reverse('notification_list'), {'page': 2})
        self.assertEqual(len(second.context['page_obj']), 5)

    def test_opening_a_solution_notification_highlights_the_solution(self):
        self.notify(NotificationVerb.LIKED_SOLUTION, target=self.solution)
        notification = Notification.objects.get(verb=NotificationVerb.LIKED_SOLUTION)
        response = self.client.get(reverse('mark_notification_read', args=[notification.id]))
        self.assertRedirects(
            response, f'{self.solution.analysis_task.get_absolute_url()}?highlight_solution={self.solution.id}',
            fetch_redirect_response=False,
        )
        notification.refresh_from_db()
        self.assertFalse(notification.unread)
