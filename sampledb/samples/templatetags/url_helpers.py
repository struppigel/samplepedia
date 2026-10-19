from django import template

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


@register.simple_tag(takes_context=True)
def page_url(context, number, param='page'):
    """
    Link to another page of a paginated list, keeping the other query parameters.
    Usage: {% page_url page_obj.next_page_number %} or {% page_url 2 'tasks_page' %}
    """
    query = context['request'].GET.copy()
    query[param] = number
    return f"?{query.urlencode()}"
