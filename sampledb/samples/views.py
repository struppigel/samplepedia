from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Sample, Difficulty
from django.core.paginator import Paginator
from taggit.models import Tag


def sample_list(request):
    q = request.GET.get("q", "")
    tag = request.GET.get("tag")
    difficulty = request.GET.get("difficulty")

    samples = Sample.objects.all().order_by("-id")

    if q:
        samples = samples.filter(sha256__icontains=q)

    if tag:
        samples = samples.filter(tags__name=tag)

    if difficulty:
        samples = samples.filter(difficulty=difficulty)

    samples = samples.distinct()

    paginator = Paginator(samples, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Get all tags used in samples
    all_tags = Tag.objects.filter(
        taggit_taggeditem_items__content_type__model='sample'
    ).distinct().order_by('name')

    return render(request, "samples/list.html", {
        "page_obj": page_obj,
        "q": q,
        "selected_tag": tag,
        "selected_difficulty": difficulty,
        "all_tags": all_tags,
        "difficulties": Difficulty.choices,
    })



def sample_detail(request, sha256):
    sample = get_object_or_404(Sample, sha256=sha256)
    
    # Check if user has liked this sample (stored in cookies)
    liked_samples = request.COOKIES.get('liked_samples', '').split(',')
    user_has_liked = sha256 in liked_samples
    
    return render(request, "samples/detail.html", {
        "sample": sample,
        "user_has_liked": user_has_liked,
    })


def toggle_like(request, sha256):
    """Toggle like for a sample using cookies to track"""
    sample = get_object_or_404(Sample, sha256=sha256)
    
    # Get list of liked samples from cookies
    liked_samples = request.COOKIES.get('liked_samples', '').split(',')
    liked_samples = [s for s in liked_samples if s]  # Remove empty strings
    
    if sha256 in liked_samples:
        # Unlike: remove from cookie and decrement counter
        liked_samples.remove(sha256)
        sample.like_count = max(0, sample.like_count - 1)
        user_has_liked = False
    else:
        # Like: add to cookie and increment counter
        liked_samples.append(sha256)
        sample.like_count += 1
        user_has_liked = True
    
    sample.save()
    
    # Return JSON response for AJAX
    response = JsonResponse({
        'liked': user_has_liked,
        'like_count': sample.like_count
    })
    
    # Update cookie with new liked samples list
    response.set_cookie('liked_samples', ','.join(liked_samples), max_age=365*24*60*60)  # 1 year
    
    return response
