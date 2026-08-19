import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0003_backfill_jobapplication_worker'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='jobapplication',
            name='worker',
        ),
        migrations.RenameField(
            model_name='jobapplication',
            old_name='worker_new',
            new_name='worker',
        ),
        migrations.AlterField(
            model_name='jobapplication',
            name='worker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='jobapplication',
            unique_together={('job', 'worker')},
        ),
    ]
