from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from ..models import Solution, AnalysisTask
from ..forms import UserRegistrationForm


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
