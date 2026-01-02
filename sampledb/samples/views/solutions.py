from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from markdownx.utils import markdownify

from ..models import AnalysisTask, Solution, SolutionType
from ..forms import SolutionForm


def solution_list(request):
    """List all solutions with optional filtering by solution type"""
    solution_type = request.GET.get("solution_type", "")
    
    # Get all solutions ordered by most recent first
    solutions = Solution.objects.select_related('analysis_task', 'author').all()
    
    # Filter by solution type if specified
    if solution_type:
        solutions = solutions.filter(solution_type=solution_type)
    
    # Paginate the results (25 per page)
    paginator = Paginator(solutions, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Get user's liked solution IDs for display
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    return render(request, 'samples/solutions_list.html', {
        'page_obj': page_obj,
        'selected_type': solution_type,
        'solution_types': SolutionType.choices,
        'user_liked_solution_ids': user_liked_solution_ids,
    })


@login_required
def create_solution(request, sha256, task_id):
    """Create a new solution for an analysis task"""
    sample = get_object_or_404(AnalysisTask, id=task_id)
    
    if request.method == 'POST':
        form = SolutionForm(request.POST)
        if form.is_valid():
            solution = form.save(commit=False)
            solution.analysis_task = sample
            solution.author = request.user
            solution.save()
            messages.success(request, 'Solution added successfully!')
            return redirect('sample_detail', sha256=sha256, task_id=task_id)
    else:
        form = SolutionForm()
    
    return render(request, 'samples/solution_form.html', {
        'form': form,
        'sample': sample,
    })


@login_required
def edit_solution(request, sha256, task_id, solution_id):
    """Edit a solution (by author or staff)"""
    from django.urls import reverse
    
    sample = get_object_or_404(AnalysisTask, id=task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample)
    
    # Only allow the author or staff to edit
    if solution.author != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this solution.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    # Redirect onsite solutions to the dedicated editor
    if solution.solution_type == 'onsite':
        return redirect('edit_onsite_solution', sha256=sha256, task_id=task_id, solution_id=solution_id)
    
    if request.method == 'POST':
        form = SolutionForm(request.POST, instance=solution)
        if form.is_valid():
            form.save()
            messages.success(request, 'Solution updated successfully!')
            return redirect('sample_detail', sha256=sha256, task_id=task_id)
    else:
        form = SolutionForm(instance=solution)
    
    return render(request, 'samples/solution_form.html', {
        'form': form,
        'sample': sample,
        'solution': solution,
    })


@login_required
def delete_solution(request, sha256, task_id, solution_id):
    """Delete a solution (only by its author)"""
    sample = get_object_or_404(AnalysisTask, id=task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample)
    
    # Only allow the author to delete their own solution
    if solution.author != request.user:
        messages.error(request, 'You can only delete your own solutions.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    if request.method == 'POST':
        # Check if this is a reference solution (author is task author)
        is_reference_solution = solution.author == sample.author
        
        # Prevent deleting the last reference solution (for everyone, including staff)
        if is_reference_solution:
            # Count reference solutions for this task
            reference_solution_count = Solution.objects.filter(
                analysis_task=sample,
                author=sample.author
            ).count()
            
            if reference_solution_count <= 1:
                messages.error(request, 'Cannot delete the last reference solution. At least one reference solution must remain.')
                return redirect('sample_detail', sha256=sha256, task_id=task_id)
        
        solution.delete()
        messages.success(request, 'Solution deleted successfully.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    return redirect('sample_detail', sha256=sha256, task_id=task_id)


def view_onsite_solution(request, sha256, task_id, solution_id):
    """View an on-site solution with rendered markdown content"""
    from django.urls import reverse
    
    sample = get_object_or_404(AnalysisTask, id=task_id)
    solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample, solution_type='onsite')
    
    # Check if user liked this solution
    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = solution.liked_by.filter(id=request.user.id).exists()
    
    # Check if user can edit
    user_can_edit = False
    edit_solution_url = None
    if request.user.is_authenticated:
        user_can_edit = solution.author == request.user or request.user.is_staff
        if user_can_edit:
            edit_solution_url = reverse('edit_onsite_solution', kwargs={
                'sha256': sha256,
                'task_id': task_id,
                'solution_id': solution_id
            })
    
    # Render markdown content
    rendered_content = markdownify(solution.content) if solution.content else ''
    
    # Prepare URLs for template
    is_reference = solution.author == sample.author
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
    sample = get_object_or_404(AnalysisTask, id=task_id)
    solution = None
    
    # If editing, get the solution
    if solution_id:
        solution = get_object_or_404(Solution, id=solution_id, analysis_task=sample, solution_type='onsite')
        
        # Only allow the author or staff to edit
        if solution.author != request.user and not request.user.is_staff:
            messages.error(request, 'You do not have permission to edit this solution.')
            return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        # Validation
        if not title:
            messages.error(request, 'Title is required.')
            return render(request, 'samples/onsite_solution_editor.html', {
                'sample': sample,
                'solution': solution,
                'form': {'title': {'value': title}, 'content': {'value': content}},
            })
        
        if not content:
            messages.error(request, 'Content is required.')
            return render(request, 'samples/onsite_solution_editor.html', {
                'sample': sample,
                'solution': solution,
                'form': {'title': {'value': title}, 'content': {'value': content}},
            })
        
        # Create or update solution
        if solution:
            # Update existing solution
            solution.title = title
            solution.content = content
            solution.save()
            messages.success(request, 'Solution updated successfully!')
        else:
            # Create new solution
            solution = Solution.objects.create(
                analysis_task=sample,
                author=request.user,
                title=title,
                content=content,
                solution_type='onsite',
            )
            messages.success(request, 'Solution added successfully!')
        
        return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    # Prepare initial values for the form
    initial_title = solution.title if solution else ''
    initial_content = solution.content if solution else ''
    
    return render(request, 'samples/onsite_solution_editor.html', {
        'sample': sample,
        'solution': solution,
        'initial_title': initial_title,
        'initial_content': initial_content,
    })


def solutions_showcase(request):
    """Display the newest solutions (all types) in a card grid layout"""
    # Get the 6 most recent solutions with their related data
    solutions = Solution.objects.select_related(
        'analysis_task', 'author'
    ).order_by('-created_at')[:6]
    
    # Get user's liked solution IDs for display
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    return render(request, 'samples/solutions_showcase.html', {
        'solutions': solutions,
        'user_liked_solution_ids': user_liked_solution_ids,
    })
