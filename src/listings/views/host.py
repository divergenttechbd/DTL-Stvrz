import json
import uuid
from django.db.models import F, Prefetch
from django.contrib.gis.geos import Point
from datetime import datetime

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db import transaction, IntegrityError
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    views, get_object_or_404,
)
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from base.helpers.constants import (
    PLACE_TYPE_DESCRIPTION_MAPPING,
    PLACE_TYPE_ICON_MAPPING, PLACE_TYPE_ICON_MOBILE_MAPPING,
)
from base.helpers.decorators import exception_handler
from base.permissions import HostUserHasObjectAccess, IsHostUser, IsPrimaryHostOrActiveCoHost
from base.type_choices import PlaceTypeOption, ServiceChargeTypeOption, UserTypeOption, ListingStatusOption
from configurations.data import CANCELLATION_POLICY_DATA
from configurations.models import ServiceCharge
from listings.filters import HostListingFilter
from django.contrib.auth import get_user_model
from listings.models import Category, Amenity, Listing, ListingCalendar, ListingCoHost
from listings.serializers import (
    ListingSerializer,
    ListingAmenitySerializer, AssignCoHostSerializer, ListingCoHostSerializer, GrantedListingWithDetailsSerializer,
    BasicListingInfoWithPriceSerializer, ListingCoHostDetailForPrimaryHostSerializer, CoHostedListingDetailSerializer,
    UpdateCoHostAssignmentSerializer, PrimaryHostAssignmentViewSerializer,
)
from listings.views.service import ListingCalendarDataProcess, ListingCreateDataProcess

User = get_user_model()


class HostListingConfigurationApiView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    swagger_tags = ["Host Listings"]

    def get(self, request, *args, **kwargs):
        categories = list(Category.objects.filter().values("id", "name", "icon", "icon_mobile", "status"))
        amenity_data = list(
            Amenity.objects.filter().values("a_type", "id", "name", "icon", "icon_mobile", "status")
        )

        amenity_list_dict = dict()
        for obj in amenity_data:
            amenity_list_dict.setdefault(obj.pop("a_type"), []).append(obj)

        place_types = []
        for choice in PlaceTypeOption:
            place_types.append(
                {
                    "id": choice.value,
                    "name": choice.value.replace("_", " ").title(),
                    "icon": PLACE_TYPE_ICON_MAPPING.get(choice.value),
                    "icon_mobile": PLACE_TYPE_ICON_MOBILE_MAPPING.get(choice.value),
                    "short_description": PLACE_TYPE_DESCRIPTION_MAPPING.get(
                        choice.value
                    ),
                }
            )
        data = {
            "categories": categories,
            "amenities": json.loads(json.dumps(amenity_list_dict)),
            "place_types": place_types,
            "cancellation_policy": CANCELLATION_POLICY_DATA,
        }

        return Response(data=data, status=status.HTTP_200_OK)


class HostListingListCreateAPIView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    serializer_class = ListingSerializer
    http_method_names = ["get", "post"]
    filterset_class = HostListingFilter
    search_fields = ("title",)
    swagger_tags = ["Host Listings"]

    def get_queryset(self):
        return Listing.objects.filter(host_id=self.request.user.id).order_by(
            "-created_at"
        )

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        request.data["host"] = request.user.id
        request.data["title"] = "Write your awesome title"
        request.data["unique_id"] = uuid.uuid4()

        serializer = ListingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            User.objects.filter(id=request.user.id).update(
                total_property=F("total_property") + 1
            )

        return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)


class HostListingRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated, IsPrimaryHostOrActiveCoHost)
    lookup_field = "unique_id"
    queryset = Listing.objects.filter()
    serializer_class = ListingSerializer
    http_method_names = ["get", "patch"]
    removeable_keys = ("unique_id", "host")
    swagger_tags = ["Host Listings"]

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
        service_charges = list(ServiceCharge.objects.values())
        guest_service_charge = 0
        host_service_charge = 0

        for item in service_charges:
            if item["sc_type"] == "host_charge":
                host_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )
            elif item["sc_type"] == "guest_charge":
                guest_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )

        data["guest_service_charge"] = guest_service_charge
        data["host_service_charge"] = host_service_charge
        return Response(data)

    @method_decorator(exception_handler)
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        current_price = instance.price
        amenities = request.data.pop("amenities", None)

        if request.data.get("latitude") and request.data.get("longitude"):
            request.data["location"] = Point(
                float(request.data.get("longitude")),
                float(request.data.get("latitude")),
            )

        serializer = ListingSerializer(
            instance=instance,
            data=request.data,
            partial=True,
            exclude_fields=self.removeable_keys,
        )
        serializer.is_valid(raise_exception=True)

        listing_data_process = ListingCreateDataProcess(instance)

        with transaction.atomic():
            serializer.save()

            if request.data.get("price") and current_price != float(
                request.data.get("price")
            ):
                listing_data_process.process_listing_price(request.data.get("price"))

            if amenities:
                listing_data_process.process_amenities(amenities)

        return Response(
            self.get_serializer(instance=instance).data, status=status.HTTP_200_OK
        )


class HostListingHardDeleteAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsPrimaryHostOrActiveCoHost,)  # Restrict to superusers only
    swagger_tags = ["Host Listings"]

    def delete(self, request, pk, *args, **kwargs):
        try:
            instance = Listing.all_objects.get(pk=pk)
            instance.hard_delete()
            return Response(
                {"message": "Listing has been permanently deleted."},
                status=status.HTTP_200_OK
            )
        except Listing.DoesNotExist:
            return Response(
                {"message": "Listing not found."},
                status=status.HTTP_404_NOT_FOUND
            )



class HostListingCalendarApiView(views.APIView):
    permission_classes = (IsAuthenticated, IsPrimaryHostOrActiveCoHost)

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        listing_id = kwargs.get("listing_id")
        listing = Listing.objects.get(id=listing_id)

        self.check_object_permissions(request, listing)

        formatted_data = request.data["data"]

        # valid_price = all(
        #     entry["price"] == formatted_data[0]["price"] for entry in formatted_data
        # )
        # valid_is_booked = all(not entry["is_booked"] for entry in formatted_data)

        # if not (valid_price and valid_is_booked):
        #     return Response(
        #         data={"message": "Invalid data"},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # #  data formatting
        # grouped_data = []
        # current_group = None
        # for item in formatted_data:
        #     if current_group and current_group[-1]["is_blocked"] == item["is_blocked"]:
        #         current_group[-1]["end_date"] = item["end_date"]
        #     else:
        #         current_group = [item]
        #         grouped_data.append(current_group)

        # result = []
        # for group in grouped_data:
        #     if len(group) > 1:
        #         combined_dict = group[0].copy()
        #         combined_dict["end_date"] = group[-1]["end_date"]
        #         result.append(combined_dict)
        #     else:
        #         result.append(group[0])
        #  data formatting

        for entry in formatted_data:
            start_date = entry["start_date"]
            end_date = entry["end_date"]

            defaults = {
                "base_price": listing.price,
                "custom_price": entry[
                    "price"
                ],  # request.data.get("price", listing.price),
                "is_blocked": entry[
                    "is_blocked"
                ],  # request.data.get("is_blocked", False),
                # "is_booked": entry["is_booked"],
                "note": entry["note"],
            }

            obj, created = ListingCalendar.objects.update_or_create(
                listing_id=listing_id,
                start_date=start_date,
                end_date=end_date,
                defaults=defaults,
            )

            # if not created:
            #     for key, value in defaults.items():
            #         setattr(obj, key, value)
            #     obj.save()

        return Response(
            data={"message": "Successfully submitted"}, status=status.HTTP_200_OK
        )

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        listing_id = kwargs.get("listing_id")
        listing = Listing.objects.get(id=listing_id)

        self.check_object_permissions(request, listing)

        if not request.GET.get("from_date") or not request.GET.get("to_date"):
            calendar_data = {}
        else:
            query_data = {
                "from_date": datetime.strptime(
                    request.GET.get("from_date"), "%Y-%m-%d"
                ).date(),
                "to_date": datetime.strptime(
                    request.GET.get("to_date"), "%Y-%m-%d"
                ).date(),
            }
            calendar_data = ListingCalendarDataProcess()(query_data, listing_id)

        service_charges = list(ServiceCharge.objects.values())
        guest_service_charge = 0
        host_service_charge = 0

        for item in service_charges:
            if item["sc_type"] == "host_charge":
                host_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )
            elif item["sc_type"] == "guest_charge":
                guest_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )

        data = {
            "listing": {
                "base_price": listing.price,
                "minimum_nights": listing.minimum_nights,
                "maximum_nights": listing.maximum_nights,
                "guest_service_charge": guest_service_charge,
                "host_service_charge": host_service_charge,
            },
            "calendar_data": calendar_data,
        }
        return Response(data=data, status=status.HTTP_200_OK)



