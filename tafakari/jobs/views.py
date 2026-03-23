from time import timezone
from .serializers import JobSerializer, JobCategorySerializer, JobSkillSerializer, JobImageSerializer, JobAttachmentSerializer
from .search_serializers import JobSearchSerializer, JobSearchQuerySerializer
from rest_framework import views, permissions, status
from .models import Job, JobCategory, JobSkill, JobImage, JobAttachment
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from .models import Job, JobCategory, Skill
from .serializers import FeaturedJobSerializer
from employers.models import EmployerProfile
from skills.models import Skill
from utils.custom_pagination import CustomPagination
from utils.views import send_otp_to_email
from utils.file_upload import FileUploadService
import mimetypes
import logging

logger = logging.getLogger(__name__)

# Per-job file limits
MAX_IMAGES_PER_JOB = 3
MAX_ATTACHMENTS_PER_JOB = 5

class JobCategoriesListView(views.APIView):
    pagination_class = CustomPagination

    def get(self, request):
        categories = JobCategory.objects.all()
        paginator = self.pagination_class()
        paginated_categories = paginator.paginate_queryset(categories, request)
        serializer = JobCategorySerializer(paginated_categories, many=True)
        return Response(
            {
                "message": "Job categories retrieved successfully",
                "data": serializer.data
            },
            status=200
        )

class JobCategoryDetailView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request, category_id):
        try:
            category = JobCategory.objects.get(pk=category_id)
            serializer = JobCategorySerializer(category)
            return Response(
                {
                    "message": "Job category retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except JobCategory.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)
    
class CreateJobCategoryView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = JobCategorySerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            return Response(
                {
                    "message": "Job category created successfully",
                    "data": JobCategorySerializer(category).data
                },
                status=201
            )
        return Response(serializer.errors, status=400)

class UpdateJobCategoryView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def put(self, request, category_id):
        try:
            category = JobCategory.objects.get(pk=category_id)
            serializer = JobCategorySerializer(category, data=request.data)
            if serializer.is_valid():
                updated_category = serializer.save()
                return Response(
                    {
                        "message": "Job category updated successfully",
                        "data": JobCategorySerializer(updated_category).data
                    },
                    status=200
                )
            return Response(serializer.errors, status=400)
        except JobCategory.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)

class DeleteJobCategoryView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, category_id):
        try:
            category = JobCategory.objects.get(pk=category_id)
            category.delete()
            return Response({"message": "Category deleted successfully"}, status=204)
        except JobCategory.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)

