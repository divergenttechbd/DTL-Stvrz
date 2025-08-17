from django.db.models import Q
from django_filters import rest_framework as filters
from listings.models import Listing, ListingCalendar

from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D # D is a distance object
from rest_framework.exceptions import ValidationError

class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class CharacterInFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class HostListingFilter(filters.FilterSet):
    class Meta:
        model = Listing
        fields = ("status",)


class PublicListingFilter(filters.FilterSet):
    listing_amenity__in = NumberInFilter(
        field_name="listingamenity__amenity_id", lookup_expr="in"
    )
    category__in = NumberInFilter(field_name="category_id", lookup_expr="in")
    guests = filters.NumberFilter(field_name="guest_count", lookup_expr="gte")
    bedroom_count = filters.NumberFilter(lookup_expr="gte")
    bed_count = filters.NumberFilter(lookup_expr="gte")
    bathroom_count = filters.NumberFilter(lookup_expr="gte")
    place_type__in = CharacterInFilter(field_name="place_type", lookup_expr="in")
    price = filters.RangeFilter()

    host_superhost_tier__in = CharacterInFilter(
        field_name="host__current_superhost_tier",
        lookup_expr="in",
        label="Superhost Tier(s) (e.g., SILVER,GOLD)"
    )


    is_superhost = filters.BooleanFilter(
        method='filter_is_superhost',
        label="Show only listings from Superhosts (any tier)"
    )

    class Meta:
        model = Listing
        fields = (
            "guests",
            "pet_allowed",
            "bedroom_count",
            "bed_count",
            "bathroom_count",
            "listing_amenity__in",
            "category__in",
            "price",
            "host_superhost_tier__in",
            "is_superhost",
        )

    def filter_is_superhost(self, queryset, name, value):

        if value is True:

            return queryset.filter(host__current_superhost_tier__isnull=False).exclude(
                host__current_superhost_tier__exact='')
        elif value is False:
            return queryset.filter(
                Q(host__current_superhost_tier__isnull=True) | Q(host__current_superhost_tier__exact=''))
        return queryset

    @property
    def qs(self):
        parent = super().qs
        return parent.distinct()

class PublicListingFilterR(filters.FilterSet):
    listing_amenity__in = NumberInFilter(
        field_name="listingamenity__amenity_id", lookup_expr="in"
    )
    category__in = NumberInFilter(field_name="category_id", lookup_expr="in")
    guests = filters.NumberFilter(field_name="guest_count", lookup_expr="gte")
    bedroom_count = filters.NumberFilter(lookup_expr="gte")
    bed_count = filters.NumberFilter(lookup_expr="gte")
    bathroom_count = filters.NumberFilter(lookup_expr="gte")
    place_type__in = CharacterInFilter(field_name="place_type", lookup_expr="in")
    price = filters.RangeFilter()

    host_superhost_tier__in = CharacterInFilter(
        field_name="host__current_superhost_tier",
        lookup_expr="in",
        label="Superhost Tier(s) (e.g., SILVER,GOLD)"
    )

    is_superhost = filters.BooleanFilter(
        method='filter_is_superhost',
        label="Show only listings from Superhosts (any tier)"
    )

    # Use a custom method for date filters to prevent name collision with model's TimeFields.
    # This allows the API to keep using 'check_in' and 'check_out' as query parameters.
    check_in = filters.DateFilter(method='pass_through_filter')
    check_out = filters.DateFilter(method='pass_through_filter')

    class Meta:
        model = Listing
        # Define all fields that the filter set should recognize.
        fields = (
            "guests",
            "pet_allowed",
            "bedroom_count",
            "bed_count",
            "bathroom_count",
            "listing_amenity__in",
            "category__in",
            "price",
            "host_superhost_tier__in",
            "is_superhost",
            "check_in",
            "check_out",
        )

    def pass_through_filter(self, queryset, name, value):
        """
        A placeholder method to prevent django-filter from automatically
        filtering on fields named 'check_in' and 'check_out', which would
        conflict with the model's TimeFields and cause a TypeError.
        The actual date filtering logic is handled in `filter_queryset`.
        """
        return queryset

    def filter_is_superhost(self, queryset, name, value):
        """ Custom method to filter for listings by Superhosts of any tier. """
        if value is True:
            return queryset.filter(host__current_superhost_tier__isnull=False).exclude(
                host__current_superhost_tier__exact='')
        elif value is False:
            return queryset.filter(
                Q(host__current_superhost_tier__isnull=True) | Q(host__current_superhost_tier__exact=''))
        return queryset

    def filter_queryset(self, queryset):
        """
        Overrides the default filter method to add complex, cross-model logic
        for date-based availability.
        """
        # First, apply all standard filters (like guests, price, etc.)
        queryset = super().filter_queryset(queryset)

        # Now, handle the custom availability filtering logic
        check_in_date = self.form.cleaned_data.get('check_in')
        check_out_date = self.form.cleaned_data.get('check_out')

        # Only proceed if both dates are provided in the query parameters
        if check_in_date and check_out_date:
            # Basic validation for the date range
            if check_out_date <= check_in_date:
                raise ValidationError({
                    'dates': 'Check-out date must be after the check-in date.'
                })

            # Logic to find listings that are UNAVAILABLE for the requested dates.
            # An overlap occurs if a calendar block starts before the checkout
            # and ends on or after the check-in.

            # This handles multi-day calendar entries (e.g., start: Aug 15, end: Aug 20)
            range_overlap = Q(
                end_date__isnull=False,
                start_date__lt=check_out_date,
                end_date__gt=check_in_date  # Changed from '>=' to '>'
            )

            # This handles single-day blocks within the desired date range
            single_day_overlap = Q(
                end_date__isnull=True,
                start_date__gte=check_in_date,
                start_date__lt=check_out_date
            )
            # Get the IDs of all listings that have a conflicting booked or blocked entry
            unavailable_listing_ids = ListingCalendar.objects.filter(
                Q(is_blocked=True) | Q(is_booked=True),
                range_overlap | single_day_overlap
            ).values_list('listing_id', flat=True).distinct()

            # Exclude the unavailable listings from the final result set
            queryset = queryset.exclude(pk__in=unavailable_listing_ids)

        return queryset

    @property
    def qs(self):
        parent = super().qs
        return parent.distinct()


class ListingFilter(filters.FilterSet):
    created_at = filters.DateFromToRangeFilter()

    district__in = CharacterInFilter(field_name="district", lookup_expr="in")

    deleted_status = filters.ChoiceFilter(
        method='filter_deleted_status',
        choices=(
            ('active', 'Active Only'),
            ('deleted', 'Deleted Only'),
            ('all', 'All'),
        ),
        label="Deleted Status"
    )



    class Meta:
        model = Listing
        fields = ("category", "status", "verification_status", "created_at", "host", "deleted_status", "district__in")

    def __init__(self, data=None, *args, **kwargs):
        # If 'deleted_status' is not provided, set it to 'active' by default
        if data is not None and "deleted_status" not in data:
            data = data.copy()
            data["deleted_status"] = "active"
        super().__init__(data, *args, **kwargs)

    def filter_deleted_status(self, queryset, name, value):
        if value == 'active':
            return queryset.filter(is_deleted=False)
        elif value == 'deleted':
            return queryset.filter(is_deleted=True)
        elif value == 'all':
            return queryset
        return queryset.filter(is_deleted=False)
