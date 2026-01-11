# chronomail/celery.py
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chronomail.settings')
app = Celery('chronomail', broker=settings.CELERY_BROKER_URL)
app.autodiscover_tasks()

# core/tasks.py - обновление для Celery
from celery import shared_task

@shared_task
def send_time_capsule_async(capsule_id):
    return send_time_capsule(capsule_id)

@shared_task
def schedule_capsule_check():
    return check_and_send_pending_capsules()