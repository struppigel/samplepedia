from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from .models import AnalysisTask, Difficulty, Course, Solution, SampleImage
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.db.models import Count, Case, When, IntegerField
from taggit.models import Tag
from .forms import SolutionForm, AnalysisTaskForm, UserRegistrationForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

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
@permission_required('samples.add_analysistask', raise_exception=True)
def submit_task(request):
    """Allow users to submit their own analysis task"""
    if request.method == 'POST':
        form = AnalysisTaskForm(request.POST)
        if form.is_valid():
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
            
            # Convert tags and tools to lowercase
            if form.cleaned_data.get('tags'):
                tags = [tag.strip().lower() for tag in form.cleaned_data['tags'] if tag.strip()]
                sample.tags.set(tags)
            
            if form.cleaned_data.get('tools'):
                tools = [tool.strip().lower() for tool in form.cleaned_data['tools'] if tool.strip()]
                sample.tools.set(tools)
            
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


def register(request):
    """User registration view - creates inactive account pending email verification"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Create user but keep inactive until email verification
            user = form.save(commit=False)
            user.is_active = False  # Will be activated after email verification
            user.save()
            
            # Send verification email
            send_verification_email(request, user)
            
            messages.success(
                request, 
                f'Account created for {user.username}! Please check your email to verify your account.'
            )
            return redirect('verification_sent')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'registration/register.html', {'form': form})


def send_verification_email(request, user):
    """Send email verification link to user"""
    # Generate token
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build verification URL
    verification_url = request.build_absolute_uri(
        f'/verify-email/{uid}/{token}/'
    )
    
    # Render email templates
    context = {
        'user': user,
        'verification_url': verification_url,
    }
    
    subject = 'Verify your Samplepedia account'
    html_message = render_to_string('registration/verification_email.html', context)
    plain_message = render_to_string('registration/verification_email.txt', context)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def verification_sent(request):
    """Confirmation page after registration"""
    return render(request, 'registration/verification_sent.html')


def verify_email(request, uidb64, token):
    """Verify email and activate user account"""
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    # Verify token and activate account
    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save()
            messages.success(request, 'Your email has been verified! You can now log in.')
        else:
            messages.info(request, 'Your email was already verified.')
        success = True
    else:
        messages.error(request, 'The verification link is invalid or has expired.')
        success = False
    
    return render(request, 'registration/verify_email.html', {'success': success})


def resend_verification(request):
    """Resend verification email to user"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            
            # Only send if account is not yet verified
            if not user.is_active:
                send_verification_email(request, user)
                messages.success(
                    request,
                    'Verification email has been resent! Please check your inbox.'
                )
            else:
                messages.info(
                    request,
                    'This account is already verified. You can log in now.'
                )
        except User.DoesNotExist:
            # Don't reveal whether email exists (security best practice)
            messages.success(
                request,
                'If an unverified account exists with this email, a verification link has been sent.'
            )
        
        return redirect('verification_sent')
    
    return render(request, 'registration/resend_verification.html')


@login_required
def user_profile(request, username):
    """Display user profile with their submitted solutions and analysis tasks"""
    profile_user = get_object_or_404(User, username=username)
    
    # Get user's submitted solutions with related analysis tasks
    solutions = Solution.objects.filter(author=profile_user).select_related('analysis_task').order_by('-created_at')
    
    # Get user's submitted analysis tasks
    analysis_tasks = AnalysisTask.objects.filter(author=profile_user).order_by('-created_at')
    
    context = {
        'profile_user': profile_user,
        'solutions': solutions,
        'analysis_tasks': analysis_tasks,
    }
    
    return render(request, 'samples/profile.html', context)
