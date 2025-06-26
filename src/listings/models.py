from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.gis.db.models import PointField
from django.contrib.gis.geos import Point
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from base.models import BaseModel
from base.type_choices import (
    AmenityTypeOption,
    ListingStatusOption,
    ListingVerificationStatusOption,
    PlaceTypeOption, UserTypeOption,
)
from django.utils import timezone
from configurations.data import default_cancellation_policy
from django.utils.translation import gettext_lazy as _

from myproject import settings

# Create your models here.
User = get_user_model()


class SuperhostTierChoices(models.TextChoices):
    SILVER = 'SILVER', 'Silver Host'
    GOLD = 'GOLD', 'Gold Host'
    PLATINUM = 'PLATINUM', 'Platinum Host'

class ListingSoftDeleteManager(models.Manager):
    def get_queryset(self):
        return ListingSoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class ListingSoftDeleteQuerySet(models.QuerySet):
    """
    QuerySet that supports soft delete operations for listings.
    """

    def delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(is_deleted=False, deleted_at=None)


class Category(BaseModel):
    name = models.CharField(max_length=200)
    icon = models.CharField(max_length=255)
    icon_mobile = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Listing Category"
        verbose_name_plural = "1. Listing Category"

    def __str__(self):
        return self.name


class Amenity(BaseModel):
    name = models.CharField(max_length=200)
    a_type = models.CharField(max_length=20, choices=AmenityTypeOption.choices)
    icon = models.CharField(max_length=255)
    icon_mobile = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Listing Amenity"
        verbose_name_plural = "2. Listing Amenities"

    def __str__(self):
        return self.name


class Listing(BaseModel):
    unique_id = models.UUIDField(unique=True)
    host = models.ForeignKey(User, on_delete=models.PROTECT)
    category = models.ForeignKey(
        "listings.Category", on_delete=models.PROTECT, null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.FloatField(default=0)
    cover_photo = models.URLField(blank=True)
    images = models.JSONField(default=list, blank=True)
    place_type = models.CharField(
        max_length=20, choices=PlaceTypeOption.choices, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=ListingStatusOption.choices,
        default=ListingStatusOption.IN_PROGRESS,
    )
    verification_status = models.CharField(
        max_length=20,
        choices=ListingVerificationStatusOption.choices,
        default=ListingVerificationStatusOption.UNVERIFIED,
    )
    guest_count = models.PositiveIntegerField(default=0)
    bedroom_count = models.PositiveIntegerField(default=0)
    bed_count = models.PositiveIntegerField(default=0)
    bathroom_count = models.PositiveIntegerField(default=0)
    minimum_nights = models.PositiveIntegerField(default=1)
    maximum_nights = models.PositiveIntegerField(default=30)
    address = models.CharField(max_length=200, blank=True)
    pet_allowed = models.BooleanField(default=False)
    event_allowed = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    media_allowed = models.BooleanField(default=False)
    unmarried_couples_allowed = models.BooleanField(default=False)
    cancellation_policy = models.JSONField(default=default_cancellation_policy)
    check_in = models.TimeField(default="12:00")
    check_out = models.TimeField(default="11:00")
    avg_rating = models.FloatField(default=0)
    total_rating_sum = models.FloatField(default=0)
    total_rating_count = models.PositiveIntegerField(default=0)
    total_booking_count = models.PositiveIntegerField(default=0)
    location = PointField(default=Point(0, 0))

    district = models.CharField(blank=True)
    division = models.CharField(blank=True)

    area = models.CharField(blank=True)
    city = models.CharField(blank=True)

    enable_length_of_stay_discount = models.BooleanField(default=False)
    length_of_stay_discounts = models.JSONField(
        default=dict,
        blank=True,
        help_text="Define discounts for longer stays, e.g., {\"3\": 5, \"7\": 10} for 5% off 3+ days, 10% off 7+ days."
    )


    instant_booking_allowed = models.BooleanField(default=False)
    require_guest_good_track_record = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = ListingSoftDeleteManager()
    all_objects = ListingSoftDeleteQuerySet.as_manager()

    class Meta:
        verbose_name = "Listing"
        verbose_name_plural = "3. Listing"

    @property
    def latitude(self) -> float:
        return self.location.x

    @property
    def longitude(self) -> float:
        return self.location.y

    def delete(self, using=None, keep_parents=False):
        """Override delete method to implement soft delete"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self, using=None, keep_parents=False):
        """Method to actually delete the record from the database"""
        super().delete(using, keep_parents)

    def restore(self):
        """Method to restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def clean(self):
        if self.require_guest_good_track_record and not self.instant_booking_allowed:
            raise ValidationError({
                'require_guest_good_track_record': _(
                    'Cannot require good track record if instant booking is not allowed.')
            })
        super().clean()

    def save(self, *args, **kwargs):
        if not self.instant_booking_allowed:
            self.require_guest_good_track_record = False
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ListingAmenity(BaseModel):
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT)
    amenity = models.ForeignKey("listings.Amenity", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Listing Amenity"
        verbose_name_plural = "4. Listing Amenity"

    def __str__(self):
        return str(self.pk)


class ListingCalendar(BaseModel):
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT)
    base_price = models.FloatField()
    custom_price = models.FloatField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_blocked = models.BooleanField(default=False)
    is_booked = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    booking_data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Listing Calendar"
        verbose_name_plural = "5. Listing Calendar"

    def __str__(self):
        return str(self.pk)


