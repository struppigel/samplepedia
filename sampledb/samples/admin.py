from django.contrib import admin
from .models import AnalysisTask, CourseReference, Course, Solution, SampleImage

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


@admin.register(AnalysisTask)
class AnalysisTaskAdmin(admin.ModelAdmin):
    list_display = ("sha256", "difficulty", "author", "created_at")
    list_filter = ("difficulty", "author")
    search_fields = ("sha256", "goal", "description", "author__username")
    filter_horizontal = ("course_references",)
    autocomplete_fields = ["author"]
    readonly_fields = ("created_at",)
    
    def get_changeform_initial_data(self, request):
        return {"author": request.user}


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ("title", "analysis_task_sha256", "solution_type", "author", "created_at")
    list_filter = ("solution_type", "created_at")
    search_fields = ("title", "analysis_task__sha256", "author__username")
    autocomplete_fields = ["analysis_task", "author"]
    readonly_fields = ("created_at",)
    
    def analysis_task_sha256(self, obj):
        return obj.analysis_task.sha256[:12] + "..."
    analysis_task_sha256.short_description = "Analysis Task"


@admin.register(SampleImage)
class SampleImageAdmin(admin.ModelAdmin):
    list_display = ("id", "image_preview", "created_at")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "image_preview")
    
    def image_preview(self, obj):
        if obj.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"