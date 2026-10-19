"""
Account e-mails. Each is sent as HTML plus a plain-text alternative, rendered
from registration/<name>.html and registration/<name>.txt; links are built
with reverse() and the current request's host.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_templated_email(name, *, subject, to, context):
    send_mail(
        subject=subject,
        message=render_to_string(f'registration/{name}.txt', context),
        html_message=render_to_string(f'registration/{name}.html', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )


def one_time_link(request, viewname, user):
    """(absolute URL, token) for a view taking uidb64 and token, e.g. verify_email."""
    token = default_token_generator.make_token(user)
    path = reverse(viewname, kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk)), 'token': token})
    return request.build_absolute_uri(path), token


def send_verification_email(request, user):
    """Ask a new user to confirm their address; the link activates the account."""
    link, _ = one_time_link(request, 'verify_email', user)
    send_templated_email(
        'verification_email',
        subject='Verify your Samplepedia account',
        to=user.email,
        context={'user': user, 'verification_url': link},
    )


def send_email_change_verification(request, user, new_email):
    """
    Ask the owner of `new_email` to confirm the change. Returns the token, which
    the caller keeps with the pending address until the link is opened.
    """
    link, token = one_time_link(request, 'verify_email_change', user)
    send_templated_email(
        'email_change_verification',
        subject='Verify your new email address - Samplepedia',
        to=new_email,
        context={'user': user, 'new_email': new_email, 'verification_url': link},
    )
    return token


def send_password_reset_email(request, form):
    """Send reset links for a valid PasswordResetForm (to every active account with that address)."""
    form.save(
        request=request,
        use_https=request.is_secure(),
        # The Sites framework's domain isn't maintained; the request host is
        domain_override=request.get_host(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        subject_template_name='registration/password_reset_subject.txt',
        email_template_name='registration/password_reset_email.txt',
        html_email_template_name='registration/password_reset_email.html',
    )
