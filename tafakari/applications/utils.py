from rest_framework.response import Response
from .models import JobApplication
from rest_framework.permissions import IsAuthenticated


def check_if_user_isOwner(request_user, application_id):
    try:
            application_worker_profile = JobApplication.objects.filter(id=application_id, worker=request_user).first()
            if not application_worker_profile:
                return Response({
                    'status': 'error',
                    'message': 'You are not authorized to update this job application.'
                }, status=403)
    except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=500)