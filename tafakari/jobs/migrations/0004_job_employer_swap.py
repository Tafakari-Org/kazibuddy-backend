import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0003_backfill_job_employer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='employer',
        ),
        migrations.RenameField(
            model_name='job',
            old_name='employer_new',
            new_name='employer',
        ),
        migrations.AlterField(
            model_name='job',
            name='employer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='jobs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
