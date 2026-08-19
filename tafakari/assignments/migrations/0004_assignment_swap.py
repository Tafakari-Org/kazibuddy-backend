import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0003_backfill_assignment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assignment',
            name='worker',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='employer',
        ),
        migrations.RenameField(
            model_name='assignment',
            old_name='worker_new',
            new_name='worker',
        ),
        migrations.RenameField(
            model_name='assignment',
            old_name='employer_new',
            new_name='employer',
        ),
        migrations.AlterField(
            model_name='assignment',
            name='worker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='worker_assignments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='employer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='employer_assignments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='assignment',
            index=models.Index(fields=['worker'], name='assignments_worker__226652_idx'),
        ),
    ]
