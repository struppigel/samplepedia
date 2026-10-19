from django import template

from samples.utils.markdown import render_markdown

register = template.Library()


@register.filter(name='markdownify')
def markdownify(text):
    """
    Render user markdown as sanitized HTML.
    """
    return render_markdown(text)
