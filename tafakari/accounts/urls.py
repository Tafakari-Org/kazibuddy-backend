from django.urls import path
from .views import (
    LoginView,
    RegisterView,
    UserProfileView,
    LogoutView,
    UpdateUserProfileView,
    DeleteAccountView,
    VerifyEmailView,
    PasswordResetView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    # User registration and login endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # Token refresh endpoint
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', UserProfileView.as_view(), name='profile'),
    path('me/update/', UpdateUserProfileView.as_view(), name='update_profile'),
    path('me/delete/', DeleteAccountView.as_view(), name='delete_profile'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),

    # Legacy OTP-based password reset (preserved)
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),

    # Secure token-based password reset (new)
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]

