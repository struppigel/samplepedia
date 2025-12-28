from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..models import AnalysisTask, Solution
from ..forms import SolutionForm


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
    
    return render(request, 'samples/create_solution.html', {
        'form': form,
        'sample': sample,
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
        solution.delete()
        messages.success(request, 'Solution deleted successfully.')
        return redirect('sample_detail', sha256=sha256, task_id=task_id)
    
    return redirect('sample_detail', sha256=sha256, task_id=task_id)
