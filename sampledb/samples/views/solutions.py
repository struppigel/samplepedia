import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models import Q, F
from django.db.models.functions import Coalesce, Lower
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from taggit.models import Tag
from ..models import AnalysisTask, Difficulty, Platform, Solution, SolutionType, EditorImage, Article
from ..forms import ArticleForm, SolutionForm
from ..constants import SHOWCASE_PER_PAGE, SOLUTIONS_PER_PAGE
from ..querysets import difficulty_order
from ..services.solutions import create_solution as add_solution, update_onsite_solution
from ..utils.http import safe_next_url
from ..utils.markdown import render_markdown
from .lookups import get_task_or_404

logger = logging.getLogger(__name__)


def solution_list(request):
    """List all solutions with optional filtering by solution type, search, and sorting"""
    solution_type = request.GET.get("solution_type", "")
    q = request.GET.get("q", "").strip()
    tag = request.GET.get("tag")
    difficulty = request.GET.get("difficulty")
    platform = request.GET.get("platform")
    sort = request.GET.get("sort", "-created")
    
    solutions = Solution.objects.visible_to(request.user).for_listing().prefetch_related(
        'analysis_task__tags'
    ).annotate(
        difficulty_order=difficulty_order('analysis_task__difficulty'),
    )

    # Filter by solution type if specified
    if solution_type:
        solutions = solutions.filter(solution_type=solution_type)
    
    # Search by title or SHA256
    if q:
        solutions = solutions.filter(
            Q(title__icontains=q) | Q(analysis_task__sha256__icontains=q)
        )
    
    # Filter by tag if specified
    if tag:
        solutions = solutions.filter(analysis_task__tags__name=tag)
    
    # Filter by difficulty if specified
    if difficulty:
        solutions = solutions.filter(analysis_task__difficulty=difficulty)
    
    # Filter by platform if specified
    if platform:
        solutions = solutions.filter(analysis_task__platform=platform)
    
    # Ensure distinct results after filtering
    solutions = solutions.distinct()
    
    # Handle sorting
    sort_mapping = {
        'title': 'title',
        '-title': '-title',
        'sha256': 'analysis_task__sha256',
        '-sha256': '-analysis_task__sha256',
        'difficulty': 'difficulty_order',
        '-difficulty': '-difficulty_order',
        'author': 'author__username',
        '-author': '-author__username',
        'likes': 'like_count_annotated',
        '-likes': '-like_count_annotated',
        'created': 'created_at',
        '-created': '-created_at',
    }
    
    if sort in sort_mapping:
        solutions = solutions.order_by(sort_mapping[sort])
    else:
        solutions = solutions.order_by('-created_at')
    
    paginator = Paginator(solutions, SOLUTIONS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get user's liked solution IDs for display
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    # Get all tags used in solutions (through analysis tasks)
    all_tags = Tag.objects.filter(
        taggit_taggeditem_items__content_type__model='analysistask',
        taggit_taggeditem_items__object_id__in=Solution.objects.values_list('analysis_task_id', flat=True)
    ).distinct().order_by(Lower('name'))
    
    return render(request, 'samples/solutions_list.html', {
        'page_obj': page_obj,
        'q': q,
        'selected_type': solution_type,
        'solution_types': SolutionType.choices,
        'selected_tag': tag,
        'selected_difficulty': difficulty,
        'selected_platform': platform,
        'all_tags': all_tags,
        'difficulties': Difficulty.choices,
        'platforms': Platform.choices,
        'is_filtered': any([q, solution_type, tag, difficulty, platform]),
        'user_liked_solution_ids': user_liked_solution_ids,
        'sort': sort,
    })


@login_required
def create_solution(request, sha256, task_id):
    """Create a new solution for an analysis task"""
    sample = get_task_or_404(sha256, task_id)
    
    if request.method == 'POST':
        form = SolutionForm(request.POST, task=sample, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            draft = data.get('draft_article')
            try:
                add_solution(
                    task=sample,
                    author=request.user,
                    solution_type=data['solution_type'],
                    title=data.get('title') or '',
                    url=data.get('url') or '',
                    content=data.get('content') or '',
                    article=draft,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                if draft:
                    messages.success(request, f'Draft article "{draft.title}" has been published as a solution!')
                else:
                    messages.success(request, 'Solution added successfully!')
                return redirect('sample_detail', sha256=sha256, task_id=task_id)
    else:
        form = SolutionForm(task=sample)
    
    return render(request, 'samples/solution_form.html', {
        'form': form,
        'sample': sample,
    })


@login_required
def edit_solution(request, sha256, task_id, solution_id):
    """Edit a solution (by author or staff)"""
    sample = get_task_or_404(sha256, task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample)
    
    if not solution.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this solution.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)

    # Redirect onsite solutions to the dedicated editor
    if solution.solution_type == SolutionType.ONSITE:
        return redirect('edit_onsite_solution', sha256=sha256, task_id=task_id, solution_id=solution_id)
    
    if request.method == 'POST':
        form = SolutionForm(request.POST, instance=solution, task=sample)
        if form.is_valid():
            form.save()
            messages.success(request, 'Solution updated successfully!')
            return redirect('sample_detail', sha256=sha256, task_id=task_id)
    else:
        form = SolutionForm(instance=solution, task=sample)
    
    return render(request, 'samples/solution_form.html', {
        'form': form,
        'sample': sample,
        'solution': solution,
    })


@login_required
def delete_solution(request, sha256, task_id, solution_id):
    """Delete a solution (by its author or staff)"""
    sample = get_task_or_404(sha256, task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample)
    
    next_url = safe_next_url(request, 'sample_detail', sha256=sha256, task_id=task_id)

    if not solution.user_can_edit(request.user):
        messages.error(request, 'You can only delete your own solutions.')
        return redirect(next_url)

    if request.method == 'POST':
        # Applies to everyone, including staff
        if solution.is_last_reference():
            messages.error(request, 'Cannot delete the last reference solution. At least one reference solution must remain.')
            return redirect(next_url)

        solution.delete()
        messages.success(request, 'Solution deleted successfully.')

    return redirect(next_url)


def view_onsite_solution(request, sha256, task_id, solution_id):
    """View an on-site solution with rendered markdown content"""
    sample = get_task_or_404(sha256, task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample, solution_type=SolutionType.ONSITE)
    
    if not solution.user_can_view(request.user):
        messages.error(request, 'This solution is not yet available.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)

    # Count only views that actually show the solution (atomic F-expression update)
    if solution.article:
        Article.objects.filter(id=solution.article.id).update(view_count=F('view_count') + 1)
        solution.article.refresh_from_db()

    # Check if user liked this solution
    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = solution.liked_by.filter(id=request.user.id).exists()
    
    user_can_edit = solution.user_can_edit(request.user)
    edit_solution_url = None
    if user_can_edit:
        edit_solution_url = reverse('edit_onsite_solution', kwargs={
            'sha256': sha256,
            'task_id': task_id,
            'solution_id': solution_id
        })
    
    rendered_content = render_markdown(solution.get_content)
    
    # Prepare URLs for template
    is_reference = solution.is_reference
    user_profile_url = reverse('user_profile', kwargs={'username': solution.author.username})
    task_detail_url = reverse('sample_detail', kwargs={'sha256': sha256, 'task_id': task_id})
    
    return render(request, 'samples/view_onsite_solution.html', {
        'sample': sample,
        'solution': solution,
        'rendered_content': rendered_content,
        'user_has_liked': user_has_liked,
        'user_can_edit': user_can_edit,
        'is_reference': is_reference,
        'user_profile_url': user_profile_url,
        'task_detail_url': task_detail_url,
        'edit_solution_url': edit_solution_url,
    })


@login_required
def onsite_solution_editor(request, sha256, task_id, solution_id=None):
    """Dedicated editor page for creating/editing on-site solutions"""
    sample = get_task_or_404(sha256, task_id)
    solution = None
    
    # If editing, get the solution
    if solution_id:
        solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample, solution_type=SolutionType.ONSITE)
        
        if not solution.user_can_edit(request.user):
            messages.error(request, 'You do not have permission to edit this solution.')
            return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()

        error = None if form.is_valid() else form.first_error()
        if error is None:
            title, content = form.cleaned_data['title'], form.cleaned_data['content']
            try:
                if solution:
                    update_onsite_solution(solution, title=title, content=content)
                    messages.success(request, 'Solution updated successfully!')
                else:
                    solution = add_solution(
                        task=sample, author=request.user, solution_type=SolutionType.ONSITE,
                        title=title, content=content,
                    )
                    messages.success(request, 'Solution added successfully!')
            except ValidationError as validation_error:
                error = ' '.join(validation_error.messages)

        if error:
            # Re-render with what the user typed so nothing is lost
            messages.error(request, error)
            return render(request, 'samples/onsite_solution_editor.html', {
                'sample': sample,
                'solution': solution,
                'initial_title': title,
                'initial_content': content,
            })
        
        # Redirect to view the published solution
        return redirect('view_onsite_solution', sha256=sha256, task_id=task_id, solution_id=solution.id)
    
    # Prepare initial values for the form
    initial_title = solution.title if solution else ''
    initial_content = solution.get_content if solution else ''
    
    return render(request, 'samples/onsite_solution_editor.html', {
        'sample': sample,
        'solution': solution,
        'initial_title': initial_title,
        'initial_content': initial_content,
    })


def solutions_showcase(request):
    """Display the newest solutions (all types) in a card grid layout"""
    # Get all recent solutions with their related data
    # Exclude all hidden solutions from showcase
    # make sure the hidden_until is considered for ordering
    solutions = Solution.objects.publicly_visible().for_listing().annotate(
        visible_date=Coalesce('hidden_until', 'created_at')
    ).order_by('-visible_date')
    
    # Pagination
    paginator = Paginator(solutions, SHOWCASE_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user's liked solution IDs for display
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    return render(request, 'samples/solutions_showcase.html', {
        'solutions': page_obj,
        'page_obj': page_obj,
        'page_numbers': list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)),
        'user_liked_solution_ids': user_liked_solution_ids,
    })


@login_required
@require_POST
def upload_editor_image(request):
    """Handle image uploads from the markdown editor"""
    if 'image' not in request.FILES:
        return JsonResponse({'error': 'No image file provided'}, status=400)
    
    image_file = request.FILES['image']
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    if image_file.size > max_size:
        return JsonResponse({'error': 'Image file too large. Maximum size is 5MB.'}, status=400)
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if image_file.content_type not in allowed_types:
        return JsonResponse({'error': 'Invalid image type. Allowed types: JPEG, PNG, GIF, WEBP'}, status=400)
    
    try:
        # Create EditorImage instance (Cloudinary will handle the upload)
        editor_image = EditorImage.objects.create(
            image=image_file,
            uploader=request.user
        )
        
        # Get the Cloudinary URL
        image_url = editor_image.image.url
        
        return JsonResponse({
            'success': True,
            'url': image_url,
            'id': editor_image.id
        })
    
    except Exception:
        logger.exception('Editor image upload failed for user %s', request.user.pk)
        return JsonResponse({'error': 'Upload failed. Please try again.'}, status=500)
