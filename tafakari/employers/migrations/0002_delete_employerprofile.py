from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('employers', '0001_initial'),
        ('jobs', '0004_job_employer_swap'),
        ('applications', '0002_add_customuser_fks'),
        ('assignments', '0004_assignment_swap'),
    ]

    operations = [
        migrations.DeleteModel(
            name='EmployerProfile',
        ),
    ]
