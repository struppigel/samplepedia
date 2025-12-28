from django import template
from urllib.parse import urlencode, urlparse, parse_qs
import re

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Preserves existing URL parameters while replacing/adding specified ones.
    Usage: {% url_replace sort='sha256' %}
    """
    query = context['request'].GET.copy()
    
    for key, value in kwargs.items():
        if value:
            query[key] = value
        elif key in query:
            del query[key]
    
    return f"?{query.urlencode()}"


@register.filter
def extract_youtube_id(url):
    """
    Extract YouTube video ID from various YouTube URL formats.
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    """
    if not url:
        return None
    
    # Pattern 1: youtube.com/watch?v=VIDEO_ID
    match = re.search(r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 2: youtu.be/VIDEO_ID
    match = re.search(r'(?:youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 3: youtube.com/embed/VIDEO_ID
    match = re.search(r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 4: youtube.com/v/VIDEO_ID
    match = re.search(r'(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    return None