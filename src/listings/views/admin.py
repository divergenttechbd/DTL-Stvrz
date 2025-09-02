from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView, views
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from base.permissions import IsStaff, IsSuperUser
from listings.filters import ListingFilter
from listings.models import Category, Listing
from listings.serializers import (
    ListingAmenitySerializer,
    ListingSerializer,
    ListingStatusUpdateSerializer,
)

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

class AdminListingCategoryListApiView(views.APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Listings"]

    def get(self, request, *args, **kwargs):
        categories = list(Category.objects.filter().values("id", "name", "icon"))
        return Response(data=categories, status=status.HTTP_200_OK)


class AdminListingListAPIView(ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = ListingSerializer
    http_method_names = ["get", "post"]
    filterset_class = ListingFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    swagger_tags = ["Admin Listings"]
    ordering_fields = ["created_at", "-created_at", "avg_rating", "-avg_rating"]

    def get_queryset(self):
        base_queryset = Listing.all_objects.select_related("category", "host")

        # Check if location-based search parameters are provided
        latitude = self.request.query_params.get("latitude")
        longitude = self.request.query_params.get("longitude")
        radius = self.request.query_params.get("radius", 25)  # Default radius: 25km

        # Flag to track if distance annotation was applied
        has_distance_annotation = False

        if latitude and longitude:
            try:
                # Create a point for the search location
                search_point = Point(float(longitude), float(latitude), srid=4326)

                # Annotate queryset with distance and filter by radius
                base_queryset = base_queryset.annotate(
                    distance=Distance("location", search_point)
                ).filter(
                    distance__lte=D(km=float(radius))
                )
                has_distance_annotation = True
            except (ValueError, TypeError):
                # If latitude/longitude are invalid, continue with normal queryset
                has_distance_annotation = False

        # Apply filterset manually to support custom filtering and deleted_status
        filterset = self.filterset_class(self.request.GET, queryset=base_queryset, request=self.request)
        if filterset.is_valid():
            filtered_qs = filterset.qs
        else:
            print(" -- wrong --")
            filtered_qs = base_queryset

        # Apply custom sort_by from query param
        sort_by = self.request.query_params.get("sort_by")
        if sort_by == "oldest":
            filtered_qs = filtered_qs.order_by("created_at")
        elif sort_by == "newest":
            filtered_qs = filtered_qs.order_by("-created_at")
        elif sort_by == "popular":
            filtered_qs = filtered_qs.order_by("-avg_rating")
        elif sort_by == "nearest" and has_distance_annotation:
            # Order by distance only if distance annotation exists
            filtered_qs = filtered_qs.order_by("distance")
        else:
            # Default ordering - if location search is active and has distance annotation, order by distance
            if has_distance_annotation:
                filtered_qs = filtered_qs.order_by("distance")
            else:
                filtered_qs = filtered_qs.order_by("-created_at")

        return filtered_qs

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["category", "owner"]
        return self.serializer_class(*args, **kwargs)


class AdminListingLitListAPIView(ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = ListingSerializer
    queryset = Listing.objects.filter().only("id", "cover_photo", "title")
    search_fields = ("title",)
    swagger_tags = ["Admin Listings"]

    def get_queryset(self):
        show_deleted = self.request.query_params.get("show_deleted", "").lower() == "true"
        if show_deleted:
            return Listing.all_objects.filter().only("id", "cover_photo", "title")
        return Listing.objects.filter().only("id", "cover_photo", "title")


    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["fields"] = ["id", "cover_photo", "title"]
        return self.serializer_class(*args, **kwargs)


class AdminListingRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    permission_classes = (IsStaff,)
    serializer_class = ListingSerializer
    swagger_tags = ["Admin Listings"]

    def get_queryset(self):
        # Check if we should include deleted items when retrieving an object
        include_deleted = self.request.query_params.get("include_deleted", "").lower() == "true"
        if include_deleted:
            return (
                Listing.all_objects.filter()
                .prefetch_related("listingamenity_set__amenity")
                .select_related("category", "host")
            )
        return (
            Listing.objects.filter()
            .prefetch_related("listingamenity_set__amenity")
            .select_related("category", "host")
        )

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
        kwargs["r_method_fields"] = ["category", "owner"]
        kwargs["related_fields"] = related_fields
        return self.serializer_class(*args, **kwargs)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ListingStatusUpdateSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            listing_status = serializer.validated_data.get(
                "listing_status", instance.status
            )
            verification_status = serializer.validated_data.get(
                "verification_status", instance.verification_status
            )

            instance.status = listing_status
            instance.verification_status = verification_status

            instance.verification_status

            instance.save()
            return Response(
                {"message": "Status updated successfully."}, status=status.HTTP_200_OK
            )

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()  # This calls the soft delete method
        return Response(
            {"message": "Listing has been soft deleted."},
            status=status.HTTP_200_OK
        )


class AdminListingRestoreAPIView(views.APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Listings"]

    def post(self, request, pk, *args, **kwargs):
        try:
            # Must use all_objects manager to find deleted listings
            instance = Listing.all_objects.get(pk=pk)
            if not instance.is_deleted:
                return Response(
                    {"message": "This listing is not deleted."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            instance.restore()
            return Response(
                {"message": "Listing has been restored successfully."},
                status=status.HTTP_200_OK
            )
        except Listing.DoesNotExist:
            return Response(
                {"message": "Listing not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminListingHardDeleteAPIView(views.APIView):
    permission_classes = (IsSuperUser,)  # Restrict to superusers only
    swagger_tags = ["Admin Listings"]

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
