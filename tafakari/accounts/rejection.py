"""Reasons an admin can give when declining a registration, shown to the user."""

REJECTION_REASONS = {
    "documents_missing": "No supporting documents were uploaded",
    "documents_unclear": "Your documents were unclear or hard to read",
    "documents_unverifiable": "We could not verify your documents",
    "name_mismatch": "The name on your documents does not match your account",
    "profile_incomplete": "Your profile information is incomplete or inconsistent",
    "duplicate_account": "This looks like a duplicate of another account",
    "other": "Other (see the note from our team)",
}

# What we suggest the user does about each reason.
REJECTION_FIXES = {
    "documents_missing": "Upload at least one certificate, transcript or ID from your profile.",
    "documents_unclear": "Upload clear, well-lit scans or photos (PDF or image, up to 5 MB each).",
    "documents_unverifiable": "Upload official documents that show the issuer clearly.",
    "name_mismatch": "Make sure the name on your profile matches your documents.",
    "profile_incomplete": "Complete your name, phone number and profile photo.",
    "duplicate_account": "Sign in with your original account, or contact support if this is a mistake.",
}


def reason_labels(codes):
    return [REJECTION_REASONS[c] for c in codes if c in REJECTION_REASONS]


def reason_fixes(codes):
    return [REJECTION_FIXES[c] for c in codes if c in REJECTION_FIXES]
