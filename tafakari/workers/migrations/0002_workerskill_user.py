import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workers', '0001_initial'),
    ]

    operations = [
        # WorkerSkill has zero rows today — safe to rename+retarget directly.
        migrations.AlterUniqueTogether(
            name='workerskill',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='workerskill',
            name='worker_profile',
        ),
        migrations.AddField(
            model_name='workerskill',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='workerskill',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='workerskill',
            unique_together={('user', 'skill')},
        ),
    ]
