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
    co_host_user_id = serializers.IntegerField(required=True, help_text="ID of the user to be assigned as co-host.")
    listing_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        required=True,
        help_text="List of IDs of the listings to assign this co-host to."
    )
    access_level = serializers.ChoiceField(choices=CoHostAccessLevel.choices, required=True)
    commission_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
        required=True
    )

    def validate_co_host_user_id(self, value):
        try:
            co_host_user = User.objects.get(pk=value, u_type=UserTypeOption.HOST, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Co-host user not found, is not a host, or is not active.")

        # Prevent assigning oneself as co-host (though primary host check later is more direct)
        request_user = self.context['request'].user
        if request_user.id == co_host_user.id:
            raise serializers.ValidationError("You cannot assign yourself as a co-host.")

        return co_host_user  # Return the User instance for convenience

    def validate_listing_ids(self, value):
        request_user = self.context['request'].user
        # Check if all listings exist and belong to the requesting user
        listings = Listing.objects.filter(pk__in=value, host=request_user, is_deleted=False)

        if len(listings) != len(set(value)):  # Using set to handle potential duplicates in input list
            # Find which IDs were problematic
            valid_ids = [l.id for l in listings]
            invalid_ids = [lid for lid in set(value) if lid not in valid_ids]
            raise serializers.ValidationError(
                f"One or more listings not found, do not belong to you, or are invalid: {invalid_ids}")

        # Check if co-host is already assigned to any of these listings
        for listing in listings:
            if listing.host_id == self.initial_data.get(
                'co_host_user_id'):  # Check against initial data before co_host_user_id is resolved to object
                raise serializers.ValidationError(
                    f"The selected co-host is the primary host of listing '{listing.title}'.")
            if ListingCoHost.objects.filter(listing=listing,
                                            co_host_user_id=self.initial_data.get('co_host_user_id')).exists():
                raise serializers.ValidationError(
                    f"This user is already a co-host for listing: '{listing.title}'. Please update existing assignment or remove first.")

        return listings


class ListingCoHostSerializer(serializers.ModelSerializer):
    co_host_user_details = UserSerializer(source='co_host_user', read_only=True,
                                          fields=['id', 'username', 'full_name', 'image'])
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    primary_host_details = UserSerializer(source='primary_host', read_only=True, fields=['id', 'username', 'full_name'])

    # To make co_host_user writable by ID
    co_host_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(u_type=UserTypeOption.HOST, is_active=True),  # Only active hosts can be co-hosts
        write_only=True
    )

    # Listing will likely be provided in the URL or context, not directly in POST body for assignment
    # primary_host is set automatically on save

    class Meta:
        model = ListingCoHost
        fields = [
            'id',
            'listing',  # Writable for creation (expecting ID), readable (shows ID or nested if configured)
            'listing_title',
            'co_host_user',  # Writable (expects ID)
            'co_host_user_details',  # Readable
            'primary_host_details',  # Readable
            'access_level',
            'commission_percentage',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'primary_host_details', 'listing_title', 'co_host_user_details', 'created_at',
                            'updated_at']
        # 'listing' is often set via URL or context, not direct payload in update/create sometimes.
        # If creating: listing ID will be in URL or passed as a field.
        # If listing via /api/listings/<listing_pk>/cohosts/, then listing is implicit.

    def validate(self, data):
        listing = None
        # On create, 'listing' might be in data or come from view context (URL)
        # On update, self.instance will have the listing
        if self.instance:
            listing = self.instance.listing
        elif 'listing' in data:
            listing = data['listing']  # This would be a Listing instance if PKRelatedField resolved it
            # Or just the ID if not yet resolved.
        else:  # If creating and listing_id is expected from URL context
            view = self.context.get('view')
            if view and hasattr(view, 'kwargs') and view.kwargs.get('listing_pk'):
                try:
                    listing = Listing.objects.get(pk=view.kwargs.get('listing_pk'))
                    # No need to add to data, as it's used for validation context
                except Listing.DoesNotExist:
                    raise serializers.ValidationError("Listing not found.")
            else:  # If listing is required and not found anywhere
                if not self.partial:  # If it's not a PATCH request
                    raise serializers.ValidationError({"listing": "Listing must be provided."})

        co_host_user = data.get('co_host_user')  # This is a User instance after PKRelatedField resolves

        if listing and co_host_user:
            if listing.host == co_host_user:
                raise serializers.ValidationError("A host cannot assign themselves as a co-host to their own listing.")

        # Ensure commission is reasonable
        commission = data.get('commission_percentage')
        if commission is not None and (commission < Decimal('0.00') or commission > Decimal('100.00')):
            raise serializers.ValidationError({"commission_percentage": "Commission must be between 0 and 100."})

        return data

    def create(self, validated_data):
        # primary_host is set automatically by the model's save method
        # Listing might come from context if using nested routers
        listing = validated_data.get('listing')
        view = self.context.get('view')

        if not listing and view and hasattr(view, 'kwargs') and view.kwargs.get('listing_pk'):
            try:
                listing = Listing.objects.get(pk=view.kwargs.get('listing_pk'))
                validated_data['listing'] = listing
            except Listing.DoesNotExist:
                raise serializers.ValidationError("Associated listing not found.")

        if not listing:
            raise serializers.ValidationError({"listing": "Listing is required to assign a co-host."})

        # Ensure the user making the request is the primary host of the listing
        request_user = self.context['request'].user
        if listing.host != request_user:
            raise serializers.PermissionDenied("You do not have permission to assign co-hosts to this listing.")

        validated_data['primary_host'] = listing.host  # Explicitly set for clarity, though model save might do it
        return super().create(validated_data)


