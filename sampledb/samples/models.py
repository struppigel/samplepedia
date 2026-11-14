from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from taggit.managers import TaggableManager
from taggit.models import TaggedItemBase
from cloudinary.models import CloudinaryField
from django.core.validators import RegexValidator

from .querysets import AnalysisTaskQuerySet, SolutionQuerySet


class NotificationVerb(models.TextChoices):
    """The stored values are the legacy free-text verbs, so existing rows stay valid"""
    LIKED_TASK = 'liked', 'Liked a task'
    LIKED_SOLUTION = 'liked_solution', 'Liked a solution'
    COMMENTED = 'commented', 'Commented'
    MENTIONED = 'mentioned you in a comment', 'Mentioned in a comment'
    SUBMITTED_SOLUTION = 'submitted a solution', 'Submitted a solution'


NOTIFICATION_ICONS = {
    NotificationVerb.LIKED_TASK: 'fas fa-heart text-danger',
    NotificationVerb.LIKED_SOLUTION: 'fas fa-heart text-danger',
    NotificationVerb.COMMENTED: 'fas fa-comment text-info',
    NotificationVerb.MENTIONED: 'fas fa-at text-info',
    NotificationVerb.SUBMITTED_SOLUTION: 'fas fa-lightbulb text-warning',
}


class NotificationQuerySet(models.QuerySet):
    """Custom queryset for Notification model"""
    
    def unread(self):
        """Return only unread notifications"""
        return self.filter(unread=True)
    
    def read(self):
        """Return only read notifications"""
        return self.filter(unread=False)
    
    def mark_all_as_read(self, recipient=None):
        """Mark all notifications as read"""
        qs = self.unread()
        if recipient:
            qs = qs.filter(recipient=recipient)
        return qs.update(unread=False)
    
    def mark_all_as_unread(self, recipient=None):
        """Mark all notifications as unread"""
        qs = self.read()
        if recipient:
            qs = qs.filter(recipient=recipient)
        return qs.update(unread=True)


class Notification(models.Model):
    """
    Custom notification model for tracking user notifications.
    Supports likes, comments, solutions, and other activities.
    """
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Recipient"
    )
    
    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        verbose_name="Actor",
        help_text="The user who triggered this notification"
    )
    
    verb = models.CharField(
        max_length=50,
        choices=NotificationVerb.choices,
        verbose_name="Verb",
        help_text="What the actor did"
    )
    
    # GenericForeignKey for the target object (what was acted upon)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='notification_targets'
    )
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_content_type', 'target_object_id')
    
    # Optional: GenericForeignKey for the action object (additional context)
    action_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='notification_actions',
        null=True,
        blank=True
    )
    action_object_id = models.PositiveIntegerField(null=True, blank=True)
    action_object = GenericForeignKey('action_content_type', 'action_object_id')
    
    description = models.TextField(
        verbose_name="Description",
        help_text="Human-readable description of the notification"
    )
    
    unread = models.BooleanField(
        default=True,
        verbose_name="Unread",
        db_index=True
    )
    
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Extra data",
        help_text="Additional JSON data (e.g., sha256, URLs)"
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Timestamp",
        db_index=True
    )
    
    objects = NotificationQuerySet.as_manager()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['recipient', 'unread']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
    
    def __str__(self):
        return f"{self.actor.username} {self.verb} → {self.recipient.username}"
    
    @property
    def icon(self):
        """Font Awesome classes for this kind of notification"""
        return NOTIFICATION_ICONS.get(self.verb, 'fas fa-bell text-muted')

    def mark_as_read(self):
        """Mark this notification as read"""
        if self.unread:
            self.unread = False
            self.save(update_fields=['unread'])
    
    def mark_as_unread(self):
        """Mark this notification as unread"""
        if not self.unread:
            self.unread = True
            self.save(update_fields=['unread'])


class Difficulty(models.TextChoices):
    EASY = "easy", "easy"
    MEDIUM = "medium", "medium"
    ADVANCED = "advanced", "advanced"
    EXPERT = "expert", "expert"

# Points per like, by task difficulty - SINGLE SOURCE OF TRUTH
# Used by samples/scoring.py and displayed in the UI
DIFFICULTY_POINTS = {
    Difficulty.EASY: 10,
    Difficulty.MEDIUM: 20,
    Difficulty.ADVANCED: 40,
    Difficulty.EXPERT: 80,
}


class Platform(models.TextChoices):
    WINDOWS = "windows", "Windows"
    LINUX = "linux", "Linux"
    MACOS = "macos", "MacOS"
    IOS = "ios", "iOS"
    ANDROID = "android", "Android" 
    MULTIPLE = "multiple", "Multiple"
    OTHER = "other", "Other"

