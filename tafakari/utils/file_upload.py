from abc import ABC
import os
import uuid
import mimetypes
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class FileUploadManagerService(ABC):
    """Abstract base class for file upload management services."""
    def __init__(self):
        """Initialize the file upload manager."""
        pass

class FileUploadService(FileUploadManagerService):
    """Service for handling file upload/delete operations on local disk."""

    # ── Allowed types & size limits ────────────────────────────────────────────────
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt'}
    MAX_IMAGE_SIZE = 5 * 1024 * 1024        # 5 MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024    # 10 MB

    def upload(self, uploaded_file, subfolder='images'):
        """
        Save an uploaded file to MEDIA_ROOT/<subfolder>/ and return its public URL.

        Args:
            uploaded_file: The file object from request.FILES
            subfolder: 'images' or 'documents'
            
        Returns:
            str: Public URL path
            
        Raises:
            ValueError: If validation fails
        """
        _, ext = os.path.splitext(uploaded_file.name.lower())

        # Validate by subfolder
        if subfolder == 'images':
            if ext not in self.ALLOWED_IMAGE_EXTENSIONS:
                raise ValueError(
                    f"Invalid image type '{ext}'. "
                    f"Allowed: {', '.join(self.ALLOWED_IMAGE_EXTENSIONS)}"
                )
            if uploaded_file.size > self.MAX_IMAGE_SIZE:
                raise ValueError("Image exceeds the 5 MB size limit.")
        elif subfolder == 'documents':
            if ext not in self.ALLOWED_DOCUMENT_EXTENSIONS:
                raise ValueError(
                    f"Invalid document type '{ext}'. "
                    f"Allowed: {', '.join(self.ALLOWED_DOCUMENT_EXTENSIONS)}"
                )
            if uploaded_file.size > self.MAX_DOCUMENT_SIZE:
                raise ValueError("Document exceeds the 10 MB size limit.")

        # Generate a unique filename to avoid collisions
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_dir = os.path.join(settings.MEDIA_ROOT, subfolder)
        os.makedirs(save_dir, exist_ok=True)

        dest_path = os.path.join(save_dir, unique_name)
        try:
            with open(dest_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Return the URL Django's media-serving will expose
            media_url = f"{settings.MEDIA_URL.rstrip('/')}/{subfolder}/{unique_name}"
            logger.info(f"File saved: {dest_path} → {media_url}")
            return media_url
            
        except Exception as e:
            logger.error(f"Failed to save file {uploaded_file.name}: {str(e)}")
            raise Exception(f"Failed to upload file: {str(e)}")

    def remove(self, file_url):
        """
        Delete a previously uploaded file from disk given its media URL.

        Args:
            file_url: The URL stored in the DB
            
        Returns:
            bool: True if deleted, False otherwise
        """
        if not file_url:
            return False

        # Strip MEDIA_URL prefix to get the path relative to MEDIA_ROOT
        media_url_prefix = settings.MEDIA_URL.rstrip('/')
        relative_path = file_url.lstrip('/')
        
        # Check if it's a media URL
        clean_prefix = media_url_prefix.lstrip('/')
        if relative_path.startswith(clean_prefix):
            relative_path = relative_path[len(clean_prefix):].lstrip('/')

        abs_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
                logger.info(f"File deleted: {abs_path}")
                return True
            except OSError as e:
                logger.warning(f"Could not delete file {abs_path}: {e}")
                return False

        logger.warning(f"File not found on disk, skipping delete: {abs_path}")
        return False
