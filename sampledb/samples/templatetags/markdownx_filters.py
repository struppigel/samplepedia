from django import template
from django.utils.safestring import mark_safe
from markdownx.utils import markdownify as markdownx_markdownify

register = template.Library()


@register.filter(name='markdownify')
def markdownify(text):
    """
    Render markdown text as HTML using django-markdownx's markdownify function.
    """
    if not text:
        return ''
    return mark_safe(markdownx_markdownify(text))
