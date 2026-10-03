from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    target_type_label = serializers.CharField(source='get_target_type_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor', 'actor_name', 'actor_email', 'actor_role',
            'action', 'action_label', 'target_type', 'target_type_label',
            'target_id', 'target_label', 'details', 'ip_address', 'created_at',
        ]
        read_only_fields = fields
