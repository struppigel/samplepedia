"""
Comment rendering: @mentions become links to the mentioned user's profile.

    {% load comment_tags %}
    {% mentioned_users comment_list as known_users %}   {# one query for the whole list #}
    {{ comment.comment|mention_links:known_users }}

Without the set, mention_links looks the mentioned users up itself (one query per comment).
"""
from django import template
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import escape, format_html, linebreaks
from django.utils.safestring import mark_safe

from samples.signals import MENTION_RE

register = template.Library()


def existing_usernames(texts):
    """The usernames @mentioned in the texts that belong to an account."""
    mentioned = {username for text in texts for username in MENTION_RE.findall(text or '')}
    if not mentioned:
        return frozenset()
    return frozenset(User.objects.filter(username__in=mentioned).values_list('username', flat=True))


@register.simple_tag
def mentioned_users(comments):
    """The existing usernames @mentioned anywhere in the comments, for mention_links."""
    return existing_usernames(comment.comment for comment in comments)


@register.filter(is_safe=True)
def mention_links(text, known_usernames=None):
    """
    Like |linebreaks, with each @username of an existing user linked to their profile.
    The text is escaped; e-mail addresses (name@host) are not mentions.
    """
    text = text or ''
    if known_usernames is None:
        known_usernames = existing_usernames([text])

    parts = []
    last = 0
    for match in MENTION_RE.finditer(text):
        username = match.group(1)
        if username not in known_usernames:
            continue
        parts.append(escape(text[last:match.start()]))
        parts.append(format_html(
            '<a href="{}" class="mention-link">@{}</a>',
            reverse('user_profile', args=[username]),
            username,
        ))
        last = match.end()
    parts.append(escape(text[last:]))

    return mark_safe(linebreaks(''.join(parts), autoescape=False))
