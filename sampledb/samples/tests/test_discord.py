"""
Tests for samples/discord_utils.py: which webhook gets which post, what the
embeds link to, and that failures are logged instead of raised.
"""
from unittest import mock

import requests
from django.test import override_settings

from samples import discord_utils
from samples.models import Difficulty
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_onsite_solution, make_solution, make_task

WEBHOOKS = {
    'DISCORD_WEBHOOK_URL': 'https://discord.invalid/default',
    'DISCORD_WEBHOOK_EASY': 'https://discord.invalid/easy',
    'DISCORD_WEBHOOK_EXPERT': '',
    'DISCORD_WEBHOOK_LOGGING': 'https://discord.invalid/logging',
    'BASE_URL': 'https://samplepedia.example/',
}


@override_settings(**WEBHOOKS)
@mock.patch('samples.discord_utils.requests.post')
class DiscordTestCase(SampleTestCase):
    def posted(self, post):
        """(webhook url, embed) of the single post"""
        post.assert_called_once()
        return post.call_args.args[0], post.call_args.kwargs['json']['embeds'][0]

    def test_sample_goes_to_its_difficulty_channel(self, post):
        task = make_task(difficulty=Difficulty.EASY)
        self.assertTrue(discord_utils.send_sample_notification(task))
        url, embed = self.posted(post)
        self.assertEqual(url, 'https://discord.invalid/easy')
        self.assertEqual(embed['url'], f'https://samplepedia.example{task.get_absolute_url()}')

    def test_unconfigured_difficulty_falls_back_to_default(self, post):
        discord_utils.send_sample_notification(make_task(difficulty=Difficulty.EXPERT))
        self.assertEqual(self.posted(post)[0], 'https://discord.invalid/default')

    def test_description_is_a_spoiler_and_long_text_is_cut(self, post):
        discord_utils.send_sample_notification(make_task(description='x' * 300))
        fields = {f['name']: f['value'] for f in self.posted(post)[1]['fields']}
        self.assertEqual(fields['Description'], '||' + 'x' * 200 + '...||')

    def test_onsite_solution_links_to_its_page(self, post):
        solution = make_onsite_solution()
        discord_utils.send_solution_notification(solution)
        embed = self.posted(post)[1]
        page = f'https://samplepedia.example{solution.get_absolute_url()}'
        self.assertEqual(embed['url'], page)
        self.assertIn(f'({page})', embed['fields'][-1]['value'])

    def test_external_solution_links_to_the_writeup(self, post):
        solution = make_solution(url='https://blog.example/post')
        discord_utils.send_solution_notification(solution)
        self.assertIn('(https://blog.example/post)', self.posted(post)[1]['fields'][-1]['value'])

    def test_account_events_go_to_the_logging_channel(self, post):
        discord_utils.send_user_registration_notification('newbie')
        self.assertEqual(self.posted(post)[0], 'https://discord.invalid/logging')

    def test_failures_are_logged_not_raised(self, post):
        post.side_effect = requests.ConnectionError('down')
        with self.assertLogs('samples.discord_utils', level='ERROR'):
            self.assertFalse(discord_utils.send_user_registration_notification('newbie'))

    @override_settings(DISCORD_WEBHOOK_LOGGING='')
    def test_missing_webhook_skips_quietly(self, post):
        self.assertFalse(discord_utils.send_user_registration_notification('newbie'))
        post.assert_not_called()

    def test_background_sending_swallows_unexpected_errors(self, post):
        def broken(_):
            raise ValueError('bug')

        with self.assertLogs('samples.discord_utils', level='ERROR'):
            discord_utils.send_in_background(broken, 'x')