class JobsInCategoryView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, category_id):
        try:
            category = JobCategory.objects.get(pk=category_id)
            jobs = category.jobs.all()
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serializer = JobSerializer(paginated_jobs, many=True, context={'request': request})
            return Response(
                {
                    "message": "Jobs in category retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except JobCategory.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)


#job endpoints
class JobListView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination 
    
    def get(self, request):
        jobs = Job.objects.filter(admin_approved=True)
        
        # Create paginator instance
        paginator = self.pagination_class()
        
        # Paginate the queryset
        paginated_jobs = paginator.paginate_queryset(jobs, request)
        
        # Serialize the paginated data
        serializer = JobSerializer(paginated_jobs, many=True, context={'request': request})
        
        # Return paginated response
        return paginator.get_paginated_response({
            "message": "Jobs retrieved successfully",
            "data": serializer.data
        })




class JobDetailView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id)
            serializer = JobSerializer(job, context={'request': request})
            return Response(
                {
                    "message": "Job retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)
        

class CreateJobView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # ── Validate category ──────────────────────────────────────────────
        category = None
        if 'category' in request.data:
            try:
                category = JobCategory.objects.get(pk=request.data['category'])
            except JobCategory.DoesNotExist:
                return Response({"error": "Category not found"}, status=404)

        # ── Validate employer profile ──────────────────────────────────────
        try:
            employer_profile = EmployerProfile.objects.get(user=request.user)
        except EmployerProfile.DoesNotExist:
            return Response({"error": "Employer profile not found"}, status=404)

        serializer = JobSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        job = serializer.save(employer=employer_profile, category=category)
        file_service = FileUploadService()

        # ── Optional: cover image (is_cover=True) ──────────────────────────
        cover_file = request.FILES.get('cover_image')
        extra_images = request.FILES.getlist('images')
        total_images = (1 if cover_file else 0) + len(extra_images)

        if total_images > MAX_IMAGES_PER_JOB:
            job.delete()
            return Response(
                {"error": f"A job may have at most {MAX_IMAGES_PER_JOB} images total "
                          f"(cover_image + images). You provided {total_images}."},
                status=400
            )

        if cover_file:
            try:
                url = file_service.upload(cover_file, subfolder='images')
                JobImage.objects.create(job=job, image_url=url, file_name=cover_file.name, is_cover=True)
            except ValueError as e:
                job.delete()
                return Response({"error": str(e)}, status=400)

        # ── Optional: extra images (is_cover=False) ────────────────────────
        for img in extra_images:
            try:
                url = file_service.upload(img, subfolder='images')
                JobImage.objects.create(job=job, image_url=url, file_name=img.name, is_cover=False)
            except ValueError as e:
                logger.warning(f"Image skipped ({img.name}): {e}")

        # ── Optional: attachments ──────────────────────────────────────────
        attachment_files = request.FILES.getlist('attachments')
        slots_available = MAX_ATTACHMENTS_PER_JOB - job.attachments.count()

        if len(attachment_files) > slots_available:
            job.delete()
            return Response(
                {"error": f"A job may have at most {MAX_ATTACHMENTS_PER_JOB} attachments. "
                          f"You tried to upload {len(attachment_files)} but only {slots_available} slot(s) remain."},
                status=400
            )

        for f in attachment_files:
            try:
                url = file_service.upload(f, subfolder='documents')
                mime_type, _ = mimetypes.guess_type(f.name)
                JobAttachment.objects.create(job=job, file_url=url, file_name=f.name, file_size=f.size, file_type=mime_type)
            except ValueError as e:
                logger.warning(f"Attachment skipped ({f.name}): {e}")

        # ── Notify ────────────────────────────────────────────────────────
        send_otp_to_email(
            user=request.user,
            otp_type='job_notification',
            action_type='created',
            job_title=job.title,
            job_status=job.get_status_display()
        )
        return Response(
            {"message": "Job created successfully", "data": JobSerializer(job, context={'request': request}).data},
            status=201
        )


class UpdateJobView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, job_id):
        # ── Fetch & authorize ──────────────────────────────────────────────
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)

        # Bug 1 fixed: ownership check
        if job.employer != request.user.employerprofile:
            return Response({"error": "You do not own this job"}, status=403)

        # Bug 2 fixed: partial=True so only sent fields are required
        serializer = JobSerializer(
            job, data=request.data, context={"request": request}, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        file_service = FileUploadService()

        with transaction.atomic():
            updated_job = serializer.save()

            # ── Optional: replace cover image (is_cover=True) ──────────────
            cover_file = request.FILES.get('cover_image')
            if cover_file:
                try:
                    new_url = file_service.upload(cover_file, subfolder='images')
                except ValueError as e:
                    return Response({"error": str(e)}, status=400)

                existing_cover = updated_job.images.filter(is_cover=True).first()
                if existing_cover:
                    file_service.remove(existing_cover.image_url)
                    existing_cover.delete()

                JobImage.objects.create(
                    job=updated_job,
                    image_url=new_url,
                    file_name=cover_file.name,
                    is_cover=True,
                )

            # ── Optional: add extra images (is_cover=False) ────────────────
            extra_images = request.FILES.getlist('images')
            if extra_images:
                existing_image_count = updated_job.images.count()
                slots_available = MAX_IMAGES_PER_JOB - existing_image_count
                if len(extra_images) > slots_available:
                    return Response(
                        {"error": f"Only {slots_available} image slot(s) remain (max {MAX_IMAGES_PER_JOB} total including cover)."},
                        status=400
                    )
                for img in extra_images:
                    try:
                        url = file_service.upload(img, subfolder='images')
                        JobImage.objects.create(job=updated_job, image_url=url, file_name=img.name, is_cover=False)
                    except ValueError as e:
                        logger.warning(f"Image skipped ({img.name}): {e}")

            # ── Optional: add attachments ──────────────────────────────────
            attachment_files = request.FILES.getlist("attachments")
            if attachment_files:
                existing_count = updated_job.attachments.count()
                slots_available = MAX_ATTACHMENTS_PER_JOB - existing_count
                if len(attachment_files) > slots_available:
                    return Response(
                        {"error": f"Only {slots_available} attachment slot(s) remain (max {MAX_ATTACHMENTS_PER_JOB})."},
                        status=400,
                    )

                upload_errors = []
                uploaded = []
                for f in attachment_files:
                    try:
                        url = file_service.upload(f, subfolder="documents")
                        mime_type, _ = mimetypes.guess_type(f.name)
                        uploaded.append(
                            JobAttachment(
                                job=updated_job,
                                file_url=url,
                                file_name=f.name,
                                file_size=f.size,
                                file_type=mime_type,
                            )
                        )
                    except ValueError as e:
                        upload_errors.append({"file": f.name, "error": str(e)})

                if upload_errors:
                    return Response({"errors": upload_errors}, status=400)

                JobAttachment.objects.bulk_create(uploaded)

        return Response(
            {"message": "Job updated successfully", "data": serializer.data},
            status=200,
        )

        

class DeleteJobView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id)
            job_title = job.title
            job.delete()
            # Send notification for job deletion
            send_otp_to_email(
                user=request.user, 
                otp_type='job_notification', 
                action_type='deleted',
                job_title=job_title
            )
            return Response({"message": "Job deleted successfully"}, status=204)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)

