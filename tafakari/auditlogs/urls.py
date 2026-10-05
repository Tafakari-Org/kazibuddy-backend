from django.urls import path

from .views import AuditLogBulkDeleteView, AuditLogListView, AuditLogFiltersView

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-log-list'),
    path('bulk-delete/', AuditLogBulkDeleteView.as_view(), name='audit-log-bulk-delete'),
    path('filters/', AuditLogFiltersView.as_view(), name='audit-log-filters'),
]
