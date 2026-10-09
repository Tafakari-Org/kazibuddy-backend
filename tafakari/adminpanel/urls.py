from django.urls import path
from .dashboard import AdminDashboardStatsView
from .footer import FooterView
from .job_analytics import AdminJobAnalyticsView
from .job_deletion import BulkDeleteJobsView, JobDeletionReasonsView
from .views import (
    ApproveUserView,
    BulkApproveUsersView,
    RejectUserView,
    RejectJobView,
    JobRejectionReasonsView,
    RejectionReasonsView,
    DeactivateUserView,
    AllJobsListView,
    ApproveJobView,
    PendingJobsListView,
    ListPendingUsersView,
    PendingUserDetailView,
    AdminUserDocumentDownloadView,
    UpdateJobApplicationStatusView,
    DeleteAllUsersView,
    GetAllUsersView,
    DeleteUserByEmailView,
    # Admin / SuperAdmin management
    CreateAdminView,
    CreateSuperAdminView,
    AdminListView,
    AdminDetailView,
    # Invite-based flows
    SetupAdminAccountView,
    ResendAdminInviteView,

    ChangeUserRoleView
)

urlpatterns = [
    # existing routes
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('users/rejection-reasons/', RejectionReasonsView.as_view(), name='rejection_reasons'),
    path('users/<uuid:user_id>/reject/', RejectUserView.as_view(), name='reject_user'),
    path('users/bulk-approve/', BulkApproveUsersView.as_view(), name='bulk_approve_users'),
    path('users/<uuid:user_id>/approve/', ApproveUserView.as_view(), name='approve_user'),
    path('users/<uuid:user_id>/deactivate/', DeactivateUserView.as_view(), name='deactivate_user'),
    path('admin/jobs/', AllJobsListView.as_view(), name='all-jobs-list'),
    path('jobs/analytics/', AdminJobAnalyticsView.as_view(), name='admin-job-analytics'),
    path('jobs/bulk-delete/', BulkDeleteJobsView.as_view(), name='bulk-delete-jobs'),
    path('jobs/deletion-reasons/', JobDeletionReasonsView.as_view(), name='job-deletion-reasons'),
    path('jobs/pending/', PendingJobsListView.as_view(), name='pending-jobs-list'),
    path('jobs/rejection-reasons/', JobRejectionReasonsView.as_view(), name='job-rejection-reasons'),
    path('jobs/<uuid:job_id>/reject/', RejectJobView.as_view(), name='reject-job'),
    path('jobs/<uuid:job_id>/approve/', ApproveJobView.as_view(), name='approve-job'),
    path('users/pending/', ListPendingUsersView.as_view(), name='list-pending-users'),
    path('users/<uuid:user_id>/', PendingUserDetailView.as_view(), name='user-detail'),
    path('users/<uuid:user_id>/documents/<uuid:document_id>/download/', AdminUserDocumentDownloadView.as_view(), name='admin-user-document-download'),
    path('applications/<uuid:application_id>/status/', UpdateJobApplicationStatusView.as_view(), name='update-application-status'),
    path('delete-users/', DeleteAllUsersView.as_view(), name='delete_all_users'),
    path('all-users/', GetAllUsersView.as_view(), name='get_all_users'),
    path('delete-user/<str:email>/', DeleteUserByEmailView.as_view(), name='delete_user_by_email'),

    # public site footer (GET is public, PUT is admin-only)
    path('footer/', FooterView.as_view(), name='site-footer'),

    # admin / superadmin management
    path('admins/', AdminListView.as_view(), name='admin-list'),
    path('admins/create/', CreateAdminView.as_view(), name='admin-create'),
    path('admins/<uuid:admin_id>/', AdminDetailView.as_view(), name='admin-detail'),
    path('admins/<uuid:admin_id>/resend-invite/', ResendAdminInviteView.as_view(), name='admin-resend-invite'),
    path('superadmins/create/', CreateSuperAdminView.as_view(), name='superadmin-create'),

    # invite acceptance (public — no auth required)
    path('setup-admin-account/', SetupAdminAccountView.as_view(), name='setup-admin-account'),

    path('users/<uuid:user_id>/change-role/', ChangeUserRoleView.as_view(), name='change-user-role'),
]
