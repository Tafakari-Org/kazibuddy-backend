from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser
from applications.models import JobApplication
from assignments.models import Assignment
from auditlogs.models import AuditLog
from auditlogs.serializers import AuditLogSerializer
from jobs.models import Job, JobCategory

TREND_DAYS = 14
ADMIN_TYPES = ('admin', 'super_admin')


def _daily_counts(queryset, field, since, days):
    """Counts per calendar day for the last `days` days, zero-filled, oldest first."""
    rows = (
        queryset.filter(**{f"{field}__gte": since})
        .annotate(day=TruncDate(field))
        .values('day')
        .annotate(count=Count('pk'))
    )
    by_day = {r['day']: r['count'] for r in rows}
    start = since.date()
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": by_day.get(start + timedelta(days=i), 0)}
        for i in range(days)
    ]


class AdminDashboardStatsView(APIView):
    """
    GET /api/adminpanel/dashboard/stats/

    Everything the admin dashboard shows, aggregated in the database in one call.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        # Day buckets use the server's local timezone (TruncDate), so start there too.
        trend_start = (timezone.localtime(now) - timedelta(days=TREND_DAYS - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0)

        users = CustomUser.objects.aggregate(
            total=Count('pk'),
            admins=Count('pk', filter=Q(user_type__in=ADMIN_TYPES)),
            approved=Count('pk', filter=Q(is_verified=True)),
            pending_approval=Count('pk', filter=Q(is_verified=False, email_verified=True)),
            unverified_email=Count('pk', filter=Q(is_verified=False, email_verified=False)),
            new_this_week=Count('pk', filter=Q(created_at__gte=week_ago)),
        )

        jobs = Job.objects.aggregate(
            total=Count('pk'),
            pending_approval=Count('pk', filter=Q(admin_approved=False) & ~Q(status=Job.Status.CANCELLED)),
            active=Count('pk', filter=Q(status=Job.Status.ACTIVE, admin_approved=True)),
            filled=Count('pk', filter=Q(status__in=[Job.Status.FILLED, Job.Status.COMPLETED])),
            featured=Count('pk', filter=Q(is_featured=True)),
            new_this_week=Count('pk', filter=Q(created_at__gte=week_ago)),
        )

        applications = JobApplication.objects.aggregate(
            total=Count('pk'),
            pending=Count('pk', filter=Q(status='pending')),
            accepted=Count('pk', filter=Q(status='accepted')),
            rejected=Count('pk', filter=Q(status='rejected')),
            new_this_week=Count('pk', filter=Q(applied_at__gte=week_ago)),
        )

        assignments = Assignment.objects.aggregate(
            total=Count('pk'),
            new_this_week=Count('pk', filter=Q(created_at__gte=week_ago)),
        )

        categories = list(
            JobCategory.objects.annotate(jobs_count=Count('jobs'))
            .order_by('-jobs_count', 'name')
            .values('id', 'name', 'jobs_count')[:8]
        )

        recent_signups = list(
            CustomUser.objects.order_by('-created_at')
            .values('id', 'full_name', 'email', 'user_type', 'is_verified', 'email_verified', 'created_at')[:6]
        )

        recent_activity = AuditLogSerializer(AuditLog.objects.order_by('-created_at')[:8], many=True).data

        return Response({
            "generated_at": now,
            "users": users,
            "jobs": jobs,
            "applications": applications,
            "assignments": assignments,
            "categories": [{**c, "id": str(c['id'])} for c in categories],
            "trends": {
                "signups": _daily_counts(CustomUser.objects.all(), 'created_at', trend_start, TREND_DAYS),
                "jobs_posted": _daily_counts(Job.objects.all(), 'created_at', trend_start, TREND_DAYS),
                "applications": _daily_counts(JobApplication.objects.all(), 'applied_at', trend_start, TREND_DAYS),
            },
            "recent_signups": [{**u, "id": str(u['id'])} for u in recent_signups],
            "recent_activity": recent_activity,
        }, status=status.HTTP_200_OK)
