from django.urls import path
from . import views

urlpatterns = [
    path("", views.sample_list, name="sample_list"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/<int:course_id>/", views.course_samples, name="course_samples"),
    path("sample/<str:sha256>/", views.sample_detail, name="sample_detail"),
    path("sample/<str:sha256>/like/", views.toggle_like, name="toggle_like"),
]
