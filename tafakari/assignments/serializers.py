from rest_framework import serializers
from .models import Assignment, AssignmentCheckin, AssignmentMilestone


class AssignmentCheckinSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.user.full_name', read_only=True)

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
    worker_name = serializers.CharField(source='worker.user.full_name', read_only=True)
    employer_name = serializers.CharField(source='employer.user.full_name', read_only=True)
    checkins = AssignmentCheckinSerializer(
        many=True,
        read_only=True,
        source='assignmentcheckin_set'
    )
    milestones = AssignmentMilestoneSerializer(
        many=True,
        read_only=True,
        source='assignmentmilestone_set'
    )

    class Meta:
        model = Assignment
        fields = [
            'id', 'job', 'job_title', 'worker', 'worker_name',
            'employer', 'employer_name', 'application',
            'title', 'description', 'agreed_rate', 'payment_type',
            'start_date', 'end_date', 'estimated_hours', 'actual_hours',
            'status', 'completion_percentage',
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
        fields = [
            'job', 'worker', 'employer', 'application',
            'title', 'description', 'agreed_rate', 'payment_type',
            'start_date', 'end_date', 'estimated_hours',
        ]

    def validate(self, data):
        job = data.get('job')
        worker = data.get('worker')
        employer = data.get('employer')
        application = data.get('application')

        # 1. Verify worker profile exists
        from workers.models import WorkerProfile
        if not WorkerProfile.objects.filter(id=worker.id).exists():
            raise serializers.ValidationError({
                'worker': 'Worker profile does not exist.'
            })

        # 2. Verify application exists and belongs to the given worker
        if application:
            from applications.models import JobApplication
            try:
                app = JobApplication.objects.get(id=application.id)
            except JobApplication.DoesNotExist:
                raise serializers.ValidationError({
                    'application': 'Application does not exist.'
                })

            if app.worker != worker:
                raise serializers.ValidationError({
                    'application': 'This application does not belong to the given worker profile.'
                })

        # 3. Verify employer exists and the job belongs to that employer
        from employers.models import EmployerProfile
        if not EmployerProfile.objects.filter(id=employer.id).exists():
            raise serializers.ValidationError({
                'employer': 'Employer profile does not exist.'
            })

        if job.employer != employer:
            raise serializers.ValidationError({
                'employer': 'This job does not belong to the given employer.'
            })

        # 4. Prevent duplicate active assignments for the same job
        if Assignment.objects.filter(
            job=job,
            status__in=['assigned', 'in_progress', 'paused']
        ).exists():
            raise serializers.ValidationError({
                'job': 'This job already has an active assignment.'
            })

        # 5. Validate date range
        if data.get('end_date') and data['end_date'] < data['start_date']:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })

        return data

class UpdateAssignmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Assignment.STATUS_CHOICES)
    completion_percentage = serializers.IntegerField(min_value=0, max_value=100, required=False)

    def validate(self, data):
        instance = self.context.get('instance')
        new_status = data['status']

        # Define allowed transitions
        allowed_transitions = {
            'assigned': ['in_progress', 'cancelled'],
            'in_progress': ['paused', 'completed', 'disputed', 'cancelled'],
            'paused': ['in_progress', 'cancelled'],
            'completed': [],
            'cancelled': [],
            'disputed': ['in_progress', 'cancelled'],
        }

        if new_status not in allowed_transitions.get(instance.status, []):
            raise serializers.ValidationError({
                'status': f'Cannot transition from {instance.status} to {new_status}.'
            })

        return data


class UpdateAssignmentMilestoneSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AssignmentMilestone.STATUS_CHOICES)
    completion_notes = serializers.CharField(required=False, allow_blank=True)