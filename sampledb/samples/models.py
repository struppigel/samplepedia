from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from taggit.managers import TaggableManager
from taggit.models import TaggedItemBase
from cloudinary.models import CloudinaryField
from django.core.validators import RegexValidator

class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    ADVANCED = "advanced", "Advanced"
    EXPERT = "expert", "Expert"


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
    content_object = models.ForeignKey('Sample', on_delete=models.CASCADE)


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

class Sample(models.Model):

    sha256_validator = RegexValidator(
        regex=r'^[a-fA-F0-9]{64}$',
        message='Must be a valid SHA256 hash (64 hexadecimal characters)',
        code='invalid_sha256'
    )

    sha256 = models.CharField(
        max_length=64,
        validators=[sha256_validator],
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
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    send_discord_notification = models.BooleanField(default=True, verbose_name="Send Discord notification")
    
    @property
    def favorite_count(self):
        return self.favorited_by.count()

    def __str__(self):
        return self.sha256
    
    def save(self, *args, **kwargs):
        # Convert to lowercase before saving
        if self.sha256:
            self.sha256 = self.sha256.lower()
        
        super().save(*args, **kwargs)

