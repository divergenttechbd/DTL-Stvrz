# import os
#
# from celery import Celery
# from celery.schedules import crontab
# from django.conf import settings
# from dotenv import load_dotenv
# from pathlib import Path
#
# BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
# env_path = BASE_DIR / ".env"
# print(env_path)
# load_dotenv(dotenv_path=env_path)
#
# print(" --- ",settings.BARIKOI_API_KEY)
#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
#
# celery_app = Celery("myproject")
#
# celery_app.config_from_object("django.conf:settings", namespace="CELERY")
#
# celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
#
# celery_app.conf.beat_schedule = {
#     'check-for-post-booking-notifications-daily': {
#         'task': 'notifications.tasks.check_and_send_post_booking_notifications_periodic',
#         'schedule': crontab(hour='3', minute='30'),
#     },
#     'assess-superhost-statuses-quarterly': {
#         'task': 'achievements.tasks.assess_and_log_quarterly_superhost_status',
#         'schedule': crontab(day_of_month='1', month_of_year='1,4,7,10', hour="2", minute="0"),
#     },
# }
# celery_app.conf.timezone = settings.TIME_ZONE

# ===================================================

import os
from celery import Celery
from celery.schedules import crontab
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# This part is fine, as it's setting up the environment for Django to find settings later.
# It doesn't access settings itself.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# --- THIS IS THE OLD, PROBLEMATIC CODE ---
# BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
# env_path = BASE_DIR / ".env"
# print(env_path) # Debugging print, can be removed
# load_dotenv(dotenv_path=env_path)
# print(" --- ", settings.BARIKOI_API_KEY) # <-- THIS IS THE CRASH POINT

# --- THE CORRECT APPROACH ---
# The load_dotenv() should happen in your settings entry point (like base.py or __init__.py)
# so it's loaded before ANY setting is accessed. Let's assume it's already loaded by the time
# Django starts up.

# Define the Celery app
celery_app = Celery("myproject")


celery_app.config_from_object("django.conf:settings", namespace="CELERY")

celery_app.autodiscover_tasks()


celery_app.conf.beat_schedule = {
    'check-for-post-booking-notifications-daily': {
        'task': 'check_and_send_post_booking_notifications_periodic',

        'schedule': crontab(hour='3', minute='30'),
        # 'schedule': timedelta(seconds=10),
    },
    'assess-superhost-statuses-quarterly': {
        'task': 'assess_and_log_quarterly_superhost_status',
        'schedule': crontab(day_of_month='1', month_of_year='1,4,7,10', hour="2", minute="0"),
    },
}

