import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_action(request, action, target_type, target_id='', target_label='', details=None, staff_only=False):
    """
    Record an admin action. Never raises — a logging failure must not break
    the action being logged.

    staff_only: for endpoints shared with regular users (e.g. job edit), only
    record the call when the actor is an admin.
    """
    try:
        user = getattr(request, 'user', None)
        actor = user if user is not None and user.is_authenticated else None
        if staff_only and not (actor and actor.is_staff):
            return None

        return AuditLog.objects.create(
            actor=actor,
            actor_name=getattr(actor, 'full_name', '') or '',
            actor_email=getattr(actor, 'email', '') or '',
            actor_role=getattr(actor, 'user_type', '') or '',
            action=action,
            target_type=target_type,
            target_id=str(target_id or ''),
            target_label=str(target_label or '')[:255],
            details=details or {},
            ip_address=_client_ip(request),
        )
    except Exception as e:
        logger.error(f"Failed to write audit log ({action}): {e}", exc_info=True)
        return None
