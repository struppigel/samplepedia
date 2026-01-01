from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.db.models import Count, Case, When, IntegerField
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from taggit.models import Tag
import re

from ..models import AnalysisTask, Difficulty, SampleImage, Solution
from ..forms import AnalysisTaskForm
from markdownx.utils import markdownify


def sample_list(request):
    # Show landing page to non-authenticated users (unless they want to browse)
    browse = request.GET.get("browse", "")
    if not request.user.is_authenticated and not browse:
        return render(request, "samples/landing.html")
    
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
    
    # Get user's liked solution IDs
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    # Count reference solutions (by task author) for delete permission check
    reference_solution_count = solutions.filter(author=sample.author).count()
    
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
        "user_can_edit": sample.user_can_edit(request.user),
        "user_liked_solution_ids": user_liked_solution_ids,
        "reference_solution_count": reference_solution_count,
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
def submit_task(request):
    """Allow users to submit their own analysis task"""
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST, user=request.user, is_edit=False)
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
                
                # Create reference solution if provided (required for non-staff, optional for staff)
                ref_title = form.cleaned_data.get('reference_solution_title')
                ref_type = form.cleaned_data.get('reference_solution_type')
                ref_url = form.cleaned_data.get('reference_solution_url')
                
                if ref_title and ref_type and ref_url:
                    Solution.objects.create(
                        analysis_task=sample,
                        title=ref_title,
                        solution_type=ref_type,
                        url=ref_url,
                        author=request.user
                    )
            
            # Transaction committed, Discord notification will fire now with correct data
            messages.success(request, f'AnalysisTask {sample.sha256[:12]}... submitted successfully!')
            return redirect('sample_detail', sha256=sample.sha256, task_id=sample.id)
    else:
        form = AnalysisTaskForm(user=request.user, is_edit=False)
    
    # Get available images from image library
    available_images = SampleImage.objects.all()
    
    return render(request, 'samples/submit_task.html', {
        'form': form,
        'available_images': available_images,
        'is_edit': False,
    })


@login_required
def edit_task(request, sha256, task_id):
    """Allow users to edit their own analysis task (or admins/contributors to edit any)"""
    task = get_object_or_404(AnalysisTask, sha256=sha256, id=task_id)
    
    # Check permissions using model method
    if not task.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('sample_detail', sha256=task.sha256, task_id=task.id)
    
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST, instance=task, user=request.user, is_edit=True)
        if form.is_valid():
            # Use atomic transaction
            with transaction.atomic():
                sample = form.save(commit=False)
                
                # Handle image selection
                image_id = request.POST.get('image_id')
                if image_id:
                    try:
                        sample_image = SampleImage.objects.get(id=image_id)
                        sample.image = sample_image.image
                    except SampleImage.DoesNotExist:
                        pass
                elif request.POST.get('clear_image'):
                    sample.image = None
                
                sample.save()
                
                # Convert tags and tools to lowercase and save
                if form.cleaned_data.get('tags'):
                    tags = [tag.strip().lower() for tag in form.cleaned_data['tags'] if tag.strip()]
                    sample.tags.set(tags)
                
                if form.cleaned_data.get('tools'):
                    tools = [tool.strip().lower() for tool in form.cleaned_data['tools'] if tool.strip()]
                    sample.tools.set(tools)
            
            messages.success(request, f'AnalysisTask {sample.sha256[:12]}... updated successfully!')
            return redirect('sample_detail', sha256=sample.sha256, task_id=sample.id)
    else:
        # Prepare initial data with properly formatted tags and tools
        initial_data = {
            'tags': ', '.join(task.tags.values_list('name', flat=True)),
            'tools': ', '.join(task.tools.values_list('name', flat=True)),
        }
        form = AnalysisTaskForm(instance=task, initial=initial_data, user=request.user, is_edit=True)
    
    # Get available images from image library
    available_images = SampleImage.objects.all()
    
    # Find current image if it exists
    current_image_id = None
    if task.image:
        try:
            current_image = SampleImage.objects.get(image=task.image)
            current_image_id = current_image.id
        except SampleImage.DoesNotExist:
            pass
    
    return render(request, 'samples/submit_task.html', {
        'form': form,
        'available_images': available_images,
        'is_edit': True,
        'task': task,
        'current_image_id': current_image_id,
    })


@login_required
def delete_task(request, sha256, task_id):
    """Allow users to delete their own analysis task (or admins/contributors to delete any)"""
    task = get_object_or_404(AnalysisTask, sha256=sha256, id=task_id)
    
    # Check permissions using model method
    if not task.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to delete this task.')
        return redirect('sample_detail', sha256=task.sha256, task_id=task.id)
    
    if request.method == 'POST':
        sha256_preview = task.sha256[:12]
        task.delete()
        messages.success(request, f'AnalysisTask {sha256_preview}... has been deleted successfully.')
        return redirect('sample_list')
    
    # If not POST, redirect back to detail page
    return redirect('sample_detail', sha256=task.sha256, task_id=task.id)


@require_POST
def markdown_preview(request):
    """AJAX endpoint to render markdown preview"""
    content = request.POST.get('content', '')
    html = markdownify(content)
    return JsonResponse({'html': html})
