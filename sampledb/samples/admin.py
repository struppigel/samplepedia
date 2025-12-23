from django.contrib import admin
from .models import Sample

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sha256", "difficulty")
    list_filter = ("difficulty",)
    search_fields = ("sha256", "goal", "description")