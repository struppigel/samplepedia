from .models import AnalysisTask, Difficulty, Solution
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django_comments_xtd.forms import XtdCommentForm


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
            'download_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed description of the sample, will be in spoiler tags'}),
            'goal': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Analysis goal(s)'}),
            'difficulty': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True
        
        # Exclude expert difficulty from choices
        self.fields['difficulty'].choices = [
            (value, label) for value, label in Difficulty.choices 
            if value != Difficulty.EXPERT
        ]


# User Registration Form with Email Field
class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'})
    )

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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email
