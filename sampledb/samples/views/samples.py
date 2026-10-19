from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.db.models import Case, When, IntegerField, F
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from taggit.models import Tag
import re

from ..models import AnalysisTask, Difficulty, SampleImage, SolutionType
from ..forms import AnalysisTaskForm
from ..constants import TASKS_PER_PAGE
from ..querysets import difficulty_order
from ..services.solutions import create_solution, hidden_until_from_weeks
from ..utils.markdown import render_markdown
from .lookups import get_task_or_404


def sample_list(request):
    # Get search/filter parameters first
    q = request.GET.get("q", "")
    tag = request.GET.get("tag")
    difficulty = request.GET.get("difficulty")
    platform = request.GET.get("platform")
    favorites_only = request.GET.get("favorites") == "true"
    sort = request.GET.get("sort", "-id")  # Default to reverse chronological
    browse = request.GET.get("browse", "")
    
    # Show landing page to non-authenticated users (unless they want to browse or are filtering)
    # Check if any filter parameters are present in the URL (even if empty)
    has_filter_params = any(param in request.GET for param in ['q', 'tag', 'difficulty', 'browse', 'sort', 'page'])
    if not request.user.is_authenticated and not has_filter_params:
        return render(request, "samples/landing.html")

    # Counts for display and sorting come from for_listing(), so rows cost no extra queries
    samples = AnalysisTask.objects.for_listing().prefetch_related('tags', 'tools').annotate(
        difficulty_order=difficulty_order(),
        has_video=Case(
            When(youtube_id='', then=0),
            default=1,
            output_field=IntegerField(),
        )
    )

    # filter course samples, those are only displayed in course view
    # if they overlap, they need a different description anyways
    samples = samples.exclude(course_references__isnull=False).distinct()

    if q:
        samples = samples.filter(sha256__icontains=q)

    if tag:
        samples = samples.filter(tags__name=tag)

    if difficulty:
        samples = samples.filter(difficulty=difficulty)
    
    if platform:
        samples = samples.filter(platform=platform)
    
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
        'solutions': 'solution_count_annotated',
        '-solutions': '-solution_count_annotated',
        'comments': 'comment_count_annotated',
        '-comments': '-comment_count_annotated',
        'likes': 'favorite_count_annotated',
        '-likes': '-favorite_count_annotated',
        'created': 'created_at',
        '-created': '-created_at',
        '-id': '-id',  # Default
    }
    
    sort_field = valid_sorts.get(sort, '-id')
    samples = samples.order_by(sort_field, '-id')  # Secondary sort by ID for consistency

    paginator = Paginator(samples, TASKS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Get user's favorited sample IDs for display
    user_favorited_ids = set()
    if request.user.is_authenticated:
        user_favorited_ids = set(
            request.user.favorite_samples.values_list('id', flat=True)
        )
    
    # Get all tags used in samples
    all_tags = Tag.objects.filter(
        taggit_taggeditem_items__content_type__model='analysistask'
    ).distinct().order_by(Lower('name'))

    from ..models import Platform
    
    return render(request, "samples/list.html", {
        "page_obj": page_obj,
        "q": q,
        "selected_tag": tag,
        "selected_difficulty": difficulty,
        "selected_platform": platform,
        "all_tags": all_tags,
        "difficulties": Difficulty.choices,
        "platforms": Platform.choices,
        "favorites_only": favorites_only,
        "user_favorited_ids": user_favorited_ids,
        "sort": sort,
    })


def sample_detail(request, sha256, task_id):
    sample = get_object_or_404(AnalysisTask, id=task_id)
    # One canonical URL per task: a wrong or outdated hash redirects instead of echoing it back
    if sha256 != sample.sha256:
        return redirect(sample, permanent=True)
        
    # Increment view count using F expression for atomic update
    AnalysisTask.objects.filter(id=task_id).update(view_count=F('view_count') + 1)
    # Refresh from database to get updated view_count
    sample.refresh_from_db()
    
    # Check if user has favorited this sample
    user_has_favorited = False
    if request.user.is_authenticated:
        user_has_favorited = sample.favorited_by.filter(id=request.user.id).exists()
    
    # reference_count lets the template lock the last reference solution
    solutions = list(sample.solutions.visible_to(request.user).for_listing().with_reference_count())

    # Get user's liked solution IDs
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
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
        form = AnalysisTaskForm(request.POST, request.FILES, user=request.user, is_edit=False)
        if form.is_valid():
            try:
                # Atomic: tags/tools are saved before the Discord notification fires on
                # commit, and a rejected reference solution leaves no task behind
                with transaction.atomic():
                    sample = _create_task(request, form)
            except ValidationError as error:
                form.add_error(None, error)
            else:
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


def _save_task(request, form, task):
    """
    Save a task from a valid AnalysisTaskForm: an uploaded image wins over a gallery
    choice (or clearing it), and tags and tools are stored lowercased.
    """
    data = form.cleaned_data
    image_id = request.POST.get('image_id', '')
    if data.get('image_upload'):
        # Upload directly to AnalysisTask.image (NOT to the SampleImage gallery)
        task.image = data['image_upload']
    elif image_id.isdigit():
        gallery_image = SampleImage.objects.filter(id=image_id).first()
        if gallery_image:
            task.image = gallery_image.image
    elif request.POST.get('clear_image'):
        task.image = None
    task.save()

    if data.get('tags'):
        task.tags.set([tag.strip().lower() for tag in data['tags'] if tag.strip()])
    if data.get('tools'):
        task.tools.set([tool.strip().lower() for tool in data['tools'] if tool.strip()])
    return task


def _create_task(request, form):
    """Save a new task from a valid AnalysisTaskForm, with its reference solution if one was given."""
    data = form.cleaned_data
    sample = form.save(commit=False)
    sample.author = request.user
    _save_task(request, form, sample)

    # Reference solution: required for non-staff (the form enforces it), optional for staff
    hidden_until = hidden_until_from_weeks(data.get('hide_weeks'))
    draft = data.get('_draft_article') if data.get('reference_draft_article_id') else None
    if draft:
        create_solution(
            task=sample, author=request.user, solution_type=SolutionType.ONSITE,
            article=draft, hidden_until=hidden_until,
        )
    elif data.get('reference_solution_title') and data.get('reference_solution_type'):
        create_solution(
            task=sample,
            author=request.user,
            solution_type=data['reference_solution_type'],
            title=data['reference_solution_title'],
            url=data.get('reference_solution_url') or '',
            content=data.get('reference_solution_content') or '',
            hidden_until=hidden_until,
        )
    return sample


@login_required
def edit_task(request, sha256, task_id):
    """Allow users to edit their own analysis task (or admins/contributors to edit any)"""
    task = get_task_or_404(sha256, task_id)

    # Check permissions using model method
    if not task.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('sample_detail', sha256=task.sha256, task_id=task.id)
    
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST, request.FILES, instance=task, user=request.user, is_edit=True)
        if form.is_valid():
            with transaction.atomic():
                sample = _save_task(request, form, form.save(commit=False))
                        
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
            # Convert CloudinaryResource to string for database query
            current_image = SampleImage.objects.get(image=str(task.image))
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
    task = get_task_or_404(sha256, task_id)

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
    html = render_markdown(content)
    return JsonResponse({'html': html})
