# assignments/tasks.py
import logging
from celery import shared_task

logger = logging.getLogger('tafakari.assignments')


@shared_task(bind=True, max_retries=3)
def notify_rejected_applicants(self, job_id: str, assigned_worker_id: str):
    """
    Fires automatically after an assignment is created.

    Fetches all JobApplication rows for ``job_id`` whose status is 'rejected'
    and whose worker is NOT the assigned worker, then sends each one a
    personalised rejection email via the existing application_notification
    email template.

    Design notes:
    - Dispatched AFTER transaction.atomic() commits, so the 'rejected' status
      rows are guaranteed to be visible in the DB when this task runs.
    - Per-email failures are logged and skipped; one bad address never aborts
      the rest of the batch.
    - Idempotent: if the task is retried, only rows still marked 'rejected'
      are processed — no duplicate risk for rows whose status has changed.
    - Retry with exponential backoff on unexpected DB / infrastructure errors.
    """
    from applications.models import JobApplication  # local import — avoids circular deps at startup
    from utils.views import send_otp_to_email       # local import — same reason

    try:
        rejected_apps = (
            JobApplication.objects
            .filter(job_id=job_id, status='rejected')
            .exclude(worker_id=assigned_worker_id)
            .select_related('worker__user', 'job')
        )

        if not rejected_apps.exists():
            logger.info(
                f"[notify_rejected] No rejected applicants for job {job_id}. Skipping."
            )
            return

        sent_count = 0
        failed_count = 0

        for application in rejected_apps:
            worker_id = str(application.worker_id)
            try:
                send_otp_to_email(
                    user=application.worker.user,
                    otp_type='application_notification',
                    action_type='application_rejected',
                    job_title=application.job.title,
                    application_id=str(application.id),
                )
                sent_count += 1
                logger.info(
                    f"[notify_rejected] Rejection email sent → worker {worker_id} "
                    f"(job {job_id})."
                )
            except Exception as email_exc:
                failed_count += 1
                logger.error(
                    f"[notify_rejected] Failed to email worker {worker_id} "
                    f"for job {job_id}: {email_exc}"
                )

        logger.info(
            f"[notify_rejected] Done for job {job_id}: "
            f"{sent_count} sent, {failed_count} failed."
        )

    except Exception as exc:
        logger.error(f"[notify_rejected] Task-level error for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
