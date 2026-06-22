from rest_framework import serializers
from django.db.models import Count
from .models import Job, JobCategory, JobSkill, JobImage, JobAttachment
from skills.models import Skill
from employers.serializers import EmployerProfileSerializer


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

    def create(self, validated_data):
        return JobCategory.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()
        return instance


class JobSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobSkill
        fields = ['id', 'skill', 'job', 'is_required', 'experience_level']
        read_only_fields = ['id', 'job']
        extra_kwargs = {
            'is_required': {'required': False},
            'experience_level': {'required': False},
            'skill': {'required': False},
        }


class JobImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobImage
        fields = ['id', 'image_url', 'file_name', 'caption', 'is_cover', 'uploaded_at']
        read_only_fields = ['id', 'image_url', 'file_name', 'uploaded_at']


class JobAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAttachment
        fields = ['id', 'file_url', 'file_name', 'file_size', 'file_type', 'uploaded_at']
        read_only_fields = ['id', 'file_url', 'file_name', 'file_size', 'file_type', 'uploaded_at']


class JobSerializer(serializers.ModelSerializer):
    """Full serializer — use for detail/single job views only"""
    category = JobCategorySerializer(read_only=True)
    job_skills = JobSkillSerializer(many=True, read_only=True)
    employer = EmployerProfileSerializer(read_only=True)
    employer_name = serializers.CharField(source='employer.company_name', read_only=True)
    images = JobImageSerializer(many=True, read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'employer', 'employer_name', 'category', 'title', 'description', 'location',
            'location_text', 'job_type', 'urgency_level', 'budget_min',
            'budget_max', 'payment_type', 'start_date', 'end_date',
            'estimated_hours', 'max_applicants', 'status', 'visibility',
            'admin_approved', 'is_assigned', 'views_count', 'applications_count',
            'created_at', 'updated_at', 'expires_at', 'filled_at',
            'job_skills', 'images', 'attachments'
        ]
        extra_kwargs = {
            'estimated_hours': {'required': False}
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            data.pop('employer', None)
        return data

    def create(self, validated_data):
        skills_data = validated_data.pop('skills', [])
        validated_data['employer'] = self.context['request'].user.employerprofile
        job = Job.objects.create(**validated_data)
        self._create_job_skills(job, skills_data)
        return job

    def update(self, instance, validated_data):
        skills_data = validated_data.pop('skills', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if skills_data is not None:
            instance.job_skills.all().delete()
            self._create_job_skills(instance, skills_data)
        return instance

    def _create_job_skills(self, job, skills_data):
        # Use bulk_create instead of creating one by one
        JobSkill.objects.bulk_create([
            JobSkill(
                job=job,
                skill_id=skill_data.get('skill_id'),
                is_required=skill_data.get('is_required', True),
                experience_level=skill_data.get('experience_level', 'intermediate')
            )
            for skill_data in skills_data
        ])


class JobListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views (pending jobs, search results, etc.)
    Avoids heavy nested serialization — use this instead of JobSerializer in list endpoints.
    Images and attachments are prefetched on the queryset for zero N+1 overhead.
    """
    employer_name = serializers.CharField(source='employer.company_name', read_only=True)
    employer_id = serializers.UUIDField(source='employer.id', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_id = serializers.UUIDField(source='category.id', read_only=True)

    # Reads from annotation in the queryset — no extra query per row
    skills_count = serializers.IntegerField(read_only=True)

    # Prefetched in JobListView — no extra queries here
    images = JobImageSerializer(many=True, read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'description', 'employer_id', 'employer_name',
            'category_id', 'category_name', 'location_text', 'job_type',
            'urgency_level', 'budget_min', 'budget_max', 'payment_type',
            'status', 'admin_approved', 'is_assigned', 'views_count', 'applications_count',
            'skills_count', 'created_at', 'expires_at',
            'images', 'attachments',
        ]


class FeaturedJobSerializer(serializers.ModelSerializer):
    """Serializer for featured jobs"""
    employer_name = serializers.CharField(source='employer.company_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'description', 'employer_name', 'category_name', 'location_text',
            'job_type', 'urgency_level', 'budget_min', 'budget_max',
            'payment_type', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'employer': {'required': False},
            'category': {'required': False},
            'location': {'required': False},
            'location_text': {'required': False},
            'budget_min': {'required': False},
            'budget_max': {'required': False},
            'start_date': {'required': False},
            'end_date': {'required': False},
            'estimated_hours': {'required': False},
            'max_applicants': {'required': False},
            'status': {'required': False},
            'visibility': {'required': False},
            'description': {'required': False},
            'job_type': {'required': False},
            'payment_type': {'required': False},
        }

class AssignedJobListSerializer(JobListSerializer):
    """
    Extends JobListSerializer with assigned worker details.
    Used specifically in AssignedJobsByEmployerView.
    """
    worker_name = serializers.CharField(
        source='assignment.worker.user.full_name', 
        read_only=True
    )
    worker_id = serializers.UUIDField(
        source='assignment.worker.id', 
        read_only=True
    )

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + ['worker_name', 'worker_id']
    