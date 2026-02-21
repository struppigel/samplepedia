from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import JsonResponse
from markdownx.utils import markdownify
from ..models import Article, AnalysisTask, Solution


@login_required
def article_list(request):
    """List all articles by the current user (both drafts and published)"""
    from django.db.models import Count, Q
    
    articles = Article.objects.filter(
        author=request.user
    ).select_related('author').prefetch_related(
        'solution',
        'solution__analysis_task',
        'solution__analysis_task__author',
        'solution__liked_by'
    ).order_by('-updated_at')
    
    # Get IDs of solutions liked by current user
    user_liked_solution_ids = set()
    if request.user.is_authenticated:
        user_liked_solution_ids = set(
            request.user.liked_solutions.values_list('id', flat=True)
        )
    
    # For each published article, calculate reference solution count
    articles_with_counts = []
    for article in articles:
        article_data = {
            'article': article,
            'reference_solution_count': 0
        }
        
        # If article is published and is a reference solution, count reference solutions
        if article.is_published():
            solution = article.solution
            task = solution.analysis_task
            if solution.author_id == task.author_id:
                # Count reference solutions for this task
                article_data['reference_solution_count'] = task.solutions.filter(
                    author=task.author
                ).count()
        
        articles_with_counts.append(article_data)
    
    # Pagination
    paginator = Paginator(articles_with_counts, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'samples/article_list.html', {
        'page_obj': page_obj,
        'user_liked_solution_ids': user_liked_solution_ids,
    })


@login_required
def article_editor(request, article_id=None):
    """Dedicated editor page for creating/editing article drafts"""
    article = None
    
    # If editing, get the article
    if article_id:
        article = get_object_or_404(Article, id=article_id)
        
        # Only allow the author or staff to edit
        if not article.user_can_edit(request.user):
            messages.error(request, 'You do not have permission to edit this article.')
            return redirect('article_list')
        
        # Don't allow editing published articles (attached to solutions)
        if article.is_published():
            messages.error(request, 'This article is already published as a solution. You cannot edit it directly.')
            return redirect('article_list')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        # Validation
        if not title:
            messages.error(request, 'Title is required.')
            return render(request, 'samples/article_editor.html', {
                'article': article,
                'form': {'title': {'value': title}, 'content': {'value': content}},
            })
        
        if not content:
            messages.error(request, 'Content is required.')
            return render(request, 'samples/article_editor.html', {
                'article': article,
                'form': {'title': {'value': title}, 'content': {'value': content}},
            })
        
        # Create or update article
        if article:
            # Update existing article
            article.title = title
            article.content = content
            article.save()
            messages.success(request, 'Article draft updated successfully!')
        else:
            # Create new article
            article = Article.objects.create(
                author=request.user,
                title=title,
                content=content,
            )
            messages.success(request, 'Article draft created successfully!')
        
        # Redirect to view the article
        return redirect('article_view', article_id=article.id)
    
    # Prepare initial values for the form
    initial_title = article.title if article else ''
    initial_content = article.content if article else ''
    
    return render(request, 'samples/article_editor.html', {
        'article': article,
        'initial_title': initial_title,
        'initial_content': initial_content,
    })


@login_required
def article_view(request, article_id):
    """View an article draft with rendered markdown content"""
    from django.urls import reverse
    
    article = get_object_or_404(Article, id=article_id)
    
    # Only allow the author or staff to view draft articles
    if article.author != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this article.')
        return redirect('article_list')
    
    # If article is published, redirect to the solution view
    if article.is_published():
        solution = article.solution
        return redirect('view_onsite_solution', 
                       sha256=solution.analysis_task.sha256, 
                       task_id=solution.analysis_task.id, 
                       solution_id=solution.id)
    
    # Increment view count using F expression for atomic update
    Article.objects.filter(id=article_id).update(view_count=F('view_count') + 1)
    # Refresh from database to get updated view_count
    article.refresh_from_db()
    
    # Check if user can edit
    user_can_edit = article.user_can_edit(request.user)
    edit_url = reverse('article_editor_edit', kwargs={'article_id': article_id}) if user_can_edit else None
    
    # Render markdown content
    rendered_content = markdownify(article.content) if article.content else ''
    
    return render(request, 'samples/article_view.html', {
        'article': article,
        'rendered_content': rendered_content,
        'user_can_edit': user_can_edit,
        'edit_url': edit_url,
    })


@login_required
def article_delete(request, article_id):
    """Delete an article (and cascade delete solution if published)"""
    article = get_object_or_404(Article, id=article_id)
    
    # Get redirect target from POST data or referrer
    redirect_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    default_redirect = 'article_list'
    
    # Only allow the author or staff to delete
    if not article.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to delete this article.')
        if redirect_url:
            return redirect(redirect_url)
        return redirect(default_redirect)
    
    # Prevent deleting if it's the last reference solution
    if article.is_published():
        solution = article.solution
        task = solution.analysis_task
        is_reference_solution = solution.author == task.author
        
        if is_reference_solution:
            reference_solution_count = task.solutions.filter(author=task.author).count()
            if reference_solution_count <= 1:
                messages.error(request, 'Cannot delete the last reference solution. At least one reference solution must remain.')
                if redirect_url:
                    return redirect(redirect_url)
                return redirect(default_redirect)
    
    if request.method == 'POST':
        article_title = article.title
        article.delete()  # This will cascade delete the solution if published
        messages.success(request, f'Article "{article_title}" has been deleted.')
        if redirect_url:
            return redirect(redirect_url)
        return redirect(default_redirect)
    
    # If not POST, redirect back
    if redirect_url:
        return redirect(redirect_url)
    return redirect(default_redirect)