class ListingCoHostSerializer(serializers.ModelSerializer):
    co_host_user_details = UserSerializer(source='co_host_user', read_only=True, fields=['id', 'username', 'full_name', 'image', 'u_type'])
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
    Allows changing the access_level, commission_percentage, and is_active status.
    """
    # Make fields not required for PATCH requests
    access_level = serializers.ChoiceField(choices=CoHostAccessLevel.choices, required=False)
    commission_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
        required=False
    )
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = ListingCoHost
        fields = [
            'access_level',
            'commission_percentage',
            'is_active'
        ]

class BasicListingInfoWithPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['id', 'title', 'cover_photo', 'price', 'address']

class PrimaryHostAssignmentViewSerializer(serializers.ModelSerializer):
    """
    Represents a co-host assignment, including its ID and commission,
    and nests the essential details of the associated listing.
    """
    # Use your existing listing serializer to show listing info.
    # If you don't have one, the definition is provided below.
    listing_details = BasicListingInfoWithPriceSerializer(source='listing', read_only=True)

    class Meta:
        model = ListingCoHost
        fields = [
            'id',
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
    # Instead of co_host_user_details as a nested object,
    # directly source fields from the co_host_user
    id = serializers.IntegerField(source='co_host_user.id', read_only=True)
    name = serializers.CharField(source='co_host_user.get_full_name', read_only=True)
    image = serializers.URLField(source='co_host_user.image', read_only=True, allow_null=True)

    # commission_percentage is already a field on ListingCoHost model,
    # so it will be included by default or if listed in Meta.fields.
    # We can rename it in the output if desired using source.
    commission = serializers.DecimalField(
        source='commission_percentage',
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    # You might also want to include access_level
    access_level = serializers.CharField(read_only=True)
    access_level_display = serializers.CharField(source='get_access_level_display', read_only=True)

    class Meta:
        model = ListingCoHost
        fields = [
            'id',  # This will be co_host_user.id because of source='co_host_user.id'
            'name',  # This will be co_host_user.get_full_name()
            'image',  # Uncomment if you add it above
            'commission',  # Renamed from commission_percentage
            'access_level',
            'access_level_display',
            # 'listing_cohost_assignment_id': serializers.IntegerField(source='id', read_only=True) # If you need the ID of the ListingCoHost record itself
        ]


class CoHostedListingDetailSerializer(serializers.ModelSerializer):
    # Fields from the Listing model, accessed via listing relation
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    title = serializers.CharField(source='listing.title', read_only=True)
    address = serializers.CharField(source='listing.address', read_only=True) # Assuming Listing has 'address'
    cover_photo = serializers.URLField(source='listing.cover_photo', read_only=True, allow_null=True)
    price = serializers.FloatField(source='listing.price', read_only=True) # Per-night price from Listing

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
            'address',
            'cover_photo',
            'price',
            'primary_host_id',
            'primary_host_name',

            'access_level',
            'access_level_display',
            'commission_percentage',
            'is_active',
            'id',
        ]
