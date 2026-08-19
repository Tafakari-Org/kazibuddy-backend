from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_worker(apps, schema_editor):
    JobApplication = apps.get_model('applications', 'JobApplication')
    WorkerProfile = apps.get_model('workers', 'WorkerProfile')
    JobApplication.objects.filter(worker__isnull=False).update(
        worker_new=Subquery(
            WorkerProfile.objects.filter(pk=OuterRef('worker_id')).values('user_id')[:1]
        )
    )
    if JobApplication.objects.filter(worker__isnull=False, worker_new__isnull=True).exists():
        raise RuntimeError('JobApplication.worker_new backfill left rows null — aborting migration.')


def reverse_backfill_worker(apps, schema_editor):
    JobApplication = apps.get_model('applications', 'JobApplication')
    JobApplication.objects.update(worker_new=None)


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0002_add_customuser_fks'),
        ('workers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_worker, reverse_backfill_worker),
    ]
