from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status

from .models import Assignment, AssignmentCheckin, AssignmentMilestone
from .serializers import (
    AssignmentSerializer,
    CreateAssignmentSerializer,
    AssignmentCheckinSerializer,
    AssignmentMilestoneSerializer,
    UpdateAssignmentStatusSerializer,
    UpdateAssignmentMilestoneSerializer,
)
from utils.custom_pagination import CustomPagination
from utils.views import send_otp_to_email


#Assignments

class ListCreateAssignmentView(APIView):
    """
    GET  /assignments/         — list all assignments
    POST /assignments/         — create a new assignment
    """
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            status_filter = request.query_params.get('status')
            worker_id = request.query_params.get('worker_id')
            job_id = request.query_params.get('job_id')

            assignments = Assignment.objects.select_related(
                'job', 'worker__user', 'employer__user', 'application'
            ).prefetch_related(
                'assignmentcheckin_set', 'assignmentmilestone_set'
            ).order_by('-created_at')

            if status_filter:
                assignments = assignments.filter(status=status_filter)
            if worker_id:
                assignments = assignments.filter(worker_id=worker_id)
            if job_id:
                assignments = assignments.filter(job_id=job_id)

            paginator = self.pagination_class()
            paginated = paginator.paginate_queryset(assignments, request)
            serializer = AssignmentSerializer(paginated, many=True)

            return paginator.get_paginated_response({
                'status': 'success',
                'message': 'Assignments retrieved successfully.',
                'data': serializer.data,
            })

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve assignments.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            serializer = CreateAssignmentSerializer(data=request.data)
            if not serializer.is_valid():
                errors = serializer.errors
                first_error = next(iter(errors.values()))[0]
                return Response({
                    'status': 'error',
                    'message': str(first_error),
                    'errors': errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                assignment = serializer.save()
                assignment.job.is_assigned = True
                assignment.job.save(update_fields=['is_assigned'])

            # Notify worker
            send_otp_to_email(
                user=assignment.worker.user,
                otp_type='assignment_notification',
                action_type='assignment_created',
                job_title=assignment.job.title,
                employer_name=assignment.employer.user.full_name,
                start_date=str(assignment.start_date),
                agreed_rate=str(assignment.agreed_rate),
                payment_type=assignment.payment_type,
            )

            # Notify employer
            send_otp_to_email(
                user=assignment.employer.user,
                otp_type='assignment_notification',
                action_type='assignment_created',
                job_title=assignment.job.title,
                worker_name=assignment.worker.user.full_name,
                start_date=str(assignment.start_date),
                agreed_rate=str(assignment.agreed_rate),
                payment_type=assignment.payment_type,
            )

            return Response({
                'status': 'success',
                'message': 'Assignment created successfully.',
                'data': AssignmentSerializer(assignment).data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to create assignment.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignmentDetailView(APIView):
    """
    GET    /assignments/<id>/  — retrieve assignment
    PATCH  /assignments/<id>/  — update assignment fields
    DELETE /assignments/<id>/  — delete assignment
    """
    permission_classes = [IsAdminUser]

    def get_object(self, assignment_id):
        try:
            return Assignment.objects.select_related(
                'job', 'worker__user', 'employer__user'
            ).prefetch_related(
                'assignmentcheckin_set', 'assignmentmilestone_set'
            ).get(id=assignment_id)
        except Assignment.DoesNotExist:
            return None

    def get(self, request, assignment_id):
        try:
            assignment = self.get_object(assignment_id)
            if not assignment:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'status': 'success',
                'message': 'Assignment retrieved successfully.',
                'data': AssignmentSerializer(assignment).data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve assignment.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, assignment_id):
        try:
            assignment = self.get_object(assignment_id)
            if not assignment:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = AssignmentSerializer(
                assignment, data=request.data, partial=True
            )
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': 'Invalid data.',
                    'errors': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()

            return Response({
                'status': 'success',
                'message': 'Assignment updated successfully.',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to update assignment.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, assignment_id):
        try:
            assignment = self.get_object(assignment_id)
            if not assignment:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            with transaction.atomic():
                # Reopen job when assignment is deleted
                assignment.job.is_assigned = False
                assignment.job.save(update_fields=['is_assigned'])
                assignment.delete()

            return Response({
                'status': 'success',
                'message': 'Assignment deleted successfully.',
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to delete assignment.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateAssignmentStatusView(APIView):
    """PATCH /assignments/<id>/status/ — update assignment status with transition validation"""
    permission_classes = [IsAdminUser]

    def patch(self, request, assignment_id):
        try:
            assignment = Assignment.objects.select_related('job').get(id=assignment_id)
        except Assignment.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Assignment not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            serializer = UpdateAssignmentStatusSerializer(
                data=request.data,
                context={'instance': assignment}
            )
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': 'Invalid status transition.',
                    'errors': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                new_status = serializer.validated_data['status']
                assignment.status = new_status

                if serializer.validated_data.get('completion_percentage') is not None:
                    assignment.completion_percentage = serializer.validated_data['completion_percentage']

                # Set relevant timestamps automatically
                if new_status == 'in_progress' and not assignment.worker_started_at:
                    assignment.worker_started_at = timezone.now()
                elif new_status == 'completed':
                    assignment.worker_completed_at = timezone.now()
                    assignment.completion_percentage = 100
                    assignment.job.status = 'filled'
                    assignment.job.filled_at = timezone.now()
                    assignment.job.save(update_fields=['status', 'filled_at'])
                elif new_status == 'cancelled':
                    assignment.job.is_assigned = False
                    assignment.job.status = 'active'
                    assignment.job.save(update_fields=['is_assigned', 'status'])

                assignment.save()

            return Response({
                'status': 'success',
                'message': f'Assignment status updated to {new_status}.',
                'data': AssignmentSerializer(assignment).data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to update assignment status.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Checkins

class ListCreateCheckinView(APIView):
    """
    GET  /assignments/<id>/checkins/  — list checkins for an assignment
    POST /assignments/<id>/checkins/  — add a checkin
    """
    permission_classes = [IsAdminUser]

    def get(self, request, assignment_id):
        try:
            checkins = AssignmentCheckin.objects.select_related(
                'worker__user'
            ).filter(
                assignment_id=assignment_id
            ).order_by('-checkin_time')

            serializer = AssignmentCheckinSerializer(checkins, many=True)

            return Response({
                'status': 'success',
                'message': 'Checkins retrieved successfully.',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve checkins.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, assignment_id):
        try:
            try:
                assignment = Assignment.objects.get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            data = request.data.copy()
            data['assignment'] = assignment_id

            serializer = AssignmentCheckinSerializer(data=data)
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': 'Invalid data.',
                    'errors': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            checkin = serializer.save()

            return Response({
                'status': 'success',
                'message': 'Checkin added successfully.',
                'data': AssignmentCheckinSerializer(checkin).data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to add checkin.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Milestones ────────────────────────────────────────────────────────────────

class ListCreateMilestoneView(APIView):
    """
    GET  /assignments/<id>/milestones/  — list milestones for an assignment
    POST /assignments/<id>/milestones/  — add a milestone
    """
    permission_classes = [IsAdminUser]

    def get(self, request, assignment_id):
        try:
            milestones = AssignmentMilestone.objects.filter(
                assignment_id=assignment_id
            ).order_by('due_date', 'created_at')

            serializer = AssignmentMilestoneSerializer(milestones, many=True)

            return Response({
                'status': 'success',
                'message': 'Milestones retrieved successfully.',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve milestones.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, assignment_id):
        try:
            try:
                Assignment.objects.get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            data = request.data.copy()
            data['assignment'] = assignment_id

            serializer = AssignmentMilestoneSerializer(data=data)
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': 'Invalid data.',
                    'errors': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            milestone = serializer.save()

            return Response({
                'status': 'success',
                'message': 'Milestone created successfully.',
                'data': AssignmentMilestoneSerializer(milestone).data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to create milestone.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateMilestoneStatusView(APIView):
    """PATCH /assignments/milestones/<id>/status/ — update milestone status"""
    permission_classes = [IsAdminUser]

    def patch(self, request, milestone_id):
        try:
            try:
                milestone = AssignmentMilestone.objects.get(id=milestone_id)
            except AssignmentMilestone.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Milestone not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = UpdateAssignmentMilestoneSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': 'Invalid data.',
                    'errors': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

            milestone.status = serializer.validated_data['status']
            milestone.completion_notes = serializer.validated_data.get(
                'completion_notes', milestone.completion_notes
            )
            if milestone.status == 'completed':
                milestone.completed_at = timezone.now()

            milestone.save()

            return Response({
                'status': 'success',
                'message': 'Milestone status updated successfully.',
                'data': AssignmentMilestoneSerializer(milestone).data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to update milestone.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)