@login_required
def article_unpublish(request, article_id):
    """Unpublish an article (delete solution, keep article as draft)"""
    article = get_object_or_404(Article, id=article_id)
    
    # Get redirect target from POST data or referrer
    redirect_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    default_redirect = 'article_list'
    
    # Only allow the author or staff to unpublish
    if not article.user_can_edit(request.user):
        messages.error(request, 'You do not have permission to unpublish this article.')
        if redirect_url:
            return redirect(redirect_url)
        return redirect(default_redirect)
    
    # Check if it's published
    if not article.is_published():
        messages.error(request, 'This article is not published.')
        if redirect_url:
            return redirect(redirect_url)
        return redirect(default_redirect)
    
    # Prevent unpublishing if it's the last reference solution
    solution = article.solution
    task = solution.analysis_task
    is_reference_solution = solution.author == task.author
    
    if is_reference_solution:
        reference_solution_count = task.solutions.filter(author=task.author).count()
        if reference_solution_count <= 1:
            messages.error(request, 'Cannot unpublish the last reference solution. At least one reference solution must remain.')
            if redirect_url:
                return redirect(redirect_url)
            return redirect(default_redirect)
    
    if request.method == 'POST':
        article_title = article.title
        solution.delete()  # Delete only the solution, keep the article
        messages.success(request, f'Article "{article_title}" has been unpublished and converted to a draft.')
        if redirect_url:
            return redirect(redirect_url)
        return redirect(default_redirect)
    
    # If not POST, redirect back
    if redirect_url:
        return redirect(redirect_url)
    return redirect(default_redirect)


@login_required
def search_samples_ajax(request):
    """AJAX endpoint to search for samples when publishing an article"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search in SHA256, goal, and description
    samples = AnalysisTask.objects.filter(
        Q(sha256__icontains=query) |
        Q(goal__icontains=query) |
        Q(description__icontains=query)
    ).select_related('author').order_by('-created_at')[:20]
    
    results = []
    for sample in samples:
        results.append({
            'id': sample.id,
            'sha256': sample.sha256,
            'sha256_short': sample.sha256[:12],
            'goal': sample.goal[:80] + '...' if len(sample.goal) > 80 else sample.goal,
            'difficulty': sample.difficulty,
            'difficulty_display': sample.get_difficulty_display(),
            'author': sample.author.username,
        })
    
    return JsonResponse({'results': results})


@login_required
def get_user_drafts_ajax(request):
    """AJAX endpoint to get user's draft articles for attaching to a sample"""
    drafts = Article.objects.filter(
        author=request.user,
        solution__isnull=True  # Only unpublished articles
    ).order_by('-updated_at')[:20]
    
    results = []
    for draft in drafts:
        results.append({
            'id': draft.id,
            'title': draft.title,
            'updated_at': draft.updated_at.strftime('%Y-%m-%d %H:%M'),
            'content_preview': draft.content[:100] + '...' if len(draft.content) > 100 else draft.content,
        })
    
    return JsonResponse({'results': results})


@login_required
def publish_article(request, article_id):
    """Publish an article by attaching it to a sample"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    article = get_object_or_404(Article, id=article_id, author=request.user)
    
    # Check if already published
    if article.is_published():
        return JsonResponse({'error': 'Article is already published'}, status=400)
    
    sample_id = request.POST.get('sample_id')
    if not sample_id:
        return JsonResponse({'error': 'Sample ID required'}, status=400)
    
    sample = get_object_or_404(AnalysisTask, id=sample_id)
    
    # Create the solution
    solution = Solution.objects.create(
        analysis_task=sample,
        author=request.user,
        title=article.title,
        solution_type='onsite',
        article=article,
        url=''  # Not used for onsite solutions
    )
    
    messages.success(request, f'Article "{article.title}" has been published to sample {sample.sha256[:12]}.')
    return JsonResponse({
        'success': True,
        'redirect_url': f'/sample/{sample.sha256}/{sample.id}/'
    })


@login_required
def attach_draft_to_sample(request, sha256, task_id):
    """Attach a draft article to a sample"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    sample = get_object_or_404(AnalysisTask, id=task_id, sha256=sha256)
    
    article_id = request.POST.get('article_id')
    if not article_id:
        return JsonResponse({'error': 'Article ID required'}, status=400)
    
    article = get_object_or_404(Article, id=article_id, author=request.user)
    
    # Check if already published
    if article.is_published():
        return JsonResponse({'error': 'Article is already published'}, status=400)
    
    # Create the solution
    solution = Solution.objects.create(
        analysis_task=sample,
        author=request.user,
        title=article.title,
        solution_type='onsite',
        article=article,
        url=''  # Not used for onsite solutions
    )
    
    messages.success(request, f'Article "{article.title}" has been published to this sample.')
    return JsonResponse({
        'success': True,
        'reload': True
    })