class JobSkillsView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id)
            job_skills = job.job_skills.all()
            serializer = JobSkillSerializer(job_skills, many=True)
            return Response(
                {
                    "message": "Job skills retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)

class UpdateJobStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id)
            status_val = request.data.get('status')
            if status_val not in [choice[0] for choice in Job.Status.choices]:
                return Response({"error": "Invalid status"}, status=400)
            job.status = status_val
            job.save()
            # Send notification for status update
            send_otp_to_email(
                user=request.user, 
                otp_type='job_notification', 
                action_type='updated',
                job_title=job.title,
                job_status=job.get_status_display()
            )
            return Response(
                {
                    "message": "Job status updated successfully",
                    "data": JobSerializer(job).data
                },
                status=200
            )
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)


class ToggleFeaturedJobView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, job_id):
        """
        Toggle the featured status of a job.
        Body: {"is_featured": true/false}
        """
        try:
            job = Job.objects.get(pk=job_id)
            is_featured = request.data.get('is_featured')
            
            if is_featured is None:
                return Response({
                    "error": "is_featured field is required"
                }, status=400)
            
            if not isinstance(is_featured, bool):
                return Response({
                    "error": "is_featured must be a boolean value"
                }, status=400)
            
            job.is_featured = is_featured
            job.save()
            
            return Response({
                "message": f"Job {'marked as featured' if is_featured else 'removed from featured'} successfully",
                "data": {
                    "id": str(job.id),
                    "title": job.title,
                    "is_featured": job.is_featured
                }
            }, status=200)
            
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)


class FeaturedJobsView(views.APIView):
    """
    GET /jobs/featured/ - List featured jobs with pagination
    """
    pagination_class = CustomPagination
    
    def get(self, request):
        try:
            # Query featured jobs with proper optimization
            featured_jobs = Job.objects.filter(
                is_featured=True,
                status='active',
                admin_approved=True,
                visibility='public'
            ).select_related(
                'employer__user',  # Optimize employer data access
                'category'
            ).order_by('-created_at')  # Show newest featured jobs first
            
            # Apply pagination
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(featured_jobs, request)
            
            # Serialize the paginated data
            serializer = FeaturedJobSerializer(paginated_jobs, many=True, context={'request': request})
            
            # Return paginated response
            return paginator.get_paginated_response({
                'message': 'Featured jobs retrieved successfully',
                'data': serializer.data
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to fetch featured jobs: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobsByEmployerView(views.APIView):
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = CustomPagination

        def get(self, request):
            employer_id = request.query_params.get('employer_id')
            if not employer_id:
                return Response({"error": "Employer ID is required"}, status=400)
            try:
                paginator = self.pagination_class()
                jobs = Job.objects.filter(employer=employer_id)
                paginated_jobs = paginator.paginate_queryset(jobs, request)
                serializer = JobSerializer(paginated_jobs, many=True)
                return Response(
                    {
                        "message": f"Jobs  retrieved successfully for employer {jobs[0].employer.user.full_name if jobs else 'Unknown'}",
                        "data": serializer.data
                    },
                    status=200
                )
            except Job.DoesNotExist:
                return Response({"error": "No jobs found for the given employer"}, status=404)
        
class ListJobsByCategoryView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, category_id):
        try:
            category = JobCategory.objects.get(pk=category_id)
            paginator = self.pagination_class()
            jobs = category.jobs.all()
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serializer = JobSerializer(paginated_jobs, many=True, context={'request': request})
            return Response(
                {
                    "message": f"Jobs in category '{category.name}' retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except JobCategory.DoesNotExist:
            return Response({"error": "Category not found"}, status=404)
        
#endpoint to get the employer who posted the job
class JobEmployerView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id)
            employer = job.employer
            return Response(
                {
                    "message": "Employer retrieved successfully",
                    "data": {
                        "id": employer.id,
                        "full_name": employer.user.full_name,
                        "email": employer.user.email
                    }
                },
                status=200
            )
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)

class ListJobsByFilterView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]
    paginator_class = CustomPagination
    def get(self, request):
        filters = {}
        for key in ['job_type', 'urgency_level', 'payment_type', 'status', 'visibility','location','category','title']:
            value = request.query_params.get(key)
            if value:
                filters[key] = value
        paginator = self.paginator_class()
        jobs = Job.objects.filter(**filters)
        paginated_jobs = paginator.paginate_queryset(jobs, request)
        serializer = JobSerializer(paginated_jobs, many=True, context={'request': request})
        return Response(
            {
                "message": "Filtered jobs retrieved successfully",
                "data": serializer.data
            },
            status=200
        )
    
