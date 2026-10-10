"""
Why an account that passed the password check still can't sign in.

Each refusal carries a machine-readable `code` so the frontend can show the
right screen instead of guessing from the message text.
"""
from rest_framework import status
from rest_framework.response import Response

from .rejection import reason_labels


def support_email():
    """The contact address admins set for the site footer, else the default support inbox."""
    from adminpanel.models import FooterSettings
    from utils.views import SUPPORT_EMAIL

    configured = FooterSettings.objects.filter(pk=1).values_list('email', flat=True).first()
    return configured or SUPPORT_EMAIL


def login_refusal(user):
    """(code, message) when `user` may not sign in yet, else None."""
    if not user.email_verified:
        return 'email_unverified', "Email not verified. Please verify your email before logging in."
    if user.is_verified:
        return None
    if user.rejected_at:
        return 'account_rejected', "Your registration was not approved."
    return 'pending_approval', "You are not approved by admin yet. Please wait for approval."


def rejection_details(user):
    """What a rejected user is shown at sign-in. Only sent after the password (or Google) check passed."""
    return {
        "reasons": reason_labels(user.rejection_reasons or []),
        "note": user.rejection_note or '',
        "rejected_at": user.rejected_at,
        "support_email": support_email(),
    }


def _refusal(code, message, **extra):
    return Response({"code": code, "message": message, "error": message, **extra}, status=status.HTTP_403_FORBIDDEN)


def rejected_login_response(user):
    """403 for a rejected account, with the reasons and who to contact."""
    return _refusal('account_rejected', "Your registration was not approved.", rejection=rejection_details(user))


def login_refusal_response(user):
    """403 Response describing why `user` can't sign in, or None if they can."""
    refusal = login_refusal(user)
    if refusal is None:
        return None
    code, message = refusal
    if code == 'account_rejected':
        return rejected_login_response(user)
    return _refusal(code, message)
