from django.db import models


class UserTypeOption(models.TextChoices):
    """CONSTANT = DB_VALUE, USER_DISPLAY_VALUE"""

    HOST = "host", "host"
    GUEST = "guest", "guest"
    SYSTEM = "system", "system"


class UserRoleOption(models.TextChoices):
    SUPER_ADMIN = "super_admin", "super_admin"
    ADMIN = "admin", "admin"
    COORDINATOR = "coordinator", "coordinator"


class UserStatusOption(models.TextChoices):
    ACTIVE = "active", "active"
    DEACTIVATED = "deactivated", "deactivated"
    RESTRICTED = "restricted", "restricted"


class IdentityVerificationMethod(models.TextChoices):
    PASSPORT = "passport", "passport"
    NID = "nid", "nid"
    DRIVING_LICENSE = "driving_license", "driving_license"
    LIVE = "live", "live"


class IdentityVerificationStatusOption(models.TextChoices):
    PENDING = "pending", "pending"
    VERIFIED = "verified", "verified"
    NOT_VERIFIED = "not_verified", "not_verified"
    REJECTED = "rejected", "rejected"


class ListingStatusOption(models.TextChoices):
    IN_PROGRESS = "in_progress", "in_progress"
    UNPUBLISHED = "unpublished", "unpublished"
    PUBLISHED = "published", "published"
    RESTRICTED = "restricted", "restricted"


class ListingVerificationStatusOption(models.TextChoices):
    VERIFIED = "verified", "verified"
    UNVERIFIED = "unverified", "unverified"


class PlaceTypeOption(models.TextChoices):
    ENTIRE_PLACE = "entire_place", "entire_place"
    SINGLE_ROOM = "single_room", "single_room"
    SHARED_ROOM = "shared_room", "shared_room"


class AmenityTypeOption(models.TextChoices):
    REGULAR = "entire_place", "entire_place"
    STAND_OUT = "stand_out", "stand_out"
    SAFETY = "safety", "safety"


class PaymentStatusOption(models.TextChoices):
    UNPAID = "unpaid", "unpaid"
    PAID = "paid", "paid"
    FAILED = "failed", "failed"


class BookingStatusOption(models.TextChoices):
    INITIATED = "initiated", "initiated"
    CONFIRMED = "confirmed", "confirmed"
    CANCELLED = "cancelled", "cancelled"
    PENDING_CONFIRMATION = "pending_conf", "pending_conf"
    DECLINED = "declined", "declined"
    ACCEPTED = "accepted", "accepted"



class OnlinePaymentMethodOption(models.TextChoices):
    SSL_COMMERZ = "ssl_commerz", "ssl_commerz"


class OnlinePaymentStatusOption(models.TextChoices):
    INITIATED = "initiated", "initiated"
    COMPLETED = "completed", "completed"
    CANCELLED = "cancelled", "cancelled"
    REJECTED = "rejected", "rejected"
    VALID = "failed", "failed"
    PAID = "paid", "paid"


class ServiceChargeTypeOption(models.TextChoices):
    HOST_CHARGE = "host_charge", "host_charge"
    GUEST_CHARGE = "guest_charge", "guest_charge"


class ServiceChargeCalculationTypeOption(models.TextChoices):
    FLAT = "flat", "flat"
    PERCENTAGE = "percentage", "percentage"


class HostPaymentMethodOption(models.TextChoices):
    BKASH = "bkash", "bkash"
    NAGAD = "nagad", "nagad"
    ROCKET = "rocket", "rocket"
    BANK = "bank", "bank"


class BlogStatusOption(models.TextChoices):
    PUBLISHED = "published", "published"
    DRAFT = "draft", "DRAFT"


class NotificationEventTypeOption(models.TextChoices):
    BOOKING_REQUEST_DECLINED = "booking_decline", "booking_decline"
    BOOKING_REQUEST_ACCEPTED = "booking_accepted", "booking_accepted"
    BOOKING_REQUEST_CONF = "booking_conformation", "booking_conformation"
    BOOKING_CONFIRMED = "booking_confirmed", "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled", "booking_cancelled"
    BOOKING_INQUIRY = "booking_inquiry", "booking_inquiry"
    REVIEW = "review", "review"
    PAYMENT_METHOD = "payment_method", "payment_method"
    USER_VERIFICATION = "user_verification", "user_verification"
    PAYOUT = "payout", "payout"
    SIGN_UP = "sign_up", "sign_up"

    PRE_ARRIVAL = "pre_arrival", "Pre-Arrival Reminder"
    POST_BOOKING_GUEST = "post_booking_guest", "Post-Booking Guest Feedback"
    POST_BOOKING_HOST = "post_booking_host", "Post-Booking Host Feedback"


class NotificationTypeOption(models.TextChoices):
    ADMIN_NOTIFICATION = "admin_notification", "admin_notification"
    USER_NOTIFICATION = "user_notification", "user_notification"
