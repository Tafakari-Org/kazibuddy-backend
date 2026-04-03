from django.shortcuts import render
from .serializers import JobApplicationSerializer,JobApplicationListSerializer,JobApplicationWorkerSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from jobs.models import Job
from .models import JobApplication
from workers.models import WorkerProfile
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .utils import check_if_user_isOwner
from utils.custom_pagination import CustomPagination
from django.db import transaction
from utils.views import send_otp_to_email
from rest_framework.permissions import IsAdminUser


# Create your views here.
class CreateJobApplicationView(APIView):
    """
    View to create a new job application.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = JobApplicationSerializer

    def post(self, request, *args, **kwargs):
        # Get the job_id from the URL parameters
        job_id = kwargs.get('job_id')
        if not job_id:
            return Response({
                'status': 'error',
                'message': 'Job ID is required.'
            }, status=400)

        # Atomic: duplicate check + application creation must be atomic to prevent
        # race conditions where two workers could simultaneously create duplicate applications
        with transaction.atomic():
            # Lock the job row to prevent concurrent application count issues
            try:
                job = Job.objects.select_for_update().get(id=job_id)
            except Job.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Job not found.'
                }, status=404)

            # Check if the worker has already applied for the job
            worker = request.user
            worker_profile = WorkerProfile.objects.filter(user=worker).first()
            if not worker_profile:
                return Response({
                    'status': 'error',
                    'message': 'Worker profile not found,you need to create a  profile before applying for jobs.'
                }, status=404)
            if JobApplication.objects.filter(job=job, worker=worker_profile).exists():
                return Response({
                    'status': 'error',
                    'message': 'You have already applied for this job.'
                }, status=400)

            serializer = self.serializer_class(data=request.data, context={'request': request})
            if serializer.is_valid():
                application = serializer.save(job=job, worker=worker_profile)
                
                # Send notification for application creation
                # Notify the applicant (worker)
                send_otp_to_email(
                    user=request.user, 
                    otp_type='job_notification', 
                    action_type='application_created',
                    job_title=job.title,
                )
                
                # Optionally notify the employer as well (customer/employer who posted the job)
                if job.employer and job.employer.user:
                    send_otp_to_email(
                        user=job.employer.user, 
                        otp_type='job_notification', 
                        action_type='new_application', # I should add this too
                        job_title=job.title,
                        applicant_name=request.user.full_name
                    )

                return Response({
                    'status': 'success',
                    'message': 'Job application created successfully.',
                    'application_id': str(application.id),
                    'user': {
                        'id': str(application.worker.id),
                        'name': application.worker.user.full_name,
                        'email': application.worker.user.email
                    }
                }, status=201)
            return Response({
                'status': 'error',
                'message': 'Failed to create job application.',
                'errors': serializer.errors
            }, status=400)
    
class MyJobApplicationListView(APIView):
    """
    View to list all job applications for a worker.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        worker_profile = WorkerProfile.objects.filter(user=request.user).first()
        if not worker_profile:
            return Response({
                'status': 'error',
                'message': 'Worker profile not found.'
            }, status=404)

        applications = JobApplication.objects.filter(worker=worker_profile)
        paginator = self.pagination_class()
        paginated_applications = paginator.paginate_queryset(applications, request)
        serializer = self.serializer_class(paginated_applications, many=True)
        return Response({
            'status': 'success',
            'applications': serializer.data
        }, status=200)

class JobApplicationDetailView(APIView):
    """
    View to retrieve, update, or delete a job application.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        application_id = kwargs.get('application_id')
        try:
            application = JobApplication.objects.get(id=application_id)
            paginator = self.pagination_class()
            paginated_application = paginator.paginate_queryset([application], request)
        except JobApplication.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Job application not found.'
            }, status=404)
        #check wheather the user is the owner of the application
        check_if_user_isOwner(request.user, application_id)
        serializer = self.serializer_class(paginated_application)
        return Response({
            'status': 'success',
            'application': serializer.data
        }, status=200)
    
    def put(self, request, *args, **kwargs):
        application_id = kwargs.get('application_id')
        #check wheather the application_id is provided
        if not application_id:
            return Response({
                'status': 'error',
                'message': 'Application ID is required.'
            }, status=400)
        #check wheather the user is the owner of the application
        check_if_user_isOwner(request.user, application_id)
        

        try:
            application = JobApplication.objects.get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Job application not found.'
            }, status=404)
        # only allow updating if only the status is pending

        if application.status != 'pending':
            return Response({
                'status': 'error',
                'message': 'You can only update applications with a status of pending.'
            }, status=400)
        
        
        serializer = self.serializer_class(application, data=request.data, partial=True)
        if serializer.is_valid():
            updated_application = serializer.save()
            return Response({
                'status': 'success',
                'message': 'Job application updated successfully.',
                'application': self.serializer_class(updated_application).data
            }, status=200)
        return Response({
            'status': 'error',
            'message': 'Failed to update job application.',
            'errors': serializer.errors
        }, status=400)
    
    def delete(self, request, *args, **kwargs):
        application_id = kwargs.get('application_id')
        #check wheather the application_id is provided
        if not application_id:
            return Response({
                'status': 'error',
                'message': 'Application ID is required.'
            }, status=400)

        #check wheather the user is the owner of the application
        check_if_user_isOwner(request.user, application_id)  
        
        # Check if the application exists
        try:
            application = JobApplication.objects.get(id=application_id)
            job_title = application.job.title
            application.delete()
            
            # Send notification for application withdrawal/deletion
            send_otp_to_email(
                user=request.user, 
                otp_type='job_notification', 
                action_type='application_deleted',
                job_title=job_title
            )
            
            return Response({
                'status': 'success',
                'message': 'Job application deleted successfully.'
            }, status=status.HTTP_204_NO_CONTENT)
        except JobApplication.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Job application not found.'
            }, status=status.HTTP_404_NOT_FOUND)

class SpecificJobApplicationListView(APIView):
    """
    View to list all job applications for a job.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        job_id = kwargs.get('job_id')
        if not job_id:
            return Response({
                'status': 'error',
                'message': 'Job ID is required.'
            }, status=400)

        # Check if the job exists
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Job not found.'
            }, status=404)
        
        paginator = self.pagination_class()
        applications = JobApplication.objects.filter(job=job)
        paginated_applications = paginator.paginate_queryset(applications, request)
        serializer = self.serializer_class(paginated_applications, many=True)
        return Response({
            'status': 'success',
            'applications': serializer.data
        }, status=200)

class AllJobApplicationListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        applications = JobApplication.objects.all()\
            .select_related(
                'job',
                'job__employer',
                'job__category',
                'worker',
                'worker__user',  # adjust to match your WorkerProfile -> User relation
            )\
            .prefetch_related(
                'job__job_skills',
                'job__images',
                'job__attachments',
            )\
            .order_by('-applied_at')

        paginator = CustomPagination()
        page = paginator.paginate_queryset(applications, request)
        serializer = JobApplicationListSerializer(page, many=True, context={'request': request})

        return paginator.get_paginated_response({
            'status': 'success',
            'data': serializer.data,
            'total': paginator.page.paginator.count
        })

#get all rejected job applications
class RejectedJobApplicationListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        try:
            applications = JobApplication.objects.filter(status='rejected')
            paginator = self.pagination_class()
            paginated_applications = paginator.paginate_queryset(applications, request)
            serializer = self.serializer_class(paginated_applications, many=True)
            return Response({
            'status': 'success',
            'data': serializer.data
            }, status=200)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve rejected job applications.',
                'errors': str(e)
            }, status=500)

#get all pending job applications
class PendingJobApplicationListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        try:
            applications = JobApplication.objects.filter(status='pending')\
                .select_related('job','worker')\
                .prefetch_related('job__job_skills','job__category', 'job__images','job__attachments', 'worker__user')\
                .order_by('-applied_at')
            paginator = self.pagination_class()
            paginated_applications = paginator.paginate_queryset(applications, request)
            serializer = self.serializer_class(paginated_applications, many=True)
            return Response({
            'status': 'success',
            'data': serializer.data
            }, status=200)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve pending job applications.',
                'errors': str(e)
            }, status=500)

#get all accepted job applications
class AcceptedJobApplicationListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination
    serializer_class = JobApplicationSerializer

    def get(self, request, *args, **kwargs):
        try:
            applications = JobApplication.objects.filter(status='accepted')\
                .select_related('job','worker')\
                .prefetch_related('job__job_skills','job__category', 'job__images', 'job__attachments', 'worker__user')\
                .order_by('-applied_at')
            paginator = self.pagination_class()
            paginated_applications = paginator.paginate_queryset(applications, request)
            serializer = self.serializer_class(paginated_applications, many=True)
            return Response({
            'status': 'success',
            'data': serializer.data
            }, status=200)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve accepted job applications.',
                'errors': str(e)
            }, status=500)  
            

#get total applications
class TotalApplicationsView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            total_applications = JobApplication.objects.count()
            return Response({
                'status': 'success',
                'data': total_applications
            }, status=200)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve total applications.',
                'errors': str(e)
            }, status=500)

#get total applications by job
class TotalApplicationsByJobView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            job_id = kwargs.get('job_id')
            if not job_id:
                return Response({
                    'status': 'error',
                    'message': 'Job ID is required.'
                }, status=400)
            total_applications = JobApplication.objects.filter(job_id=job_id).count()
            return Response({
                'status': 'success',
                'data': total_applications
            }, status=200)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve total applications.',
                'errors': str(e)
            }, status=500)

#list worker profiles for a specific job
class JobApplicationWorkerView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    serializer_class = JobApplicationWorkerSerializer

    def get(self, request, *args, **kwargs):
        job_id = kwargs.get('job_id')

        if not job_id:
            return Response({
                'status': 'error',
                'message': 'Job ID is required.'
            }, status=400)

        try:
            applications = JobApplication.objects.filter(job_id=job_id).select_related('worker').prefetch_related('worker__user')
            paginator = self.pagination_class()
            paginated_applications = paginator.paginate_queryset(applications, request)
            serializer = self.serializer_class(paginated_applications, many=True)

            return paginator.get_paginated_response({
                'status': 'success',
                'data': serializer.data
            })

        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve job applications.',
                'errors': str(e)
            }, status=500)