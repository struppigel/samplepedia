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


# Difficulty point multipliers - SINGLE SOURCE OF TRUTH
# Used in score calculation and displayed in UI
DIFFICULTY_POINTS = {
    'easy': 10,
    'medium': 20,
    'advanced': 40,
    'expert': 80,
}


def get_user_score(user):
    """Calculate user score based on likes received with difficulty multipliers.
    
    Scoring system:
    - Easy task like: 100 points
    - Medium task like: 200 points
    - Advanced task like: 300 points
    - Expert task like: 500 points
    
    - Easy solution like: 100 points
    - Medium solution like: 200 points
    - Advanced solution like: 300 points
    - Expert solution like: 500 points
    """
    from django.db.models import Count, Case, When, IntegerField, Sum
    
    # Score from analysis task likes
    task_score = 0
    tasks = user.analysis_tasks.annotate(
        points=Case(
            When(difficulty='easy', then=DIFFICULTY_POINTS['easy']),
            When(difficulty='medium', then=DIFFICULTY_POINTS['medium']),
            When(difficulty='advanced', then=DIFFICULTY_POINTS['advanced']),
            When(difficulty='expert', then=DIFFICULTY_POINTS['expert']),
            default=1,
            output_field=IntegerField(),
        ),
        weighted_likes=Count('favorited_by') * models.F('points')
    ).aggregate(total=Sum('weighted_likes'))
    
    task_score = task_score or 0
    if tasks['total']:
        task_score = tasks['total']
    
    # Score from solution likes (based on the task difficulty they solved)
    solution_score = 0
    solutions = user.solutions.select_related('analysis_task').annotate(
        points=Case(
            When(analysis_task__difficulty='easy', then=DIFFICULTY_POINTS['easy']),
            When(analysis_task__difficulty='medium', then=DIFFICULTY_POINTS['medium']),
            When(analysis_task__difficulty='advanced', then=DIFFICULTY_POINTS['advanced']),
            When(analysis_task__difficulty='expert', then=DIFFICULTY_POINTS['expert']),
            default=1,
            output_field=IntegerField(),
        ),
        weighted_likes=Count('liked_by') * models.F('points')
    ).aggregate(total=Sum('weighted_likes'))
    
    if solutions['total']:
        solution_score = solutions['total']
    
    return task_score + solution_score


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
        verbose_name="Verb",
        help_text="Action type: liked, commented, added_solution, etc."
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
    
    tags = TaggableManager(blank=True, verbose_name="Tags", related_name='tagged_samples')
    tools = TaggableManager(blank=True, verbose_name="Tools", related_name='tool_samples', through=TaggedTools)
    youtube_id = models.CharField(max_length=32, blank=True, verbose_name="YouTube ID")
    image = CloudinaryField('image', blank=True, null=True)
    like_count = models.IntegerField(default=0, verbose_name="Like count")
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
    
    class Meta:
        indexes = [
            models.Index(fields=['difficulty'], name='idx_difficulty'),
            models.Index(fields=['-created_at'], name='idx_created_desc'),
            models.Index(fields=['difficulty', '-created_at'], name='idx_diff_created'),
            models.Index(fields=['sha256'], name='idx_sha256'),
        ]
    
    @property
    def favorite_count(self):
        return self.favorited_by.count()
    
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
    
    content = models.TextField(
        verbose_name="Content",
        blank=True,
        help_text="Markdown content for on-site solutions"
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
    
    @property
    def like_count(self):
        return self.liked_by.count()
    
    class Meta:
        unique_together = ['title', 'analysis_task']
        ordering = ['-created_at']
    
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

