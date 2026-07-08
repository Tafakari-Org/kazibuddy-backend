from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0002_workerskill_user'),
        ('applications', '0004_jobapplication_worker_swap'),
        ('assignments', '0004_assignment_swap'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WorkerProfile',
        ),
    ]
