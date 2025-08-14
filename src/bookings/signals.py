import logging

from django.utils import timezone

from django.core.files.base import ContentFile
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.conf import settings
from decimal import Decimal
from datetime import timedelta, datetime, time
# Booking and User models
from .models import Booking  # Make sure this path is correct
from django.contrib.auth import get_user_model

# Referral system models
from referrals.models import (
    Referral, ReferralType, ReferralStatus,
    ReferralReward, RewardStatus,
    Coupon as ReferralGeneratedCoupon,  # Alias for clarity
    CouponStatus as ReferralCouponStatus
)
# Admin coupon system model
from coupons.models import Coupon as AdminConfiguredCoupon  # Alias for clarity

# Type choices
from base.type_choices import UserTypeOption, BookingStatusOption  # Make sure this path is correct
from .views.invoice_service import generate_invoice_pdf_content, send_invoice_email

from notifications.task import send_pre_arrival_notification_task

User = get_user_model()

# --- Configuration for Referral Rewards (defaults if not in settings.py) ---
GUEST_POINTS_PER_TAKA_SPENT = Decimal(getattr(settings, 'GUEST_POINTS_PER_TAKA_SPENT', '0.01'))
HOST_REFERRAL_COMMISSION_RATE = Decimal(getattr(settings, 'HOST_REFERRAL_COMMISSION_RATE', '0.03'))


@receiver(post_save, sender=Booking)
@transaction.atomic  # Apply transaction to the entire signal handler
def handle_booking_updates(sender, instance: Booking, created: bool, **kwargs):
    """
    Combined signal handler for:
    1. Awarding referral points/commissions.
    2. Marking applied coupons as used.
    Triggered when a Booking instance is saved.
    """

    # --- Section 1: Referral Rewards Processing ---
    if instance.status == BookingStatusOption.CONFIRMED:
        # Idempotency check: has this booking's referral rewards part already run?
        # We use a temporary attribute on the instance for the current save cycle.
        if not getattr(instance, '_referral_rewards_processed_signal', False):
            process_referral_rewards(instance)
            instance._referral_rewards_processed_signal = True

    if instance.status == BookingStatusOption.CONFIRMED and \
        not getattr(instance, '_pre_arrival_scheduled_signal', False):


        day_before_check_in = instance.check_in - timedelta(days=1)

        if day_before_check_in >= timezone.now().date():  # Ensure target day is not in the past
            # Schedule for a specific time, e.g., 10:00 AM server's local time on that day
            target_send_datetime_naive = datetime.combine(day_before_check_in, time(10, 0, 0))

            if settings.USE_TZ:
                target_send_datetime_aware = timezone.make_aware(target_send_datetime_naive,
                                                                 timezone.get_default_timezone())
            else:
                target_send_datetime_aware = target_send_datetime_naive

            if target_send_datetime_aware > timezone.now():
                send_pre_arrival_notification_task.apply_async(
                    args=[instance.id],
                    eta=target_send_datetime_aware
                )
                print(
                    f"Signal: Scheduled pre-arrival notification for booking {instance.id} at {target_send_datetime_aware}")
            else:
                print(
                    f"Signal: Target pre-arrival time for booking {instance.id} ({target_send_datetime_aware}) is in the past. Not scheduling.")
        else:
            print(f"Signal: Day before check-in for booking {instance.id} is in the past. Not scheduling pre-arrival.")

        instance._pre_arrival_scheduled_signal = True


    if instance.status == BookingStatusOption.CONFIRMED and \
        instance.applied_coupon_code and \
        not getattr(instance, '_coupon_usage_processed_signal', False):  # Idempotency for coupon part

        print(
            f"Signal: Processing applied coupon for booking {instance.invoice_no} (Coupon Code: {instance.applied_coupon_code})")

        if instance.applied_coupon_type == 'referral' and instance.applied_referral_coupon_id:
            try:
                # Use select_for_update to lock the coupon row during update
                ref_coupon = ReferralGeneratedCoupon.objects.select_for_update().get(
                    id=instance.applied_referral_coupon_id)
                if ref_coupon.status == ReferralCouponStatus.ACTIVE:
                    # mark_as_used should ideally take booking and user who used it
                    ref_coupon.mark_as_used(user=instance.guest, booking=instance)
                    print(
                        f"Signal: Referral coupon {ref_coupon.code} marked as USED for booking {instance.invoice_no}.")
                else:
                    print(
                        f"Signal: Referral coupon {ref_coupon.code} was already not active for booking {instance.invoice_no} when trying to mark used.")
            except ReferralGeneratedCoupon.DoesNotExist:
                print(
                    f"Error in Signal: Applied referral coupon ID {instance.applied_referral_coupon_id} not found for booking {instance.invoice_no}.")
            except Exception as e:
                print(f"Error marking referral coupon used for booking {instance.invoice_no}: {e}")

        elif instance.applied_coupon_type == 'admin' and instance.applied_admin_coupon_id:
            try:
                admin_coupon = AdminConfiguredCoupon.objects.select_for_update().get(
                    id=instance.applied_admin_coupon_id)
                # Double check validity before incrementing (though is_valid was checked before applying)
                if admin_coupon.is_active and admin_coupon.uses_count < admin_coupon.max_use:

                    AdminConfiguredCoupon.objects.filter(pk=admin_coupon.pk).update(uses_count=F('uses_count') + 1)

                    # 2. Refresh the local Python instance to get the new value from the database
                    admin_coupon.refresh_from_db()

                    # 3. Now, check if the coupon should be deactivated based on the NEW usage count
                    if admin_coupon.uses_count >= admin_coupon.max_use:
                        admin_coupon.is_active = False
                        # A simple .save() is fine here as we are not using F() objects
                        admin_coupon.save(update_fields=['is_active', 'updated_at'])

                    print(
                        f"Signal: Admin coupon {admin_coupon.code} usage count incremented for booking {instance.invoice_no}. New count is {admin_coupon.uses_count}."
                    )
                else:
                    print(
                        f"Signal: Admin coupon {admin_coupon.code} was not active or limit reached for booking {instance.invoice_no} when trying to mark used.")


            except AdminConfiguredCoupon.DoesNotExist:

                print(

                    f"Error in Signal: Applied admin coupon ID {instance.applied_admin_coupon_id} not found for booking {instance.invoice_no}.")

            except Exception as e:

                # IMPORTANT: Re-raising the exception is better to ensure the transaction rolls back

                print(f"Error incrementing admin coupon usage for booking {instance.invoice_no}: {e}")

                raise  # This will cause the atomic transaction to fail and roll back, which is safer.

        instance._coupon_usage_processed_signal = True


