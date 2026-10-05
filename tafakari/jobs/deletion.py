"""Reasons an admin can give when deleting a job listing, shown to the poster."""

JOB_DELETION_REASONS = {
    "completed_or_filled": "The job has been filled or completed and the listing is no longer needed",
    "expired": "The listing is out of date and no longer active",
    "duplicate": "This duplicates another job you posted",
    "poster_request": "You asked us to remove it",
    "policy_violation": "The listing breaks the KaziBuddy Terms of Use",
    "fraud_or_scam": "The listing looked fraudulent or misleading",
    "unsafe": "The job may be unsafe or illegal",
    "other": "Other (see the note from our team)",
}


def job_deletion_labels(codes):
    return [JOB_DELETION_REASONS[c] for c in codes if c in JOB_DELETION_REASONS]
