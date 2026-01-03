# Import all views for backward compatibility with urls.py
from .samples import sample_list, sample_detail, submit_task, edit_task, delete_task, markdown_preview
from .solutions import create_solution, edit_solution, delete_solution, solution_list, view_onsite_solution, onsite_solution_editor, solutions_showcase
from .courses import course_list, course_samples
from .likes import toggle_like, toggle_solution_like
from .auth import (
    register, 
    send_verification_email, 
    verification_sent, 
    verify_email, 
    resend_verification,
    user_profile,
    login_view,
    password_reset_request,
    profile_settings,
    change_password,
    change_email,
    verify_email_change,
    ranking
)
from .pages import impressum, privacy_policy, markdown_editor
from .comments import edit_comment, delete_comment
from .notifications import (
    notification_list,
    notification_dropdown,
    mark_notification_read,
    mark_all_read,
    delete_notification,
    unread_count
)

__all__ = [
    # Samples
    'sample_list',
    'sample_detail',
    'submit_task',
    'edit_task',
    'delete_task',
    'markdown_preview',
    # Solutions
    'create_solution',
    'edit_solution',
    'delete_solution',
    'solution_list',
    'view_onsite_solution',
    'onsite_solution_editor',
    'solutions_showcase',
    # Courses
    'course_list',
    'course_samples',
    # Likes
    'toggle_like',
    'toggle_solution_like',
    # Auth
    'register',
    'send_verification_email',
    'verification_sent',
    'verify_email',
    'resend_verification',
    'user_profile',
    'login_view',
    'password_reset_request',
    'profile_settings',
    'change_password',
    'change_email',
    'verify_email_change',
    'ranking',
    # Pages
    'impressum',
    'privacy_policy',
    'markdown_editor',
    # Comments
    'edit_comment',
    'delete_comment',
    # Notifications
    'notification_list',
    'notification_dropdown',
    'mark_notification_read',
    'mark_all_read',
    'delete_notification',
    'unread_count',
]
