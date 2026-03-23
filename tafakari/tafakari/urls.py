from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
from accounts.views import GoogleLoginCallback, GoogleLogin, LoginPage
import os


def serve_media(request, path):
    """Serve uploaded media files — works with both runserver and daphne."""
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    # Prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404
    if not os.path.isfile(file_path):
        raise Http404
    return FileResponse(open(file_path, 'rb'))


urlpatterns = [
    path('admin/', admin.site.urls),
    # Include the URLs from the accounts app
    path('api/accounts/', include('accounts.urls')),

    path('api/v1/auth/', include('dj_rest_auth.urls')),
    path("auth/google/login/", LoginPage.as_view(), name="login"),

    re_path(r"^api/v1/auth/accounts/", include("allauth.urls")),

    path("api/v1/auth/registration/", include("dj_rest_auth.registration.urls")),
    #google auth urls
    path('api/v1/auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('api/v1/auth/google/callback/', GoogleLoginCallback.as_view(), name='google_callback'),
    # Include the URLs from the workers app
    path('api/workers/', include('workers.urls')),
    # Include the URLs from the employers app
    path('api/employers/', include('employers.urls')),
    # Include the URLs from the jobs app
    path('api/jobs/', include('jobs.urls')),
    # Include the URLs from the skills app
    path('api/skills/', include('skills.urls')),
    path('api/applications/', include('applications.urls')),
    path('api/messages/', include('messaging.urls')),
    path('api/adminpanel/', include('adminpanel.urls')),

    # Media file serving (works with daphne/ASGI too)
    re_path(r'^media/(?P<path>.*)$', serve_media, name='serve-media'),
]