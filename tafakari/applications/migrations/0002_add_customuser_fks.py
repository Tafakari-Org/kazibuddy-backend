import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('applications', '0001_initial'),
    ]

    operations = [
        # JobApplication.worker has data (must be backfilled) — add a temp column.
        # unique_together references 'worker', so it must be cleared before we can
        # later remove that field.
        migrations.AlterUniqueTogether(
            name='jobapplication',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='worker_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='job_applications_new',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # WorkerInvitation has zero rows today — safe to retarget its FKs directly.
        migrations.AlterField(
            model_name='workerinvitation',
            name='worker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='worker_invitations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='workerinvitation',
            name='employer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='employer_invitations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
