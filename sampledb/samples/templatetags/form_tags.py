"""
Form rendering helpers: one Bootstrap 5 form field, the Turnstile challenge,
and the password rules of the configured validators.

    {% load form_tags %}
    {% form_field form.email label="Email Address" help_text="We'll never share it." %}
    {% password_rules as rules %}{% form_field form.password1 help_text=rules %}
    {% turnstile form.turnstile 'submit-button' %}
"""
from django import forms, template
from django.contrib.auth.password_validation import password_validators_help_texts
from django.forms.widgets import Input
from django.utils.html import format_html, format_html_join

register = template.Library()

# Global JS function (samples/_turnstile_script.html) that Turnstile calls once solved
TURNSTILE_CALLBACK = 'spTurnstileSolved'


def bootstrap_class(widget):
    """Bootstrap's class for a widget that has none of its own; '' for widgets we leave alone."""
    if isinstance(widget, forms.CheckboxInput):
        return 'form-check-input'
    if isinstance(widget, forms.Select):
        return 'form-select'
    if isinstance(widget, (Input, forms.Textarea)):
        return 'form-control'
    return ''


def field_context(field, label=None, help_text=None, wrapper_class='mb-3', attrs=None):
    """Context for samples/_form_field.html: the rendered widget plus its label, errors and help text."""
    label = field.label if label is None else label
    help_text = field.help_text if help_text is None else help_text
    widget = field.field.widget
    attrs = dict(attrs or {})

    base_class = bootstrap_class(widget)
    if base_class:
        classes = widget.attrs.get('class') or base_class
        attrs['class'] = f'{classes} is-invalid' if field.errors else classes

    # The ids Django itself uses for help text and errors (BoundField.aria_describedby)
    described_by = [
        f'{field.auto_id}_{suffix}' for suffix, shown in (('helptext', help_text), ('error', field.errors)) if shown
    ]
    if field.auto_id and described_by:
        attrs['aria-describedby'] = ' '.join(described_by)

    return {
        'field': field,
        'widget': field.as_widget(attrs=attrs),
        'label': label,
        'help_text': help_text,
        'wrapper_class': wrapper_class,
        'is_checkbox': isinstance(widget, forms.CheckboxInput),
    }


@register.inclusion_tag('samples/_form_field.html')
def form_field(field, label=None, help_text=None, wrapper_class='mb-3', **attrs):
    """
    One bound field: label, widget, errors and help text, Bootstrap 5 style.
    label and help_text default to the field's own; pass "" to leave them out.
    Other keyword arguments become widget attributes (underscores turn into dashes):
    {% form_field form.new_password1 autofocus=True %}
    """
    attrs = {name.replace('_', '-'): value for name, value in attrs.items()}
    return field_context(field, label, help_text, wrapper_class, attrs)


@register.inclusion_tag('samples/_turnstile.html')
def turnstile(field, button_id):
    """
    The form's Cloudflare Turnstile challenge. The submit button with id button_id
    should start out disabled; it is enabled once the challenge is solved.
    """
    return field_context(field, label='', help_text='', attrs={
        'data-callback': TURNSTILE_CALLBACK,
        'data-submit-button': button_id,
    })


@register.simple_tag
def password_rules():
    """The rules of the configured password validators (AUTH_PASSWORD_VALIDATORS) as a list."""
    rules = password_validators_help_texts()
    if not rules:
        return ''
    items = format_html_join('', '<li>{}</li>', ((rule,) for rule in rules))
    return format_html('<ul class="mb-0">{}</ul>', items)
