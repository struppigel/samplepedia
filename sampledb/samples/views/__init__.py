# Import all views for backward compatibility with urls.py
from .samples import sample_list, sample_detail, submit_task, edit_task
from .solutions import create_solution, delete_solution
from .courses import course_list, course_samples
from .likes import toggle_like
from .auth import (
    register, 
    send_verification_email, 
    verification_sent, 
    verify_email, 
    resend_verification,
    user_profile
)
from .pages import impressum, privacy_policy

__all__ = [
    # Samples
    'sample_list',
    'sample_detail',
    'submit_task',
    'edit_task',
    # Solutions
    'create_solution',
    'delete_solution',
    # Courses
    'course_list',
    'course_samples',
    # Likes
    'toggle_like',
    # Auth
    'register',
    'send_verification_email',
    'verification_sent',
    'verify_email',
    'resend_verification',
    'user_profile',
    # Pages
    'impressum',
    'privacy_policy',
]
