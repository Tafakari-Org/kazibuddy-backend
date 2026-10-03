from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.models import JobApplication
from assignments.models import Assignment
from documents.models import UserDocument
from documents.views import MAX_DOCUMENTS_PER_USER
from jobs.models import Job
from .rejection import reason_fixes, reason_labels


class MyDashboardView(APIView):
    """
    GET /api/accounts/me/dashboard/

    The signed-in user's own numbers for /dashboard: account readiness, their
    applications (as a worker), their posted jobs (as an employer) and how many
    jobs are open on the platform.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        week_ago = timezone.now() - timedelta(days=7)

        # ── Account readiness ──
        documents_count = UserDocument.objects.filter(user_id=user).count()
        checklist = [
            {"key": "email", "label": "Verify your email", "done": bool(user.email_verified)},
            {"key": "photo", "label": "Add a profile photo", "done": bool(user.profile_photo_url)},
            {"key": "phone", "label": "Add your phone number", "done": bool(user.phone_number)},
            {"key": "documents", "label": "Upload your certificates", "done": documents_count > 0},
        ]
        done = sum(1 for item in checklist if item["done"])

        # ── As a worker ──
        my_apps = JobApplication.objects.filter(worker=user)
        applications = my_apps.aggregate(
            total=Count('pk'),
            pending=Count('pk', filter=Q(status='pending')),
            shortlisted=Count('pk', filter=Q(status='shortlisted')),
            accepted=Count('pk', filter=Q(status='accepted')),
            rejected=Count('pk', filter=Q(status='rejected')),
        )
        recent_applications = [
            {
                "id": str(a.id),
                "job_id": str(a.job_id),
                "job_title": a.job.title,
                "status": a.status,
                "applied_at": a.applied_at,
                "responded_at": a.responded_at,
            }
            for a in my_apps.select_related('job')
            .annotate(last_change=Coalesce('responded_at', 'applied_at'))
            .order_by('-last_change')[:5]
        ]

        # ── As an employer ──
        my_jobs = Job.objects.filter(employer=user)
        jobs = my_jobs.aggregate(
            total=Count('pk'),
            pending_approval=Count('pk', filter=Q(admin_approved=False) & ~Q(status=Job.Status.CANCELLED)),
            live=Count('pk', filter=Q(admin_approved=True, is_assigned=False) & ~Q(status=Job.Status.CANCELLED)),
            assigned=Count('pk', filter=Q(is_assigned=True)),
        )
        applicants = JobApplication.objects.filter(job__employer=user).aggregate(
            total=Count('pk'),
            pending=Count('pk', filter=Q(status='pending')),
        )
        recent_jobs = [
            {
                "id": str(j.id),
                "title": j.title,
                "status": j.status,
                "admin_approved": j.admin_approved,
                "is_assigned": j.is_assigned,
                "applicants": j.applicants,
                "created_at": j.created_at,
            }
            for j in my_jobs.annotate(applicants=Count('jobapplication')).order_by('-created_at')[:5]
        ]

        # ── Marketplace ──
        open_jobs = Job.objects.filter(admin_approved=True, is_assigned=False).exclude(status=Job.Status.CANCELLED)

        return Response({
            "account": {
                "full_name": user.full_name,
                "is_approved": bool(user.is_verified),
                "rejection": {
                    "rejected_at": user.rejected_at,
                    "reasons": reason_labels(user.rejection_reasons or []),
                    "fixes": reason_fixes(user.rejection_reasons or []),
                    "note": user.rejection_note,
                } if user.rejected_at and not user.is_verified else None,
                "email_verified": bool(user.email_verified),
                "documents_count": documents_count,
                "documents_max": MAX_DOCUMENTS_PER_USER,
                "checklist": checklist,
                "completion": round(done * 100 / len(checklist)),
            },
            "applications": applications,
            "jobs_won": Assignment.objects.filter(worker=user).count(),
            "recent_applications": recent_applications,
            "my_jobs": jobs,
            "applicants": applicants,
            "recent_jobs": recent_jobs,
            "marketplace": {
                "open_jobs": open_jobs.count(),
                "new_this_week": open_jobs.filter(created_at__gte=week_ago).count(),
            },
        }, status=status.HTTP_200_OK)


class RequestReviewView(APIView):
    """
    POST /api/accounts/me/request-review/

    After fixing what an admin flagged, a rejected user puts their account back
    in the approval queue. The earlier reasons are cleared.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({"message": "Your account is already approved."}, status=status.HTTP_200_OK)
        if not user.rejected_at:
            return Response({"message": "Your account is already waiting for review."}, status=status.HTTP_200_OK)

        user.rejected_at = None
        user.rejection_reasons = []
        user.rejection_note = ''
        user.save(update_fields=['rejected_at', 'rejection_reasons', 'rejection_note', 'updated_at'])
        return Response({"message": "Thanks! Your account is back in the review queue."}, status=status.HTTP_200_OK)
