from .models import AnalysisTask, Difficulty, Solution
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django_comments_xtd.forms import XtdCommentForm
from turnstile.fields import TurnstileField
from disposable_email_domains import blocklist


# Custom comment form for authenticated users
class AuthenticatedCommentForm(XtdCommentForm):
    """
    Custom comment form for authenticated users that hides name and email fields
    since they are auto-populated from the logged-in user.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hide name and email fields for authenticated users
        if 'name' in self.fields:
            self.fields['name'].widget = forms.HiddenInput()
            self.fields['name'].required = False
        
        if 'email' in self.fields:
            self.fields['email'].widget = forms.HiddenInput()
            self.fields['email'].required = False
        
        if 'url' in self.fields:
            self.fields['url'].widget = forms.HiddenInput()
            self.fields['url'].required = False
    
    def get_comment_create_data(self, site_id=None):
        """Override to ensure name and email come from user"""
        data = super().get_comment_create_data(site_id=site_id)
        
        # If user is authenticated, use their info
        if hasattr(self, 'user') and self.user and self.user.is_authenticated:
            data['user_name'] = self.user.username
            data['user_email'] = self.user.email
            data['user'] = self.user
        
        return data

# For submitting analysis solutions to an analysis task
class SolutionForm(forms.ModelForm):
    class Meta:
        model = Solution
        fields = ['title', 'solution_type', 'url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solution title'}),
            'solution_type': forms.Select(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }

# for submitting analysis tasks
class AnalysisTaskForm(forms.ModelForm):
    class Meta:
        model = AnalysisTask
        fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'tags', 'tools']
        widgets = {
            'sha256': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '64 character hex string'}),
            'download_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://bazaar.abuse.ch/... or https://malshare.com/...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed description of the sample, will be in spoiler tags'}),
            'goal': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Analysis goal(s)'}),
            'difficulty': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True
        
        # Exclude expert difficulty from choices
        self.fields['difficulty'].choices = [
            (value, label) for value, label in Difficulty.choices 
            if value != Difficulty.EXPERT
        ]
    
    def clean_download_link(self):
        download_link = self.cleaned_data.get('download_link')
        
        # Admins can add any URL
        if self.user and (self.user.is_staff or self.user.is_superuser):
            return download_link
        
        # Non-admins must use supported sources
        if download_link:
            allowed_domains = [
                'bazaar.abuse.ch',
                'malshare.com',
            ]
            
            from urllib.parse import urlparse
            parsed_url = urlparse(download_link)
            domain = parsed_url.netloc.lower()
            
            # Check if domain matches any allowed domain
            if not any(domain == allowed or domain.endswith('.' + allowed) for allowed in allowed_domains):
                raise forms.ValidationError(
                    "Only MalwareBazaar (bazaar.abuse.ch) and MalShare (malshare.com) URLs are currently supported. "
                    "Please use one of these sources for the download link."
                )
        
        return download_link


# Custom authentication form with Turnstile CAPTCHA
class TurnstileAuthenticationForm(AuthenticationForm):
    """
    Custom login form that adds Cloudflare Turnstile CAPTCHA protection
    to prevent automated login attempts.
    """
    turnstile = TurnstileField(label="")


# User Registration Form with Turnstile CAPTCHA
class TurnstileUserRegistrationForm(UserCreationForm):
    """
    Custom registration form with Turnstile CAPTCHA protection
    to prevent automated account creation.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'})
    )
    turnstile = TurnstileField(label="")

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to password fields
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm password'})

    def clean_username(self):
        """Validate username against reserved names"""
        username = self.cleaned_data.get('username')
        
        # List of reserved usernames (case-insensitive)
        reserved_names = [
            'samplepedia',
            'adminuser',
            'malwareanalysisforhedgehogs',
            'malwareanalysis4hedgehogs',
            'karstenhahn',
            'khahn',
            'gdata',
            'administrator',
            'admin',
            'root',
            'moderator',
            'mod',
            'support',
            'help',
            'system',
            'official',
            'staff',
        ]
        
        # Check if username matches any reserved name (case-insensitive)
        if username and username.lower() in reserved_names:
            raise forms.ValidationError(
                f"The username '{username}' is reserved and cannot be used. "
                "Please choose a different username."
            )
        
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if email is already registered
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        
        # Block disposable/temporary email domains
        if email:
            domain = email.split('@')[-1].lower()
            
            if domain in blocklist:
                raise forms.ValidationError(
                    "Temporary or disposable email addresses are not allowed. "
                    "Please use a permanent email address."
                )
        
        return email


# Password Reset Form with Turnstile CAPTCHA
class TurnstilePasswordResetForm(forms.Form):
    """
    Custom password reset form with Turnstile CAPTCHA protection.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'})
    )
    turnstile = TurnstileField(label="")


# Resend Verification Form with Turnstile CAPTCHA
class TurnstileResendVerificationForm(forms.Form):
    """
    Custom resend verification form with Turnstile CAPTCHA protection.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'})
    )
    turnstile = TurnstileField(label="")
