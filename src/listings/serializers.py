from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from rest_framework.fields import BooleanField
from rest_framework.serializers import (
    Serializer,
    ValidationError,
    ChoiceField,
    FloatField,
)

User = get_user_model()
from accounts.serializers import UserSerializer
from base.serializers import DynamicFieldsModelSerializer
from base.type_choices import UserTypeOption
from listings.models import Listing, ListingAmenity, Category, CoHostAccessLevel, ListingCoHost
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

class CategorySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"



class UserSerializerX(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "image", "identity_verification_status", "status", "current_superhost_tier"]


class ListingSerializer(DynamicFieldsModelSerializer):
    latitude = FloatField(source="location.y", read_only=True)
    longitude = FloatField(source="location.x", read_only=True)
    instant_booking_allowed = BooleanField(required=False)
    require_guest_good_track_record = BooleanField(required=False)
    category_name = serializers.SerializerMethodField()



    enable_length_of_stay_discount = serializers.BooleanField(required=False)
    length_of_stay_discounts = serializers.JSONField(required=False)

    class Meta:
        model = Listing
        fields = "__all__"

    def get_category(self, obj):
        return (
            CategorySerializer(obj.category, fields=["id", "name"]).data
            if obj.category
            else None
        )

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_owner(self, obj):
        return UserSerializer(
            instance=obj.host,
            fields=[
                "id",
                "full_name",
                "image",
                "email",
                "identity_verification_status",
                "status",
                "phone_number"
            ],
        ).data

    def validate_length_of_stay_discounts(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Length of stay discounts must be a dictionary.")
        for days_str, percentage in value.items():
            try:
                days = int(days_str)
                if days <= 0:
                    raise serializers.ValidationError(f"Discount days '{days_str}' must be a positive integer.")
            except ValueError:
                raise serializers.ValidationError(f"Discount days key '{days_str}' must be an integer string.")

            try:
                percent_val = Decimal(str(percentage))
                if not (0 < percent_val <= 100):  # Discount should be between 0 exclusive and 100 inclusive
                    raise serializers.ValidationError(
                        f"Discount percentage '{percentage}' for {days} days must be between 0 (exclusive) and 100.")
            except (TypeError, InvalidOperation):
                raise serializers.ValidationError(f"Discount percentage '{percentage}' must be a valid number.")
        return value

    def validate(self, data):

        instant_booking_final_state = data.get(
            'instant_booking_allowed',
            getattr(self.instance, 'instant_booking_allowed', False) if self.instance else False
        )

        require_good_track_record_incoming = data.get('require_guest_good_track_record')


        if require_good_track_record_incoming is True and instant_booking_final_state is False:

            raise ValidationError({
                'require_guest_good_track_record': _(
                    'Cannot set require good track record to true when instant booking is false or being set to false.')
            })

        if not instant_booking_final_state:
            data['require_guest_good_track_record'] = False

        instance = getattr(self, 'instance', None)
        enable_discount = data.get('enable_length_of_stay_discount',
                                   getattr(instance, 'enable_length_of_stay_discount', False) if instance else False)
        discounts = data.get('length_of_stay_discounts',
                             getattr(instance, 'length_of_stay_discounts', {}) if instance else {})

        if enable_discount and not discounts:
            pass
        if not enable_discount and discounts:

            if 'enable_length_of_stay_discount' in data and not data['enable_length_of_stay_discount']:
                data['length_of_stay_discounts'] = {}


        return data
class ListingSerializerM(DynamicFieldsModelSerializer):
    latitude = FloatField(source="location.y", read_only=True)
    longitude = FloatField(source="location.x", read_only=True)
    instant_booking_allowed = BooleanField(required=False)
    require_guest_good_track_record = BooleanField(required=False)
    host = UserSerializerX(read_only=True)
    category_name = serializers.SerializerMethodField()



    enable_length_of_stay_discount = serializers.BooleanField(required=False)
    length_of_stay_discounts = serializers.JSONField(required=False)

    class Meta:
        model = Listing
        fields = "__all__"

    def get_category(self, obj):
        return (
            CategorySerializer(obj.category, fields=["id", "name"]).data
            if obj.category
            else None
        )

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_owner(self, obj):
        return UserSerializer(
            instance=obj.host,
            fields=[
                "id",
                "full_name",
                "image",
                "email",
                "identity_verification_status",
                "status",
            ],
        ).data

    def validate_length_of_stay_discounts(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Length of stay discounts must be a dictionary.")
        for days_str, percentage in value.items():
            try:
                days = int(days_str)
                if days <= 0:
                    raise serializers.ValidationError(f"Discount days '{days_str}' must be a positive integer.")
            except ValueError:
                raise serializers.ValidationError(f"Discount days key '{days_str}' must be an integer string.")

            try:
                percent_val = Decimal(str(percentage))
                if not (0 < percent_val <= 100):  # Discount should be between 0 exclusive and 100 inclusive
                    raise serializers.ValidationError(
                        f"Discount percentage '{percentage}' for {days} days must be between 0 (exclusive) and 100.")
            except (TypeError, InvalidOperation):
                raise serializers.ValidationError(f"Discount percentage '{percentage}' must be a valid number.")
        return value

    def validate(self, data):

        instant_booking_final_state = data.get(
            'instant_booking_allowed',
            getattr(self.instance, 'instant_booking_allowed', False) if self.instance else False
        )

        require_good_track_record_incoming = data.get('require_guest_good_track_record')


        if require_good_track_record_incoming is True and instant_booking_final_state is False:

            raise ValidationError({
                'require_guest_good_track_record': _(
                    'Cannot set require good track record to true when instant booking is false or being set to false.')
            })

        if not instant_booking_final_state:
            data['require_guest_good_track_record'] = False

        instance = getattr(self, 'instance', None)
        enable_discount = data.get('enable_length_of_stay_discount',
                                   getattr(instance, 'enable_length_of_stay_discount', False) if instance else False)
        discounts = data.get('length_of_stay_discounts',
                             getattr(instance, 'length_of_stay_discounts', {}) if instance else {})

        if enable_discount and not discounts:
            pass
        if not enable_discount and discounts:

            if 'enable_length_of_stay_discount' in data and not data['enable_length_of_stay_discount']:
                data['length_of_stay_discounts'] = {}


        return data


class ListingAmenitySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = ListingAmenity
        fields = "__all__"

    def get_amenity(self, obj):
        amenity = obj.amenity
        return {
            "name": amenity.name,
            "a_type": amenity.a_type,
            "icon": amenity.icon,
            "id": amenity.id,
        }


class ListingStatusUpdateSerializer(Serializer):
    listing_status = ChoiceField(
        choices=["restricted", "published", "unpublished"], required=False
    )
    verification_status = ChoiceField(
        choices=["unverified", "verified"], required=False
    )

    def validate(self, data):
        if not data.get("listing_status") and not data.get("verification_status"):
            raise ValidationError(
                "At least one of 'listing_status' or 'verification_status' must be provided."
            )

        return data


class AssignCoHostSerializer(serializers.Serializer):
    """
    Validates the data for assigning or replacing a co-host for a single listing.
    The `listing_id` field expects a list containing exactly one ID.
    """
    co_host_user_id = serializers.IntegerField(
        required=True,
        help_text="ID of the user to be assigned as co-host."
    )
    listing_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False,
        help_text="A list containing the single ID of the listing to assign the co-host to. e.g., [101]"
    )
    access_level = serializers.ChoiceField(
        choices=CoHostAccessLevel.choices,
        required=True
    )
    commission_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
        required=True
    )

    def validate_co_host_user_id(self, value):
        """Validates the co-host user and returns the User instance."""
        try:
            co_host_user = User.objects.get(pk=value, u_type=UserTypeOption.HOST, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Co-host user not found, is not a host, or is not active.")

        request_user = self.context['request'].user
        if request_user.id == co_host_user.id:
            raise serializers.ValidationError("You cannot assign yourself as a co-host.")
        return co_host_user

    def validate_listing_ids(self, value):  # Changed from validate_listing_id to validate_listing_ids
        """Validates that the list contains exactly one valid listing ID."""
        request_user = self.context['request'].user

        # Fetch all listings that match the provided IDs and are owned by the user
        listings = Listing.objects.filter(pk__in=value, host=request_user, is_deleted=False)

        # Check if we found all the listings they asked for
        if len(listings) != len(set(value)):
            found_ids = set(listings.values_list('id', flat=True))
            missing_ids = set(value) - found_ids
            raise serializers.ValidationError(
                f"The following listings were not found or you do not have permission to manage them: {list(missing_ids)}")

        # Return the queryset of valid Listing objects
        return listings

    def validate(self, data):
        """Performs cross-field validation."""
        listing_queryset = data['listing_ids']  # Now this will be Listing instances
        co_host_user = data['co_host_user_id']

        if listing_queryset and co_host_user:
            for listing in listing_queryset:
                if listing.host == co_host_user:
                    raise serializers.ValidationError({
                        "co_host_user_id": f"Cannot assign user as co-host to their own listing (ID: {listing.id})."
                    })
        return data

class ListingCoHostSerializer(serializers.ModelSerializer):
    """
    General purpose serializer for ListingCoHost assignments.
    Represents the assignment and its related objects.
    """
    co_host_user_details = UserSerializer(source='co_host_user', read_only=True, fields=['id', 'username', 'full_name', 'image'])
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    primary_host_details = UserSerializer(source='primary_host', read_only=True, fields=['id', 'username', 'full_name'])

    class Meta:
        model = ListingCoHost
        # 'listing' is the primary key and represents the ID of the related listing.
        fields = [
            'listing',
            'listing_title',
            'co_host_user_details',
            'primary_host_details',
            'access_level',
            'commission_percentage',
            'is_active',
            'created_at',
            'updated_at'
        ]



class ListingCoHostSerializer(serializers.ModelSerializer):
    co_host_user_details = UserSerializer(source='co_host_user', read_only=True, fields=['id', 'username', 'full_name', 'image', 'u_type'])
    id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_details = ListingSerializer(source='listing', read_only=True, fields=['id', 'title', 'cover_photo']) # Show some listing details
    # primary_host_details is not strictly needed here if the API is for the primary host viewing their assignments

    class Meta:
        model = ListingCoHost
        fields = [
            'id',
            'listing_details', # Details of the co-hosted listing
            'co_host_user_details', # Details of the assigned co-host
            'access_level',
            'commission_percentage',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields


class UpdateCoHostAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for partially updating a ListingCoHost assignment.
    """
    access_level = serializers.ChoiceField(choices=CoHostAccessLevel.choices, required=False)
    commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0.00'), max_value=Decimal('100.00'), required=False)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = ListingCoHost
        fields = ['access_level', 'commission_percentage', 'is_active']


class BasicListingInfoWithPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['id', 'title', 'cover_photo', 'price', 'address']


class PrimaryHostAssignmentViewSerializer(serializers.ModelSerializer):
    """
    Represents a co-host assignment for the PrimaryHostViewCoHostAssignmentsStatusAPIView.
    """
    id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_details = BasicListingInfoWithPriceSerializer(source='listing', read_only=True)

    class Meta:
        model = ListingCoHost
        fields = [
            'id',  # This IS the assignment ID now. It holds the listing's PK.
            'access_level',
            'commission_percentage',
            'is_active',
            'listing_details',
        ]



class GrantedListingWithDetailsSerializer(BasicListingInfoWithPriceSerializer): # Inherits id, title, cover_photo, price
    # Get from the attached ListingCoHost assignment object
    access_level = serializers.CharField(source='cohost_assignment_details.access_level', read_only=True)
    access_level_display = serializers.CharField(source='cohost_assignment_details.get_access_level_display', read_only=True)
    commission_percentage = serializers.DecimalField(
        source='cohost_assignment_details.commission_percentage',
        read_only=True,
        max_digits=5,
        decimal_places=2
    )

    class Meta(BasicListingInfoWithPriceSerializer.Meta):
        fields = BasicListingInfoWithPriceSerializer.Meta.fields + ['access_level', 'access_level_display', 'commission_percentage']


class ListingCoHostDetailForPrimaryHostSerializer(serializers.ModelSerializer):
    """
    Lists the co-host's details for a given listing.
    """
    co_host_user_id = serializers.IntegerField(source='co_host_user.id', read_only=True)
    name = serializers.CharField(source='co_host_user.get_full_name', read_only=True)
    image = serializers.URLField(source='co_host_user.image', read_only=True, allow_null=True)
    commission = serializers.DecimalField(source='commission_percentage', max_digits=5, decimal_places=2, read_only=True)
    access_level_display = serializers.CharField(source='get_access_level_display', read_only=True)

    class Meta:
        model = ListingCoHost
        fields = [
            'co_host_user_id',
            'name',
            'image',
            'commission',
            'access_level',
            'access_level_display',
        ]




class CoHostedListingDetailSerializer(serializers.ModelSerializer):
    """
    Shows details of a listing that the current user is co-hosting.
    """
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    status = serializers.CharField(source='listing.status', read_only=True)
    title = serializers.CharField(source='listing.title', read_only=True)
    address = serializers.CharField(source='listing.address', read_only=True)
    cover_photo = serializers.URLField(source='listing.cover_photo', read_only=True, allow_null=True)
    price = serializers.FloatField(source='listing.price', read_only=True)
    unique_id = serializers.UUIDField(source='listing.unique_id', read_only=True)
    primary_host_id = serializers.IntegerField(source='primary_host.id', read_only=True)
    primary_host_name = serializers.CharField(source='primary_host.get_full_name', read_only=True)
    access_level_display = serializers.CharField(source='get_access_level_display', read_only=True)

    class Meta:
        model = ListingCoHost
        fields = [
            'listing_id',
            'unique_id',
            'title',
            'status',
            'address',
            'cover_photo',
            'price',
            'primary_host_id',
            'primary_host_name',
            'access_level',
            'access_level_display',
            'commission_percentage',
            'is_active',
        ]
