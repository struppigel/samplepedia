from django.db import models
from taggit.managers import TaggableManager


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
    image = models.ImageField(upload_to='sample_images/', blank=True, verbose_name="Image")
    like_count = models.IntegerField(default=0, verbose_name="Like count")

    def __str__(self):
        return self.sha256

