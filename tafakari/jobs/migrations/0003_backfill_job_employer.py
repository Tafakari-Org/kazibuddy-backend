from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_employer(apps, schema_editor):
    Job = apps.get_model('jobs', 'Job')
    EmployerProfile = apps.get_model('employers', 'EmployerProfile')
    Job.objects.filter(employer__isnull=False).update(
        employer_new=Subquery(
            EmployerProfile.objects.filter(pk=OuterRef('employer_id')).values('user_id')[:1]
        )
    )
    if Job.objects.filter(employer__isnull=False, employer_new__isnull=True).exists():
        raise RuntimeError('Job.employer_new backfill left rows null — aborting migration.')


def reverse_backfill_employer(apps, schema_editor):
    Job = apps.get_model('jobs', 'Job')
    Job.objects.update(employer_new=None)


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_job_employer_new'),
        ('employers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_employer, reverse_backfill_employer),
    ]
