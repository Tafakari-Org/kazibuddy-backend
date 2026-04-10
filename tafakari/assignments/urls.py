from django.urls import path
from .views import (
    ListCreateAssignmentView,
    AssignmentDetailView,
    ListCreateCheckinView,
    ListCreateMilestoneView,
    UpdateMilestoneStatusView,
    NotifyRejectedApplicantsView,
    NotifySingleRejectedApplicantView,
    ListWorkerAssignmentsView,
)

urlpatterns = [
    # Assignments
    path('', ListCreateAssignmentView.as_view(), name='list-create-assignment'),
    path('<uuid:assignment_id>/', AssignmentDetailView.as_view(), name='assignment-detail'),
    path('worker/<uuid:worker_id>/', ListWorkerAssignmentsView.as_view(), name='list-worker-assignments'),
    # Checkins
    path('<uuid:assignment_id>/checkins/', ListCreateCheckinView.as_view(), name='list-create-checkins'),

    # Milestones
    path('<uuid:assignment_id>/milestones/', ListCreateMilestoneView.as_view(), name='list-create-milestones'),
    path('milestones/<uuid:milestone_id>/status/', UpdateMilestoneStatusView.as_view(), name='update-milestone-status'),

    # Notifications
    path('<uuid:assignment_id>/notify-rejected/', NotifyRejectedApplicantsView.as_view(), name='notify-rejected-applicants'),
    path('<uuid:assignment_id>/notify-rejected/<uuid:applicant_id>/', NotifySingleRejectedApplicantView.as_view(), name='notify-single-rejected-applicant'),
]
