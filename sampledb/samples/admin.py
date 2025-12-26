from django.contrib import admin
from .models import Sample, CourseReference, Course

@admin.register(CourseReference)
class CourseReferenceAdmin(admin.ModelAdmin):
    list_display = ("course", "section", "lecture_number", "lecture_title_short")
    list_filter = ("course", "section", "lecture_number")
    search_fields = ("lecture_title", "course__name")
    ordering = ("course__name", "section", "lecture_number")
    
    def lecture_title_short(self, obj):
        return obj.lecture_title[:50] + "..." if len(obj.lecture_title) > 50 else obj.lecture_title
    lecture_title_short.short_description = "Lecture Title"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "url")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sha256", "difficulty")
    list_filter = ("difficulty",)
    search_fields = ("sha256", "goal", "description")
    filter_horizontal = ("course_references",)