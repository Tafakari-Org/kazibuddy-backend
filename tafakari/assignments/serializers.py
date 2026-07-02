from rest_framework import serializers
from .models import Assignment, AssignmentCheckin, AssignmentMilestone


class AssignmentCheckinSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)

    class Meta:
        model = AssignmentCheckin
        fields = [
            'id', 'assignment', 'worker', 'worker_name',
            'checkin_type', 'location', 'location_text',
            'notes', 'photo_url', 'checkin_time',
        ]
        read_only_fields = ['id', 'checkin_time']


class AssignmentMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentMilestone
        fields = [
            'id', 'assignment', 'title', 'description',
            'due_date', 'status', 'completion_notes',
            'completed_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']


class AssignmentSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    job_payment_type = serializers.CharField(source='job.payment_type', read_only=True)
    job_start_date = serializers.DateField(source='job.start_date', read_only=True)
    job_end_date = serializers.DateField(source='job.end_date', read_only=True)
    job_budget_min = serializers.DecimalField(source='job.budget_min', max_digits=10, decimal_places=2, read_only=True)
    job_budget_max = serializers.DecimalField(source='job.budget_max', max_digits=10, decimal_places=2, read_only=True)
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)
    employer_name = serializers.CharField(source='employer.full_name', read_only=True)
    checkins = AssignmentCheckinSerializer(many=True, read_only=True)
    milestones = AssignmentMilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'job', 'job_title', 'job_payment_type',
            'job_start_date', 'job_end_date',
            'job_budget_min', 'job_budget_max',
            'worker', 'worker_name',
            'employer', 'employer_name',
            'worker_started_at', 'worker_completed_at', 'employer_approved_at',
            'created_at', 'updated_at',
            'checkins', 'milestones',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'worker_started_at', 'worker_completed_at', 'employer_approved_at',
        ]


class CreateAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ['job', 'worker', 'employer']

    def validate(self, data):
        job = data.get('job')
        worker = data.get('worker')
        employer = data.get('employer')

        # 1. A user cannot be assigned to their own job
        if worker == employer:
            raise serializers.ValidationError({
                'worker': 'A user cannot be assigned as the worker on their own job.'
            })

        # 2. Verify job belongs to the given employer
        if job.employer != employer:
            raise serializers.ValidationError({
                'employer': 'This job does not belong to the given employer.'
            })

        # 3. Prevent duplicate assignment for the same job
        if Assignment.objects.filter(job=job).exists():
            raise serializers.ValidationError({
                'job': 'This job already has an assignment.'
            })

        return data


class UpdateAssignmentMilestoneSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AssignmentMilestone.STATUS_CHOICES)
    completion_notes = serializers.CharField(required=False, allow_blank=True)