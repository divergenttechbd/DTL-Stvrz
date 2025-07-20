from datetime import datetime, timedelta, date
import json

from django.db.models import F
from django.utils.decorators import method_decorator
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from rest_framework.permissions import AllowAny
from rest_framework.generics import ListAPIView, RetrieveAPIView, views
from rest_framework import status
from rest_framework.response import Response
from base.helpers.decorators import exception_handler
from base.helpers.utils import calculate_days_between_dates
from base.type_choices import ListingStatusOption, ServiceChargeTypeOption
from bookings.models import ListingBookingReview
from bookings.serializers import BookingReviewSerializer
from configurations.models import ServiceCharge
from listings.filters import PublicListingFilter
from listings.models import Amenity, Category, Listing

from listings.serializers import ListingSerializer, ListingAmenitySerializer, ListingSerializerM
from listings.utils import get_user_with_profile
from listings.views.service import ListingCalendarDataProcess, ListingCheckoutCalculate
from myproject import settings

NEW_PROPERTY_BOOST = getattr(settings, 'NEW_PROPERTY_BOOST_SCORE', 100)
POPULAR_PROPERTY_BOOST_RATING = getattr(settings, 'POPULAR_PROPERTY_BOOST_RATING_SCORE', 75)
POPULAR_PROPERTY_BOOST_BOOKINGS = getattr(settings, 'POPULAR_PROPERTY_BOOST_BOOKINGS_SCORE', 50)
SUPERHOST_PROPERTY_BOOST = getattr(settings, 'SUPERHOST_PROPERTY_BOOST_SCORE', 150)


NEW_PROPERTY_DAYS_THRESHOLD = getattr(settings, 'NEW_PROPERTY_DAYS_THRESHOLD', 14)


POPULAR_RATING_THRESHOLD = getattr(settings, 'POPULAR_RATING_THRESHOLD', 4.7)
POPULAR_MIN_REVIEWS_THRESHOLD = getattr(settings, 'POPULAR_MIN_REVIEWS_THRESHOLD', 10)


from django.db.models import Q, Case, When, IntegerField, F
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone
from datetime import timedelta
import random
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny


class PublicListingListAPIView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ListingSerializer
    filterset_class = PublicListingFilter
    swagger_tags = ["Public Listings"]

    def get_queryset(self):
        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            latitude = self.request.GET.get("latitude")
            longitude = self.request.GET.get("longitude")
            search_point = Point(float(longitude), float(latitude), srid=4326)
            return (
                Listing.objects.annotate(distance=Distance("location", search_point))
                .filter(
                    status=ListingStatusOption.PUBLISHED,
                    distance__lte=D(km=float(self.request.GET.get("radius", 25))),
                )
                .order_by("distance")
            )

        return Listing.objects.filter(status=ListingStatusOption.PUBLISHED).order_by(
            "-created_at"
        )