def process_referral_rewards(instance: Booking):
    """
    Helper function for referral reward logic. Called by the main signal handler.
    - GUEST: Awards points to BOTH the referrer and the referred guest.
    - HOST: Awards commission to BOTH the referrer and the new host.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Signal: Processing referral rewards for booking {instance.invoice_no}")

    # --- I. Guest-to-Guest Referral: Both Referrer (A) and Referred (B) get points ---
    if not ReferralReward.objects.filter(booking=instance, referral__referral_type=ReferralType.GUEST_TO_GUEST).exists():
        booking_guest = instance.guest  # This is the referred user 'B'
        try:
            guest_referral = Referral.objects.select_related('referrer').get(
                referred_user=booking_guest,
                referral_type=ReferralType.GUEST_TO_GUEST,
                status__in=[ReferralStatus.SIGNED_UP, ReferralStatus.COMPLETED]
            )
            if guest_referral.is_active_for_rewards:
                potential_points = int(Decimal(str(instance.total_price)) * GUEST_POINTS_PER_TAKA_SPENT)
                if potential_points > 0:
                    # --- Award to Referrer (A) ---
                    referrer_user = guest_referral.referrer
                    if referrer_user and referrer_user.u_type == UserTypeOption.GUEST:
                        can_earn_ref, points_for_referrer = referrer_user.can_earn_more_referral_points(potential_points)
                        if can_earn_ref and points_for_referrer > 0:
                            User.objects.filter(pk=referrer_user.pk).update(
                                points_balance=F('points_balance') + points_for_referrer,
                                lifetime_referral_points_earned=F('lifetime_referral_points_earned') + points_for_referrer
                            )
                            ReferralReward.objects.create(referral=guest_referral, user=referrer_user, booking=instance, amount=Decimal(points_for_referrer), status=RewardStatus.CREDITED)
                            logger.info(f"Referrer (A) {referrer_user.username} earned {points_for_referrer} points from {booking_guest.username}'s booking.")

                    # --- Award to Referred Guest (B) ---
                    can_earn_new, points_for_new_guest = booking_guest.can_earn_more_referral_points(potential_points)
                    if can_earn_new and points_for_new_guest > 0:
                        User.objects.filter(pk=booking_guest.pk).update(
                            points_balance=F('points_balance') + points_for_new_guest,
                            lifetime_referral_points_earned=F('lifetime_referral_points_earned') + points_for_new_guest
                        )
                        ReferralReward.objects.create(referral=guest_referral, user=booking_guest, booking=instance, amount=Decimal(points_for_new_guest), status=RewardStatus.CREDITED)
                        logger.info(f"Referred Guest (B) {booking_guest.username} earned {points_for_new_guest} bonus points for their booking.")

                    # Update the referral link's booking count
                    guest_referral.rewarded_booking_count = F('rewarded_booking_count') + 1
                    guest_referral.save(update_fields=['rewarded_booking_count', 'updated_at'])
                    guest_referral.refresh_from_db()
                    if guest_referral.rewarded_booking_count >= guest_referral.max_rewardable_bookings:
                        guest_referral.status = ReferralStatus.COMPLETED
                        guest_referral.save(update_fields=['status', 'updated_at'])
        except Referral.DoesNotExist:
            pass  # No G2G referral for this guest
    else:
        logger.info(f"Booking {instance.invoice_no}: G2G referral rewards already processed.")

    # --- II. Host-to-Host Referral: Both Referrer and New Host get commission ---
    if not ReferralReward.objects.filter(booking=instance, referral__referral_type=ReferralType.HOST_TO_HOST).exists():
        property_host = instance.host
        if property_host.u_type == UserTypeOption.HOST:
            try:
                host_referral = Referral.objects.select_related('referrer').get(
                    referred_user=property_host,
                    referral_type=ReferralType.HOST_TO_HOST,
                    status__in=[ReferralStatus.HOST_ACTIVE, ReferralStatus.COMPLETED]
                )
                if host_referral.is_active_for_rewards:
                    commission_amount = (Decimal(str(instance.total_price)) * HOST_REFERRAL_COMMISSION_RATE).quantize(Decimal('0.01'))
                    if commission_amount > 0:
                        # --- Award to Original Referrer Host ---
                        referrer_host = host_referral.referrer
                        if referrer_host:
                            can_earn_ref, taka_for_referrer = referrer_host.can_earn_more_referral_taka(commission_amount)
                            if can_earn_ref and taka_for_referrer > 0:
                                User.objects.filter(pk=referrer_host.pk).update(
                                    host_referral_credit_balance=F('host_referral_credit_balance') + taka_for_referrer,
                                    lifetime_referral_taka_earned=F('lifetime_referral_taka_earned') + taka_for_referrer
                                )
                                ReferralReward.objects.create(referral=host_referral, user=referrer_host, booking=instance, amount=taka_for_referrer, status=RewardStatus.CREDITED)
                                logger.info(f"Referrer host {referrer_host.username} credited {taka_for_referrer} Taka for booking.")

                        # --- Award to Newly Referred Host ---
                        new_host = property_host
                        can_earn_new, taka_for_new_host = new_host.can_earn_more_referral_taka(commission_amount)
                        if can_earn_new and taka_for_new_host > 0:
                            User.objects.filter(pk=new_host.pk).update(
                                host_referral_credit_balance=F('host_referral_credit_balance') + taka_for_new_host,
                                lifetime_referral_taka_earned=F('lifetime_referral_taka_earned') + taka_for_new_host
                            )
                            ReferralReward.objects.create(referral=host_referral, user=new_host, booking=instance, amount=taka_for_new_host, status=RewardStatus.CREDITED)
                            logger.info(f"Newly referred host {new_host.username} credited {taka_for_new_host} Taka (bonus) for booking.")

                        # Update referral instance's booking count
                        host_referral.rewarded_booking_count = F('rewarded_booking_count') + 1
                        host_referral.save(update_fields=['rewarded_booking_count', 'updated_at'])
                        host_referral.refresh_from_db()
                        if host_referral.rewarded_booking_count >= host_referral.max_rewardable_bookings:
                            host_referral.status = ReferralStatus.COMPLETED
                            host_referral.save(update_fields=['status', 'updated_at'])
            except Referral.DoesNotExist:
                pass  # No H2H referral for this host
    else:
        logger.info(f"Booking {instance.invoice_no}: H2H referral rewards already processed.")


@receiver(post_save, sender=Booking)
@transaction.atomic
def handle_booking_lifecycle_events(sender, instance: Booking, created: bool, **kwargs):

    if instance.status == BookingStatusOption.CONFIRMED:
        if not getattr(instance, '_referral_rewards_processed_signal', False):

            instance._referral_rewards_processed_signal = True


    if instance.status == BookingStatusOption.CONFIRMED and \
        instance.applied_coupon_code and \
        not getattr(instance, '_coupon_usage_processed_signal', False):

        instance._coupon_usage_processed_signal = True


    # Assuming BookingStatusOption.COMPLETED signifies the booking is finished and invoice should be generated
    if instance.status == BookingStatusOption.CONFIRMED and not instance.invoice_pdf:

        print(f"Signal: Booking {instance.invoice_no} marked COMPLETED. Attempting invoice generation.")
        try:
            pdf_content = generate_invoice_pdf_content(instance)

            # Save PDF to model field
            file_name = f'Invoice_{instance.invoice_no}_{instance.id}.pdf'
            instance.invoice_pdf.save(file_name, ContentFile(pdf_content), save=False)  # save=False first
            instance.invoice_generated_at = timezone.now()
            instance.save(
                update_fields=['invoice_pdf', 'invoice_generated_at', 'updated_at'])  # Now save the model fields
            print(f"Signal: Invoice PDF saved for booking {instance.invoice_no}")

            # Send email with PDF (consider doing this in a Celery task for reliability)
            # send_invoice_email_task.delay(instance.id)
            send_invoice_email(instance, pdf_content)  # Synchronous for now

        except Exception as e:
            print(f"ERROR generating or sending invoice for booking {instance.invoice_no}: {e}")
