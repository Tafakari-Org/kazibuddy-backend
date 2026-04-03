from django.urls import path
from .views import (
    ListCreateAssignmentView,
    AssignmentDetailView,
    UpdateAssignmentStatusView,
    ListCreateCheckinView,
    ListCreateMilestoneView,
    UpdateMilestoneStatusView,
)

urlpatterns = [
    # Assignments
    path('', ListCreateAssignmentView.as_view(), name='list-create-assignment'),
    path('<uuid:assignment_id>/', AssignmentDetailView.as_view(), name='assignment-detail'),
    path('<uuid:assignment_id>/status/', UpdateAssignmentStatusView.as_view(), name='update-assignment-status'),

    # Checkins
    path('<uuid:assignment_id>/checkins/', ListCreateCheckinView.as_view(), name='list-create-checkins'),

    # Milestones
    path('<uuid:assignment_id>/milestones/', ListCreateMilestoneView.as_view(), name='list-create-milestones'),
    path('milestones/<uuid:milestone_id>/status/', UpdateMilestoneStatusView.as_view(), name='update-milestone-status'),
]