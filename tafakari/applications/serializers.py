from .models import JobApplication, WorkerInvitation
from jobs.serializers import JobSerializer
from workers.serializers import WorkerProfileSerializer

from rest_framework import serializers

class JobApplicationSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)
    worker = WorkerProfileSerializer(read_only=True)
    class Meta:
        model = JobApplication
        fields = '__all__'
        read_only_fields = ('id', 'applied_at', 'reviewed_at', 'responded_at','status','worker')
        extra_kwargs = {
            'proposed_rate': {'required': True, 'min_value': 0},
            'availability_start': {'required': True},
            'cover_letter': {'required': False, 'allow_blank': True},
            'worker_notes': {'required': False, 'allow_blank': True},
            'employer_notes': {'required': False, 'allow_blank': True},
            'job': {'required': False, 'write_only': False},
        }
        def validate(self, data):
            if data['proposed_rate'] < 0:
                raise serializers.ValidationError("Proposed rate must be a non-negative value.")
            return data
        def create(self, validated_data):
            # Automatically set the worker from the request context
            validated_data['worker'] = self.context['request'].user.workerprofile
            return super().create(validated_data)


class JobApplicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing applications — avoids heavy nested serializers"""
    # Job fields — flat, no nested JobSerializer
    job_id = serializers.UUIDField(source='job.id', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    job_type = serializers.CharField(source='job.job_type', read_only=True)
    job_budget_min = serializers.DecimalField(source='job.budget_min', max_digits=10, decimal_places=2, read_only=True)
    job_budget_max = serializers.DecimalField(source='job.budget_max', max_digits=10, decimal_places=2, read_only=True)
    employer_name = serializers.CharField(source='job.employer.company_name', read_only=True)

    # Worker fields — flat, no nested WorkerProfileSerializer
    worker_id = serializers.UUIDField(source='worker.id', read_only=True)
    worker_name = serializers.CharField(source='worker.user.get_full_name', read_only=True)  # adjust as needed

    class Meta:
        model = JobApplication
        fields = [
            'id', 'status', 'proposed_rate', 'availability_start',
            'cover_letter', 'applied_at', 'reviewed_at', 'responded_at',
            'job_id', 'job_title', 'job_type', 'job_budget_min', 'job_budget_max', 'employer_name',
            'worker_id', 'worker_name',
        ]

#list workers applied to a job
class JobApplicationWorkerSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)

    class Meta:
        model = JobApplication
        fields = ['id', 'worker']
    