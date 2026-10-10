import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from auditlogs.models import AuditLog
from auditlogs.service import log_action
from utils.custom_error import error_response

logger = logging.getLogger(__name__)


def log_staff_password_change(request, user, via):
    """Admins' password changes go in the audit trail (never the password itself)."""
    log_action(request, AuditLog.Action.ADMIN_PASSWORD_CHANGED, AuditLog.TargetType.ADMIN, user.id, user.email,
               {"full_name": user.full_name, "role": user.user_type, "via": via}, staff_only=True)


class ChangePasswordView(APIView):
    """
    POST /api/accounts/me/change-password/
    Body: {"current_password": "...", "new_password": "..."}

    The signed-in user changes their own password. The current password is
    required so a stolen session token alone can't take over the account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current = request.data.get("current_password") or ""
        new = request.data.get("new_password") or ""

        if not user.has_usable_password():
            return error_response(
                "Your account signs in with Google, so it has no password yet. "
                "Use “Forgot password” on the login page to set one.",
                {"current_password": ["This account has no password set."]},
            )
        if not current or not user.check_password(current):
            return error_response("Your current password is incorrect.",
                                  {"current_password": ["Your current password is incorrect."]})
        if not new:
            return error_response("Enter a new password.", {"new_password": ["Enter a new password."]})
        if new == current:
            return error_response("Choose a password different from your current one.",
                                  {"new_password": ["Choose a password different from your current one."]})
        try:
            validate_password(new, user=user)
        except ValidationError as e:
            return error_response(e.messages[0], {"new_password": list(e.messages)})

        user.set_password(new)
        user.save(update_fields=["password", "updated_at"])
        log_staff_password_change(request, user, via="profile")
        logger.info(f"Password changed for user: {user.email}")

        return Response({"message": "Your password has been changed."}, status=status.HTTP_200_OK)
