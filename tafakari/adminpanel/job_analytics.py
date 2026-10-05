from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.models import JobApplication
from jobs.models import Job

from .dashboard import _daily_counts

TREND_DAYS = 30
TOP_LIMIT = 8


def _breakdown(field, choices):
    """Count per choice, in the model's declared order, including zero rows."""
    counts = dict(Job.objects.values_list(field).annotate(n=Count('pk')).values_list(field, 'n'))
    return [{"key": value, "label": label, "count": counts.get(value, 0)} for value, label in choices]


class AdminJobAnalyticsView(APIView):
    """
    GET /api/adminpanel/jobs/analytics/

    Job-posting analytics for the admin Job Analytics page, aggregated in the database.
    Budget uses budget_max, falling back to budget_min when only a minimum was given.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        trend_start = (timezone.localtime(now) - timedelta(days=TREND_DAYS - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0)

        totals = Job.objects.aggregate(
            total=Count('pk'),
            active=Count('pk', filter=Q(status=Job.Status.ACTIVE, admin_approved=True)),
            featured=Count('pk', filter=Q(is_featured=True)),
            assigned=Count('pk', filter=Q(is_assigned=True)),
            new_this_week=Count('pk', filter=Q(created_at__gte=week_ago)),
            views=Coalesce(Sum('views_count'), 0),
        )
        totals["applications"] = JobApplication.objects.count()

        approval = Job.objects.aggregate(
            approved=Count('pk', filter=Q(admin_approved=True)),
            pending=Count('pk', filter=Q(admin_approved=False) & ~Q(status=Job.Status.CANCELLED)),
            rejected=Count('pk', filter=Q(rejected_at__isnull=False, admin_approved=False)),
        )

        budget = (
            Job.objects.annotate(amount=Coalesce('budget_max', 'budget_min'))
            .filter(amount__isnull=False)
            .aggregate(total=Sum('amount'), average=Avg('amount'), jobs=Count('pk'))
        )

        categories = list(
            Job.objects.filter(category__isnull=False)
            .values('category_id', 'category__name')
            .annotate(count=Count('pk'))
            .order_by('-count', 'category__name')[:TOP_LIMIT]
        )

        locations = list(
            Job.objects.exclude(location_text='')
            .values('location_text')
            .annotate(count=Count('pk'))
            .order_by('-count', 'location_text')[:TOP_LIMIT]
        )

        top_jobs = list(
            Job.objects.annotate(apps=Count('jobapplication', distinct=True))
            .filter(apps__gt=0)
            .order_by('-apps', '-views_count')
            .values('id', 'title', 'status', 'admin_approved', 'views_count', 'apps', 'created_at')[:5]
        )

        return Response({
            "generated_at": now,
            "totals": totals,
            "approval": approval,
            "status": _breakdown('status', Job.Status.choices),
            "urgency": _breakdown('urgency_level', Job.UrgencyLevel.choices),
            "job_type": _breakdown('job_type', Job.JobType.choices),
            "payment_type": _breakdown('payment_type', Job.PaymentType.choices),
            "budget": {
                "total": float(budget['total'] or 0),
                "average": float(budget['average'] or 0),
                "jobs_with_budget": budget['jobs'],
            },
            "categories": [
                {"id": str(c['category_id']), "name": c['category__name'], "count": c['count']} for c in categories
            ],
            "uncategorized": Job.objects.filter(category__isnull=True).count(),
            "locations": [{"name": l['location_text'], "count": l['count']} for l in locations],
            "top_jobs": [
                {"id": str(j['id']), "title": j['title'], "status": j['status'], "admin_approved": j['admin_approved'],
                 "views": j['views_count'], "applications": j['apps'], "created_at": j['created_at']}
                for j in top_jobs
            ],
            "trend": _daily_counts(Job.objects.all(), 'created_at', trend_start, TREND_DAYS),
        }, status=status.HTTP_200_OK)