class CoHostAccessLevel(models.TextChoices):
    SEMI_ACCESS = 'semi', 'Semi Access'     # Limited permissions
    FULL_ACCESS = 'full', 'Full Access'     # Full permissions (like primary host for that listing)
    CUSTOM = 'custom', 'Custom Access'


class ListingCoHost(BaseModel): # Inherits created_at, updated_at
    listing = models.ForeignKey(
        'listings.Listing', # Use string reference if Listing is in the same app or to avoid circular import
        on_delete=models.CASCADE,
        related_name='cohost_assignments',
        null=True,
        blank=True,
    )
    co_host_user = models.ForeignKey( # The user who is the co-host
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cohosting_gigs',
        limit_choices_to={'u_type': UserTypeOption.HOST} # Co-hosts are also hosts
        ,null=True,blank=True
    )
    primary_host = models.ForeignKey( # The original owner of the listing
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_cohosts_to_listings'
        , null=True, blank=True
    )
    access_level = models.CharField(
        max_length=10,
        choices=CoHostAccessLevel.choices,
        default=CoHostAccessLevel.SEMI_ACCESS
    )
    commission_percentage = models.DecimalField(
        max_digits=5, # Allows up to 100.00%
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        default=Decimal('0.00'),
        help_text="Percentage of booking revenue (e.g., host payout) co-host receives for this listing."
        , null=True, blank=True
    )
    is_active = models.BooleanField(default=True, help_text="Is this co-hosting assignment currently active?")

    class Meta:
        unique_together = ('listing', 'co_host_user') # A user can only be a co-host once for a specific listing
        verbose_name = "Listing Co-Host Assignment"
        verbose_name_plural = "Listing Co-Host Assignments"

    def __str__(self):
        return f"{self.co_host_user.username} co-hosting {self.listing.title} ({self.get_access_level_display()})"

    def clean(self):
        super().clean()
        if self.listing.host == self.co_host_user:
            raise ValidationError("A host cannot assign themselves as a co-host to their own listing.")
        # Ensure primary_host matches listing.host if you keep this field
        if hasattr(self, '_primary_host_is_listing_host_check') and self.primary_host != self.listing.host:
             raise ValidationError("Primary host must be the owner of the listing.")

    def save(self, *args, **kwargs):
        # Automatically set primary_host if not provided and if listing is set
        if not self.primary_host_id and self.listing_id:
             self.primary_host = self.listing.host
        # Set a flag to perform the check only if primary_host was part of the instance or data.
        # This avoids error when self.listing.host is not yet available (e.g. during initial creation if listing is not set).
        self._primary_host_is_listing_host_check = True
        self.full_clean()
        delattr(self, '_primary_host_is_listing_host_check') # Clean up temporary attribute
        super().save(*args, **kwargs)
