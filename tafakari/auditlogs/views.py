from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.custom_pagination import CustomPagination
from .models import AuditLog
from .serializers import AuditLogSerializer


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
        }, status=status.HTTP_200_OK)
