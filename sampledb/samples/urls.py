from django.urls import path
from . import views

urlpatterns = [
    path("", views.sample_list, name="sample_list"),
    path("sample/<str:sha256>/", views.sample_detail, name="sample_detail"),
    path("sample/<str:sha256>/like/", views.toggle_like, name="toggle_like"),
]
