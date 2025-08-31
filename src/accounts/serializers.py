import re
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.serializers import (
    Serializer,
    ModelSerializer,
    ValidationError,
    SerializerMethodField,
    ChoiceField,
    CharField,
)
from accounts.models import UserProfile, SuperhostStatusHistory
from base.serializers import DynamicFieldsModelSerializer
from base.type_choices import (
    IdentityVerificationStatusOption,
    UserTypeOption,
)

User = get_user_model()


class HostGuestUserSerializer(ModelSerializer):
    full_name = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "phone_number",
            "email",
            "is_active",
            "status",
            "is_phone_verified",
            "is_email_verified",
            "u_type",
            "country_code",
            "password",
            "image",
            "date_joined",
            "full_name",
            "identity_verification_status",
            "identity_verification_images",
            "identity_verification_method",
            "identity_verification_reject_reason",
            "avg_rating",
            "total_rating_count",
            "wishlist_listings",
            "is_available_for_cohosting"
        )
        extra_kwargs = {
            "password": {"write_only": True},
            "country_code": {"read_only": True},
            "avg_rating": {"read_only": True},
            "total_rating_count": {"read_only": True},
        }

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class UserSerializer(DynamicFieldsModelSerializer):
    full_name = SerializerMethodField()
    total_bookings = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = "__all__"
        ref_name = 'AccountsUserSerializer'
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate(self, attrs):
        user = None

        if self.instance:
            user = self.instance.user

        if user and user.u_type == UserTypeOption.HOST:
            emergency_contact = attrs.get("emergency_contact")
            is_updating_field = emergency_contact in attrs
            if is_updating_field:
                if not emergency_contact:
                    raise ValidationError({"emergency_contact": "Emergency contact is required for hosts."})
            elif self.instance and self.instance.emergency_contact:
                raise ValidationError({"emergency_contact": "Emergency contact is required for hosts."})
        return attrs

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class UserProfileSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"


class UserIdentityVerificationSerializer(Serializer):
    document_type = CharField(required=True)
    front_image = CharField(required=True)
    back_image = CharField(required=False)

    def validate_document_type(self, value):
        if value not in ["passport", "nid", "driving_license"]:
            raise ValidationError("document_type is not valid")
        return value


class UserLiveVerificationSerializer(Serializer):
    document_type = CharField(required=True)
    live = CharField(required=True)

    def validate_document_type(self, value):
        if value not in ["passport", "nid", "driving_license", "live"]:
            raise ValidationError("document_type is not valid")
        return value


class StatusUpdateSerializer(Serializer):
    first_name = CharField(required=False)
    last_name = CharField(required=False)
    phone_number = CharField(required=False)
    email = CharField(required=False)
    user_status = ChoiceField(choices=["active", "restricted"], required=False)
    identity_status = ChoiceField(choices=["rejected", "verified", "not_verified", "pending"], required=False)
    reject_reason = CharField(required=False, allow_blank=True)

    def validate(self, data):
        if not data.get("user_status") and not data.get("identity_status"):
            raise ValidationError(
                "At least one of 'user_status' or 'identity_status' must be provided."
            )

        if data.get(
            "identity_status"
        ) == IdentityVerificationStatusOption.REJECTED and not data.get(
            "reject_reason"
        ):
            raise ValidationError(
                "You must give a reject_reason while reject an account"
            )

        return data


class ChangePasswordSerializer(Serializer):
    old_password = CharField(required=True)
    new_password = CharField(required=True)


class AuthSerializer(Serializer):
    phone_number = CharField(required=True)
    u_type = CharField(required=True)

    def validate_u_type(self, value):
        if value not in [UserTypeOption.HOST, UserTypeOption.GUEST]:
            raise ValidationError("u_type is invalid")
        return value

    def validate_username(self, value):
        pattern = r"^\d{11}$"
        if not re.match(pattern, value):
            raise ValidationError("invalid phone number")
        return value


class RegisterSerializer(AuthSerializer):
    full_name = CharField(required=True)
    password = CharField(required=True)
    otp = CharField(required=True)



class AuthSerializerDTL(Serializer):
    phone_number = CharField(required=True)
    u_type = CharField(required=True)

    # def validate_u_type(self, value):
    #     if value not in [UserTypeOption.HOST, UserTypeOption.GUEST]:
    #         raise ValidationError("u_type is invalid")
    #     return value

    def validate_phone_number(self, value):
        pattern = r"^\d{11}$"
        if not re.match(pattern, value):
            raise ValidationError("invalid phone number")
        return value



class RegisterSerializerRef(AuthSerializerDTL):
    full_name = CharField(required=True)
    password = CharField(required=True)
    otp = CharField(required=True)
    referral_code = CharField(required=False)


class ResetPasswordSerializer(AuthSerializer):
    password = CharField(required=True)
    otp = CharField(required=True)


class LoginSerializer(AuthSerializer):
    password = CharField(required=True)


class UserDTLSerializer(Serializer):
    name = CharField(max_length=200)
    email = CharField()
    password = CharField(max_length=200)



from rest_framework import serializers

class SuperhostMetricDetailSerializer(serializers.Serializer):
    current = serializers.FloatField()
    required = serializers.FloatField()
    met = serializers.BooleanField()
    comparison = serializers.CharField(required=False, help_text="'lower_is_better' or implicitly 'higher_is_better'")

class SuperhostTierProgressSerializer(serializers.Serializer):
    tier_key = serializers.CharField()
    name = serializers.CharField()
    achieved = serializers.BooleanField()
    progress_details = serializers.DictField(child=SuperhostMetricDetailSerializer())


class SuperhostStatusHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = SuperhostStatusHistory
        fields = [
            'id',
            'tier_key',
            'tier_name',
            'assessment_period_start',
            'assessment_period_end',
            'status_achieved_on',
            'metrics_snapshot',
            'created_at'
        ]


class HostCohostingAvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for updating a host's co-hosting availability status.
    """
    class Meta:
        model = User
        fields = ['is_available_for_cohosting']

class HostPublicProfileSerializer(serializers.ModelSerializer):

    bio = serializers.CharField(source='userprofile.bio', read_only=True, allow_null=True)
    # total_listings = serializers.IntegerField(source='listing_set.count', read_only=True) # Basic count
    # More accurate total_listings considering only PUBLISHED:
    total_active_listings = serializers.SerializerMethodField()
    years_hosting = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'full_name',
            'image',
            'bio',
            'total_active_listings',
            'avg_rating',
            'years_hosting',
            'current_superhost_tier',
            'distance_km'
        ]
        read_only_fields = fields

    def get_total_active_listings(self, obj: User) -> int:

        from listings.models import Listing
        from base.type_choices import ListingStatusOption
        return Listing.objects.filter(host=obj, status=ListingStatusOption.PUBLISHED, is_deleted=False).count()

    def get_years_hosting(self, obj: User) -> int:
        if obj.date_joined:
            years = (timezone.now().date() - obj.date_joined.date()).days / 365.25
            return int(years)
        return 0

    def get_superhost_tier_display_name(self, obj: User) -> str:
        return obj.get_current_superhost_tier_display()

    def get_distance_km(self, obj: User) -> Decimal | None:

        if hasattr(obj, 'calculated_distance_km'):
            return obj.calculated_distance_km.quantize(Decimal('0.1'))

        return None


class UserDeleteSerializer(serializers.Serializer):

    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True
    )