class SimpleRandomPriorityAPIView(ListAPIView):
    """
    Simplified version that randomly rotates between the three criteria
    Each API call will prioritize one of: New, Popular, or Superhost properties
    """
    permission_classes = (AllowAny,)
    serializer_class = ListingSerializerM
    filterset_class = PublicListingFilter
    swagger_tags = ["Public Listings"]


    def get_queryset(self):
        print(" --------------------- simple ----------------------")
        # Get base queryset
        base_queryset = self._get_base_queryset()

        # Randomly select priority criteria
        priority_type = random.choice(['new', 'popular', 'superhost'])

        # Apply prioritization
        return self._prioritize_by_criteria(base_queryset, priority_type)

    def _get_base_queryset(self):
        """Get base queryset with optional location filtering"""
        base_filter = Q(status=ListingStatusOption.PUBLISHED)

        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            latitude = self.request.GET.get("latitude")
            longitude = self.request.GET.get("longitude")
            radius = float(self.request.GET.get("radius", 25))
            search_point = Point(float(longitude), float(latitude), srid=4326)

            return Listing.objects.annotate(
                distance=Distance("location", search_point)
            ).filter(base_filter, distance__lte=D(km=radius))

        return Listing.objects.filter(base_filter)

    def _prioritize_by_criteria(self, queryset, priority_type):
        """Apply prioritization based on the selected criteria"""

        if priority_type == 'new':
            # Prioritize new properties (created in last 7 days)
            new_threshold = timezone.now() - timedelta(days=7)
            queryset = queryset.annotate(
                is_priority=Case(
                    When(created_at__gte=new_threshold, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )

        elif priority_type == 'popular':
            # Prioritize popular properties (high rating + bookings)
            queryset = queryset.annotate(
                is_priority=Case(
                    When(
                        Q(avg_rating__gte=4.0) & Q(total_booking_count__gte=5),
                        then=1
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )

        else:  # superhost
            # Prioritize superhost properties
            queryset = queryset.annotate(
                is_priority=Case(
                    When(
                        host__current_superhost_tier__isnull=False,
                        host__current_superhost_tier__gt='',
                        then=1
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )

        # Apply ordering
        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            # For location searches: priority -> distance -> created_at
            return queryset.order_by('-is_priority', 'distance', '-created_at')
        else:
            # For general searches: priority -> created_at
            return queryset.order_by('-is_priority', '-created_at')



class TimeBasedRotationAPIView(ListAPIView):
    """
    Rotates criteria based on time intervals (e.g., every hour)
    This ensures more predictable rotation patterns
    """
    permission_classes = (AllowAny,)
    serializer_class = ListingSerializer
    filterset_class = PublicListingFilter
    swagger_tags = ["Public Listings"]

    def get_queryset(self):
        base_queryset = self._get_base_queryset()
        priority_type = self._get_time_based_priority()
        return self._prioritize_by_criteria(base_queryset, priority_type)

    def _get_time_based_priority(self):
        """Get priority based on current hour (rotates every hour)"""
        current_hour = timezone.now().hour
        criteria_cycle = ['new', 'popular', 'superhost']
        return criteria_cycle[current_hour % 3]

    def _get_base_queryset(self):
        """Same as SimpleRandomPriorityAPIView"""
        base_filter = Q(status=ListingStatusOption.PUBLISHED)

        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            latitude = self.request.GET.get("latitude")
            longitude = self.request.GET.get("longitude")
            radius = float(self.request.GET.get("radius", 25))
            search_point = Point(float(longitude), float(latitude), srid=4326)

            return Listing.objects.annotate(
                distance=Distance("location", search_point)
            ).filter(base_filter, distance__lte=D(km=radius))

        return Listing.objects.filter(base_filter)

    def _prioritize_by_criteria(self, queryset, priority_type):
        """Same prioritization logic as SimpleRandomPriorityAPIView"""
        if priority_type == 'new':
            new_threshold = timezone.now() - timedelta(days=7)
            queryset = queryset.annotate(
                is_priority=Case(
                    When(created_at__gte=new_threshold, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )
        elif priority_type == 'popular':
            queryset = queryset.annotate(
                is_priority=Case(
                    When(Q(avg_rating__gte=4.0) & Q(total_booking_count__gte=5), then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )
        else:  # superhost
            queryset = queryset.annotate(
                is_priority=Case(
                    When(
                        host__current_superhost_tier__isnull=False,
                        host__current_superhost_tier__gt='',
                        then=1
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )

        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            return queryset.order_by('-is_priority', 'distance', '-created_at')
        else:
            return queryset.order_by('-is_priority', '-created_at')

    """
    Enhanced version with more sophisticated randomization strategies
    """

    def _apply_top_viewing_logic(self, queryset):
        """Enhanced logic with strategy-based randomization"""

        # Get prioritization strategy from request or use random
        strategy = self.request.GET.get('strategy', self._get_random_strategy())

        # Define base categories
        new_property_threshold = timezone.now() - timedelta(days=7)

        # Get category querysets
        new_properties = queryset.filter(created_at__gte=new_property_threshold)
        popular_properties = queryset.filter(
            avg_rating__gte=4.0,
            total_booking_count__gte=5
        )
        superhost_properties = queryset.filter(
            host__current_superhost_tier__isnull=False
        ).exclude(host__current_superhost_tier='')

        # Apply strategy-based prioritization
        if strategy == 'new_focus':
            priority_weights = {'new': 1000, 'popular': 600, 'superhost': 400}
        elif strategy == 'popular_focus':
            priority_weights = {'new': 600, 'popular': 1000, 'superhost': 400}
        elif strategy == 'superhost_focus':
            priority_weights = {'new': 400, 'popular': 600, 'superhost': 1000}
        else:  # balanced
            priority_weights = {'new': 800, 'popular': 800, 'superhost': 800}

        # Apply the prioritization
        queryset = queryset.annotate(
            is_new_property=Case(
                When(created_at__gte=new_property_threshold, then=priority_weights['new']),
                default=0,
                output_field=IntegerField()
            ),
            is_popular_property=Case(
                When(
                    Q(avg_rating__gte=4.0) & Q(total_booking_count__gte=5),
                    then=priority_weights['popular']
                ),
                default=0,
                output_field=IntegerField()
            ),
            is_superhost_property=Case(
                When(
                    host__current_superhost_tier__isnull=False,
                    host__current_superhost_tier__gt='',
                    then=priority_weights['superhost']
                ),
                default=0,
                output_field=IntegerField()
            ),
            random_factor=Case(
                When(pk__isnull=False, then=random.randint(0, 200)),
                default=0,
                output_field=IntegerField()
            ),
            priority_score=F('is_new_property') + F('is_popular_property') + F('is_superhost_property') + F(
                'random_factor')
        )

        # Apply ordering
        if self.request.GET.get("latitude") and self.request.GET.get("longitude"):
            return queryset.order_by('-priority_score', 'distance', '-created_at')
        else:
            return queryset.order_by('-priority_score', '-created_at')

    def _get_random_strategy(self):
        """Randomly select a prioritization strategy"""
        strategies = ['new_focus', 'popular_focus', 'superhost_focus', 'balanced']
        return random.choice(strategies)


# Configuration settings (can be moved to Django settings)
PROPERTY_PRIORITIZATION_CONFIG = {
    'NEW_PROPERTY_DAYS': 7,  # Days to consider a property "new"
    'POPULAR_RATING_THRESHOLD': 4.0,
    'POPULAR_BOOKING_THRESHOLD': 5,
    'BASE_WEIGHTS': {
        'NEW': 1000,
        'POPULAR': 800,
        'SUPERHOST': 600,
    },
    'SUPERHOST_TIER_MULTIPLIERS': {
        'PLATINUM': 1.3,
        'GOLD': 1.2,
        'SILVER': 1.1,
    },
    'RANDOM_FACTOR_MAX': 200,
    'STRATEGIES': {
        'new_focus': {'new': 1000, 'popular': 600, 'superhost': 400},
        'popular_focus': {'new': 600, 'popular': 1000, 'superhost': 400},
        'superhost_focus': {'new': 400, 'popular': 600, 'superhost': 1000},
        'balanced': {'new': 800, 'popular': 800, 'superhost': 800},
    }
}


# Utility class for managing prioritization rules
class PropertyPrioritizationManager:
    """
    Utility class to manage different prioritization strategies
    """

    @staticmethod
    def get_new_property_threshold(days=None):
        """Get threshold for what constitutes a 'new' property"""
        if days is None:
            days = PROPERTY_PRIORITIZATION_CONFIG['NEW_PROPERTY_DAYS']
        return timezone.now() - timedelta(days=days)

    @staticmethod
    def get_popular_property_criteria():
        """Get criteria for popular properties"""
        return {
            'min_rating': PROPERTY_PRIORITIZATION_CONFIG['POPULAR_RATING_THRESHOLD'],
            'min_bookings': PROPERTY_PRIORITIZATION_CONFIG['POPULAR_BOOKING_THRESHOLD'],
        }

    @staticmethod
    def get_superhost_tier_weights():
        """Get weight multipliers for different superhost tiers"""
        return PROPERTY_PRIORITIZATION_CONFIG['SUPERHOST_TIER_MULTIPLIERS']

    @staticmethod
    def calculate_dynamic_weights(time_of_day=None, day_of_week=None, user_preferences=None):
        """
        Calculate dynamic weights based on time patterns and user preferences
        """
        base_weights = PROPERTY_PRIORITIZATION_CONFIG['BASE_WEIGHTS'].copy()

        # Time-based adjustments
        if day_of_week and day_of_week in [5, 6]:  # Weekend boost for new properties
            base_weights['NEW'] += 200

        if time_of_day and 18 <= time_of_day <= 22:  # Peak hours boost for popular
            base_weights['POPULAR'] += 200

        # User preference adjustments (if available)
        if user_preferences:
            if user_preferences.get('prefers_new_properties'):
                base_weights['NEW'] += 300
            if user_preferences.get('prefers_superhosts'):
                base_weights['SUPERHOST'] += 300
            if user_preferences.get('prefers_popular'):
                base_weights['POPULAR'] += 300

        return base_weights

    @staticmethod
    def get_strategy_weights(strategy_name):
        """Get weights for a specific strategy"""
        return PROPERTY_PRIORITIZATION_CONFIG['STRATEGIES'].get(
            strategy_name,
            PROPERTY_PRIORITIZATION_CONFIG['STRATEGIES']['balanced']
        )

class PublicListingConfigurationListApiView(views.APIView):
    permission_classes = (AllowAny,)
    swagger_tags = ["Public Listings"]

    def get(self, request, *args, **kwargs):
        categories = list(Category.objects.filter().values("id", "name", "icon", "icon_mobile", "status"))
        amenity_data = list(
            Amenity.objects.filter().values("a_type", "id", "name", "icon", "icon_mobile", "status")
        )

        amenity_list_dict = dict()
        for obj in amenity_data:
            amenity_list_dict.setdefault(obj.pop("a_type"), []).append(obj)

        data = {
            "categories": categories,
            "amenities": json.loads(json.dumps(amenity_list_dict)),
        }

        return Response(data=data, status=status.HTTP_200_OK)


class PublicListingRetrieveAPIView(RetrieveAPIView):
    permission_classes = (AllowAny,)
    lookup_field = "unique_id"
    queryset = (
        Listing.objects.filter()
        .prefetch_related("listingamenity_set__amenity")
        .select_related("host__userprofile")
    )
    serializer_class = ListingSerializer
    swagger_tags = ["Public Listings"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        related_fields = [
            {
                "serializer": ListingAmenitySerializer(
                    source="listingamenity_set",
                    read_only=True,
                    many=True,
                    fields=["id"],
                    r_method_fields=["amenity"],
                ),
                "name": "amenities",
            }
        ]
        kwargs["related_fields"] = related_fields
        return self.serializer_class(*args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        data["host"] = get_user_with_profile(instance.host)

        calendar_start_date = date.today()
        calendar_end_date = calendar_start_date + timedelta(weeks=53)

        calendar_data = ListingCalendarDataProcess()(
            {
                "from_date": calendar_start_date,
                "to_date": calendar_end_date,
            },
            instance.id,
        )
        data["calendar_data"] = calendar_data

        service_charge = ServiceCharge.objects.filter(
            sc_type=ServiceChargeTypeOption.GUEST_CHARGE
        ).first()
        data["service_charge_percentage"] = (
            service_charge.value / 100
            if service_charge.calculation_type == "percentage"
            else service_charge.value
        )

        reviews = ListingBookingReview.objects.filter(
            listing_id=instance.id,
            is_host_review=False,
        ).select_related("review_by")
        data["reviews"] = BookingReviewSerializer(
            reviews,
            many=True,
            fields=["rating", "review", "id"],
            r_method_fields=["review_by"],
        ).data

        # data["checkout_data"] = {
        #     "nights": 0,
        #     "service_charge": 0.03,
        #     "booking_price": 0,
        #     "total_price": 0,
        # }

        # if request.GET.get("from_date") and request.GET.get("to_date"):
        #     from_date = datetime.strptime(
        #         request.GET.get("from_date"), "%Y-%m-%d"
        #     ).date()
        #     to_date = datetime.strptime(request.GET.get("to_date"), "%Y-%m-%d").date()
        #     if from_date >= calendar_start_date and to_date >= calendar_start_date:
        #         booking_date_info = {}
        #         for c_date, data_entry in calendar_data.items():
        #             c_date = datetime.strptime(c_date, "%Y-%m-%d").date()
        #             if from_date <= c_date <= to_date:
        #                 booking_date_info[str(c_date)] = data_entry

        #         checkout_data = ListingCheckoutCalculate()(
        #             booking_date_info=booking_date_info,
        #             date_range={"from_date": from_date, "to_date": to_date},
        #             instance=instance,
        #         )
        #         data["checkout_data"] = checkout_data

        return Response(data)


class PublicListingCheckoutCalculateAPIView(views.APIView):
    permission_classes = (AllowAny,)
    swagger_tags = ["Public Listings"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        instance = Listing.objects.get(unique_id=kwargs.get("unique_id"))
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")
        current_date = date.today()

        if not from_date or not to_date:
            return Response(
                data={"message": "from_date and to_date is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
        if (
            from_date >= current_date
            and to_date >= current_date
            and to_date > from_date
        ):
            date_filter = {
                "from_date": from_date,
                "to_date": to_date,
            }
            calendar_data = ListingCalendarDataProcess()(
                date_filter,
                instance.id,
            )
            checkout_data = ListingCheckoutCalculate()(
                booking_date_info=calendar_data,
                date_range=date_filter,
                instance=instance,
            )
            status = checkout_data.pop("status")
            return Response(
                data=checkout_data,
                status=status,
            )


class PublicListingLiteRetrieveAPIView(views.APIView):
    permission_classes = (AllowAny,)
    swagger_tags = ["Public Listings"]

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        instance = Listing.objects.get(unique_id=kwargs.get("unique_id"))
        data = ListingSerializer(
            instance,
            many=False,
            fields=[
                "id",
                "unique_id",
                "title",
                "cover_photo",
                "address",
                "cancellation_policy",
                "avg_rating",
                "total_rating_count",
            ],
        ).data

        return Response(
            data=data,
            status=status.HTTP_200_OK,
        )
