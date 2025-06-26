from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone

from base.models import BaseModel
from base.type_choices import (
    IdentityVerificationMethod,
    IdentityVerificationStatusOption,
    UserStatusOption,
    UserTypeOption,
    UserRoleOption,
)
from myproject import settings


# Create your models here.
class User(AbstractUser, BaseModel):
    email = models.EmailField(blank=True)
    image = models.URLField(blank=True)
    phone_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=15, choices=UserStatusOption.choices, default=UserStatusOption.ACTIVE
    )
    u_type = models.CharField(max_length=15, choices=UserTypeOption.choices)
    role = models.CharField(max_length=15, choices=UserRoleOption.choices, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    identity_verification_status = models.CharField(
        max_length=15,
        choices=IdentityVerificationStatusOption.choices,
        default=IdentityVerificationStatusOption.NOT_VERIFIED,
    )
    identity_verification_method = models.CharField(
        max_length=15, choices=IdentityVerificationMethod.choices, blank=True
    )
    identity_verification_images = models.JSONField(default=dict)
    identity_verification_reject_reason = models.TextField(blank=True)
    country_code = models.CharField(max_length=10, default="BD")
    avg_rating = models.FloatField(default=0)
    total_rating_sum = models.FloatField(default=0)
    total_rating_count = models.PositiveIntegerField(default=0)
    total_property = models.PositiveIntegerField(default=0)
    total_sell_amount = models.FloatField(default=0)
    wishlist_listings = ArrayField(models.PositiveBigIntegerField(), blank=True)
    points_balance = models.PositiveIntegerField(default=0, help_text="Points earned by guest users for spending and referrals.")

    is_available_for_cohosting = models.BooleanField(
        default=False,
        help_text="If True, this host is open to being contacted or found for co-hosting opportunities."
    )

    current_superhost_tier = models.CharField(
        max_length=20,
        choices=[(key, data['name']) for key, data in settings.SUPERHOST_TIERS.items()] + [(None, 'Not a Superhost')],
        null=True,
        blank=True,
        help_text="Current calculated Superhost tier "
    )
    superhost_metrics_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time Superhost metrics were calculated for this user"
    )

    host_referral_credit_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Claimable credit balance for HOSTS from referrals"
    )

    lifetime_referral_points_earned = models.PositiveIntegerField(
        default=0,
        help_text="Total points earned by this GUEST from all referral activities (as referrer)"
    )
    lifetime_referral_taka_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Total Taka earned by this HOST from all referral activities (as referrer or referred bonus)"
    )

    # avg_rating,

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "1. User"

    def get_current_superhost_tier_display(self):
        if self.current_superhost_tier and hasattr(settings, 'SUPERHOST_TIERS'):
            return settings.SUPERHOST_TIERS.get(self.current_superhost_tier, {}).get('name',
                                                                                     self.current_superhost_tier)
        return "Not a Superhost"

    def __str__(self):
        return self.username

    LIFETIME_REFERRAL_POINTS_CAP = getattr(settings, 'LIFETIME_REFERRAL_EARNINGS_CAP_POINTS', 10000)
    LIFETIME_REFERRAL_TAKA_CAP = getattr(settings, 'LIFETIME_REFERRAL_EARNINGS_CAP_TAKA', Decimal('10000.00'))

    def can_earn_more_referral_points(self, points_to_be_added: int) -> tuple[bool, int]:
        """Checks if the guest can earn more referral points and returns earnable amount."""
        if self.u_type != UserTypeOption.GUEST: return False, 0  # Only guests earn points this way

        # Ensure lifetime_referral_points_earned is not None
        current_lifetime_earned = self.lifetime_referral_points_earned or 0

        if current_lifetime_earned >= self.LIFETIME_REFERRAL_POINTS_CAP:
            return False, 0

        remaining_capacity = self.LIFETIME_REFERRAL_POINTS_CAP - current_lifetime_earned
        earnable_points = min(points_to_be_added, remaining_capacity)
        return earnable_points > 0, earnable_points

    def can_earn_more_referral_taka(self, taka_to_be_added: Decimal) -> tuple[bool, Decimal]:
        """Checks if the host can earn more referral Taka and returns earnable amount."""
        if self.u_type != UserTypeOption.HOST: return False, Decimal('0.00')  # Only hosts earn Taka this way

        # Ensure lifetime_referral_taka_earned is not None
        current_lifetime_earned = self.lifetime_referral_taka_earned or Decimal('0.00')

        if current_lifetime_earned >= self.LIFETIME_REFERRAL_TAKA_CAP:
            return False, Decimal('0.00')

        remaining_capacity = self.LIFETIME_REFERRAL_TAKA_CAP - current_lifetime_earned
        earnable_taka = min(taka_to_be_added, remaining_capacity)
        return earnable_taka > Decimal('0.00'), earnable_taka

    def get_current_superhost_tier_display(self):  # Keep this method
        if self.current_superhost_tier and hasattr(settings, 'SUPERHOST_TIERS'):
            return settings.SUPERHOST_TIERS.get(self.current_superhost_tier, {}).get('name',
                                                                                     self.current_superhost_tier)
        return "Not a Superhost"


class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    school = models.CharField(max_length=200, blank=True)
    work = models.CharField(max_length=200, blank=True)
    address = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(default=0)
    longitude = models.FloatField(default=0)
    bio = models.TextField(blank=True)
    languages = ArrayField(models.CharField(max_length=50), blank=True)
    emergency_contact = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "2. User Profile"

    def __str__(self):
        return str(self.pk)


class UserDTL(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    password = models.CharField(max_length=200)

# class UserReview(BaseModel):
#     review_giver = models.ForeignKey(
#         User, on_delete=models.PROTECT, related_name="review_giver"
#     )
#     review_receiver = models.ForeignKey(
#         User, on_delete=models.PROTECT, related_name="review_receiver"
#     )
#     review = models.TextField()
#     rating = models.PositiveIntegerField()


from django.db import models
from django.conf import settings
from django.utils import timezone
from base.models import BaseModel

class SuperhostStatusHistory(BaseModel):  #
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='superhost_history')

    tier_key = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Key of the achieved Superhost tier (e.g., SILVER, GOLD, NONE)"
    )
    tier_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Name of the achieved Superhost tier (e.g., Silver Host)"
    )

    assessment_period_start = models.DateField()
    assessment_period_end = models.DateField()
    status_achieved_on = models.DateTimeField(default=timezone.now)

    metrics_snapshot = models.JSONField(
        default=dict,
        help_text="Snapshot of host's metrics for the assessed period (review_score, hosted_days, etc.)"
    )

    class Meta:
        verbose_name = "Superhost Status History"
        verbose_name_plural = "Superhost Status Histories"
        ordering = ['-assessment_period_end', '-status_achieved_on']

        unique_together = ('host', 'assessment_period_start', 'assessment_period_end')

    def __str__(self):
        tier_display = self.tier_name or "No Tier Achieved"
        return f"{self.host.username} - {tier_display} (Q: {self.assessment_period_start.strftime('%Y-%m-%d')} to {self.assessment_period_end.strftime('%Y-%m-%d')})"
