import uuid
from datetime import date

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from celery import shared_task
from django.utils import timezone
from requests import RequestException

from accounts.models import User, SuperhostStatusHistory
from base.type_choices import UserTypeOption

from accounts.services import get_superhost_progress, get_previous_completed_quarter_start_end_dates, \
    calculate_host_review_score, calculate_hosted_days, calculate_cancellation_rate, get_superhost_progress_for_period
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


@shared_task(name="myproject.users.send_sms")
def send_sms(username: str, message: str) -> None:
    data = {
        "api_token": settings.SSL_TOKEN,
        "sid": settings.SSL_SID,
        "csms_id": uuid.uuid1().hex[:20],
        "sms": message,
        "msisdn": username,
    }
    res = requests.post(settings.SSL_URL, data=data)
    print(res.json())
    return

# def send_sms(username: str, message: str) -> None:
#     # Construct the SMS URL using the provided msisdn and message
#     sms_url = f"http://192.168.7.180:8080/bulk_sms_bd/sms_send_2?msisdn={username}&message={message}"
#
#     # Send the request to the Bulk SMS URL
#     try:
#         res = requests.get(sms_url, timeout=5)  # Add timeout to avoid hanging forever
#
#         print(message)
#
#         if res.status_code == 200:
#             print("SMS sent successfully.")
#         else:
#             print(f"Failed to send SMS. Status Code: {res.status_code}")
#
#     except RequestException as e:
#         # Handle any request-related exception (e.g., ConnectionError, Timeout, etc.)
#         print(f"Error sending SMS: {e}")



@shared_task(name="assess_and_log_quarterly_superhost_status")
def assess_and_log_quarterly_superhost_status():
    logger.info('Starting QUARTERLY Superhost status assessment process...')
    active_hosts = User.objects.filter(u_type=UserTypeOption.HOST, is_active=True)
    logger.info(f"Found {active_hosts.count()} active hosts to process.")

    updated_official_tier_count = 0
    history_logged_count = 0

    assess_period_start, assess_period_end = get_previous_completed_quarter_start_end_dates()
    logger.info(
        f"Assessing Superhost status for completed quarter: {assess_period_start.strftime('%Y-%m-%d')} to {assess_period_end.strftime('%Y-%m-%d')}")

    for host in active_hosts:
        logger.info(f"  Processing host: {host.username} (ID: {host.id})")
        try:
            assessment_data = get_superhost_progress_for_period(host, assess_period_start, assess_period_end)
            assessed_tier_key = assessment_data['achieved_tier_key']
            assessed_tier_name = settings.SUPERHOST_TIERS.get(assessed_tier_key, {}).get(
                'name') if assessed_tier_key else None
            metrics_for_assessment = assessment_data['metrics']

            # --- Logging to SuperhostStatusHistory ---
            history_entry, created = SuperhostStatusHistory.objects.update_or_create(
                host=host,
                assessment_period_start=assess_period_start,
                assessment_period_end=assess_period_end,
                defaults={
                    'tier_key': assessed_tier_key,
                    'tier_name': assessed_tier_name,
                    'status_achieved_on': timezone.now(),
                    'metrics_snapshot': {k: str(v) for k, v in metrics_for_assessment.items()}
                }
            )
            history_logged_count += 1
            action_taken = "Logged new" if created else "Updated existing"
            logger.info(f"    {action_taken} history for {host.username} - Tier: {assessed_tier_name or 'None'}")

            # --- Update User model's official tier ---
            if host.current_superhost_tier != assessed_tier_key:
                host.current_superhost_tier = assessed_tier_key
                host.superhost_metrics_updated_at = timezone.now()
                host.save(update_fields=['current_superhost_tier', 'superhost_metrics_updated_at'])
                updated_official_tier_count += 1
                logger.info(
                    f"    Updated official Superhost tier on User model for {host.username} to {assessed_tier_name or 'None'}.")
                # TODO: Send notification about official status change

        except Exception as e:
            logger.error(f"  Error processing Superhost status for {host.username}: {e}", exc_info=True)

    logger.info(
        f"Finished QUARTERLY Superhost status assessment. {updated_official_tier_count} official tiers updated. {history_logged_count} history records created/updated.")
