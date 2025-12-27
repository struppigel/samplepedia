from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import AnalysisTask, Difficulty, Course, CourseReference, Solution
from django import forms
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.db.models import Count, Case, When, IntegerField
from taggit.models import Tag


class SolutionForm(forms.ModelForm):
    class Meta:
        model = Solution
        fields = ['title', 'solution_type', 'url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solution title'}),
            'solution_type': forms.Select(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }


class AnalysisTaskForm(forms.ModelForm):
    class Meta:
        model = AnalysisTask
        fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'tags', 'tools']
        widgets = {
            'sha256': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '64 character hex string'}),
            'download_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed description of the sample'}),
            'goal': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Analysis goal or learning objective'}),
            'difficulty': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True


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
    
    return render(request, "samples/detail.html", {
        "sample": sample,
        "user_has_liked": user_has_favorited,
        "solutions": solutions,
    })


def toggle_like(request, sha256, task_id):
    """Toggle favorite for a sample (requires authentication)"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Login required',
            'redirect': '/accounts/login/'
        }, status=401)
    
    sample = get_object_or_404(AnalysisTask, id=task_id)
    
    if sample.favorited_by.filter(id=request.user.id).exists():
        # Remove from favorites
        sample.favorited_by.remove(request.user)
        user_has_favorited = False
    else:
        # Add to favorites
        sample.favorited_by.add(request.user)
        user_has_favorited = True
    
    # Return JSON response for AJAX
    return JsonResponse({
        'liked': user_has_favorited,
        'like_count': sample.favorite_count
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


@login_required
def submit_task(request):
    """Allow users to submit their own analysis task"""
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST)
        if form.is_valid():
            sample = form.save(commit=False)
            sample.save()
            
            # Convert tags and tools to lowercase
            if form.cleaned_data.get('tags'):
                tags = [tag.strip().lower() for tag in form.cleaned_data['tags'] if tag.strip()]
                sample.tags.set(*tags)
            
            if form.cleaned_data.get('tools'):
                tools = [tool.strip().lower() for tool in form.cleaned_data['tools'] if tool.strip()]
                sample.tools.set(*tools)
            
            messages.success(request, f'AnalysisTask {sample.sha256[:12]}... submitted successfully!')
            return redirect('sample_detail', sha256=sample.sha256, task_id=sample.id)
    else:
        form = AnalysisTaskForm()
    
    return render(request, 'samples/submit_task.html', {
        'form': form,
    })


def course_list(request):
    """Display list of available courses"""
    courses = Course.objects.annotate(
        sample_count=Count('references__samples', distinct=True)
    ).order_by('name')
    
    return render(request, "samples/course_list.html", {
        "courses": courses,
    })


def course_samples(request, course_id):
    """Display samples for a specific course, sorted by section number"""
    # Get the course or 404
    course = get_object_or_404(Course, id=course_id)
    
    # Get all samples that have references to this course
    # We need to get distinct samples and annotate with the minimum section number
    samples = AnalysisTask.objects.filter(
        course_references__course=course
    ).prefetch_related('course_references').distinct()
    
    # Build a list with samples and their course references
    sample_data = []
    for sample in samples:
        # Get all course references for this sample in this course
        refs = sample.course_references.filter(
            course=course
        ).order_by('section')
        
        for ref in refs:
            sample_data.append({
                'sample': sample,
                'section': ref.section,
                'lecture_number': ref.lecture_number,
                'lecture_title': ref.lecture_title,
            })
    
    # Sort by section number
    sample_data.sort(key=lambda x: (x['section'], x['lecture_number']))
    
    # Get user's favorited sample IDs for display
    user_favorited_ids = set()
    if request.user.is_authenticated:
        user_favorited_ids = set(
            request.user.favorite_samples.values_list('id', flat=True)
        )
    
    return render(request, "samples/course_samples.html", {
        "course": course,
        "sample_data": sample_data,
        "user_favorited_ids": user_favorited_ids,
    })


def impressum(request):
    return render(request, "samples/impressum.html")


def privacy_policy(request):
    return render(request, "samples/privacy.html")
