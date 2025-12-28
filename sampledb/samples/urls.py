from django.urls import path
from . import views

urlpatterns = [
    path("", views.sample_list, name="sample_list"),
    path("submit/", views.submit_task, name="submit_task"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/<int:course_id>/", views.course_samples, name="course_samples"),
    path("sample/<str:sha256>/<int:task_id>/", views.sample_detail, name="sample_detail"),
    path("sample/<str:sha256>/<int:task_id>/like/", views.toggle_like, name="toggle_like"),
    path("sample/<str:sha256>/<int:task_id>/solution/add/", views.create_solution, name="create_solution"),
    path("sample/<str:sha256>/<int:task_id>/solution/<int:solution_id>/delete/", views.delete_solution, name="delete_solution"),
    path("impressum/", views.impressum, name="impressum"),
    path("privacy/", views.privacy_policy, name="privacy_policy"),
    path("register/", views.register, name="register"),
    path("verification-sent/", views.verification_sent, name="verification_sent"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
]
