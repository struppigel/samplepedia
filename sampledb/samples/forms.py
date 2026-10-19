from .models import AnalysisTask, Difficulty, Solution, SolutionType, Article
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django_comments_xtd.forms import XtdCommentForm
from turnstile.fields import TurnstileField
from disposable_email_domains import blocklist


def get_publishable_draft(article_id, user):
    """The user's unpublished draft with this id; otherwise a ValidationError for the form."""
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        raise forms.ValidationError("Selected draft article does not exist.")
    if user is not None and article.author_id != user.id:
        raise forms.ValidationError("You can only use your own draft articles.")
    if article.is_published():
        raise forms.ValidationError(
            "This draft article is already published. Please select an unpublished draft."
        )
    return article


def check_new_email(email, user=None):
    """An address for a new account or an e-mail change: not taken by anyone else, not disposable."""
    taken = User.objects.filter(email__iexact=email)
    if user is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        raise forms.ValidationError("This email address is already registered.")
    if email.split('@')[-1].lower() in blocklist:
        raise forms.ValidationError(
            "Temporary or disposable email addresses are not allowed. "
            "Please use a permanent email address."
        )
    return email


class UserFormMixin:
    """For forms acting on the logged-in user: takes the user first and can verify their password."""

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def verified_password(self, field, message="Your password is incorrect."):
        password = self.cleaned_data.get(field)
        if not self.user.check_password(password):
            raise forms.ValidationError(message)
        return password


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
        
        return data
    
    def get_success_url(self):
        """
        Override success URL to redirect to the comment with highlight parameter.
        """
        # This method will be called after the comment is posted
        # We'll need to get the comment ID from the saved instance
        return None  # Will be handled by the signal instead

