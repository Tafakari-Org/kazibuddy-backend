import logging
import uuid

from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.models import JobApplication
from auditlogs.models import AuditLog
from auditlogs.service import log_action
from jobs.deletion import JOB_DELETION_REASONS, job_deletion_labels
from jobs.models import Job
from utils.file_upload import FileUploadService
from utils.views import build_job_deleted_email, send_job_deleted_email

logger = logging.getLogger(__name__)

MAX_BULK_DELETE = 50


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _remove_files(urls, job_id):
    """Best-effort storage cleanup after the DB delete; orphaned files beat a half-deleted job."""
    file_service = FileUploadService()
    for url in urls:
        try:
            if not file_service.remove(url):
                logger.warning(f"File not found on storage (job={job_id}): {url}")
        except Exception as e:
            logger.error(f"Failed to delete file (job={job_id}, url={url}): {e}", exc_info=True)


class JobDeletionReasonsView(APIView):
    """GET /api/adminpanel/jobs/deletion-reasons/ — options for the delete-jobs dialog."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response({"reasons": [{"value": k, "label": v} for k, v in JOB_DELETION_REASONS.items()]})


class BulkDeleteJobsView(APIView):
    """
    POST /api/adminpanel/jobs/bulk-delete/
    Body: {"job_ids": [...], "reasons": ["duplicate", ...], "note": "optional message to the poster"}

    Permanently deletes each job (cascading to its applications and assignment), emails
    the poster the reasons, and records a job.deleted entry in the audit log.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        job_ids = request.data.get("job_ids")
        reasons = request.data.get("reasons") or []
        note = (request.data.get("note") or "").strip()

        if not isinstance(job_ids, list) or not job_ids:
            return Response({"error": "job_ids must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)
        if len(job_ids) > MAX_BULK_DELETE:
            return Response({"error": f"You can delete at most {MAX_BULK_DELETE} jobs at once."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(reasons, list) or not reasons:
            return Response({"error": "Choose at least one reason."}, status=status.HTTP_400_BAD_REQUEST)
        unknown = [r for r in reasons if r not in JOB_DELETION_REASONS]
        if unknown:
            return Response({"error": f"Unknown reason(s): {', '.join(map(str, unknown))}"}, status=status.HTTP_400_BAD_REQUEST)
        if "other" in reasons and not note:
            return Response({"error": "Add a note explaining the 'Other' reason."}, status=status.HTTP_400_BAD_REQUEST)
        if len(note) > 1000:
            return Response({"error": "Keep the note under 1000 characters."}, status=status.HTTP_400_BAD_REQUEST)

        reasons = list(dict.fromkeys(reasons))
        labels = job_deletion_labels(reasons)
        unique_ids = list(dict.fromkeys(str(i) for i in job_ids))
        jobs = {
            str(j.id): j for j in Job.objects.filter(id__in=[i for i in unique_ids if _is_uuid(i)])
            .select_related('employer', 'category').prefetch_related('images', 'attachments')
        }

        deleted, skipped = [], []
        for jid in unique_ids:
            job = jobs.get(jid)
            if job is None:
                skipped.append({"id": jid, "title": None, "reason": "Job not found"})
                continue
            try:
                # Everything the email and audit entry need, captured while the job still exists.
                poster_email = getattr(job.employer, "email", None)
                subject, html = build_job_deleted_email(job, labels, note) if poster_email else (None, None)
                applications = JobApplication.objects.filter(job=job).count()
                file_urls = [i.image_url for i in job.images.all() if i.image_url] + \
                            [a.file_url for a in job.attachments.all() if a.file_url]
                details = {"employer": poster_email, "status": job.status, "applications": applications,
                           "reasons": labels, "note": note, "bulk": len(unique_ids) > 1}

                with transaction.atomic():
                    job.delete()
            except Exception as e:
                logger.error(f"Bulk delete failed for job {jid}: {e}", exc_info=True)
                skipped.append({"id": jid, "title": job.title, "reason": "Unexpected error"})
                continue

            _remove_files(file_urls, jid)
            if poster_email:
                send_job_deleted_email(poster_email, subject, html)
            log_action(request, AuditLog.Action.JOB_DELETED, AuditLog.TargetType.JOB, jid, job.title, details)
            deleted.append({"id": jid, "title": job.title})

        noun = "job" if len(deleted) == 1 else "jobs"
        return Response({
            "message": f"Deleted {len(deleted)} {noun}; posters have been emailed the reasons."
                       if deleted else "No jobs were deleted.",
            "deleted": deleted,
            "skipped": skipped,
        }, status=status.HTTP_200_OK)
