from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_assignment(apps, schema_editor):
    Assignment = apps.get_model('assignments', 'Assignment')
    WorkerProfile = apps.get_model('workers', 'WorkerProfile')
    EmployerProfile = apps.get_model('employers', 'EmployerProfile')

    Assignment.objects.filter(worker__isnull=False).update(
        worker_new=Subquery(
            WorkerProfile.objects.filter(pk=OuterRef('worker_id')).values('user_id')[:1]
        )
    )
    Assignment.objects.filter(employer__isnull=False).update(
        employer_new=Subquery(
            EmployerProfile.objects.filter(pk=OuterRef('employer_id')).values('user_id')[:1]
        )
    )

    if Assignment.objects.filter(worker__isnull=False, worker_new__isnull=True).exists():
        raise RuntimeError('Assignment.worker_new backfill left rows null — aborting migration.')
    if Assignment.objects.filter(employer__isnull=False, employer_new__isnull=True).exists():
        raise RuntimeError('Assignment.employer_new backfill left rows null — aborting migration.')


def reverse_backfill_assignment(apps, schema_editor):
    Assignment = apps.get_model('assignments', 'Assignment')
    Assignment.objects.update(worker_new=None, employer_new=None)


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0002_add_customuser_fks'),
        ('workers', '0001_initial'),
        ('employers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_assignment, reverse_backfill_assignment),
    ]
