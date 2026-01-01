from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def impressum(request):
    """Display impressum/legal notice page"""
    return render(request, "samples/impressum.html")


def privacy_policy(request):
    """Display privacy policy page"""
    return render(request, "samples/privacy.html")


@login_required
def markdown_editor(request):
    """Full-featured markdown editor for blog-like solution submissions"""
    return render(request, "samples/markdown_editor.html")
