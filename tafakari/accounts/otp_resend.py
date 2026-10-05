import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.views import generate_otp, send_otp_to_email
from .models import CustomUser, OTPVerification
from .tasks import cleanup_unverified_user

logger = logging.getLogger(__name__)

# A new code can be requested this often, and at most this many times per hour.
RESEND_COOLDOWN_SECONDS = 60
MAX_RESENDS_PER_HOUR = 5


def otp_ttl_seconds():
    return getattr(settings, 'OTP_TTL_SECONDS', 300)


def unverified_grace_seconds():
    """How long an unverified sign-up is kept after its code expires, so the user can ask for a new one."""
    return getattr(settings, 'UNVERIFIED_ACCOUNT_GRACE_SECONDS', 30 * 60)


def schedule_unverified_cleanup(user):
    """
    (Re)schedule deletion of an unverified sign-up for when its latest code expires
    plus the grace period. Any previously scheduled cleanup is revoked first, so a
    resend always pushes the deadline back. Best-effort: never raises.
    """
    delay = otp_ttl_seconds() + unverified_grace_seconds()
    key = f"cleanup_task_id:{user.id}"
    try:
        old_task_id = cache.get(key)
        if old_task_id:
            from celery.result import AsyncResult
            AsyncResult(old_task_id).revoke()
    except Exception as e:
        logger.warning(f"Could not revoke previous cleanup task for user {user.id}: {e}")

    try:
        task = cleanup_unverified_user.apply_async(args=[str(user.id)], countdown=delay)
        cache.set(key, task.id, timeout=delay + 60)
        logger.info(f"Cleanup task scheduled for user {user.id} in {delay}s")
    except Exception as e:
        logger.warning(f"Could not schedule cleanup task for user {user.id}: {e}")


def latest_otp_expiry(user, otp_type='registration'):
    otp = OTPVerification.objects.filter(user=user, otp_type=otp_type).order_by('-created_at').first()
    return otp.expires_at if otp else None


def _fail(message, code, status_code, **extra):
    return Response({"success": False, "message": message, "code": code, **extra}, status=status_code)


class ResendOTPView(APIView):
    """
    POST /api/accounts/resend-otp/
    Body: {"user_id": "...", "email": "..."}

    Sends a fresh sign-up verification code (with a one-click verify link). Older
    unused codes stop working, and the unverified-account cleanup is pushed back.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user_id = request.data.get('user_id')
        email = (request.data.get('email') or '').strip().lower()
        if not user_id or not email:
            return _fail("We need your user ID and email to send a new code.", 'missing_fields',
                         status.HTTP_400_BAD_REQUEST)

        # Match both id and email so a guessed id alone can't trigger emails.
        try:
            user = CustomUser.objects.get(id=user_id, email__iexact=email)
        except (CustomUser.DoesNotExist, ValueError, ValidationError):
            return _fail("This sign-up has expired. Please register again.", 'signup_expired',
                         status.HTTP_404_NOT_FOUND)

        if user.email_verified:
            return _fail("Your email is already verified. You can log in.", 'already_verified',
                         status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        recent = OTPVerification.objects.filter(user=user, otp_type='registration')
        last = recent.order_by('-created_at').first()
        if last and (now - last.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            wait = RESEND_COOLDOWN_SECONDS - int((now - last.created_at).total_seconds())
            return _fail(f"Please wait {wait}s before requesting another code.", 'cooldown',
                         status.HTTP_429_TOO_MANY_REQUESTS, retry_after=wait)
        if recent.filter(created_at__gte=now - timedelta(hours=1)).count() >= MAX_RESENDS_PER_HOUR:
            return _fail("Too many codes requested. Please try again in an hour.", 'too_many',
                         status.HTTP_429_TOO_MANY_REQUESTS, retry_after=3600)

        # Only the newest code should work.
        recent.filter(verified_at__isnull=True, expires_at__gt=now).update(expires_at=now)

        otp_code = generate_otp(user, 'registration', expiration_minutes=otp_ttl_seconds() / 60)
        send_otp_to_email(user, otp_code, 'registration')
        schedule_unverified_cleanup(user)
        logger.info(f"Registration OTP re-sent to {user.email}")

        return Response({
            "success": True,
            "message": f"A new code has been sent to {user.email}.",
            "otp_expires_at": latest_otp_expiry(user),
            "resend_available_in": RESEND_COOLDOWN_SECONDS,
        }, status=status.HTTP_200_OK)
