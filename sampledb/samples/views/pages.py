from django.shortcuts import render


def impressum(request):
    """Display impressum/legal notice page"""
    return render(request, "samples/impressum.html")


def privacy_policy(request):
    """Display privacy policy page"""
    return render(request, "samples/privacy.html")
