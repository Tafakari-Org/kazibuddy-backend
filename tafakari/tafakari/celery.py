# celery.py (same directory as settings.py)
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tafakari.settings')

app = Celery('tafakari')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