#job skills endpoints
class JobSkillsListView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        job_skills = JobSkill.objects.all()
        serializer = JobSkillSerializer(job_skills, many=True)
        return Response(
            {
                "message": "Job skills retrieved successfully",
                "data": serializer.data
            }
        )
    
class JobSkillDetailView(views.APIView):
    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request, skill_id):
        try:
            job_skill = JobSkill.objects.get(pk=skill_id)
            serializer = JobSkillSerializer(job_skill)
            return Response(
                {
                    "message": "Job skill retrieved successfully",
                    "data": serializer.data
                },
                status=200
            )
        except JobSkill.DoesNotExist:
            return Response({"error": "Job skill not found"}, status=404)
        
class CreateJobSkillView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request,job_id):
        # Check if the job exists
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=404)
        serializer = JobSkillSerializer(data=request.data)
        #check if the skill is provided in the request data and if it is provided, check whether the skill exists and if it exists, give a response that the skill already exists for the job
        if 'skill' in request.data:
            #check wheater the skill exists in the database and if not , tell the user to provide a valid skill
            try:
                skill = Skill.objects.get(name=request.data['skill'])
                
            except Skill.DoesNotExist:
                return Response({"error": "Skill not found in the database, it needs to be added"}, status=404)
           
            
            #check if the skill already exists for the job and if it exists, give a response that the skill already exists for the job
            try:
                skills = JobSkill.objects.filter(job=job)
                #check if the skill already exists for the job
                for skill in skills:
            
                        if skill.skill.name.lower().strip() == request.data['skill'].lower().strip():

                            return Response({"error": "Skill already exists for this job"}, status=400)
                        

            except JobSkill.DoesNotExist:
                pass
            
        if serializer.is_valid():
            job_skill = serializer.save(job=job)
            return Response(
                {
                    "message": "Job skill created successfully",
                    "data": JobSkillSerializer(job_skill).data
                }
            )
        return Response(serializer.errors, status=400)
    
class UpdateJobSkillView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, skill_id):
        try:
            job_skill = JobSkill.objects.get(pk=skill_id)
            serializer = JobSkillSerializer(job_skill, data=request.data)
            if serializer.is_valid():
                updated_job_skill = serializer.save()
                return Response(
                    {
                        "message": "Job skill updated successfully",
                        "data": JobSkillSerializer(updated_job_skill).data
                    },
                    status=200
                )
            return Response(serializer.errors, status=400)
        except JobSkill.DoesNotExist:
            return Response({"error": "Job skill not found"}, status=404)
        
class DeleteJobSkillView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, skill_id):
        try:
            job_skill = JobSkill.objects.get(pk=skill_id)
            job_skill.delete()
            return Response({"message": "Job skill deleted successfully"}, status=204)
        except JobSkill.DoesNotExist:
            return Response({"error": "Job skill not found"}, status=404)