# ------------------------------------ co host --------------------------------
class ManageListingCoHostsAPIView(APIView):
    """
    Manages the assignment of a co-host to a single listing.
    - POST: Assigns a new co-host or replaces an existing one for a listing.
    - PATCH: Updates the details (commission, access) of an existing assignment.
    - DELETE: Removes a co-host assignment from a listing.
    """
    permission_classes = [IsAuthenticated, IsHostUser]
    swagger_tags = ["Co-host"]

    @swagger_auto_schema(
        request_body=AssignCoHostSerializer,
        operation_summary="Assign or Replace a Co-host for a Listing",
        operation_description=(
            "Assigns a specified user as a co-host to a single listing owned by the authenticated host. "
            "If the listing already has a co-host, this action will **replace** the existing one with the new user."
        ),
        responses={
            201: "Co-host assigned successfully.",
            200: "Co-host replaced successfully.",
            400: "Invalid input or validation error.",
            403: "Permission denied (e.g., not the listing owner).",
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Assigns or replaces a co-host for a single specified listing.
        """
        serializer = AssignCoHostSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            validated_data = serializer.validated_data

            # The serializer provides the validated model instances directly.
            co_host_user_instance = validated_data['co_host_user_id']
            listing_instance = validated_data['listing_id']  # This is now a Listing object

            try:
                assignment, created = ListingCoHost.objects.update_or_create(
                    listing=listing_instance,
                    defaults={
                        'co_host_user': co_host_user_instance,
                        'access_level': validated_data['access_level'],
                        'commission_percentage': validated_data['commission_percentage'],
                        'is_active': True
                    }
                )

                if created:
                    message = "Co-host assigned successfully."
                    status_code = status.HTTP_201_CREATED
                else:
                    message = "Co-host replaced successfully."
                    status_code = status.HTTP_200_OK

                response_data = ListingCoHostSerializer(instance=assignment).data
                return Response({"message": message, "data": response_data}, status=status_code)

            except Exception as e:
                return Response(
                    {"message": "An unexpected error occurred.", "detail": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=UpdateCoHostAssignmentSerializer,
        operation_summary="Update a Co-host Assignment",
        operation_description=(
            "Updates specific details of a co-host assignment, such as the commission percentage, "
            "access level, or active status. This requires the ID of the assignment (which is the listing_id)."
        ),
        responses={
            200: ListingCoHostSerializer,
            403: "Permission denied.",
            404: "Assignment not found."
        }
    )
    def patch(self, request, assignment_id, *args, **kwargs):
        """
        Updates an existing co-host assignment using its ID (listing_id).
        """
        primary_host = request.user
        # Since listing_id is the primary key, we fetch the assignment with it.
        assignment = get_object_or_404(ListingCoHost, pk=assignment_id, primary_host=primary_host)

        serializer = UpdateCoHostAssignmentSerializer(
            instance=assignment,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            updated_assignment = serializer.save()
            response_serializer = ListingCoHostSerializer(updated_assignment)
            return Response(
                {"message": "Co-host assignment updated successfully.", "data": response_serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Remove a Co-host from a Listing",
        operation_description=(
            "Removes a co-host assignment from a specific listing using the assignment's ID (which is the listing_id). "
            "Only the primary host can perform this action."
        ),
        responses={
            204: "Co-host removed successfully.",
            403: "Permission denied.",
            404: "Assignment not found."
        }
    )
    def delete(self, request, assignment_id, *args, **kwargs):
        """
        Removes a co-host assignment using its ID (listing_id).
        """
        primary_host = request.user
        # The requesting user must be the primary host of the assignment.
        assignment = get_object_or_404(
            ListingCoHost,
            pk=assignment_id,
            primary_host=primary_host
        )

        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PrimaryHostCoHostAssignmentsListView(generics.ListAPIView):
    serializer_class = ListingCoHostSerializer
    permission_classes = [IsAuthenticated, IsHostUser]
    filter_backends = [DjangoFilterBackend]  # Enable basic filtering
    # Define filterset_fields if you want to filter by listing_id or co_host_user_id via query params
    # filterset_fields = ['listing__id', 'co_host_user__id', 'access_level', 'is_active']
    swagger_tags = ["Co-host"]

    @swagger_auto_schema(
        operation_summary="List co-host assignments made by the logged-in primary host.",
        operation_description="Retrieves a list of listings where the authenticated host has assigned co-hosts. Can be filtered by a specific co_host_user_id.",
        manual_parameters=[
            openapi.Parameter(
                'co_host_user_id',
                openapi.IN_QUERY,
                description="Optional: Filter assignments by the ID of a specific co-host.",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'listing_id',
                openapi.IN_QUERY,
                description="Optional: Filter assignments by the ID of a specific listing.",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ]
    )
    def get_queryset(self):
        primary_host = self.request.user
        queryset = ListingCoHost.objects.filter(
            primary_host=primary_host  # Or listing__host=primary_host if primary_host field isn't on ListingCoHost
        ).select_related(
            'listing',
            'co_host_user',
            'co_host_user__userprofile'  # If co_host_user_details needs profile info
        ).order_by('-created_at')

        # Optional filtering by a specific co-host
        co_host_user_id_param = self.request.query_params.get('co_host_user_id')
        if co_host_user_id_param:
            try:
                co_host_id = int(co_host_user_id_param)
                queryset = queryset.filter(co_host_user_id=co_host_id)
            except ValueError:
                # Handle invalid ID format, perhaps ignore filter or return error
                pass

        listing_id_param = self.request.query_params.get('listing_id')
        if listing_id_param:
            try:
                listing_id = int(listing_id_param)
                queryset = queryset.filter(listing_id=listing_id)
            except ValueError:
                pass

        return queryset


class PrimaryHostViewCoHostAssignmentsStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsHostUser]
    swagger_tags = ["Co-host"]

    def _calculate_years_hosting(self, user_instance: User) -> int:
        if user_instance.date_joined:

            delta = timezone.now().date() - user_instance.date_joined.date()
            return int(delta.days / 365.25)
        return 0

    def _get_total_active_listings_for_host(self, host_instance: User) -> int:
        return Listing.objects.filter(
            host=host_instance,
            status=ListingStatusOption.PUBLISHED,
            is_deleted=False
        ).count()

    @swagger_auto_schema(
        operation_summary="View assignment status of primary host's listings for a specific co-host",
        manual_parameters=[
            openapi.Parameter('co_host_id', openapi.IN_QUERY, description="ID of the co-host user.", type=openapi.TYPE_INTEGER, required=True)
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'status_code': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'meta_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'total_primary_host_listings_considered': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'granted_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'not_granted_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'co_host_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'bio': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                            'total_active_listings': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total active listings of THIS CO-HOST."), # New
                            'avg_rating': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT, description="Average rating of THIS CO-HOST."), # New
                            'years_hosting': openapi.Schema(type=openapi.TYPE_INTEGER, description="Years THIS CO-HOST has been hosting."), # New
                            'granted_listings': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema( # Using $ref to existing serializers would be better if possible
                                type=openapi.TYPE_OBJECT,
                                # Properties from GrantedListingWithDetailsSerializer
                            )),
                            'not_granted_listings': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                # Properties from BasicListingInfoWithPriceSerializer
                            )),
                        }
                    )
                }
            )
        }
    )
    def get(self, request, *args, **kwargs):
        primary_host = request.user
        co_host_id_str = request.query_params.get('co_host_id')

        if not co_host_id_str:
            return Response({"success": False, "status_code": 400, "message": "co_host_id query parameter is required.", "errors": {}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            co_host_id = int(co_host_id_str)
        except ValueError:
            return Response({"success": False, "status_code": 400, "message": "Invalid co_host_id format. Must be an integer.", "errors": {}}, status=status.HTTP_400_BAD_REQUEST)

        if primary_host.id == co_host_id:
            return Response({"success": False, "status_code": 400, "message": "A host cannot be queried as a co-host for themselves in this context.", "errors": {}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            co_host_user_instance = User.objects.select_related('userprofile').get(pk=co_host_id, u_type=UserTypeOption.HOST, is_active=True)
        except User.DoesNotExist:
            return Response({"success": False, "status_code": 404, "message": f"Co-host user with ID {co_host_id} not found, is not a host, or is not active.", "errors": {}}, status=status.HTTP_404_NOT_FOUND)

        # Get all active, non-deleted listings owned by the primary host
        primary_host_listings_qs = Listing.objects.filter(
            host=primary_host,
            is_deleted=False,
        ).prefetch_related(
            Prefetch(
                'cohost_assignments',
                queryset=ListingCoHost.objects.filter(co_host_user=co_host_user_instance, is_active=True),
                to_attr='active_assignment_for_this_cohost'
            )
        )

        granted_assignments_serialized_data = []
        not_granted_listings_serialized_data = []

        for listing_instance in primary_host_listings_qs:
            assignment_list = getattr(listing_instance, 'active_assignment_for_this_cohost', [])

            if assignment_list:
                assignment = assignment_list[0]
                setattr(listing_instance, 'cohost_assignment_details', assignment)
                granted_assignments_serialized_data.append(PrimaryHostAssignmentViewSerializer(assignment).data)
            else:
                not_granted_listings_serialized_data.append(BasicListingInfoWithPriceSerializer(listing_instance).data)

        co_host_bio = None
        if hasattr(co_host_user_instance, 'userprofile') and co_host_user_instance.userprofile:
            co_host_bio = co_host_user_instance.userprofile.bio

        # Get additional details for the co-host
        co_host_total_active_listings = self._get_total_active_listings_for_host(co_host_user_instance)
        co_host_years_hosting = self._calculate_years_hosting(co_host_user_instance)

        data_payload = {
            "co_host_id": co_host_user_instance.id,
            "name": co_host_user_instance.get_full_name(),
            "image":co_host_user_instance.image,
            "bio": co_host_bio,
            "total_active_listings": co_host_total_active_listings, # New
            "avg_rating": float(co_host_user_instance.avg_rating),       # New (ensure it's a float)
            "years_hosting": co_host_years_hosting,                 # New
            "granted_listings": granted_assignments_serialized_data,
            "not_granted_listings": not_granted_listings_serialized_data
        }

        meta_data = {
            "total_primary_host_listings_considered": primary_host_listings_qs.count(),
            "granted_count": len(granted_assignments_serialized_data),
            "not_granted_count": len(not_granted_listings_serialized_data)
        }

        return Response({
            "success": True,
            "status_code": status.HTTP_200_OK,
            "message": "Co-host assignment status retrieved.",
            "meta_data": meta_data,
            "data": data_payload
        }, status=status.HTTP_200_OK)


class ListCoHostsForListingAPIView(generics.ListAPIView):
    serializer_class = ListingCoHostDetailForPrimaryHostSerializer
    permission_classes = [IsAuthenticated, IsHostUser]
    swagger_tags = ["Co-host"]



    @swagger_auto_schema(
        operation_summary="List active co-hosts assigned to a specific listing.",
        operation_description="For a given listing ID (owned by the authenticated primary host), retrieve a list of all active co-hosts, their names, IDs, and commission percentages for that listing.",
        manual_parameters=[
            openapi.Parameter(
                'listing_id',
                openapi.IN_QUERY,
                description="ID of the listing for which to retrieve co-hosts.",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ]

    )
    def get_queryset(self):
        primary_host = self.request.user
        listing_id_str = self.request.query_params.get('listing_id')

        if not listing_id_str:

            from rest_framework.exceptions import ParseError
            raise ParseError(detail="listing_id query parameter is required.")

        try:
            listing_id = int(listing_id_str)
        except ValueError:
            from rest_framework.exceptions import ParseError
            raise ParseError(detail="Invalid listing_id format. Must be an integer.")


        listing_obj = get_object_or_404(Listing, pk=listing_id, host=primary_host)


        queryset = ListingCoHost.objects.filter(
            listing=listing_obj,
            is_active=True
        ).select_related(
            'co_host_user'
        ).order_by('co_host_user__first_name', 'co_host_user__last_name')

        return queryset



    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())  # Applies any defined DRF filters
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            # Customizing the paginated response
            return Response({
                "success": True,
                "status_code": status.HTTP_200_OK,
                "message": "Co-hosts retrieved successfully.",
                "meta_data": {  # Reconstruct meta_data from paginated_response
                    "total": self.paginator.page.paginator.count if self.paginator else queryset.count(),
                    "page_size": self.paginator.page_size if self.paginator else len(serializer.data),
                    "next": paginated_response.data.get('next'),
                    "previous": paginated_response.data.get('previous'),
                    "current_page": self.paginator.page.number if self.paginator else 1,
                    "total_pages": self.paginator.page.paginator.num_pages if self.paginator else 1,
                },
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "status_code": status.HTTP_200_OK,
            "message": "Co-hosts retrieved successfully.",
            "meta_data": {  # For non-paginated results
                "total": queryset.count(),
                "page_size": queryset.count(),  # All items are on one "page"
                "next": None,
                "previous": None
            },
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class MyCoHostedListingsAPIView(generics.ListAPIView):
    serializer_class = CoHostedListingDetailSerializer
    permission_classes = [IsAuthenticated, IsHostUser]  # Logged-in user must be a host
    filter_backends = [DjangoFilterBackend]
    # Add filters if co-hosts want to filter their co-hosted listings
    # e.g., by primary_host_id, listing status (if accessible via listing relation)
    filterset_fields = {
        'listing__status': ['exact'],  # Example: filter by the status of the co-hosted listing
        'primary_host__id': ['exact'],
        'access_level': ['exact']
    }
    swagger_tags = ["Co-host"]

    @swagger_auto_schema(
        operation_summary="List listings I am actively co-hosting.",
        operation_description="Retrieves a list of listings for which the authenticated user is an active co-host, including listing details like image, price, address, and title, as well as details about the primary host."
    )
    def get_queryset(self):
        current_user_as_cohost = self.request.user

        queryset = ListingCoHost.objects.filter(
            co_host_user=current_user_as_cohost,
            # is_active=True
            # Optionally, filter by listing status if co-hosts should only see published ones:
            # listing__status='PUBLISHED',
            # listing__is_deleted=False,
        ).select_related(
            'listing',  # For listing details (title, address, price, cover_photo)
            'primary_host',  # For primary host details
            # 'primary_host__userprofile' # If primary host details need UserProfile
        ).order_by('-listing__created_at')  # Example: order by when the listing was created

        return queryset
