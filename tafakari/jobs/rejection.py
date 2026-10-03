"""Reasons an admin can give when declining a job listing, shown to the poster."""

JOB_REJECTION_REASONS = {
    "unclear_description": "The job description is unclear or too short",
    "missing_details": "Key details are missing (location, dates or budget)",
    "budget_unrealistic": "The budget doesn't match the work described",
    "contact_or_payment_info": "The listing includes phone numbers, links or payment requests",
    "inappropriate_media": "Photos or attachments are unrelated or inappropriate",
    "not_allowed": "This kind of work isn't allowed on KaziBuddy",
    "unsafe": "The job may be unsafe or illegal",
    "duplicate": "This duplicates another job you posted",
    "other": "Other (see the note from our team)",
}

JOB_REJECTION_FIXES = {
    "unclear_description": "Explain the tasks step by step, what the worker should bring, and what “done” looks like.",
    "missing_details": "Add the exact area or estate, start and end dates, and a budget in KES.",
    "budget_unrealistic": "Set a fair budget for the time and skill involved, or give a range.",
    "contact_or_payment_info": "Remove phone numbers, links and payment requests — workers contact you through KaziBuddy.",
    "inappropriate_media": "Only attach photos or documents that show the work to be done.",
    "not_allowed": "Check our Terms of Use for the kinds of work KaziBuddy supports.",
    "unsafe": "Make sure the work is legal and can be done safely, with any protective equipment provided.",
    "duplicate": "Keep one listing per job; edit the existing one instead of posting again.",
}


def job_reason_labels(codes):
    return [JOB_REJECTION_REASONS[c] for c in codes if c in JOB_REJECTION_REASONS]


def job_reason_fixes(codes):
    return [JOB_REJECTION_FIXES[c] for c in codes if c in JOB_REJECTION_FIXES]