class SearchJobsView(views.APIView):
    """
    Comprehensive job search endpoint with full-text search, filtering, and sorting
    GET /jobs/search/ - Search jobs with multiple criteria
    """
    pagination_class = CustomPagination
    
    def get(self, request):
        try:
            # Validate query parameters
            query_serializer = JobSearchQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return Response({
                    'error': 'Invalid query parameters',
                    'details': query_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = query_serializer.validated_data
            
            # Start with base queryset - only approved, active, public jobs
            queryset = Job.objects.filter(
                admin_approved=True,
                status='active',
                visibility='public'
            ).select_related(
                'employer__user',
                'category'
            ).prefetch_related(
                'job_skills__skill'
            )
            
            # Full-text search on title and description
            search_query = validated_data.get('q', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
            
            # Filter by skills
            skills = validated_data.get('skills', [])
            if skills:
                # Try to determine if skills are UUIDs or names
                skill_filters = Q()
                for skill in skills:
                    # Check if it looks like a UUID
                    try:
                        from uuid import UUID
                        UUID(skill)
                        skill_filters |= Q(job_skills__skill__id=skill)
                    except (ValueError, AttributeError):
                        # Treat as skill name
                        skill_filters |= Q(job_skills__skill__name__iexact=skill)
                
                queryset = queryset.filter(skill_filters).distinct()
            
            # Filter by category
            category = validated_data.get('category')
            if category:
                queryset = queryset.filter(category_id=category)
            
            # Filter by location (case-insensitive partial match)
            location = validated_data.get('location', '').strip()
            if location:
                queryset = queryset.filter(location_text__icontains=location)
            
            # Filter by job type
            job_type = validated_data.get('job_type')
            if job_type:
                queryset = queryset.filter(job_type=job_type)
            
            # Filter by urgency level
            urgency_level = validated_data.get('urgency_level')
            if urgency_level:
                queryset = queryset.filter(urgency_level=urgency_level)
            
            # Filter by payment type
            payment_type = validated_data.get('payment_type')
            if payment_type:
                queryset = queryset.filter(payment_type=payment_type)
            
            # Filter by budget range
            budget_min = validated_data.get('budget_min')
            budget_max = validated_data.get('budget_max')
            
            if budget_min is not None:
                # Jobs where the minimum budget is at least the user's minimum
                queryset = queryset.filter(
                    Q(budget_min__gte=budget_min) | Q(budget_min__isnull=True)
                )
            
            if budget_max is not None:
                # Jobs where the maximum budget is at most the user's maximum
                queryset = queryset.filter(
                    Q(budget_max__lte=budget_max) | Q(budget_max__isnull=True)
                )
            
            # Sorting
            sort_by = validated_data.get('sort_by', 'created_at')
            order = validated_data.get('order', 'desc')
            
            # Map urgency levels to numeric values for sorting
            if sort_by == 'urgency_level':
                urgency_order = {
                    'urgent': 4,
                    'high': 3,
                    'medium': 2,
                    'low': 1
                }
                # For urgency, we'll sort in Python after fetching
                # This is a limitation of Django ORM for choice fields
                jobs_list = list(queryset)
                jobs_list.sort(
                    key=lambda x: urgency_order.get(x.urgency_level, 0),
                    reverse=(order == 'desc')
                )
                queryset = jobs_list
            else:
                # Apply database-level sorting
                order_prefix = '-' if order == 'desc' else ''
                queryset = queryset.order_by(f'{order_prefix}{sort_by}')
            
            # Apply pagination
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(queryset, request)
            
            # Serialize the paginated data
            serializer = JobSearchSerializer(paginated_jobs, many=True, context={'request': request})
            
            # Return paginated response
            return paginator.get_paginated_response({
                'message': 'Search completed successfully',
                'search_params': {
                    'query': search_query,
                    'skills': skills,
                    'location': location,
                    'filters_applied': {
                        'category': str(category) if category else None,
                        'job_type': job_type,
                        'urgency_level': urgency_level,
                        'payment_type': payment_type,
                        'budget_min': str(budget_min) if budget_min else None,
                        'budget_max': str(budget_max) if budget_max else None,
                    },
                    'sort_by': sort_by,
                    'order': order
                },
                'data': serializer.data
            })
            
        except Exception as e:
            return Response({
                'error': f'Search failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

