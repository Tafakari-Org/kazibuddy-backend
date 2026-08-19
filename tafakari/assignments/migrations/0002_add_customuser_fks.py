import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assignments', '0001_initial'),
    ]

    operations = [
        # Assignment.worker/employer have data — add temp columns, backfill later.
        # The explicit index on 'worker' must be dropped before we remove that field.
        migrations.RemoveIndex(
            model_name='assignment',
            name='assignments_worker__226652_idx',
        ),
        migrations.AddField(
            model_name='assignment',
            name='worker_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='worker_assignments_new',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='assignment',
            name='employer_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='employer_assignments_new',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # AssignmentCheckin.worker has zero rows — safe to retarget directly.
        migrations.AlterField(
            model_name='assignmentcheckin',
            name='worker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='assignment_checkins',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
