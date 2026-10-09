from django.db import migrations


def seed(apps, schema_editor):
    # Carry over the contact details the footer used to hardcode; the phone was a placeholder.
    FooterSettings = apps.get_model('adminpanel', 'FooterSettings')
    FooterSettings.objects.get_or_create(pk=1, defaults={
        'email': 'support@kazibuddy.co.ke',
        'location': 'Nairobi, Kenya',
    })


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0002_footersettings_footersociallink_footercategory'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
