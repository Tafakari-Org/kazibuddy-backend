from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from accounts.models import CustomUser
from jobs.models import Job
from jobs.serializers import JobSerializer,JobListSerializer
from .serializers import (
    ApproveUserSerializer,
    UserStatusSerializer,
    CreateAdminSerializer,
    AdminDetailSerializer,
)
from rest_framework import status
from applications.models import JobApplication
from applications.serializers import JobApplicationSerializer, JobApplicationListSerializer
from rest_framework.permissions import IsAdminUser
from utils.views import send_otp_to_email
from utils.custom_error import error_response
from utils.custom_pagination import CustomPagination
from employers.models import EmployerProfile
from employers.serializers import EmployerProfileSerializer



class ApproveUserView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        #check if email is already verified
        try:
            if not user.email_verified:
                return Response({"error": "User email is not verified"}, status=status.HTTP_400_BAD_REQUEST)
        except AttributeError:
            return Response({"error": "User email verification status unknown"}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_verified:
            return Response({"message": "User is already verified"}, status=status.HTTP_200_OK)

        # Atomic: is_verified + updated_at must update together
        with transaction.atomic():
            user.is_verified = True
            user.updated_at = timezone.now()
            user.save()
            
            # Notify user of approval
            send_otp_to_email(
                user=user, 
                otp_type='admin_notification', 
                action_type='approved'
            )

        serializer = ApproveUserSerializer(user)
        return Response(
            {"message": "User approved successfully", "user": serializer.data},
            status=status.HTTP_200_OK
        )
    
class DeactivateUserView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            return Response({"message": "User is already deactivated"}, status=status.HTTP_200_OK)

        # Atomic: is_active + updated_at must update together
        with transaction.atomic():
            user.is_active = False
            user.updated_at = timezone.now()
            user.save()
            
            # Notify user of deactivation
            send_otp_to_email(
                user=user, 
                otp_type='admin_notification', 
                action_type='deactivated'
            )

        serializer = UserStatusSerializer(user)
        return Response(
            {"message": "User deactivated successfully", "user": serializer.data},
            status=status.HTTP_200_OK
        )
    



class AllJobsListView(APIView):
    """
    List all jobs regardless of approval status.
    Typically restricted to admin users.
    """
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        jobs = Job.objects.all()\
            .select_related('employer', 'category')\
            .prefetch_related('images', 'attachments')\
            .annotate(skills_count=Count('job_skills'))\
            .order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(jobs, request)

        serializer = JobListSerializer(page, many=True, context={'request': request})

        return paginator.get_paginated_response({
            "message": "All jobs retrieved successfully",
            "data": serializer.data,
        })


class ApproveJobView(APIView):
    """
    Approve a job by setting admin_approved to True.
    Only accessible by admin users.
    """
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)
        
        # Check if already approved
        if job.admin_approved:
            return Response(
                {
                    "message": "Job is already approved",
                    "data": JobSerializer(job).data
                },
                status=status.HTTP_200_OK
            )
        
        # Approve the job
        job.admin_approved = True
        job.status = 'active'
        job.save()
        
        # Notify employer of job approval
        if job.employer and job.employer.user:
            send_otp_to_email(
                user=job.employer.user, 
                otp_type='job_notification', 
                action_type='admin_job_approved',
                job_title=job.title
            )
        
        return Response(
            {
                "message": "Job approved successfully",
                "data": JobSerializer(job).data
            },
            status=status.HTTP_200_OK
        )
    
    def delete(self, request, job_id):
        """
        Unapprove a job (set admin_approved to False).
        """
        job = get_object_or_404(Job, id=job_id)
        
        if not job.admin_approved:
            return Response(
                {
                    "message": "Job is already unapproved",
                    "data": JobSerializer(job).data
                },
                status=status.HTTP_200_OK
            )
        
        job.admin_approved = False
        job.save()
        
        # Notify employer of job unapproval
        if job.employer and job.employer.user:
            send_otp_to_email(
                user=job.employer.user, 
                otp_type='job_notification', 
                action_type='admin_job_unapproved',
                job_title=job.title
            )
        paginate_queryset
        return Response(
            {
                "message": "Job unapproved successfully",
                "data": JobSerializer(job).data
            },
            status=status.HTTP_200_OK
        )


class PendingJobsListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        jobs = Job.objects.filter(admin_approved=False)\
            .select_related('employer', 'category')\
            .annotate(skills_count=Count('job_skills'))\
            .order_by('-created_at')

        paginator = CustomPagination()
        page = paginator.paginate_queryset(jobs, request)

        serializer = JobListSerializer(page, many=True, context={'request': request})

        return paginator.get_paginated_response({
            "message": "Pending jobs retrieved successfully",
            "data": serializer.data,
            "total": paginator.page.paginator.count
        })
    
