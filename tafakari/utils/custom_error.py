from rest_framework.response import Response
from rest_framework import status

def error_response(message, errors=None, status_code=400):
    return Response(
        {
            "status": "error",
            "message": message,
            "stack": errors or {},
            "error": {
                "statusCode": status_code,
                "status": "error"
            }
        },
        status=status_code
    )


def _ok(message):
    """Standard success envelope for API responses."""
    return Response(
        {"success": True, "message": message, "status_code": status.HTTP_200_OK},
        status=status.HTTP_200_OK,
    )


def _err(message, status_code=status.HTTP_400_BAD_REQUEST):
    """Standard error envelope for API responses."""
    return Response(
        {"success": False, "message": message, "status_code": status_code},
        status=status_code,
    )


def _serializer_errors_to_message(errors):
    """
    Flatten DRF serializer error dicts into a single human-readable string.
    e.g. {'token': ['Invalid or expired reset link.']}  →  'Invalid or expired reset link.'
    """
    parts = []
    for field_errors in errors.values():
        if isinstance(field_errors, list):
            for err in field_errors:
                parts.append(str(err))
        else:
            parts.append(str(field_errors))
    return " ".join(parts) if parts else "Invalid request."
