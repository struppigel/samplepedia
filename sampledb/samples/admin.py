from django.contrib import admin
from .models import Sample, CourseReference

@admin.register(CourseReference)
class CourseReferenceAdmin(admin.ModelAdmin):
    list_display = ("course_name", "section", "video_title_short")
    list_filter = ("course_name", "section")
    search_fields = ("video_title",)
    ordering = ("course_name", "section")
    
    def video_title_short(self, obj):
        return obj.video_title[:50] + "..." if len(obj.video_title) > 50 else obj.video_title
    video_title_short.short_description = "Video Title"


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sha256", "difficulty")
    list_filter = ("difficulty",)
    search_fields = ("sha256", "goal", "description")
    filter_horizontal = ("course_references",)