class ListPendingUsersView(APIView):
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            users = CustomUser.objects.filter(
                is_verified=False
            ).only(
                'id', 'email', 'phone_number', 'user_type',
                'full_name', 'profile_photo_url', 'email_verified', 'phone_verified'
            ).order_by('-created_at')

            paginator = self.pagination_class()
            paginated_users = paginator.paginate_queryset(users, request)

            user_data = [
                {
                    'user_id': str(user.id),
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'user_type': user.user_type,
                    'full_name': user.full_name,
                    'profile_photo_url': user.profile_photo_url,
                    'email_verified': user.email_verified,
                    'phone_verified': user.phone_verified,
                }
                for user in paginated_users
            ]

            return Response(
                {
                    'message': 'Pending users retrieved successfully',
                    'data': user_data,
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    'message': 'Failed to retrieve pending users.',
                    'errors': str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateJobApplicationStatusView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, application_id):
        try:
            application = JobApplication.objects.get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response({"error": "Application not found"}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "'status' is required"}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = [choice[0] for choice in JobApplication.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status. Valid statuses: {valid_statuses}"}, status=status.HTTP_400_BAD_REQUEST)

        if application.status == new_status:
            return Response(
                {"message": "Status unchanged", "application": {"id": str(application.id), "status": application.status}},
                status=status.HTTP_200_OK
            )

        # Optional notes that may accompany the status update
        employer_notes = request.data.get("employer_notes")
        worker_notes = request.data.get("worker_notes")

        # Atomic: status + timestamps + notes must all update together;
        # select_for_update prevents concurrent admin status changes
        with transaction.atomic():
            application = JobApplication.objects.select_for_update().get(id=application_id)
            application.status = new_status

            # Set timestamps based on transition
            if application.status != "pending" and application.reviewed_at is None:
                application.reviewed_at = timezone.now()

            # Mark responded_at for decisive outcomes
            if application.status in ("accepted", "rejected", "withdrawn"):
                application.responded_at = timezone.now()
            else:
                application.responded_at = None

            if employer_notes is not None:
                application.employer_notes = employer_notes
            if worker_notes is not None:
                application.worker_notes = worker_notes

            application.save()

            # Notify worker of application status update
            send_otp_to_email(
                user=application.worker.user, 
                otp_type='job_notification', 
                action_type='application_status_updated',
                job_title=application.job.title,
                job_status=application.get_status_display()
            )

        # Use the JobApplicationSerializer for the response representation
        serializer = JobApplicationSerializer(application, context={"request": request})

        return Response(
            {"message": "Application status updated successfully", "application": serializer.data},
            status=status.HTTP_200_OK
        )


class DeleteAllUsersView(APIView):
    # permission_classes = [permissions.IsAdminUser]
    def delete(self, request):
        try:
            CustomUser.objects.all().delete()
            return Response({"message": "All users deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return error_response(
                message="Error deleting all users",
                errors={"error": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 

class GetAllUsersView(APIView):
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        users = CustomUser.objects.all()
        paginated_users = self.pagination_class().paginate_queryset(users, request)
        user_data = []
        
        for user in paginated_users:
            user_data.append({
                "user_id": str(user.id),
                "email": user.email,
                "phone_number": user.phone_number,
                "user_type": user.user_type,
                "full_name": user.full_name,
                "profile_photo_url": user.profile_photo_url,
                "email_verified": user.email_verified,
                "phone_verified": user.phone_verified,
            })
        
        return Response({
            "message": "Users retrieved successfully",
            "data": user_data, 
            "status":status.HTTP_200_OK
            })

#delete user by email endpoint 
class DeleteUserByEmailView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def delete(self, request, email):
        try:
            user = CustomUser.objects.get(email=email)
            
            # Notify user of deletion before deleting the record
            send_otp_to_email(
                user=user, 
                otp_type='admin_notification', 
                action_type='deleted'
            )
            
            user.delete()
            return Response({"message": f"User with email {email} deleted successfully"}, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return error_response(
                message="User not found",
                errors={"error": f"No user found with email {email}"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return error_response(
                message="Error deleting user",
                errors={"error": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class ListEmployerProfilesView(APIView):
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        company_name = request.GET.get("company_name")
        location = request.GET.get("location")
        industry = request.GET.get("industry")
        business_type = request.GET.get("business_type")

        employers = EmployerProfile.objects.all()

        if company_name:
            employers = employers.filter(company_name__icontains=company_name)
        if location:
            employers = employers.filter(location__icontains=location)
        if industry:
            employers = employers.filter(industry__icontains=industry)
        if business_type:
            employers = employers.filter(business_type=business_type)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(employers, request, view=self)
        if page is not None:
            serializer = EmployerProfileSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = EmployerProfileSerializer(employers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Custom permission: only super_admin users may manage admin accounts
# ---------------------------------------------------------------------------

class IsSuperAdmin(permissions.BasePermission):
    """Allow access only to authenticated users whose user_type is 'super_admin'."""

    message = "Only super-admin users can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.user_type == "super_admin"
        )


# ---------------------------------------------------------------------------
# Admin / SuperAdmin creation
# ---------------------------------------------------------------------------

class CreateAdminView(APIView):
    """
    POST /api/adminpanel/admins/create/
    Create a new admin account. Only super_admins can call this.
    """
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = CreateAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=data["email"],
                phone_number=data.get("phone_number"),
                password=data["password"],
                full_name=data["full_name"],
                user_type="admin",
                is_verified=True,        # admins are trusted — no approval needed
                email_verified=True,
                is_staff=True,
            )

        return Response(
            {
                "message": "Admin created successfully",
                "admin": AdminDetailSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CreateSuperAdminView(APIView):
    """
    POST /api/adminpanel/superadmins/create/
    Create a new super_admin account. Only existing super_admins can call this.
    """
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = CreateAdminSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=data["email"],
                phone_number=data.get("phone_number"),
                password=data["password"],
                full_name=data["full_name"],
                user_type="super_admin",
                is_verified=True,
                email_verified=True,
                is_staff=True,
                is_superuser=True,
            )

        return Response(
            {
                "message": "Super admin created successfully",
                "super_admin": AdminDetailSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Admin list & detail (get / update / delete)
# ---------------------------------------------------------------------------

class AdminListView(APIView):
    """
    GET /api/adminpanel/admins/
    List all admin AND super_admin users. Supports optional ?user_type= filter.
    Only super_admins can access this.
    """
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        user_type = request.query_params.get("user_type")

        if user_type:
            if user_type not in ("admin", "super_admin"):
                return error_response(
                    message="Invalid user_type filter. Use 'admin' or 'super_admin'.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            admins = CustomUser.objects.filter(user_type=user_type).order_by("full_name")
        else:
            admins = CustomUser.objects.filter(
                user_type__in=["admin", "super_admin"]
            ).order_by("user_type", "full_name")

        serializer = AdminDetailSerializer(admins, many=True)
        return Response(
            {
                "message": "Admins retrieved successfully",
                "total": admins.count(),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminDetailView(APIView):
    """
    GET    /api/adminpanel/admins/<uuid:admin_id>/  — retrieve one admin
    PATCH  /api/adminpanel/admins/<uuid:admin_id>/  — update fields (partial)
    DELETE /api/adminpanel/admins/<uuid:admin_id>/  — delete the admin account
    Only super_admins can access this.
    """
    permission_classes = [IsSuperAdmin]

    def _get_admin(self, admin_id):
        """Return the user if they are an admin/super_admin, else None."""
        try:
            user = CustomUser.objects.get(id=admin_id, user_type__in=["admin", "super_admin"])
            return user
        except CustomUser.DoesNotExist:
            return None

    def get(self, request, admin_id):
        user = self._get_admin(admin_id)
        if not user:
            return error_response(
                message="Admin not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "message": "Admin retrieved successfully", 
                "data": AdminDetailSerializer(user).data
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, admin_id):
        user = self._get_admin(admin_id)
        if not user:
            return error_response(
                message="Admin not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminDetailSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            serializer.save(updated_at=timezone.now())

        return Response(
            {"message": "Admin updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, admin_id):
        user = self._get_admin(admin_id)
        if not user:
            return error_response(
                message="Admin not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Prevent a super_admin from deleting their own account
        if str(user.id) == str(request.user.id):
            return error_response(
                message="You cannot delete your own admin account.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Only super_admins can delete other super_admins
        if user.user_type == "super_admin" and request.user.user_type != "super_admin":
            return error_response(
                message="Only a super_admin can delete another super_admin.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        deleted_email = user.email
        user.delete()
        return Response(
            {"message": f"Admin '{deleted_email}' deleted successfully."},
            status=status.HTTP_200_OK,
        )

# class ListJobApplicantsView(APIView):
#     """
#     GET /api/adminpanel/jobs/<uuid:job_id>/applicants/

#     List all applicants for a specific job.
#     Supports optional query params:
#       - ?status=pending|shortlisted|accepted|rejected|withdrawn
#       - Pagination via standard page/page_size params

#     Only admin users can access this endpoint.
#     """
#     permission_classes = [permissions.IsAdminUser]
#     pagination_class = CustomPagination

#     def get(self, request, job_id):
#         job = get_object_or_404(Job, id=job_id)

#         applications = JobApplication.objects.filter(job=job).select_related(
#             'job', 'job__employer', 'job__category', 'worker', 'worker__user'
#         ).prefetch_related(
#             'job__job_skills', 'job__images', 'job__attachments'
#         ).order_by('-applied_at')

#         status_filter = request.query_params.get('status')
#         if status_filter:
#             valid_statuses = [c[0] for c in JobApplication.STATUS_CHOICES]
#             if status_filter not in valid_statuses:
#                 return Response(
#                     {"status": "error", "message": f"Invalid status filter. Valid values: {valid_statuses}"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#             applications = applications.filter(status=status_filter)

#         paginator = self.pagination_class()
#         page = paginator.paginate_queryset(applications, request)
        
#         # We can use JobApplicationListSerializer which is imported at the top of the file.
#         serializer = JobApplicationListSerializer(page, many=True, context={'request': request})

#         return paginator.get_paginated_response({
#             "status": "success",
#             "message": f"Applicants for job '{job.title}' retrieved successfully.",
#             "data": serializer.data,
#         })


