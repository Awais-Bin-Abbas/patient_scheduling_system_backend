# patient_scheduling_system/celery.py

import os
from celery import Celery

# Set Django settings module for Celery
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'patient_scheduling_system.settings'
)

# Create Celery app
app = Celery('patient_scheduling_system')

# Load config from Django settings using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')