class Course(models.Model):
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Course name"
    )
    
    url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Course URL"
    )
    
    image = CloudinaryField('course_image', blank=True, null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class TaggedTools(TaggedItemBase):
    content_object = models.ForeignKey('AnalysisTask', on_delete=models.CASCADE)


class CourseReference(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='references',
        verbose_name="Course"
    )
    
    section = models.IntegerField(
        verbose_name="Section",
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    
    lecture_number = models.IntegerField(
        verbose_name="Lecture number",
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )

    lecture_title = models.CharField(
        max_length=500,
        verbose_name="Lecture title"
    )
    
    class Meta:
        ordering = ['course__name', 'section', 'lecture_number']
        unique_together = ['course', 'section', 'lecture_number']
    
    def __str__(self):
        return f"{self.course.name} - Section {self.section} Lecture {self.lecture_number}: {self.lecture_title[:50]}"

class AnalysisTask(models.Model):

    sha256_validator = RegexValidator(
        regex=r'^[a-fA-F0-9]{64}$',
        message='Must be a valid SHA256 hash (64 hexadecimal characters)',
        code='invalid_sha256'
    )

    sha256 = models.CharField(
        max_length=64,
        validators=[sha256_validator],
        verbose_name="SHA256"
    )

    download_link = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Download link"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )

    goal = models.TextField(
        blank=True,
        verbose_name="Goal"
    )
    
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
        verbose_name="Difficulty level"
    )

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.WINDOWS,
        verbose_name="Platform"
    )
    
    tags = TaggableManager(blank=True, verbose_name="Tags", related_name='tagged_samples')
    tools = TaggableManager(blank=True, verbose_name="Tools", related_name='tool_samples', through=TaggedTools)
    youtube_id = models.CharField(max_length=32, blank=True, verbose_name="YouTube ID")
    image = CloudinaryField('image', blank=True, null=True)
    view_count = models.IntegerField(default=0, verbose_name="View count")
    favorited_by = models.ManyToManyField(User, related_name='favorite_samples', blank=True)
    course_references = models.ManyToManyField(CourseReference, related_name='samples', blank=True, verbose_name="Course references")
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='analysis_tasks',
        verbose_name="Author"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    send_discord_notification = models.BooleanField(default=True, verbose_name="Send Discord notification")

    objects = AnalysisTaskQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['difficulty'], name='idx_difficulty'),
            models.Index(fields=['-created_at'], name='idx_created_desc'),
            models.Index(fields=['difficulty', '-created_at'], name='idx_diff_created'),
            models.Index(fields=['sha256'], name='idx_sha256'),
            models.Index(fields=['-view_count'], name='idx_view_count'),
        ]
    
    @property
    def favorite_count(self):
        # Use the list annotation when the queryset provides it
        annotated = getattr(self, 'favorite_count_annotated', None)
        return self.favorited_by.count() if annotated is None else annotated
    
    def user_can_edit(self, user):
        """Check if a user has permission to edit this task"""
        if not user.is_authenticated:
            return False
        return user == self.author or user.is_staff
    
    def get_absolute_url(self):
        """Return the URL to the detail page for this task"""
        return reverse('sample_detail', kwargs={'sha256': self.sha256, 'task_id': self.id})

    def __str__(self):
        return self.sha256
    
    def save(self, *args, **kwargs):
        # Convert to lowercase before saving
        if self.sha256:
            self.sha256 = self.sha256.lower()
        
        super().save(*args, **kwargs)


class Article(models.Model):
    """Article model for draft articles and on-site solution content.
    
    Articles can exist as standalone drafts (not attached to any analysis task)
    or be attached to an analysis task as an on-site solution.
    In the future, they can also be used for wiki-like entries.
    """
    
    title = models.CharField(
        max_length=200,
        verbose_name="Title"
    )
    
    content = models.TextField(
        verbose_name="Content",
        help_text="Markdown content"
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='articles',
        verbose_name="Author"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")
    
    view_count = models.IntegerField(default=0, verbose_name="View count")
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['author'], name='idx_article_author'),
            models.Index(fields=['-updated_at'], name='idx_article_updated'),
            models.Index(fields=['-created_at'], name='idx_article_created'),
        ]
        verbose_name = "Article"
        verbose_name_plural = "Articles"
    
    def __str__(self):
        return self.title
    
    def is_published(self):
        """Check if this article is attached to a solution (published)"""
        return hasattr(self, 'solution') and self.solution is not None
    
    def get_publication_date(self):
        """When the article became visible: None while unpublished or hidden"""
        if not self.is_visible():
            return None
        # A hidden solution was published when its hidden period ended
        return self.solution.hidden_until or self.solution.created_at

    def is_visible(self):
        """Check if this article is visible (published and not hidden)"""
        return self.is_published() and not self.solution.is_hidden
    
    def user_can_edit(self, user):
        """Check if a user has permission to edit this article"""
        if not user.is_authenticated:
            return False
        return user == self.author or user.is_staff


