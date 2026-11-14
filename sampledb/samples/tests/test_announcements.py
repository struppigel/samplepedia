"""
Tests for samples/services/announcements.py and manage.py announce_solutions:
each solution is announced on Discord exactly once, when it becomes publicly
visible; hidden ones only after hidden_until has passed.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

import requests
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from samples.models import Solution
from samples.services.announcements import announce_solution, due_solutions
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_onsite_solution, make_solution, make_task
from samples.tests.test_discord import WEBHOOKS


@override_settings(**WEBHOOKS)
@mock.patch('samples.discord_utils.requests.post')
class AnnouncementTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task = make_task()

    def make_hidden(self, **fields):
        return make_onsite_solution(task=self.task, hidden_until=timezone.now() + timedelta(weeks=2), **fields)

    def end_hiding(self, solution, ago=timedelta(minutes=5)):
        """Move hidden_until into the past, as if the hidden period had ended `ago`."""
        Solution.objects.filter(pk=solution.pk).update(hidden_until=timezone.now() - ago)

    def run_command(self, *args):
        out = StringIO()
        call_command('announce_solutions', *args, stdout=out)
        return out.getvalue()

    def announced_at(self, solution):
        return Solution.objects.values_list('discord_announced_at', flat=True).get(pk=solution.pk)

    def test_visible_solution_is_announced_when_created(self, post):
        with self.captureOnCommitCallbacks(execute=True):
            solution = make_solution(task=self.task)
        post.assert_called_once()
        self.assertIsNotNone(self.announced_at(solution))
        # ... and the hourly run doesn't post it again
        self.assertIn('Announced 0, not posted 0', self.run_command())
        post.assert_called_once()

    def test_hidden_solution_waits_until_its_hidden_period_ends(self, post):
        with self.captureOnCommitCallbacks(execute=True):
            solution = self.make_hidden()
        self.run_command()
        post.assert_not_called()
        self.assertIsNone(self.announced_at(solution))

        self.end_hiding(solution)
        self.assertIn('Announced 1, not posted 0', self.run_command())
        post.assert_called_once()
        self.assertIsNotNone(self.announced_at(solution))

        self.run_command()
        post.assert_called_once()

    def test_previously_hidden_solution_says_it_is_now_available(self, post):
        def description():
            return post.call_args.kwargs['json']['embeds'][0]['description']

        solution = self.make_hidden()
        self.end_hiding(solution)
        self.run_command()
        self.assertIn('solution is now available', description())

        announce_solution(make_solution(task=self.task))
        self.assertIn('solution has been added', description())

    def test_failed_post_is_retried_on_the_next_run(self, post):
        solution = self.make_hidden()
        self.end_hiding(solution)
        post.side_effect = requests.ConnectionError('down')
        with self.assertLogs('samples.discord_utils', level='ERROR'):
            self.assertIn('Announced 0, not posted 1', self.run_command())
        self.assertIsNone(self.announced_at(solution))

        post.side_effect = None
        self.assertIn('Announced 1, not posted 0', self.run_command())
        self.assertIsNotNone(self.announced_at(solution))

    def test_solutions_visible_for_longer_than_max_age_are_skipped(self, post):
        solution = self.make_hidden()
        self.end_hiding(solution, ago=timedelta(days=8))
        self.run_command()
        post.assert_not_called()
        self.assertIn('Announced 1', self.run_command('--max-age-days', '9'))

    def test_dry_run_posts_and_changes_nothing(self, post):
        solution = self.make_hidden()
        self.end_hiding(solution)
        output = self.run_command('--dry-run')
        self.assertIn(f'Would announce solution {solution.pk}', output)
        self.assertIn('1 solution(s) due', output)
        post.assert_not_called()
        self.assertIsNone(self.announced_at(solution))

    def test_a_solution_is_posted_only_once(self, post):
        solution = make_solution(task=self.task)
        self.assertTrue(announce_solution(solution))
        self.assertFalse(announce_solution(solution))
        post.assert_called_once()

    def test_still_hidden_solutions_are_not_due(self, post):
        hidden = self.make_hidden()
        visible = make_solution(task=self.task)  # created outside on_commit: not announced yet
        self.assertEqual(list(due_solutions()), [visible])
        self.assertNotIn(hidden, due_solutions())


@mock.patch('samples.discord_utils.requests.post')
class UnconfiguredWebhookTestCase(SampleTestCase):
    """Without webhooks (local runs, tests) nothing is posted and nothing is marked announced."""

    def test_nothing_is_marked_announced(self, post):
        solution = make_solution()
        self.assertFalse(announce_solution(solution))
        post.assert_not_called()
        self.assertIsNone(Solution.objects.get(pk=solution.pk).discord_announced_at)
