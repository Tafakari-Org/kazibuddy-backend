from django.db import migrations, models


def migrate_user_types(apps, schema_editor):
    """Convert worker / employer / both → user."""
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(user_type__in=['worker', 'employer', 'both']).update(user_type='user')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Step 1: run the data migration first (while old choices are still valid)
        migrations.RunPython(migrate_user_types, migrations.RunPython.noop),

        # Step 2: shrink and update the choices list
        migrations.AlterField(
            model_name='customuser',
            name='user_type',
            field=models.CharField(
                choices=[
                    ('user', 'User'),
                    ('admin', 'Admin'),
                    ('super_admin', 'Super Admin'),
                ],
                default='user',
                max_length=50,
            ),
        ),
    ]
