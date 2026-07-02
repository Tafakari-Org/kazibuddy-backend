from rest_framework import serializers
from .models import UserDocument


class UserDocumentSerializer(serializers.ModelSerializer):
    document_type = serializers.CharField(source='document_type.name', read_only=True)

    class Meta:
        model = UserDocument
        fields = [
            'id', 'document_type', 'file_name', 'file_url', 'file_type',
            'file_size', 'verification_status', 'uploaded_at',
        ]
        read_only_fields = fields
