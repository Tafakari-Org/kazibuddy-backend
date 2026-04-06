from time import timezone
from .serializers import JobSerializer, JobCategorySerializer, JobSkillSerializer, JobImageSerializer, JobAttachmentSerializer,JobListSerializer
from .search_serializers import JobSearchSerializer, JobSearchQuerySerializer
from rest_framework import views, permissions, status
from .models import Job, JobCategory, JobSkill, JobImage, JobAttachment
from applications.models import JobApplication
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.db import DatabaseError,transaction
from django.db.models import Q, Count,Case,When,IntegerField,Prefetch
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
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
    pagination_class = CustomPagination

    def get(self, request):
        try:
            jobs = Job.objects.filter(admin_approved=True,is_assigned=False)\
                .select_related('employer', 'category')\
                .prefetch_related('images', 'attachments')\
                .annotate(skills_count=Count('job_skills'))\
                .order_by('-created_at')

            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(jobs, request)

            serializer = JobListSerializer(paginated_jobs, many=True, context={'request': request})

            return paginator.get_paginated_response({
                "message": "Jobs retrieved successfully",
                "data": serializer.data,
            })

        except DatabaseError as e:
            logger.error(f"Database error in JobListView: {e}", exc_info=True)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in JobListView: {e}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




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
                return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
 
        # ── Validate employer profile ──────────────────────────────────────
        try:
            employer_profile = EmployerProfile.objects.get(user=request.user)
        except EmployerProfile.DoesNotExist:
            return Response({"error": "Employer profile not found"}, status=status.HTTP_404_NOT_FOUND)
 
        # ── Validate payload before touching the DB ────────────────────────
        serializer = JobSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Pre-flight file checks (before any DB writes) ──────────────────
        cover_file = request.FILES.get('cover_image')
        extra_images = request.FILES.getlist('images')
        attachment_files = request.FILES.getlist('attachments')
        total_images = (1 if cover_file else 0) + len(extra_images)
 
        if total_images > MAX_IMAGES_PER_JOB:
            return Response(
                {"error": f"A job may have at most {MAX_IMAGES_PER_JOB} images total "
                           f"(cover_image + images). You provided {total_images}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        if len(attachment_files) > MAX_ATTACHMENTS_PER_JOB:
            return Response(
                {"error": f"A job may have at most {MAX_ATTACHMENTS_PER_JOB} attachments. "
                           f"You tried to upload {len(attachment_files)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # ── Atomic block: DB writes + file uploads together ────────────────
        # transaction.atomic() rolls back ALL DB writes if we raise inside.
        # Files live outside the DB, so we track every uploaded URL and clean
        # them up manually before re-raising on any failure.
        uploaded_urls = []
        file_service = FileUploadService()
 
        try:
            with transaction.atomic():
                job = serializer.save(employer=employer_profile, category=category)
 
                # Cover image
                if cover_file:
                    try:
                        url = file_service.upload(cover_file, subfolder='images')
                        uploaded_urls.append(url)
                        JobImage.objects.create(
                            job=job, image_url=url,
                            file_name=cover_file.name, is_cover=True,
                        )
                    except ValueError as e:
                        raise ValueError(str(e))
 
                # Extra images
                for img in extra_images:
                    try:
                        url = file_service.upload(img, subfolder='images')
                        uploaded_urls.append(url)
                        JobImage.objects.create(
                            job=job, image_url=url,
                            file_name=img.name, is_cover=False,
                        )
                    except ValueError as e:
                        raise ValueError(f"Image upload failed ({img.name}): {e}")
 
                # Attachments
                for f in attachment_files:
                    try:
                        url = file_service.upload(f, subfolder='documents')
                        uploaded_urls.append(url)
                        mime_type, _ = mimetypes.guess_type(f.name)
                        JobAttachment.objects.create(
                            job=job, file_url=url, file_name=f.name,
                            file_size=f.size, file_type=mime_type,
                        )
                    except ValueError as e:
                        raise ValueError(f"Attachment upload failed ({f.name}): {e}")
 
        except ValueError as e:
            # Clean up any files already written to storage before DB rolls back
            self._rollback_uploads(file_service, uploaded_urls)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
 
        except Exception as e:
            self._rollback_uploads(file_service, uploaded_urls)
            logger.error(f"Unexpected error in CreateJobView: {e}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
        # ── Notify ────────────────────────────────────────────────────────
        send_otp_to_email(
            user=request.user,
            otp_type='job_notification',
            action_type='created',
            job_title=job.title,
            job_status=job.get_status_display(),
        )
 
        return Response(
            {"message": "Job created successfully",
             "data": JobSerializer(job, context={'request': request}).data},
            status=status.HTTP_201_CREATED,
        )
 
    # ── Helper ─────────────────────────────────────────────────────────────
    @staticmethod
    def _rollback_uploads(file_service, urls):
        """Best-effort removal of already-uploaded files on failure."""
        for url in urls:
            try:
                file_service.remove(url)
            except Exception as ex:
                logger.warning(f"Could not remove file during rollback ({url}): {ex}")
 
 
class UpdateJobView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
 
    def put(self, request, job_id):
        # ── Fetch & authorize ──────────────────────────────────────────────
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
 
        if job.employer != request.user.employerprofile:
            return Response({"error": "You do not own this job"}, status=status.HTTP_403_FORBIDDEN)
 
        serializer = JobSerializer(
            job, data=request.data, context={"request": request}, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Pre-flight slot checks ─────────────────────────────────────────
        extra_images = request.FILES.getlist('images')
        attachment_files = request.FILES.getlist("attachments")
 
        if extra_images:
            existing_image_count = job.images.count()
            cover_file = request.FILES.get('cover_image')
            # cover replaces existing cover, so it doesn't consume an extra slot
            slots_available = MAX_IMAGES_PER_JOB - existing_image_count
            if len(extra_images) > slots_available:
                return Response(
                    {"error": f"Only {slots_available} image slot(s) remain "
                               f"(max {MAX_IMAGES_PER_JOB} total including cover)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
 
        if attachment_files:
            existing_count = job.attachments.count()
            slots_available = MAX_ATTACHMENTS_PER_JOB - existing_count
            if len(attachment_files) > slots_available:
                return Response(
                    {"error": f"Only {slots_available} attachment slot(s) remain "
                               f"(max {MAX_ATTACHMENTS_PER_JOB})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
 
        # ── Atomic block ───────────────────────────────────────────────────
        uploaded_urls = []
        replaced_cover_url = None
        file_service = FileUploadService()
 
        try:
            with transaction.atomic():
                updated_job = serializer.save()
 
                # Replace cover image
                cover_file = request.FILES.get('cover_image')
                if cover_file:
                    url = file_service.upload(cover_file, subfolder='images')
                    uploaded_urls.append(url)
 
                    existing_cover = updated_job.images.filter(is_cover=True).first()
                    if existing_cover:
                        replaced_cover_url = existing_cover.image_url
                        existing_cover.delete()
 
                    JobImage.objects.create(
                        job=updated_job, image_url=url,
                        file_name=cover_file.name, is_cover=True,
                    )
 
                # Add extra images
                for img in extra_images:
                    url = file_service.upload(img, subfolder='images')
                    uploaded_urls.append(url)
                    JobImage.objects.create(
                        job=updated_job, image_url=url,
                        file_name=img.name, is_cover=False,
                    )
 
                # Add attachments (bulk_create for efficiency)
                if attachment_files:
                    new_attachments = []
                    for f in attachment_files:
                        url = file_service.upload(f, subfolder="documents")
                        uploaded_urls.append(url)
                        mime_type, _ = mimetypes.guess_type(f.name)
                        new_attachments.append(JobAttachment(
                            job=updated_job, file_url=url, file_name=f.name,
                            file_size=f.size, file_type=mime_type,
                        ))
                    JobAttachment.objects.bulk_create(new_attachments)
 
        except ValueError as e:
            self._rollback_uploads(file_service, uploaded_urls)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
 
        except Exception as e:
            self._rollback_uploads(file_service, uploaded_urls)
            logger.error(f"Unexpected error in UpdateJobView: {e}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
        # ── Remove old cover from storage only after DB committed cleanly ──
        if replaced_cover_url:
            try:
                file_service.remove(replaced_cover_url)
            except Exception as e:
                logger.warning(f"Old cover not removed from storage ({replaced_cover_url}): {e}")
 
        return Response(
            {"message": "Job updated successfully", "data": serializer.data},
            status=status.HTTP_200_OK,
        )
 
    @staticmethod
    def _rollback_uploads(file_service, urls):
        for url in urls:
            try:
                file_service.remove(url)
            except Exception as ex:
                logger.warning(f"Could not remove file during rollback ({url}): {ex}")
 
 
class DeleteJobView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
 
    def delete(self, request, job_id):
        try:
            job = Job.objects.prefetch_related('images', 'attachments').get(pk=job_id)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
 
        # ── Ownership check ────────────────────────────────────────────────
        if job.employer.user != request.user:
            return Response({"error": "You do not own this job"}, status=status.HTTP_403_FORBIDDEN)
 
        job_title = job.title
        file_service = FileUploadService()
 
        # ── Collect file URLs before deleting the DB record ────────────────
        image_urls = [img.image_url for img in job.images.all() if img.image_url]
        attachment_urls = [att.file_url for att in job.attachments.all() if att.file_url]
 
        # ── Delete DB record atomically (cascades to images & attachments) ─
        # Files are intentionally removed AFTER a successful DB delete.
        # If the DB delete fails, the transaction rolls back and we keep the files.
        # If file removal fails after a successful DB delete, we log and continue
        # (orphaned files are preferable to a partially-deleted job record).
        try:
            with transaction.atomic():
                job.delete()
        except Exception as e:
            logger.error(f"Failed to delete job {job_id} from DB: {e}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
        # ── Remove physical files (best-effort, outside the transaction) ───
        for url in image_urls:
            try:
                deleted = file_service.remove(url)
                if not deleted:
                    logger.warning(f"Image file not found on storage (job={job_id}): {url}")
            except Exception as e:
                logger.error(f"Failed to delete image (job={job_id}, url={url}): {e}", exc_info=True)
 
        for url in attachment_urls:
            try:
                deleted = file_service.remove(url)
                if not deleted:
                    logger.warning(f"Attachment file not found on storage (job={job_id}): {url}")
            except Exception as e:
                logger.error(f"Failed to delete attachment (job={job_id}, url={url}): {e}", exc_info=True)
 
        # ── Notify ────────────────────────────────────────────────────────
        send_otp_to_email(
            user=request.user,
            otp_type='job_notification',
            action_type='deleted',
            job_title=job_title,
        )
 
        return Response({"message": "Job deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

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
    pagination_class = CustomPagination

    def get(self, request):
        try:
            featured_jobs = Job.objects.filter(
                is_featured=True,
                is_assigned=False,
                status='active',
                admin_approved=True,
                visibility='public'
            ).select_related(
                'employer',
                'category'
            ).order_by('-created_at')

            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(featured_jobs, request)

            serializer = FeaturedJobSerializer(paginated_jobs, many=True, context={'request': request})

            return paginator.get_paginated_response({
                'message': 'Featured jobs retrieved successfully',
                'data': serializer.data
            })

        except DatabaseError as e:
            logger.error(f"Database error in FeaturedJobsView: {e}", exc_info=True)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in FeaturedJobsView: {e}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class JobsByEmployerView(views.APIView):
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = CustomPagination

        def get(self, request):
            employer_id = request.query_params.get('employer_id')
            if not employer_id:
                return Response({"error": "Employer ID is required"}, status=400)
            try:
                paginator = self.pagination_class()
                jobs = Job.objects.filter(employer=employer_id, is_assigned=False)
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
            jobs = category.jobs.filter(is_assigned=False)
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
        jobs = Job.objects.filter(**filters, is_assigned=False,admin_approved=True)
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
    Comprehensive job search endpoint with full-text search, filtering, and sorting.
    GET /jobs/search/
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

            # Base queryset — only approved, active, public jobs
            # .only() limits columns fetched from DB
            queryset = Job.objects.filter(
                admin_approved=True,
                is_assigned=False,
            ).select_related(
                'employer__user',
                'category'
            ).prefetch_related(
                'job_skills__skill'         # double underscore — populates skill cache used by serializer
            )

            # --- Full-text search ---
            search_query = validated_data.get('q', '').strip()
            if search_query:
                search = SearchQuery(search_query)
                queryset = (
                    queryset
                    .filter(search_vector=search)
                    .annotate(rank=SearchRank('search_vector', search))
                    .order_by('-rank')  #order by relevance
                )

            # --- Skill filtering (bulk __in instead of per-skill Q loop) ---
            skills = validated_data.get('skills', [])
            if skills:
                skill_ids, skill_names = [], []
                for skill in skills:
                    try:
                        skill_ids.append(UUID(skill))
                    except (ValueError, AttributeError):
                        skill_names.append(skill)

                skill_filters = Q()
                if skill_ids:
                    skill_filters |= Q(job_skills__skill__id__in=skill_ids)
                if skill_names:
                    skill_filters |= Q(job_skills__skill__name__in=skill_names)

                queryset = queryset.filter(skill_filters).distinct()

            # --- Category filter ---
            category = validated_data.get('category')
            if category:
                queryset = queryset.filter(category_id=category)

            # --- Location filter ---
            location = validated_data.get('location', '').strip()
            if location:
                queryset = queryset.filter(location_text__icontains=location)

            # --- Job type filter ---
            job_type = validated_data.get('job_type')
            if job_type:
                queryset = queryset.filter(job_type=job_type)

            # --- Urgency level filter ---
            urgency_level = validated_data.get('urgency_level')
            if urgency_level:
                queryset = queryset.filter(urgency_level=urgency_level)

            # --- Payment type filter ---
            payment_type = validated_data.get('payment_type')
            if payment_type:
                queryset = queryset.filter(payment_type=payment_type)

            # --- Budget range filter ---
            budget_min = validated_data.get('budget_min')
            budget_max = validated_data.get('budget_max')

            if budget_min is not None:
                queryset = queryset.filter(
                    Q(budget_min__gte=budget_min) | Q(budget_min__isnull=True)
                )
            if budget_max is not None:
                queryset = queryset.filter(
                    Q(budget_max__lte=budget_max) | Q(budget_max__isnull=True)
                )

            # --- Sorting ---
            sort_by = validated_data.get('sort_by', 'created_at')
            order = validated_data.get('order', 'desc')
            order_prefix = '-' if order == 'desc' else ''

            if sort_by == 'urgency_level':
                # Case/When annotation avoids loading the full queryset into memory
                urgency_rank = Case(
                    When(urgency_level='urgent', then=4),
                    When(urgency_level='high', then=3),
                    When(urgency_level='medium', then=2),
                    When(urgency_level='low', then=1),
                    default=0,
                    output_field=IntegerField()
                )
                queryset = queryset.annotate(urgency_rank=urgency_rank).order_by(f'{order_prefix}urgency_rank')
            elif not search_query:
                # Don't override relevance ordering when a search query is active
                queryset = queryset.order_by(f'{order_prefix}{sort_by}')

            # --- Pagination ---
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(queryset, request)

            serializer = JobSearchSerializer(paginated_jobs, many=True, context={'request': request})

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

#get total jobs
class TotalJobsView(views.APIView):
    def get(self, request):
        try:
            total_jobs = Job.objects.filter(admin_approved=True, status='active').count()
            return Response({
                'message': 'Total jobs fetched successfully',
                "data": total_jobs
                },status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'message': 'Failed to get total jobs',
                'error': f'Failed to get total jobs: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#total job categories
class TotalJobCategoriesView(views.APIView):
    def get(self, request):
        try:
            total_job_categories = JobCategory.objects.count()
            return Response({
                'message': 'Total job categories fetched successfully',
                "data": total_job_categories
                },status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'message': 'Failed to get total job categories',
                'error': f'Failed to get total job categories: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#list jobs with applications
class ListJobsWithApplicationsView(views.APIView):
    permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            jobs = (
                Job.objects
                .annotate(
                    total_applications=Count('jobapplication', distinct=True),
                    skills_count=Count('job_skills', distinct=True),  # required by JobListSerializer
                )
                .filter(total_applications__gt=0)
                .select_related('employer', 'category')       # flattens FK lookups into one query
                .prefetch_related('images', 'attachments')    # required by JobListSerializer
                .only(                                        # fetch only columns the serializer uses
                    'id', 'title', 'description', 'location_text', 'job_type',
                    'urgency_level', 'budget_min', 'budget_max', 'payment_type',
                    'status', 'admin_approved', 'views_count', 'applications_count',
                    'created_at', 'expires_at',
                    'employer__id', 'employer__company_name',
                    'category__id', 'category__name',
                )
                .order_by('-created_at')
            )
            #pagination
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serializer = JobListSerializer(paginated_jobs, many=True)

            return Response(
                {
                    "message": "Jobs with applications fetched successfully",
                    "count": jobs.count(),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "message": "Failed to fetch jobs with applications",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

#list draft jobs
class ListDraftJobsView(views.APIView):
    # permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            jobs = (
                Job.objects
                .annotate(
                    total_applications=Count('jobapplication', distinct=True),
                    skills_count=Count('job_skills', distinct=True),  # required by JobListSerializer
                )
                .filter(status='draft')
                .select_related('employer', 'category')       # flattens FK lookups into one query
                .prefetch_related('images', 'attachments')    # required by JobListSerializer
                .only(                                        # fetch only columns the serializer uses
                    'id', 'title', 'description', 'location_text', 'job_type',
                    'urgency_level', 'budget_min', 'budget_max', 'payment_type',
                    'status', 'admin_approved', 'views_count', 'applications_count',
                    'created_at', 'expires_at',
                    'employer__id', 'employer__company_name',
                    'category__id', 'category__name',
                )
                .order_by('-created_at')
            )
            #pagination
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serializer = JobListSerializer(paginated_jobs, many=True)

            return Response(
                {
                    "message": "Draft jobs fetched successfully",
                    "count": jobs.count(),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "message": "Failed to fetch draft jobs",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

#list active jobs
class ListActiveJobsView(views.APIView):
    # permission_classes = [IsAdminUser]
    pagination_class = CustomPagination

    def get(self, request):
        try:
            jobs = (
                Job.objects
                .annotate(
                    total_applications=Count('jobapplication', distinct=True),
                    skills_count=Count('job_skills', distinct=True),  # required by JobListSerializer
                )
                .filter(status='active')
                .select_related('employer', 'category')       # flattens FK lookups into one query
                .prefetch_related('images', 'attachments')    # required by JobListSerializer
                .only(                                        # fetch only columns the serializer uses
                    'id', 'title', 'description', 'location_text', 'job_type',
                    'urgency_level', 'budget_min', 'budget_max', 'payment_type',
                    'status', 'admin_approved', 'views_count', 'applications_count',
                    'created_at', 'expires_at',
                    'employer__id', 'employer__company_name',
                    'category__id', 'category__name',
                )
                .order_by('-created_at')
            )
            #pagination
            paginator = self.pagination_class()
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serializer = JobListSerializer(paginated_jobs, many=True)

            return Response(
                {
                    "message": "Active jobs fetched successfully",
                    "count": jobs.count(),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "message": "Failed to fetch active jobs",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )