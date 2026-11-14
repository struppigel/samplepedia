from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.translation.trans_real import parse_accept_lang_header
from django.views.decorators.vary import vary_on_headers

# The legal pages exist in German and English only
LEGAL_LANGUAGES = ('de', 'en')


def legal_language(request):
    """
    Language of a legal page: ?lang=de|en, else the first German or English
    entry of the browser's Accept-Language, else English.
    """
    requested = request.GET.get('lang', '').lower()
    if requested in LEGAL_LANGUAGES:
        return requested
    for code, _quality in parse_accept_lang_header(request.headers.get('Accept-Language', '')):
        primary = code.split('-')[0]
        if primary in LEGAL_LANGUAGES:
            return primary
    return 'en'


@vary_on_headers('Accept-Language')
def impressum(request):
    """Display impressum/legal notice page"""
    return render(request, "samples/impressum.html", {'lang': legal_language(request)})


@vary_on_headers('Accept-Language')
def privacy_policy(request):
    """Display privacy policy page"""
    return render(request, "samples/privacy.html", {'lang': legal_language(request)})


@login_required
def markdown_editor(request):
    """Full-featured markdown editor for blog-like solution submissions"""
    return render(request, "samples/markdown_editor.html")
