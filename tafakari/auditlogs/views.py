import uuid
from collections import Counter
from datetime import datetime, time

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.custom_pagination import CustomPagination
from .models import AuditLog
from .serializers import AuditLogSerializer
from .service import log_action

# Entries must be at least this old before they can be deleted.
DELETE_MIN_AGE_MONTHS = 2
MAX_BULK_DELETE = 500


def deletable_before():
    """Entries created before this moment are old enough to delete."""
    return timezone.now() - relativedelta(months=DELETE_MIN_AGE_MONTHS)


def _can_delete(user):
    return bool(user and user.is_authenticated and user.user_type == 'super_admin')


class IsSuperAdmin(permissions.BasePermission):
    message = "Only super admins can delete audit log entries."

    def has_permission(self, request, view):
        return _can_delete(request.user)


def _parse_date(value, end_of_day=False):
    try:
        d = datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(datetime.combine(d, time.max if end_of_day else time.min))


class AuditLogListView(APIView):
    """
    GET /api/adminpanel/audit-logs/

    Query params (all optional):
      search      matches admin name/email, target label/id
      action      exact action, e.g. user.approved (comma-separated for several)
      target_type user | admin | job | category | application | assignment
      actor       admin user id
      date_from   YYYY-MM-DD (inclusive)
      date_to     YYYY-MM-DD (inclusive)
      ordering    created_at | -created_at (default)
      page, page_size
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        params = request.query_params
        logs = AuditLog.objects.all()

        search = params.get('search', '').strip()
        if search:
            logs = logs.filter(
                Q(actor_name__icontains=search) | Q(actor_email__icontains=search)
                | Q(target_label__icontains=search) | Q(target_id__icontains=search)
            )

        actions = [a for a in params.get('action', '').split(',') if a]
        if actions:
            logs = logs.filter(action__in=actions)

        target_type = params.get('target_type')
        if target_type:
            logs = logs.filter(target_type=target_type)

        actor = params.get('actor')
        if actor:
            logs = logs.filter(actor_id=actor)

        date_from = _parse_date(params.get('date_from'))
        if date_from:
            logs = logs.filter(created_at__gte=date_from)
        date_to = _parse_date(params.get('date_to'), end_of_day=True)
        if date_to:
            logs = logs.filter(created_at__lte=date_to)

        ordering = params.get('ordering')
        logs = logs.order_by('created_at' if ordering == 'created_at' else '-created_at')

        paginator = CustomPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(logs, request)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)


class AuditLogFiltersView(APIView):
    """GET /api/adminpanel/audit-logs/filters/ — options for the filter dropdowns."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        actors = (
            AuditLog.objects.exclude(actor__isnull=True)
            .values('actor', 'actor_name', 'actor_email')
            .order_by('actor_name')
            .distinct()
        )
        seen, actor_options = set(), []
        for a in actors:
            if a['actor'] in seen:
                continue
            seen.add(a['actor'])
            actor_options.append({'id': str(a['actor']), 'name': a['actor_name'], 'email': a['actor_email']})

        return Response({
            'actions': [{'value': v, 'label': l} for v, l in AuditLog.Action.choices],
            'target_types': [{'value': v, 'label': l} for v, l in AuditLog.TargetType.choices],
            'actors': actor_options,
            'deletion': {
                'allowed': _can_delete(request.user),
                'min_age_months': DELETE_MIN_AGE_MONTHS,
                'deletable_before': deletable_before(),
                'protected_actions': [AuditLog.Action.AUDIT_LOGS_DELETED],
            },
        }, status=status.HTTP_200_OK)


class AuditLogBulkDeleteView(APIView):
    """
    POST /api/adminpanel/audit-logs/bulk-delete/
    Body: {"ids": [...]}

    Super admins only. Deletes entries that are at least DELETE_MIN_AGE_MONTHS old; newer
    ones are skipped. Records of earlier deletions are never deleted, and every deletion
    leaves a new audit.deleted entry saying who removed how many entries, and of what.
    """
    permission_classes = [permissions.IsAdminUser, IsSuperAdmin]

    def post(self, request):
        ids = request.data.get('ids')
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)
        if len(ids) > MAX_BULK_DELETE:
            return Response({'error': f'You can delete at most {MAX_BULK_DELETE} entries at once.'},
                            status=status.HTTP_400_BAD_REQUEST)

        unique_ids = list(dict.fromkeys(str(i) for i in ids))
        valid_ids = []
        for i in unique_ids:
            try:
                valid_ids.append(str(uuid.UUID(i)))
            except ValueError:
                pass
        found = {str(log.id): log for log in AuditLog.objects.filter(id__in=valid_ids)}
        cutoff = deletable_before()

        to_delete, skipped = [], []
        for i in unique_ids:
            log = found.get(i)
            if log is None:
                skipped.append({'id': i, 'reason': 'Entry not found'})
            elif log.action == AuditLog.Action.AUDIT_LOGS_DELETED:
                skipped.append({'id': i, 'reason': 'Records of deleted entries are kept permanently'})
            elif log.created_at >= cutoff:
                skipped.append({'id': i, 'reason': f'Less than {DELETE_MIN_AGE_MONTHS} months old'})
            else:
                to_delete.append(log)

        if to_delete:
            dates = sorted(log.created_at for log in to_delete)
            AuditLog.objects.filter(id__in=[log.id for log in to_delete]).delete()
            n = len(to_delete)
            log_action(request, AuditLog.Action.AUDIT_LOGS_DELETED, AuditLog.TargetType.AUDIT_LOG, '',
                       f"{n} audit log entr{'y' if n == 1 else 'ies'}",
                       {'count': n, 'oldest': dates[0].isoformat(), 'newest': dates[-1].isoformat(),
                        'actions': dict(Counter(log.action for log in to_delete))})

        n = len(to_delete)
        return Response({
            'message': f"Deleted {n} audit log entr{'y' if n == 1 else 'ies'}." if n else 'No entries were deleted.',
            'deleted': n,
            'skipped': skipped,
        }, status=status.HTTP_200_OK)
