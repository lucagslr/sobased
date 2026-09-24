"""Celery application. Tasks live in each app's tasks.py (autodiscovered)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("faiblegraine")
# Every CELERY_* Django setting configures Celery (beat schedule included).
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
