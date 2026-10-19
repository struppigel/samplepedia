from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from samples.views import login_view

urlpatterns = [
    path("admin/login/", login_view, name="admin_login"),
    path("admin/", admin.site.urls),
    # comments/ routes live in samples.urls so the custom views take precedence
    # Not permanent: browsers would cache the redirect even if the icon moves
    path('favicon.ico', RedirectView.as_view(url='/static/myhegebatlogo_white.png')),
    path("", include("samples.urls")),
]
