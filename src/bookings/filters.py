from django.utils import timezone
from django_filters import rest_framework as filters
from base.type_choices import BookingStatusOption, PaymentStatusOption
from bookings.models import Booking, ListingBookingReview
from django.db.models import Q


class UserBookingFilter(filters.FilterSet):
    created_at = filters.DateFromToRangeFilter()

    class Meta:
        model = Booking
        fields = ("created_at", "status")


class AdminBookingFilter(filters.FilterSet):
    created_at = filters.DateFromToRangeFilter()
    over_due = filters.CharFilter(method="over_due_filter")

    class Meta:
        model = Booking
        fields = ("status", "host_payment_status", "over_due", "host", "guest")

    def over_due_filter(self, queryset, name, value):
        current_date = timezone.now().date()
        seven_days_ago = current_date - timezone.timedelta(days=7)
        return queryset.filter(
            status=BookingStatusOption.CONFIRMED,
            host_payment_status=PaymentStatusOption.UNPAID,
            check_in__lte=seven_days_ago,
        )  # check_out__lte


class BookingReviewFilter(filters.FilterSet):
    created_at = filters.DateFromToRangeFilter()
    u_type = filters.CharFilter(method="u_type_filter")
    user = filters.CharFilter(method="user_review_filter")

    class Meta:
        model = ListingBookingReview
        fields = ("created_at", "review_by", "review_for")

    def u_type_filter(self, queryset, name, value):
        if value == "host":
            return queryset.filter(is_host_review=True)
        else:
            return queryset.filter(is_guest_review=True)

    def user_review_filter(self, queryset, name, value):
        if value == "false":
            return queryset
        return queryset.filter(Q(review_by_id=value) | Q(review_for_id=value))


class UserBookingFilterX(filters.FilterSet):
    # Add the status field to the filter
    status = filters.ChoiceFilter(choices=BookingStatusOption.choices)

    class Meta:
        model = Booking
        # Include 'status' in the list of filterable fields
        fields = ["status"]
