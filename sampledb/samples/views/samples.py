from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.db.models import Count, Case, When, IntegerField
from django.db import transaction
from taggit.models import Tag
import re

from ..models import AnalysisTask, Difficulty, SampleImage
from ..forms import AnalysisTaskForm


def sample_list(request):
    q = request.GET.get("q", "")
    tag = request.GET.get("tag")
    difficulty = request.GET.get("difficulty")
    favorites_only = request.GET.get("favorites") == "true"
    sort = request.GET.get("sort", "-id")  # Default to reverse chronological

    # Annotate with favorite count and difficulty order for sorting
    samples = AnalysisTask.objects.annotate(
        favorite_count_annotated=Count('favorited_by'),
        difficulty_order=Case(
            When(difficulty='easy', then=1),
            When(difficulty='medium', then=2),
            When(difficulty='advanced', then=3),
            When(difficulty='expert', then=4),
            output_field=IntegerField(),
        ),
        has_video=Case(
            When(youtube_id='', then=0),
            default=1,
            output_field=IntegerField(),
        )
    ).all()

    # filter course samples, those are only displayed in course view
    # if they overlap, they need a different description anyways
    samples = samples.exclude(course_references__isnull=False).distinct()

    if q:
        samples = samples.filter(sha256__icontains=q)

    if tag:
        samples = samples.filter(tags__name=tag)

    if difficulty:
        samples = samples.filter(difficulty=difficulty)
    
    # Filter by favorites if requested and user is authenticated
    if favorites_only and request.user.is_authenticated:
        samples = samples.filter(favorited_by=request.user)

    samples = samples.distinct()
    
    # Apply sorting with custom difficulty order
    valid_sorts = {
        'sha256': 'sha256',
        '-sha256': '-sha256',
        'difficulty': 'difficulty_order',
        '-difficulty': '-difficulty_order',
        'goal': 'goal',
        '-goal': '-goal',
        'video': 'has_video',
        '-video': '-has_video',
        'likes': 'favorite_count_annotated',
        '-likes': '-favorite_count_annotated',
        'created': 'created_at',
        '-created': '-created_at',
        '-id': '-id',  # Default
    }
    
    sort_field = valid_sorts.get(sort, '-id')
    samples = samples.order_by(sort_field, '-id')  # Secondary sort by ID for consistency

    paginator = Paginator(samples, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Get user's favorited sample IDs for display
    user_favorited_ids = set()
    if request.user.is_authenticated:
        user_favorited_ids = set(
            request.user.favorite_samples.values_list('id', flat=True)
        )
        print(f"DEBUG VIEW: User authenticated: {request.user.username}, favorited_ids: {user_favorited_ids}")
    else:
        print(f"DEBUG VIEW: User not authenticated")
    
    # Get all tags used in samples
    all_tags = Tag.objects.filter(
        taggit_taggeditem_items__content_type__model='analysistask'
    ).distinct().order_by(Lower('name'))

    return render(request, "samples/list.html", {
        "page_obj": page_obj,
        "q": q,
        "selected_tag": tag,
        "selected_difficulty": difficulty,
        "all_tags": all_tags,
        "difficulties": Difficulty.choices,
        "favorites_only": favorites_only,
        "user_favorited_ids": user_favorited_ids,
        "sort": sort,
    })


def sample_detail(request, sha256, task_id):
    sample = get_object_or_404(AnalysisTask, id=task_id)
    
    # Check if user has favorited this sample
    user_has_favorited = False
    if request.user.is_authenticated:
        user_has_favorited = sample.favorited_by.filter(id=request.user.id).exists()
    
    # Get solutions for this sample
    solutions = sample.solutions.select_related('author').all()
    
    # Find first YouTube solution if sample doesn't have youtube_id
    youtube_solution = None
    if not sample.youtube_id:
        for solution in solutions:
            youtube_id = extract_youtube_id(solution.url)
            if youtube_id:
                youtube_solution = {
                    'youtube_id': youtube_id,
                    'title': solution.title,
                    'author': solution.author
                }
                break
    
    return render(request, "samples/detail.html", {
        "sample": sample,
        "user_has_liked": user_has_favorited,
        "solutions": solutions,
        "youtube_solution": youtube_solution,
    })


def extract_youtube_id(url):
    """Extract YouTube video ID from various YouTube URL formats."""
    if not url:
        return None
    
    # Pattern 1: youtube.com/watch?v=VIDEO_ID
    match = re.search(r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 2: youtu.be/VIDEO_ID
    match = re.search(r'(?:youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 3: youtube.com/embed/VIDEO_ID
    match = re.search(r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    # Pattern 4: youtube.com/v/VIDEO_ID
    match = re.search(r'(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    
    return None


@login_required
@permission_required('samples.add_analysistask', raise_exception=True)
def submit_task(request):
    """Allow users to submit their own analysis task"""
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST)
        if form.is_valid():
            # Use atomic transaction to ensure tags/tools are saved before Discord notification
            with transaction.atomic():
                sample = form.save(commit=False)
                sample.author = request.user
                
                # Handle image selection
                image_id = request.POST.get('image_id')
                if image_id:
                    try:
                        sample_image = SampleImage.objects.get(id=image_id)
                        sample.image = sample_image.image
                    except SampleImage.DoesNotExist:
                        pass
                
                sample.save()
                
                # Convert tags and tools to lowercase and save (must happen in same transaction for Discord)
                if form.cleaned_data.get('tags'):
                    tags = [tag.strip().lower() for tag in form.cleaned_data['tags'] if tag.strip()]
                    sample.tags.set(tags)
                
                if form.cleaned_data.get('tools'):
                    tools = [tool.strip().lower() for tool in form.cleaned_data['tools'] if tool.strip()]
                    sample.tools.set(tools)
            
            # Transaction committed, Discord notification will fire now with correct data
            messages.success(request, f'AnalysisTask {sample.sha256[:12]}... submitted successfully!')
            return redirect('sample_detail', sha256=sample.sha256, task_id=sample.id)
    else:
        form = AnalysisTaskForm()
    
    # Get available images from image library
    available_images = SampleImage.objects.all()
    
    return render(request, 'samples/submit_task.html', {
        'form': form,
        'available_images': available_images,
    })