class SolutionType(models.TextChoices):
    BLOG = "blog", "Blog"
    PAPER = "paper", "Paper"
    VIDEO = "video", "Video"
    ONSITE = "onsite", "On-Site Article"

class Solution(models.Model):

    analysis_task = models.ForeignKey(
        AnalysisTask,
        on_delete=models.CASCADE,
        related_name='solutions',
        verbose_name="Analysis task"
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name="Title"
    )
    
    solution_type = models.CharField(
        max_length=10,
        choices=SolutionType.choices,
        verbose_name="Solution type"
    )
    
    url = models.URLField(
        max_length=500,
        verbose_name="URL",
        blank=True,
        null=True
    )
    
    # Reference to Article for on-site solutions
    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
        related_name='solution',
        verbose_name="Article",
        null=True,
        blank=True,
        help_text="Article content for on-site solutions"
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='solutions',
        verbose_name="Author"
    )
    
    liked_by = models.ManyToManyField(
        User,
        related_name='liked_solutions',
        blank=True,
        verbose_name="Liked by"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    
    # Hiding feature for reference solutions
    hidden_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Hidden until",
        help_text="Date and time when this solution becomes visible. Leave blank for immediate visibility."
    )

    # Set when the solution was announced on Discord: at creation if visible, else by
    # the announce_solutions command once hidden_until has passed
    discord_announced_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Announced on Discord at",
    )

    objects = SolutionQuerySet.as_manager()

    @property
    def like_count(self):
        # Use the list annotation when the queryset provides it
        annotated = getattr(self, 'like_count_annotated', None)
        return self.liked_by.count() if annotated is None else annotated
    
    @property
    def get_content(self):
        """The text of an on-site solution, stored in its Article"""
        return self.article.content if self.article else ""
    
    def user_can_see_hidden_status(self, user):
        """Staff, the task author and the solution author may see a hidden solution"""
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user == self.analysis_task.author or user == self.author

    @property
    def is_hidden(self):
        """True while the solution is still hidden from other users"""
        return bool(self.hidden_until and self.hidden_until > timezone.now())

    def user_can_view(self, user):
        """The instance-level twin of Solution.objects.visible_to(user)"""
        return not self.is_hidden or self.user_can_see_hidden_status(user)

    def user_can_edit(self, user):
        return user.is_authenticated and (user == self.author or user.is_staff)

    @property
    def is_reference(self):
        """Written by the task's own author"""
        return self.author_id == self.analysis_task.author_id

    def is_last_reference(self):
        """Every task keeps at least one reference solution, so its last one can't be removed"""
        if not self.is_reference:
            return False
        count = getattr(self, 'reference_count', None)  # from with_reference_count()
        if count is None:
            count = Solution.objects.filter(analysis_task_id=self.analysis_task_id).reference().count()
        return count <= 1

    def user_can_delete(self, user):
        return self.user_can_edit(user) and not self.is_last_reference()

    def get_absolute_url(self):
        task = self.analysis_task
        if self.solution_type == SolutionType.ONSITE:
            return reverse('view_onsite_solution', kwargs={
                'sha256': task.sha256, 'task_id': task.id, 'solution_id': self.id,
            })
        # External solutions live elsewhere; here they are a highlighted row on the task page
        return f'{task.get_absolute_url()}?highlight_solution={self.id}'

    @classmethod
    def title_taken(cls, task, title, exclude_pk=None):
        """Titles are unique per task (unique_together); check before saving to avoid an IntegrityError"""
        return cls.objects.filter(analysis_task=task, title=title).exclude(pk=exclude_pk).exists()

    class Meta:
        unique_together = ['title', 'analysis_task']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['solution_type'], name='idx_solution_type'),
            models.Index(fields=['analysis_task', 'solution_type'], name='idx_task_type'),
            models.Index(fields=['-created_at'], name='idx_solution_created'),
            models.Index(fields=['author'], name='idx_solution_author'),
            models.Index(fields=['hidden_until'], name='idx_hidden_until'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_solution_type_display()}) for {self.analysis_task.sha256}"


class SampleImage(models.Model):
    """Library of images that can be used for analysis tasks"""
    image = CloudinaryField('sample_library_image')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Uploaded at")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Sample Image"
        verbose_name_plural = "Sample Images"
    
    def __str__(self):
        return f"Sample Image {self.id}"


class EditorImage(models.Model):
    """Images uploaded through the markdown editor for use in solutions"""
    image = CloudinaryField('editor_images')
    
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='editor_images',
        verbose_name="Uploader"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Uploaded at")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Editor Image"
        verbose_name_plural = "Editor Images"
    
    def __str__(self):
        return f"Editor Image {self.id} by {self.uploader.username}"

