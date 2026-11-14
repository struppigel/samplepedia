"""
Discord webhook notifications.

New samples and solutions go to the channel for the task's difficulty (falling
back to DISCORD_WEBHOOK_URL); account events go to DISCORD_WEBHOOK_LOGGING.
Sending is best effort: failures are logged and never break the request.
"""
import logging
import threading

import requests
from django.conf import settings
from django.db import connections

from .design_tokens import DANGER_COLOR, SUCCESS_COLOR, difficulty_embed_color, hex_to_int
from .models import SolutionType

logger = logging.getLogger(__name__)

BOT_NAME = 'Samplepedia Bot'
FOOTER = 'Samplepedia • Malware Training Samples'
TIMEOUT_SECONDS = 10
PREVIEW_LENGTH = 200


def send_in_background(send, *args):
    """
    Run one of the send_* functions without making the user's request wait for
    Discord. Tests run it inline so they can assert on the result.
    """
    if getattr(settings, 'TESTING', False):
        _run(send, args)
        return

    def run_and_close_connection():
        try:
            _run(send, args)
        finally:
            connections.close_all()  # this thread's DB connection

    threading.Thread(target=run_and_close_connection, daemon=True).start()


def _run(send, args):
    try:
        send(*args)
    except Exception:
        logger.exception('Discord notification %s failed', send.__name__)


def absolute_url(path):
    return f"{settings.BASE_URL.rstrip('/')}{path}"


def _webhook_for(difficulty):
    return getattr(settings, f'DISCORD_WEBHOOK_{difficulty.upper()}', '') or settings.DISCORD_WEBHOOK_URL


def _post(webhook_url, embed, *, about):
    """Send one embed. Returns whether Discord accepted it."""
    if not webhook_url:
        logger.info('Discord webhook not configured, skipping %s', about)
        return False
    try:
        response = requests.post(
            webhook_url, json={'embeds': [embed], 'username': BOT_NAME}, timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        details = getattr(getattr(error, 'response', None), 'text', '')
        logger.error('Discord notification for %s failed: %s %s', about, error, details)
        return False
    logger.info('Sent Discord notification for %s', about)
    return True


def _field(name, value, inline=False):
    return {'name': name, 'value': value, 'inline': inline}


def _preview(text):
    if not text:
        return 'N/A'
    return text[:PREVIEW_LENGTH] + '...' if len(text) > PREVIEW_LENGTH else text


def _add_thumbnail(embed, image):
    if not image:
        return
    try:
        embed['thumbnail'] = {'url': image.url}
    except Exception:
        logger.warning('Could not build a thumbnail URL for %s', image, exc_info=True)


def send_sample_notification(sample):
    """Announce a new sample in its difficulty's channel."""
    tags = [tag.name for tag in sample.tags.all()]
    tools = [tool.name for tool in sample.tools.all()]

    fields = [
        _field('Description', f'||{_preview(sample.description)}||'),  # spoiler
        _field('Goal', _preview(sample.goal)),
        _field('Difficulty', sample.get_difficulty_display(), inline=True),
        _field('Tags', ', '.join(tags) or 'None', inline=True),
    ]
    if tools:
        fields.append(_field('Tools', f"||{', '.join(tools)}||", inline=True))
    if sample.download_link:
        fields.append(_field('Download', f'[Click here]({sample.download_link})', inline=True))
    if sample.youtube_id:
        fields.append(_field(
            'Tutorial', f'[Watch on YouTube](https://www.youtube.com/watch?v={sample.youtube_id})', inline=True,
        ))

    embed = {
        'title': sample.sha256,
        'url': absolute_url(sample.get_absolute_url()),
        'description': 'A new malware training sample has been added to Samplepedia.',
        'color': difficulty_embed_color(sample.difficulty),
        'fields': fields,
        'footer': {'text': FOOTER},
    }
    _add_thumbnail(embed, sample.image)
    return _post(_webhook_for(sample.difficulty), embed, about=f'sample {sample.sha256}')


def send_solution_notification(solution):
    """Announce a new solution, or a hidden one whose hidden period ended, in its task's difficulty channel."""
    task = solution.analysis_task
    page_url = absolute_url(solution.get_absolute_url())
    type_display = solution.get_solution_type_display()
    # External solutions link straight to the writeup; on-site ones to their page here
    link = page_url if solution.solution_type == SolutionType.ONSITE else solution.url
    if solution.hidden_until:
        description = f'A {type_display.lower()} solution is now available for a malware sample.'
    else:
        description = f'A new {type_display.lower()} solution has been added to a malware sample.'

    embed = {
        'title': solution.title,
        'url': page_url,
        'description': description,
        'color': difficulty_embed_color(task.difficulty),
        'fields': [
            _field('Author', solution.author.username, inline=True),
            _field('Sample SHA256', f'[{task.sha256[:16]}...]({absolute_url(task.get_absolute_url())})', inline=True),
            _field('Solution Type', type_display, inline=True),
            _field('Difficulty', task.get_difficulty_display(), inline=True),
            _field('Solution Link', f'[View Solution]({link})'),
        ],
        'footer': {'text': FOOTER},
    }
    _add_thumbnail(embed, task.image)
    return _post(_webhook_for(task.difficulty), embed, about=f'solution {solution.id} (task {task.sha256})')


def send_user_registration_notification(username):
    """Log a new registration in the logging channel."""
    embed = {
        'title': '🎉 New User Registration',
        'description': 'A new user has joined Samplepedia!',
        'color': hex_to_int(SUCCESS_COLOR),
        'fields': [_field('Username', username, inline=True)],
        'footer': {'text': 'Samplepedia • User Registration'},
    }
    return _post(settings.DISCORD_WEBHOOK_LOGGING, embed, about=f'registration of {username}')


def send_account_deletion_notification(username, task_count, solution_count):
    """Log a deleted account and how much it had contributed in the logging channel."""
    embed = {
        'title': '👋 User Account Deleted',
        'description': 'A user has deleted their account.',
        'color': hex_to_int(DANGER_COLOR),
        'fields': [
            _field('Username', username, inline=True),
            _field('Contributions', f'{task_count} tasks, {solution_count} solutions', inline=True),
        ],
        'footer': {'text': 'Samplepedia • Account Deletion'},
    }
    return _post(settings.DISCORD_WEBHOOK_LOGGING, embed, about=f'deletion of {username}')
