
from rest_framework import serializers
from .models import Coupon
from django.utils import timezone
import decimal


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            'id',
            'code',
            'description',
            'discount_type',
            'discount_value',
            'threshold_amount',
            'valid_from',
            'valid_to',
            'max_use',
            'uses_count',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'uses_count',
            'created_at',
            'updated_at'
        ]

    def __init__(self, *args, **kwargs):

        data = kwargs.get('data')
        if data:
            if data.get('valid_from') == '':
                data['valid_from'] = None
            if data.get('valid_to') == '':
                data['valid_to'] = None
        super().__init__(*args, **kwargs)

    def validate_code(self, value):

        return value.upper()

    def validate(self, data):


        discount_type = data.get('discount_type', getattr(self.instance, 'discount_type', None))
        discount_value = data.get('discount_value', getattr(self.instance, 'discount_value', None))
        valid_from = data.get('valid_from', getattr(self.instance, 'valid_from', None))
        valid_to = data.get('valid_to', getattr(self.instance, 'valid_to', None))


        if discount_type == Coupon.DISCOUNT_TYPE_PERCENTAGE and discount_value is not None and discount_value > 100:
            raise serializers.ValidationError({'discount_value': 'Percentage discount value cannot exceed 100.'})


        from_date = valid_from or timezone.now()
        if from_date and valid_to and from_date > valid_to:
            raise serializers.ValidationError({'valid_to': 'Valid To date cannot be before Valid From date.'})

        return data


class CouponValidateSerializer(serializers.Serializer):

    code = serializers.CharField(max_length=50, required=True)
    order_total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=decimal.Decimal('0.01')
    )

    def validate_code(self, value):
        return value.upper()
