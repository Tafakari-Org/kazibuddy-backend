import mimetypes
import logging
import os

from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.file_upload import FileUploadService
from .models import UserDocument, DocumentType
from .serializers import UserDocumentSerializer

logger = logging.getLogger(__name__)

# Total storage cap per user across all their documents (signup + profile).
# Sized to fit the 10 x 5MB allowed at registration.
MAX_PROFILE_STORAGE_BYTES = 50 * 1024 * 1024  # 50 MB
# Per-file cap, matching registration (stricter than FileUploadService's 10MB).
MAX_PROFILE_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB


def _storage_used(user):
    return UserDocument.objects.filter(user_id=user).aggregate(total=Sum('file_size'))['total'] or 0


class MyDocumentsView(APIView):
    """List the requesting user's own attachments, or upload a new one."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        documents = UserDocument.objects.filter(user_id=request.user).order_by('-uploaded_at')
        used = _storage_used(request.user)
        return Response({
            "message": "Documents retrieved successfully",
            "data": UserDocumentSerializer(documents, many=True).data,
            "storage": {
                "used_bytes": used,
                "limit_bytes": MAX_PROFILE_STORAGE_BYTES,
                "remaining_bytes": max(0, MAX_PROFILE_STORAGE_BYTES - used),
            },
        }, status=status.HTTP_200_OK)

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > MAX_PROFILE_DOCUMENT_SIZE:
            return Response(
                {"error": f'"{uploaded_file.name}" exceeds the 5 MB limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        used = _storage_used(request.user)
        if used + uploaded_file.size > MAX_PROFILE_STORAGE_BYTES:
            remaining_mb = max(0, MAX_PROFILE_STORAGE_BYTES - used) / (1024 * 1024)
            limit_mb = MAX_PROFILE_STORAGE_BYTES / (1024 * 1024)
            return Response(
                {"error": f"Not enough space — {remaining_mb:.1f} MB remaining of your {limit_mb:.0f} MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_service = FileUploadService()
        try:
            file_url = file_service.upload(uploaded_file, subfolder='documents')
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        document_type, _ = DocumentType.objects.get_or_create(
            name="Profile Attachment",
            defaults={
                "description": "Supporting document uploaded from the user's profile",
                "applicable_to": "both",
                "is_required": False,
            },
        )

        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
        document = UserDocument.objects.create(
            user_id=request.user,
            document_type=document_type,
            file_name=uploaded_file.name,
            file_url=file_url,
            file_type=mime_type,
            file_size=uploaded_file.size,
        )

        return Response({
            "message": "Document uploaded successfully",
            "data": UserDocumentSerializer(document).data,
        }, status=status.HTTP_201_CREATED)


class MyDocumentDetailView(APIView):
    """Delete one of the requesting user's own attachments."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, document_id):
        document = get_object_or_404(UserDocument, pk=document_id, user_id=request.user)

        try:
            FileUploadService().remove(document.file_url)
        except Exception as e:
            logger.warning(f"Could not remove document file from disk ({document.file_url}): {e}")

        document.delete()
        return Response({"message": "Document deleted successfully"}, status=status.HTTP_200_OK)


class MyDocumentDownloadView(APIView):
    """Stream one of the requesting user's own attachments as a download."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(UserDocument, pk=document_id, user_id=request.user)

        file_path = FileUploadService().path_for(document.file_url)
        if not file_path or not os.path.isfile(file_path):
            raise Http404("File not found")

        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=document.file_name,
            content_type=document.file_type or 'application/octet-stream',
        )
