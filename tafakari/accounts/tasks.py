# tasks.py
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def cleanup_unverified_user(self, user_id: str):
    """
    Triggered automatically via countdown when an OTP is issued.
    Fires after OTP_TTL + 30s buffer.

    Deletes the user if they never verified their email, then sends them a
    courtesy notification email so they know what happened and can re-register.

    Idempotent: safe to run multiple times — verified users are skipped.
    """
    from .models import CustomUser  # local import avoids circular deps at startup
    from utils.views import send_account_deleted_email  # local import — same reason

    try:
        user = CustomUser.objects.get(id=user_id, email_verified=False)
    except CustomUser.DoesNotExist:
        # User verified in time, or was already cleaned up — nothing to do.
        logger.info(f"[OTP cleanup] User {user_id} already verified or removed. Skipping.")
        return

    # Capture identity details BEFORE deletion so we can email after the record is gone.
    user_email = user.email
    user_full_name = getattr(user, 'full_name', None) or user.email

    try:
        user.delete()
        logger.info(f"[OTP cleanup] Deleted unverified user {user_id} ({user_email}) after OTP expiry.")
    except Exception as exc:
        logger.error(f"[OTP cleanup] Failed to delete user {user_id}: {exc}")
        # Retry with exponential backoff: 60s → 120s → 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    # Send a courtesy email AFTER successful deletion.
    # Errors here are logged but never re-raised — the cleanup already succeeded.
    try:
        send_account_deleted_email(full_name=user_full_name, email=user_email)
        logger.info(f"[OTP cleanup] Account-deleted notification dispatched to {user_email}.")
    except Exception as email_exc:
        logger.error(
            f"[OTP cleanup] Could not send account-deleted email to {user_email}: {email_exc}"
        )