# For submitting analysis solutions to an analysis task
class SolutionForm(forms.ModelForm):
    """
    Validates solution input; saving goes through services.solutions so that
    on-site text ends up in an Article. cleaned_data['draft_article'] holds the
    selected draft, if any.
    """
    draft_article_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_draft_article_id'}),
        label=''
    )
    # On-site text is stored in an Article, not on the Solution
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 15, 'id': 'id_content'}),
    )

    class Meta:
        model = Solution
        fields = ['title', 'solution_type', 'url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solution title'}),
            'solution_type': forms.Select(attrs={'class': 'form-select'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }
    
    def __init__(self, *args, task=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # The task isn't a form field, so the per-task title uniqueness is checked in clean()
        self.task = task
        self.user = user
        # Make title not required by default - we'll validate conditionally
        self.fields['title'].required = False
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        draft_article_id = self.data.get('draft_article_id')
        
        # Title is not required if draft is selected
        if draft_article_id:
            return title
        
        # Title is required if no draft is selected
        if not title:
            raise forms.ValidationError('This field is required.')
        
        return title
    
    def clean(self):
        cleaned_data = super().clean()
        solution_type = cleaned_data.get('solution_type')
        url = cleaned_data.get('url')
        content = cleaned_data.get('content')
        draft_article_id = cleaned_data.get('draft_article_id')
        
        title = cleaned_data.get('title')

        # If draft article is selected, validate it
        if draft_article_id:
            article = get_publishable_draft(draft_article_id, self.user)

            # If draft is selected, content should not be provided
            if content and content.strip():
                raise forms.ValidationError('You cannot provide both a draft article and manual content. Please choose one.')

            # The solution takes the draft's title
            title = article.title
            cleaned_data['draft_article'] = article

        if self.task and title and Solution.title_taken(self.task, title, exclude_pk=self.instance.pk):
            raise forms.ValidationError(f'This task already has a solution titled "{title}".')

        # The on-site text would have no Article to live in
        if self.instance.pk and self.instance.solution_type != SolutionType.ONSITE and solution_type == SolutionType.ONSITE:
            raise forms.ValidationError(
                "An external solution can't become an on-site one. Write a new on-site solution instead."
            )

        # For onsite solutions without draft: require content
        if solution_type == SolutionType.ONSITE and not draft_article_id and not content:
            raise forms.ValidationError('On-site solutions must have content or a draft article selected.')

        # Validate that non-onsite solutions have URL
        if solution_type != SolutionType.ONSITE and not draft_article_id and not url:
            raise forms.ValidationError('External solutions must have a URL.')
        
        return cleaned_data

# for submitting analysis tasks
class AnalysisTaskForm(forms.ModelForm):
    # Image upload field (optional alternative to gallery selection)
    image_upload = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        label='Upload Image',
        help_text='Image must be 125x125 to 1024x1024 pixels with 1:1 aspect ratio (square). Non-square images will be center-cropped.'
    )
    
    # Reference solution fields (required for non-staff users)
    reference_solution_title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solution title'}),
        label='Reference Solution Title'
    )
    reference_solution_type = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Reference Solution Type'
    )
    reference_solution_url = forms.URLField(
        max_length=500,
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        label='Reference Solution URL'
    )
    reference_solution_content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        label='Reference Solution Content'
    )
    
    # Draft article selection (alternative to writing new content)
    reference_draft_article_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_reference_draft_article_id'}),
        label='Draft Article ID'
    )
    
    # Hiding options for reference solution
    hide_weeks = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        max_value=52,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '52', 'placeholder': '0'}),
        label='Hide solution for (weeks)',
        help_text='Set to 0 to make solution visible immediately, or 1-52 to hide temporarily'
    )
    
    class Meta:
        model = AnalysisTask
        fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'platform', 'tags', 'tools']
        widgets = {
            'sha256': forms.TextInput(attrs={'class': 'form-control sha256-readonly-field', 'placeholder': 'Auto-filled from download link', 'readonly': 'readonly'}),
            'download_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://bazaar.abuse.ch/... or https://malshare.com/...', 'id': 'id_download_link'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed description of the sample, will be in spoiler tags'}),
            'goal': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Analysis goal(s)'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'platform': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'comma-separated tags'}),
            'tools': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'comma-separated tools'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.is_edit = kwargs.pop('is_edit', False)
        super().__init__(*args, **kwargs)
        
        # Make core model fields required (but not reference solution fields)
        core_fields = ['sha256', 'download_link', 'description', 'goal', 'difficulty', 'platform', 'tags', 'tools']
        for field_name in core_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        self.fields['reference_solution_type'].choices = [('', '---------')] + list(SolutionType.choices)
        
        # Hide reference solution fields when editing
        if self.is_edit:
            del self.fields['reference_solution_title']
            del self.fields['reference_solution_type']
            del self.fields['reference_solution_url']
            del self.fields['reference_solution_content']
            del self.fields['reference_draft_article_id']
            del self.fields['hide_weeks']
        # Note: For non-staff users, reference solution validation is done in clean()
        # to allow either draft selection OR manual input
    
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
    
    def clean_image_upload(self):
        """Validate uploaded image dimensions and aspect ratio"""
        image = self.cleaned_data.get('image_upload')
        
        if image:
            from PIL import Image
            import io
            
            # Open image to check dimensions
            img = Image.open(image)
            width, height = img.size
            
            # Check minimum dimensions
            if width < 125 or height < 125:
                raise forms.ValidationError(
                    f'Image is too small ({width}x{height}px). Minimum size is 125x125 pixels.'
                )
            
            # Check maximum dimensions
            if width > 1024 or height > 1024:
                raise forms.ValidationError(
                    f'Image is too large ({width}x{height}px). Maximum size is 1024x1024 pixels.'
                )
            
            # Check if image needs to be cropped (not 1:1 aspect ratio)
            if width != height:
                # Center crop to square
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                
                img = img.crop((left, top, right, bottom))
                
                # Save cropped image back to file
                output = io.BytesIO()
                img_format = image.content_type.split('/')[-1].upper()
                if img_format == 'JPG':
                    img_format = 'JPEG'
                img.save(output, format=img_format)
                output.seek(0)
                
                # Update the uploaded file with cropped version
                from django.core.files.uploadedfile import InMemoryUploadedFile
                image = InMemoryUploadedFile(
                    output,
                    'ImageField',
                    image.name,
                    image.content_type,
                    output.getbuffer().nbytes,
                    None
                )
            
            # Reset file pointer
            image.seek(0)
        
        return image
    
    def clean(self):
        """Validate reference solution fields for non-staff users when creating (not editing)"""
        cleaned_data = super().clean()
        
        # Only validate reference solution when creating a new task (not editing)
        if not self.is_edit and self.user and not self.user.is_staff:
            ref_title = cleaned_data.get('reference_solution_title')
            ref_type = cleaned_data.get('reference_solution_type')
            ref_url = cleaned_data.get('reference_solution_url')
            ref_content = cleaned_data.get('reference_solution_content')
            draft_article_id = cleaned_data.get('reference_draft_article_id')
            
            # If draft article is selected, validate it
            if draft_article_id:
                # Stored for the view, which publishes it as the reference solution
                cleaned_data['_draft_article'] = get_publishable_draft(draft_article_id, self.user)
            else:
                # No draft selected, validate manual input is provided
                # Title and type are required
                if not ref_title or not ref_type:
                    raise forms.ValidationError(
                        "You must provide a reference solution. Either select an existing draft article or fill in the reference solution fields (title and type required)."
                    )
                
                # Validate based on solution type
                if ref_type == SolutionType.ONSITE:
                    if not ref_content:
                        raise forms.ValidationError(
                            "On-site reference solutions must have content."
                        )
                else:
                    if not ref_url:
                        raise forms.ValidationError(
                            "External reference solutions (blog, paper, video) must have a URL."
                        )
        
        return cleaned_data


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
        return check_new_email(self.cleaned_data.get('email'))


# Delete Account Form with password confirmation and Turnstile CAPTCHA
class DeleteAccountForm(UserFormMixin, forms.Form):
    """
    Form for users to delete their account (requires password confirmation).
    This action is irreversible.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password to confirm deletion'
        }),
        label="Confirm Password",
        help_text="Enter your password to confirm account deletion."
    )
    confirm_deletion = forms.BooleanField(
        required=True,
        label="I understand that this action is permanent and cannot be undone",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': 'You must confirm that you understand this action is permanent.'
        }
    )
    turnstile = TurnstileField(label="")

    def clean_password(self):
        return self.verified_password('password')


# Password Reset Form with Turnstile CAPTCHA
class TurnstilePasswordResetForm(PasswordResetForm):
    """
    Django's password reset form (finds every active account with the address)
    with Turnstile CAPTCHA protection.
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


# Change Password Form with Turnstile CAPTCHA
class ChangePasswordForm(UserFormMixin, forms.Form):
    """
    Form for users to change their own password (requires current password).
    """
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current password'}),
        label="Current Password"
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}),
        label="New Password"
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
        label="Confirm New Password"
    )
    turnstile = TurnstileField(label="")

    def clean_current_password(self):
        return self.verified_password('current_password', "Your current password is incorrect.")

    def clean(self):
        """Validate that the two password fields match"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")

        # Validate password strength
        if password1:
            try:
                validate_password(password1, self.user)
            except forms.ValidationError as error:
                self.add_error('new_password1', error)

        return cleaned_data

    def save(self):
        """Set the new password"""
        password = self.cleaned_data.get('new_password1')
        self.user.set_password(password)
        self.user.save()
        return self.user


# Change Email Form with Turnstile CAPTCHA
class ChangeEmailForm(UserFormMixin, forms.Form):
    """
    Form for users to change their email address (requires password verification).
    """
    new_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'new@email.com'}),
        label="New Email Address"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm your password'}),
        label="Current Password"
    )
    turnstile = TurnstileField(label="")

    def clean_password(self):
        return self.verified_password('password')

    def clean_new_email(self):
        email = self.cleaned_data.get('new_email')
        if email.lower() == self.user.email.lower():
            raise forms.ValidationError("This is already your current email address.")
        return check_new_email(email, self.user)


class ArticleForm(forms.Form):
    """Title and text of an article, as posted by the markdown editors"""
    title = forms.CharField(max_length=200, error_messages={'required': 'Title is required.'})
    content = forms.CharField(error_messages={'required': 'Content is required.'})

    def first_error(self):
        """The editors show one message at a time"""
        return next(iter(self.errors.values()))[0]
