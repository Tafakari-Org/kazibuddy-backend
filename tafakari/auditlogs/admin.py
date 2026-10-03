from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor_email', 'action', 'target_type', 'target_label')
    list_filter = ('action', 'target_type')
    search_fields = ('actor_email', 'actor_name', 'target_label', 'target_id')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
