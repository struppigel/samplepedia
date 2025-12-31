from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

from ..models import Solution, AnalysisTask
from ..forms import (
    TurnstileAuthenticationForm,
    TurnstileUserRegistrationForm,
    TurnstilePasswordResetForm,
    TurnstileResendVerificationForm,
    ChangePasswordForm,
    ChangeEmailForm
)


def login_view(request):
    """Custom login view with Turnstile CAPTCHA protection"""
    if request.method == 'POST':
        form = TurnstileAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            
            # Redirect to 'next' parameter if present, otherwise home
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
    else:
        form = TurnstileAuthenticationForm()
    
    return render(request, 'registration/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


def register(request):
    """User registration view - creates inactive account pending email verification"""
    if request.method == 'POST':
        form = TurnstileUserRegistrationForm(request.POST)
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
        form = TurnstileUserRegistrationForm()
    
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


def password_reset_request(request):
    """Password reset request view with Turnstile CAPTCHA"""
    if request.method == 'POST':
        form = TurnstilePasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            
            # Try to find user with this email
            try:
                user = User.objects.get(email=email)
                
                # Generate password reset token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Render email templates
                context = {
                    'user': user,
                    'uid': uid,
                    'token': token,
                    'protocol': 'https' if request.is_secure() else 'http',
                    'domain': request.get_host(),
                }
                
                subject = 'Password Reset Request - Samplepedia'
                html_message = render_to_string('registration/password_reset_email.html', context)
                plain_message = render_to_string('registration/password_reset_email.txt', context)
                
                # Send email
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
            except User.DoesNotExist:
                pass  # Don't reveal whether email exists
            
            # Always show success message for security
            messages.success(
                request,
                'If an account exists with this email, you will receive password reset instructions.'
            )
            return redirect('password_reset_done')
    else:
        form = TurnstilePasswordResetForm()
    
    return render(request, 'registration/password_reset_form.html', {'form': form})


def resend_verification(request):
    """Resend verification email to user"""
    if request.method == 'POST':
        form = TurnstileResendVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email', '').strip()
            
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
    else:
        form = TurnstileResendVerificationForm()
    
    return render(request, 'registration/resend_verification.html', {'form': form})


@login_required
def user_profile(request, username):
    """Display user profile with their submitted solutions and analysis tasks"""
    from django.core.paginator import Paginator
    
    profile_user = get_object_or_404(User, username=username)
    
    # Get user's submitted solutions with related analysis tasks
    solutions_list = Solution.objects.filter(author=profile_user).select_related('analysis_task').order_by('-created_at')
    
    # Get user's submitted analysis tasks
    analysis_tasks_list = AnalysisTask.objects.filter(author=profile_user).order_by('-created_at')
    
    # Pagination for solutions
    solutions_page = request.GET.get('solutions_page', 1)
    solutions_paginator = Paginator(solutions_list, 10)  # 10 solutions per page
    solutions = solutions_paginator.get_page(solutions_page)
    
    # Pagination for analysis tasks
    tasks_page = request.GET.get('tasks_page', 1)
    tasks_paginator = Paginator(analysis_tasks_list, 10)  # 10 tasks per page
    analysis_tasks = tasks_paginator.get_page(tasks_page)
    
    # Get current user's favorited sample IDs for display
    user_favorited_ids = set()
    if request.user.is_authenticated:
        user_favorited_ids = set(
            request.user.favorite_samples.values_list('id', flat=True)
        )
    
    context = {
        'profile_user': profile_user,
        'solutions': solutions,
        'analysis_tasks': analysis_tasks,
        'user_favorited_ids': user_favorited_ids,
    }
    
    return render(request, 'samples/profile.html', context)


@login_required
def profile_settings(request):
    """Profile settings page"""
    return render(request, 'samples/profile_settings.html')


@login_required
def change_password(request):
    """Change user's password"""
    if request.method == 'POST':
        form = ChangePasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            
            # Update the session to prevent logout
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('profile_settings')
    else:
        form = ChangePasswordForm(user=request.user)
    
    return render(request, 'samples/change_password.html', {'form': form})


@login_required
def change_email(request):
    """Change user's email address (requires verification)"""
    if request.method == 'POST':
        form = ChangeEmailForm(user=request.user, data=request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            
            # Generate token for email verification
            token = default_token_generator.make_token(request.user)
            uid = urlsafe_base64_encode(force_bytes(request.user.pk))
            
            # Store the new email temporarily in session (or you could use a database field)
            request.session['pending_email'] = new_email
            request.session['pending_email_token'] = token
            
            # Build verification URL
            verification_url = request.build_absolute_uri(
                f'/verify-email-change/{uid}/{token}/'
            )
            
            # Render email templates
            context = {
                'user': request.user,
                'new_email': new_email,
                'verification_url': verification_url,
            }
            
            subject = 'Verify your new email address - Samplepedia'
            html_message = render_to_string('registration/email_change_verification.html', context)
            plain_message = render_to_string('registration/email_change_verification.txt', context)
            
            # Send email to the NEW email address
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[new_email],
                html_message=html_message,
                fail_silently=False,
            )
            
            messages.success(
                request, 
                f'A verification link has been sent to {new_email}. Please check your email to confirm the change.'
            )
            return redirect('profile_settings')
    else:
        form = ChangeEmailForm(user=request.user)
    
    return render(request, 'samples/change_email.html', {'form': form})


@login_required
def verify_email_change(request, uidb64, token):
    """Verify new email address and update user"""
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    # Verify token and check if it matches the session
    if (user is not None and 
        user == request.user and 
        default_token_generator.check_token(user, token) and
        'pending_email' in request.session and
        'pending_email_token' in request.session and
        request.session['pending_email_token'] == token):
        
        new_email = request.session['pending_email']
        
        # Check if email is still available
        if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
            messages.error(request, 'This email address is now registered by another user.')
            success = False
        else:
            # Update the email
            user.email = new_email
            user.save()
            
            # Clear session data
            del request.session['pending_email']
            del request.session['pending_email_token']
            
            messages.success(request, 'Your email address has been updated successfully!')
            success = True
    else:
        messages.error(request, 'The verification link is invalid or has expired.')
        success = False
    
    return render(request, 'samples/verify_email_change.html', {'success': success})
