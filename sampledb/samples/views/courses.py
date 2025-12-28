from django.shortcuts import render, get_object_or_404
from django.db.models import Count

from ..models import Course, AnalysisTask


def course_list(request):
    """Display list of available courses"""
    courses = Course.objects.annotate(
        sample_count=Count('references__samples', distinct=True)
    ).order_by('name')
    
    return render(request, "samples/course_list.html", {
        "courses": courses,
    })


def course_samples(request, course_id):
    """Display samples for a specific course, sorted by section number"""
    # Get the course or 404
    course = get_object_or_404(Course, id=course_id)
    
    # Get all samples that have references to this course
    # We need to get distinct samples and annotate with the minimum section number
    samples = AnalysisTask.objects.filter(
        course_references__course=course
    ).prefetch_related('course_references').distinct()
    
    # Build a list with samples and their course references
    sample_data = []
    for sample in samples:
        # Get all course references for this sample in this course
        refs = sample.course_references.filter(
            course=course
        ).order_by('section')
        
        for ref in refs:
            sample_data.append({
                'sample': sample,
                'section': ref.section,
                'lecture_number': ref.lecture_number,
                'lecture_title': ref.lecture_title,
            })
    
    # Sort by section number
    sample_data.sort(key=lambda x: (x['section'], x['lecture_number']))
    
    # Get user's favorited sample IDs for display
    user_favorited_ids = set()
    if request.user.is_authenticated:
        user_favorited_ids = set(
            request.user.favorite_samples.values_list('id', flat=True)
        )
    
    return render(request, "samples/course_samples.html", {
        "course": course,
        "sample_data": sample_data,
        "user_favorited_ids": user_favorited_ids,
    })
