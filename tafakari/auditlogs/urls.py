from django.urls import path

from .views import AuditLogListView, AuditLogFiltersView

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-log-list'),
    path('filters/', AuditLogFiltersView.as_view(), name='audit-log-filters'),
]
