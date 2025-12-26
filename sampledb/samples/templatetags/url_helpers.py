from django import template
from urllib.parse import urlencode

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