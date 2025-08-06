from accounts.serializers import UserSerializer
from base.serializers import DynamicFieldsModelSerializer
from base.type_choices import PaymentStatusOption, BookingStatusOption
from bookings.models import Booking, ListingBookingReview
from listings.serializers import ListingSerializer
from rest_framework import serializers
from decimal import Decimal

class BookingReviewSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = ListingBookingReview
        fields = "__all__"

    def get_review_by(self, obj):
        return UserSerializer(
            obj.review_by,
            fields=["id", "full_name", "image", "phone_number", "u_type"],
        ).data

    def get_review_for(self, obj):
        return UserSerializer(
            obj.review_for,
            fields=["id", "full_name", "image", "phone_number", "u_type"],
        ).data

    def get_listing(self, obj):
        return ListingSerializer(
            obj.listing,
            fields=["id", "title", "cover_photo", "unique_id"],
        ).data

    def get_booking(self, obj):
        return BookingSerializer(
            obj.booking,
            fields=[
                "id",
                "invoice_no",
                "check_in",
                "check_out",
                "guest_count",
                "night_count",
                "total_price",
                "guest_payment_status",
                "host_payment_status",
                "status",
                "listing",
                "guest",
                "host",
            ],
        ).data


class BookingSerializer(DynamicFieldsModelSerializer):
    reviews = BookingReviewSerializer(
        many=True,
        read_only=True,
        source='listingbookingreview_set'
    )

    original_price_before_discount = serializers.SerializerMethodField()
    total_discount_amount = serializers.SerializerMethodField()
    accommodation_charge = serializers.SerializerMethodField()
    subtotal_before_generic_coupon = serializers.SerializerMethodField()
    length_of_stay_discount_percent = serializers.SerializerMethodField()
    length_of_stay_discount_amount = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = "__all__"

    def create(self, validated_data):
        # Check if test booking flag is passed (from GuestBookingProcess)
        is_test_booking = validated_data.pop("is_test_booking", False)

        extra_fields = ['original_price_before_discount', 'total_discount_amount',
                        'accommodation_charge', 'subtotal_before_generic_coupon',
                        'length_of_stay_discount_percent', 'length_of_stay_discount_amount']

        for field in extra_fields:
            validated_data.pop(field, None)

        if is_test_booking:
            # Mark booking as paid, bypass gateway
            validated_data["guest_payment_status"] = PaymentStatusOption.PAID
            validated_data["paid_amount"] = validated_data["total_price"]
            validated_data["status"] = BookingStatusOption.CONFIRMED
            validated_data["pgw_transaction_number"] = "TEST-BYPASS"
            validated_data["reservation_code"] = f"TEST-{validated_data['invoice_no'][-6:]}"  # Optional

        # Create the booking
        booking = super().create(validated_data)    

        return booking

    def get_listing(self, obj):
        return ListingSerializer(
            obj.listing,
            fields=[
                "id",
                "title",
                "avg_rating",
                "total_rating_count",
                "cover_photo",
                "cancellation_policy",
                "address",
            ],
        ).data

    def get_original_price_before_discount(self, obj):
        return self.context.get('extra_data', {}).get('original_price_before_discount')

    def get_total_discount_amount(self, obj):
        return self.context.get('extra_data', {}).get('total_discount_amount')

    def get_accommodation_charge(self, obj):
        return self.context.get('extra_data', {}).get('accommodation_charge')

    def get_subtotal_before_generic_coupon(self, obj):
        return self.context.get('extra_data', {}).get('subtotal_before_generic_coupon')

    def get_length_of_stay_discount_percent(self, obj):
        return self.context.get('extra_data', {}).get('length_of_stay_discount_percent')

    def get_length_of_stay_discount_amount(self, obj):
        return self.context.get('extra_data', {}).get('length_of_stay_discount_amount')

    def get_guest(self, obj):
        return UserSerializer(
            obj.guest,
            fields=["id", "full_name", "phone_number"],
        ).data

    def get_host(self, obj):
        return UserSerializer(obj.host, fields=["id", "full_name", "phone_number"]).data




class CouponCheckResponseSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField(
        help_text="True if the coupon is valid and applicable, False otherwise."
    )
    message = serializers.CharField(
        help_text="A human-readable message explaining the validation result (e.g., 'Coupon applied successfully.', 'Coupon has expired.')."
    )
    coupon_code = serializers.CharField(
        allow_null=True, # Can be null if no valid coupon code was matched or input was empty
        help_text="The coupon code that was validated (or attempted)."
    )
    coupon_type = serializers.CharField(
        allow_null=True, # 'referral' or 'admin' if valid, otherwise null
        help_text="Indicates if the coupon is a 'referral' or 'admin' type."
    )
    discount_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True, # Null if coupon is not valid or no discount applies
        help_text="The calculated discount amount in Taka (or your currency)."
    )
    original_price_for_discount_calc = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True, # Null if no order_total was provided for context
        help_text="The order total that was used as the base for calculating the discount."
    )
    price_after_discount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True, # Null if coupon is not valid
        help_text="The calculated price after the discount is applied."
    )
    discount_display = serializers.CharField(
        allow_null=True,
        required=False, # Not always present
        help_text="A user-friendly display of the discount (e.g., '10% off', '50 Taka off')."
    )
    # You could add more specific fields from the coupon object if the UI needs them, for example:
    # description = serializers.CharField(allow_null=True, required=False)
    # valid_to = serializers.DateTimeField(allow_null=True, required=False)
    # threshold_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True, required=False)

    def create(self, validated_data):
        # This serializer is for output, so create is not applicable
        raise NotImplementedError("This serializer is for output only.")

    def update(self, instance, validated_data):
        # This serializer is for output, so update is not applicable
        raise NotImplementedError("This serializer is for output only.")
