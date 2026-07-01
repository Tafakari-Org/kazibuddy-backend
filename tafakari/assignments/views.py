from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
import logging

from .models import Assignment, AssignmentCheckin, AssignmentMilestone
from .serializers import (
    AssignmentSerializer,
    CreateAssignmentSerializer,
    AssignmentCheckinSerializer,
    AssignmentMilestoneSerializer,
    UpdateAssignmentMilestoneSerializer,
)
from applications.models import JobApplication
from utils.custom_pagination import CustomPagination
from utils.views import send_otp_to_email
from .tasks import notify_rejected_applicants

logger = logging.getLogger(__name__)


# ── Assignments ───────────────────────────────────────────────────────────────

class ListCreateAssignmentView(APIView):
    """
    GET  /assignments/  — list all assignments
    POST /assignments/  — create a new assignment
    """
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            worker_id = request.query_params.get('worker_id')
            job_id = request.query_params.get('job_id')

            assignments = Assignment.objects.select_related(
                'job', 'worker__user', 'employer__user'
            ).prefetch_related(
                'checkins', 'milestones'
            ).order_by('-created_at')

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

                # Accept the assigned worker's application
                JobApplication.objects.filter(
                    job=assignment.job,
                    worker=assignment.worker,
                ).update(
                    status='accepted',
                    responded_at=timezone.now(),
                )

                # Reject all other applications for the same job
                JobApplication.objects.filter(
                    job=assignment.job,
                ).exclude(
                    worker=assignment.worker,
                ).update(
                    status='rejected',
                    responded_at=timezone.now(),
                )

            # Notify worker
            send_otp_to_email(
                user=assignment.worker.user,
                otp_type='assignment_notification',
                action_type='assignment_created',
                job_title=assignment.job.title,
                employer_name=assignment.employer.user.full_name,
                start_date=str(assignment.job.start_date),
                agreed_rate=str(assignment.job.budget_min),
                payment_type=assignment.job.payment_type,
            )

            # Notify employer
            send_otp_to_email(
                user=assignment.employer.user,
                otp_type='assignment_notification',
                action_type='assignment_created',
                job_title=assignment.job.title,
                worker_name=assignment.worker.user.full_name,
                start_date=str(assignment.job.start_date),
                agreed_rate=str(assignment.job.budget_min),
                payment_type=assignment.job.payment_type,
            )

            # Notify all other applicants who were rejected — offloaded to Celery
            notify_rejected_applicants.delay(
                job_id=str(assignment.job.id),
                assigned_worker_id=str(assignment.worker.id),
            )
            logger.info(
                f"[Assignment] Rejection notification task queued for job {assignment.job.id}."
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
                'checkins', 'milestones'
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


#list specific worker assignments
class ListWorkerAssignmentsView(APIView):
    # permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request, worker_id):
        try:
            assignments = Assignment.objects.select_related(
                'job', 'worker__user', 'employer__user'
            ).filter(worker_id=worker_id).order_by('-created_at')

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


# ── Checkins ──────────────────────────────────────────────────────────────────

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



class NotifyRejectedApplicantsView(APIView):
    """
    POST /assignments/<id>/notify-rejected/
    Sends rejection emails to all rejected applicants for the assignment's job.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, assignment_id):
        try:
            try:
                assignment = Assignment.objects.select_related(
                    'job'
                ).get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            rejected_applications = JobApplication.objects.select_related(
                'worker__user'
            ).filter(
                job=assignment.job,
                # status='rejected',
            )

            if not rejected_applications.exists():
                return Response({
                    'status': 'success',
                    'message': 'No rejected applicants to notify.',
                }, status=status.HTTP_200_OK)

            notified, failed = [], []

            for application in rejected_applications:
                try:
                    send_otp_to_email(
                        user=application.worker.user,
                        otp_type='application_notification',
                        action_type='application_rejected',
                        job_title=assignment.job.title,
                    )
                    notified.append(str(application.worker.id))
                except Exception:
                    failed.append(str(application.worker.id))

            return Response({
                'status': 'success',
                'message': f'{len(notified)} applicant(s) notified, {len(failed)} failed.',
                'data': {
                    'notified': notified,
                    'failed': failed,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to send rejection notifications.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotifySingleRejectedApplicantView(APIView):
    """
    POST /assignments/<id>/notify-rejected/<applicant_id>/
    Sends a rejection email to a specific applicant for the assignment's job.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, assignment_id, applicant_id):
        try:
            try:
                assignment = Assignment.objects.select_related(
                    'job'
                ).get(id=assignment_id)
            except Assignment.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Assignment not found.',
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                application = JobApplication.objects.select_related(
                    'worker__user'
                ).get(
                    id=applicant_id,
                    job=assignment.job,
                )
            except JobApplication.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Application not found for this assignment.',
                }, status=status.HTTP_404_NOT_FOUND)

            # if application.status != 'rejected':
            #     return Response({
            #         'status': 'error',
            #         'message': f'Applicant status is "{application.status}", not "rejected".',
            #     }, status=status.HTTP_400_BAD_REQUEST)

            send_otp_to_email(
                user=application.worker.user,
                otp_type='application_notification',
                action_type='application_rejected',
                job_title=assignment.job.title,
            )

            return Response({
                'status': 'success',
                'message': 'Rejection email sent successfully.',
                'data': {
                    'worker_id': str(application.worker.id),
                    'worker_name': application.worker.user.full_name,
                    'job_title': assignment.job.title,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to send rejection notification.',
                'errors': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)