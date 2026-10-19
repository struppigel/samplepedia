"""
Redirect helpers that only follow targets on this site.
"""
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme


def is_safe_url(request, url):
    return bool(url) and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


def safe_next_url(request, fallback, *args, allow_referer=True, **kwargs):
    """
    Return where to send the user next: the 'next' parameter (POST, then GET),
    then the Referer, using the first one that points at this site.
    Otherwise resolve `fallback` (URL, view name or model) like redirect() does.
    """
    candidates = [request.POST.get('next'), request.GET.get('next')]
    if allow_referer:
        candidates.append(request.META.get('HTTP_REFERER'))
    for url in candidates:
        if is_safe_url(request, url):
            return url
    return resolve_url(fallback, *args, **kwargs)
