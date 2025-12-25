from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from taggit.managers import TaggableManager
from taggit.models import TaggedItemBase
from cloudinary.models import CloudinaryField


class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    ADVANCED = "advanced", "Advanced"
    EXPERT = "expert", "Expert"


class CourseName(models.TextChoices):
    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"


class TaggedTools(TaggedItemBase):
    content_object = models.ForeignKey('Sample', on_delete=models.CASCADE)


class CourseReference(models.Model):
    course_name = models.CharField(
        max_length=20,
        choices=CourseName.choices,
        verbose_name="Course name"
    )
    
    section = models.IntegerField(
        verbose_name="Section",
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    
    video_title = models.CharField(
        max_length=500,
        verbose_name="Video title"
    )
    
    class Meta:
        ordering = ['course_name', 'section']
        unique_together = ['course_name', 'section', 'video_title']
    
    def __str__(self):
        return f"{self.get_course_name_display()} - Section {self.section}: {self.video_title[:50]}"


class Sample(models.Model):
    sha256 = models.CharField(
        max_length=64,
        unique=True,
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
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created at")
    send_discord_notification = models.BooleanField(default=True, verbose_name="Send Discord notification")
    
    @property
    def favorite_count(self):
        return self.favorited_by.count()

    def __str__(self):
        return self.sha256

