from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comments/", include('django_comments_xtd.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/myhegebatlogo_white.png', permanent=True)),
    path("", include("samples.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
