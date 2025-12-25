from django.db import models
from django.contrib.auth.models import User
from taggit.managers import TaggableManager
from cloudinary.models import CloudinaryField


class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    ADVANCED = "advanced", "Advanced"
    EXPERT = "expert", "Expert"


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

    tools = models.TextField(
        blank=True,
        verbose_name="Tools"
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
    
    tags = TaggableManager(blank=True)
    youtube_id = models.CharField(max_length=32, blank=True, verbose_name="YouTube ID")
    image = CloudinaryField('image', blank=True, null=True)
    like_count = models.IntegerField(default=0, verbose_name="Like count")
    favorited_by = models.ManyToManyField(User, related_name='favorite_samples', blank=True)
    
    @property
    def favorite_count(self):
        return self.favorited_by.count()

    def __str__(self):
        return self.sha256

