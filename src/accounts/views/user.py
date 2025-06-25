from decimal import Decimal, InvalidOperation

from bson import ObjectId
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.generics import ListAPIView, get_object_or_404, UpdateAPIView
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from rest_framework.response import Response
from rest_framework import status

from accounts.models import UserProfile, SuperhostStatusHistory
from accounts.serializers import (
    ChangePasswordSerializer,
    HostGuestUserSerializer,
    UserIdentityVerificationSerializer,
    UserProfileSerializer, UserLiveVerificationSerializer,
    SuperhostStatusHistorySerializer, HostPublicProfileSerializer, HostCohostingAvailabilitySerializer,
)
from accounts.services import get_superhost_progress
from base.cache.redis_cache import delete_cache, set_cache
from base.helpers.decorators import exception_handler
from base.helpers.mongo_query import mongo_update_user
from base.mongo.connection import connect_mongo
from base.permissions import IsHostUser
from base.type_choices import (
    IdentityVerificationStatusOption,
    ListingStatusOption,
    NotificationEventTypeOption,
    NotificationTypeOption,
    UserTypeOption,
)
from base.helpers.constants import OtpScopeOption
from bookings.models import ListingBookingReview
from bookings.serializers import BookingReviewSerializer
from listings.models import Listing
from listings.serializers import ListingSerializer
from notifications.models import Notification
from notifications.utils import create_notification, send_notification
from otp.service import OtpService


User = get_user_model()


class UserProfileRetrieveUpdateAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["get", "patch"]
    swagger_tags = ["User Profile"]
    removeable_keys = ("user",)

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        user = self.request.user
        user_data = HostGuestUserSerializer(user).data


        user_data["profile"] = (
            UserProfileSerializer(request.user.userprofile).data
            if hasattr(request.user, "userprofile")
            else None
        )
        latest_reviews = (
            ListingBookingReview.objects.filter(
                review_for_id=user.id,
            )
            .select_related("review_by", "listing")
            .order_by("-created_at")[:2]
        )
        user_data["latest_reviews"] = BookingReviewSerializer(
            latest_reviews, many=True, r_method_fields=["review_by", "listing"]
        ).data

        if user.u_type == UserTypeOption.HOST:
            listings = Listing.objects.filter(
                host_id=user.id, status=ListingStatusOption.PUBLISHED
            ).only("title", "address", "cover_photo", "avg_rating", "unique_id", "price", "id")
            user_data["listings"] = ListingSerializer(
                listings,
                many=True,
                fields=["title", "address", "cover_photo", "avg_rating", "unique_id", "price", "id"],
            ).data

            print(" ----------- >>> ", user_data)

        with connect_mongo() as collections:
            mongo_user_id = collections["User"].find_one(
                {"username": request.user.username}
            )

            if mongo_user_id["u_type"] == "guest":
                user_all_room = collections["ChatRoom"].find(
                    {"from_user.$id": ObjectId(mongo_user_id["_id"])}
                )
            else:
                user_all_room = collections["ChatRoom"].find(
                    {"to_user.$id": ObjectId(mongo_user_id["_id"])}
                )

            total_unread_msg_count = 0
            for room in user_all_room:
                other_user_id = (
                    room["from_user"].id
                    if mongo_user_id["_id"] == room["to_user"].id
                    else room["to_user"].id
                )
                individual_chat_room_msg_count = collections["Message"].count_documents(
                    {
                        "chat_room.$id": ObjectId(room["_id"]),
                        "user.$id": ObjectId(other_user_id),
                        "is_read": False,
                    }
                )
                if individual_chat_room_msg_count > 0:
                    total_unread_msg_count += 1
            user_data["unread_message_count"] = total_unread_msg_count
        return Response(data=user_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=UserProfileSerializer(exclude_fields=('user',))
    )
    @method_decorator(exception_handler)
    def patch(self, request, *args, **kwargs):
        user_instance = self.request.user


        profile_field_names = [f.name for f in UserProfile._meta.get_fields() if
                               f.name not in ('user', 'id', 'created_at', 'updated_at')]
        user_field_names = ['first_name', 'last_name', 'image', 'email']

        profile_data = {}
        user_data = {}

        for key, value in request.data.items():
            if key in profile_field_names:
                profile_data[key] = value
            elif key in user_field_names:
                user_data[key] = value


        profile_instance, created = UserProfile.objects.get_or_create(user=user_instance)


        profile_serializer = None
        if profile_data:
            profile_serializer = UserProfileSerializer(
                instance=profile_instance,
                data=profile_data,
                partial=True  # Allow partial updates
            )
            profile_serializer.is_valid(
                raise_exception=True)
        else:
            profile_serializer = UserProfileSerializer(instance=profile_instance)


        user_serializer = None
        if user_data:
            user_serializer = HostGuestUserSerializer(
                instance=user_instance,
                data=user_data,
                partial=True
            )
            user_serializer.is_valid(raise_exception=True)


        updated_profile = profile_instance  # Initialize with current profile
        updated_user = user_instance  # Initialize with current user

        with transaction.atomic():
            if profile_serializer and profile_data:  # Only save if data was provided and serializer is valid
                updated_profile = profile_serializer.save()

            if user_serializer and user_data:  # Only save if data was provided and serializer is valid
                updated_user = user_serializer.save()
                # If user fields like 'image' were updated, update Mongo
                mongo_user_update_data = {"username": updated_user.username}
                if 'image' in user_data:
                    mongo_user_update_data['image'] = user_data['image']

                if len(mongo_user_update_data) > 1:
                    try:
                        mongo_update_user(data=mongo_user_update_data)
                    except Exception as e:
                        # Log error if Mongo update fails but don't fail the whole request
                        print(f"Warning: Failed to update user in MongoDB: {e}")

        response_user_data = HostGuestUserSerializer(updated_user).data
        response_user_data["profile"] = UserProfileSerializer(updated_profile).data


        return Response(response_user_data, status=status.HTTP_200_OK)



class HostCohostingAvailabilityUpdateAPIView(UpdateAPIView):
    """
    Allows a host to update their co-hosting availability status.
    Accepts a PATCH request with a boolean `is_available_for_cohosting`.
    """
    serializer_class = HostCohostingAvailabilitySerializer
    permission_classes = [IsAuthenticated, IsHostUser]
    http_method_names = ['patch']
    swagger_tags = ["Co-host"]

    def get_object(self):
        """
        This view ensures the user can only update their own profile.
        """
        return self.request.user

    def update(self, request, *args, **kwargs):
        """
        Override the default update method to provide a custom success response.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            "message": "Co-hosting availability updated successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class UserUnreadMessageCountAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        with connect_mongo() as collections:
            mongo_user_id = collections["User"].find_one(
                {"username": request.user.username}
            )

            if mongo_user_id["u_type"] == "guest":
                user_all_room = collections["ChatRoom"].find(
                    {"from_user.$id": ObjectId(mongo_user_id["_id"])}
                )
            else:
                user_all_room = collections["ChatRoom"].find(
                    {"to_user.$id": ObjectId(mongo_user_id["_id"])}
                )

            total_unread_msg_count = 0
            for room in user_all_room:
                # other_user_id = (
                #     room["from_user"].id
                #     if mongo_user_id["_id"] == room["to_user"].id
                #     else room["to_user"].id
                # )

                chat_room_user_ids = [room["to_user"].id, room["from_user"].id]
                other_user_id = (
                    chat_room_user_ids[1]
                    if chat_room_user_ids[0] == mongo_user_id["_id"]
                    else chat_room_user_ids[0]
                )

                individual_chat_room_msg_count = collections["Message"].count_documents(
                    {
                        "chat_room.$id": ObjectId(room["_id"]),
                        "user.$id": ObjectId(other_user_id),
                        "is_read": False,
                    }
                )
                if individual_chat_room_msg_count > 0:
                    total_unread_msg_count += 1
            data = {"unread_message_count": total_unread_msg_count}
        return Response(data=data, status=status.HTTP_200_OK)


class UserIdentityVerificationAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["post"]
    swagger_tags = ["User Profile"]


    @swagger_auto_schema(request_body=UserIdentityVerificationSerializer, tags=['User Profile'])
    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        user = request.user
        if (
            user.identity_verification_status
            == IdentityVerificationStatusOption.VERIFIED
        ):
            return Response(
                {"message": "Already verified"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserIdentityVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_type = NotificationEventTypeOption.USER_VERIFICATION
        user_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(user.id),
                "message": f"Thank you ! Your submission for identity verification is currently under review",
                "link": f"/profile/verify-profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=user.id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(user.id),
                "message": f"A new submission for identity verification from {user.get_full_name()}.",
                "link": f"/user/{user.id}/edit",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data = [
            user_notification,
            admin_notification,
        ]

        user.identity_verification_images = {
            "front_image": request.data["front_image"],
            "back_image": request.data.get("back_image"),
        }
        user.identity_verification_method = request.data["document_type"]
        user.identity_verification_status = IdentityVerificationStatusOption.PENDING
        with transaction.atomic():
            user.save()
            Notification.objects.bulk_create(
                [Notification(**item) for item in notification_data]
            )

        send_notification(notification_data=notification_data)
        return Response(
            {"message": "Successfully submitted"}, status=status.HTTP_200_OK
        )


class UserEmailVerificationAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["get", "post"]
    swagger_tags = ["User Profile"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        user = request.user
        username = user.username
        email = request.data["email"]

        if User.objects.filter(email=email, u_type=user.u_type).exists():
            return Response(
                {"message": "Email already is used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not OtpService.validate_otp(
            input_otp=request.data["otp"],
            username=username,
            scope=OtpScopeOption.EMAIL_VERIFY,
        ):
            return Response(
                {"message": "Invalid otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        user.is_email_verified = True
        user.email = email
        user.save()

        OtpService.delete_otp(username=username, scope=OtpScopeOption.EMAIL_VERIFY)
        return Response(
            {
                "message": "Email verification successfully done",
            },
            status=status.HTTP_200_OK,
        )


class UserPasswordChange(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.validated_data.get("old_password")):
                return Response(
                    {"message": "Wrong password."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(serializer.validated_data.get("new_password"))
            user.save()
            return Response(
                {"message": "Password updated successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserPasswordChangeMobile(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        user = request.user

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)


        if not user.check_password(serializer.validated_data.get("old_password")):
            return Response(
                {"message": "Wrong password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone_number, current_u_type = user.username.split('_', 1)
        except ValueError:
            return Response(
                {"message": "User data inconsistency. Cannot process request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        other_u_type = "guest" if current_u_type == "host" else "host"
        other_username = f"{phone_number}_{other_u_type}"

        with transaction.atomic():

            try:
                other_user = User.objects.select_for_update().get(username=other_username)
            except User.DoesNotExist:
                other_user = None

            new_password = serializer.validated_data.get("new_password")


            user.set_password(new_password)
            user.save()

            if other_user:
                other_user.set_password(new_password)
                other_user.save()

        return Response(
            {"message": "Password updated successfully"}, status=status.HTTP_200_OK
        )


class UserReviewListApi(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BookingReviewSerializer
    swagger_tags = ["User Profile"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["review_by", "listing"]
        return self.serializer_class(*args, **kwargs)

    def get_queryset(self):
        if self.request.GET.get("my_reviews") == "true":
            qs = ListingBookingReview.objects.filter(review_for_id=self.request.user.id)
        else:
            qs = ListingBookingReview.objects.filter(review_by_id=self.request.user.id)

        return qs.select_related("review_by", "listing")


@api_view(["DELETE"])
@permission_classes([AllowAny])
def logout(request: Request) -> Response:
    delete_cache(f"{request.user.username}_token_data")
    delete_cache(key=f"user_mobile_logged_in_{request.user.username}")
    response = Response()
    for cookie_name in request.COOKIES:
        response.set_cookie(
            cookie_name,
            "",
            max_age=0,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
            secure=True,
            httponly=True,
            samesite="None",
            domain=".stayverz.com",
        )
    response.status_code = status.HTTP_200_OK
    response.data = {
        "status": status.HTTP_200_OK,
        "data": [],
        "message": "Logout out successfully",
    }
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@exception_handler
def mobile_login(request: Request) -> Response:
    data = request.data["action"]
    login = data == "login"

    set_cache(
        key=f"user_mobile_logged_in_{request.user.username}",
        value=login,
        ttl=5 * 60 * 60,
    )

    return Response({"message": "success"}, status=status.HTTP_200_OK)


# --------------------- DTL ---------------------------------

class UserSelfieVerificationAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["post"]
    swagger_tags = ["User Profile"]


    @swagger_auto_schema(request_body=UserLiveVerificationSerializer, tags=['User Profile'])
    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        user = request.user
        if (
            user.identity_verification_status
            == IdentityVerificationStatusOption.VERIFIED
        ):
            return Response(
                {"message": "Already verified"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserLiveVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_type = NotificationEventTypeOption.USER_VERIFICATION
        user_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(user.id),
                "message": f"Thank you ! Your submission for identity verification is currently under review",
                "link": f"/profile/verify-profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=user.id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(user.id),
                "message": f"A new submission for identity verification from {user.get_full_name()}.",
                "link": f"/user/{user.id}/edit",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data = [
            user_notification,
            admin_notification,
        ]

        user.identity_verification_images = {
            "live": request.data["live"],
        }
        user.identity_verification_method = request.data["document_type"]
        user.identity_verification_status = IdentityVerificationStatusOption.PENDING
        with transaction.atomic():
            user.save()
            Notification.objects.bulk_create(
                [Notification(**item) for item in notification_data]
            )

        send_notification(notification_data=notification_data)
        return Response(
            {"message": "Successfully submitted"}, status=status.HTTP_200_OK
        )


# class SuperhostProgressAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#     swagger_tags = ["Superhost"]
#
#     @swagger_auto_schema(
#         operation_summary="Get Superhost Program Progress",
#         operation_description="Retrieves the host's current progress towards Superhost tiers based on recent activity.",
#         responses={200: SuperhostOverallProgressSerializer()}
#     )
#     def get(self, request, host_id, *args, **kwargs):
#         host = User.objects.get(id=host_id)
#
#         progress_data = get_superhost_progress(host)
#
#         serializer = SuperhostOverallProgressSerializer(data=progress_data)
#         serializer.is_valid(raise_exception=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


class SuperhostProgressAPIView(APIView):

    permission_classes = [IsAuthenticated]  # Adjust permissions as needed

    swagger_tags = ["Superhost"]

    @swagger_auto_schema(
        operation_summary="Get Host's Superhost Program Progress and Official History",
        operation_description="Retrieves the host's current ongoing progress towards Superhost tiers for the active quarter, their officially awarded Superhost tier, and their quarterly assessment history.",
    )
    def get(self, request, host_id=None, *args, **kwargs):  # host_id from URL
        target_host = None
        if host_id:
            # if not request.user.is_staff:
            #     return Response({"message": "You do not have permission to view other hosts' progress."},
            #                     status=status.HTTP_403_FORBIDDEN)
            target_host = get_object_or_404(User, id=host_id, u_type=UserTypeOption.HOST)
        elif hasattr(request.user, 'u_type') and request.user.u_type == UserTypeOption.HOST:  # Host checking their own
            target_host = request.user
        else:
            return Response({"message": "Host not specified or user is not a host."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not target_host:  # Should be caught by get_object_or_404 or the logic above
            return Response({"message": "Host not found."}, status=status.HTTP_404_NOT_FOUND)


        ongoing_progress_data_dict = get_superhost_progress(target_host)


        history_queryset = SuperhostStatusHistory.objects.filter(host=target_host).order_by('-assessment_period_end',
                                                                                            '-status_achieved_on')[
                           :10]  # Limit for display
        history_serializer = SuperhostStatusHistorySerializer(history_queryset, many=True)

        # 3. Get currently awarded official tier name from User model
        awarded_tier_name = None
        if target_host.current_superhost_tier and hasattr(settings, 'SUPERHOST_TIERS'):
            tier_info = settings.SUPERHOST_TIERS.get(target_host.current_superhost_tier)
            if tier_info:
                awarded_tier_name = tier_info.get('name', target_host.current_superhost_tier)

        if not awarded_tier_name and target_host.current_superhost_tier:  # Fallback if name not in settings
            awarded_tier_name = target_host.current_superhost_tier
        elif not awarded_tier_name:
            awarded_tier_name = "Not a Superhost"

        response_data = {
            'current_ongoing_progress': ongoing_progress_data_dict,  # This dict is already structured
            'official_status_history': history_serializer.data,
            'currently_awarded_official_tier_key': target_host.current_superhost_tier,
            'currently_awarded_official_tier_name': awarded_tier_name,
            'last_official_assessment_on': target_host.superhost_metrics_updated_at
        }

        return Response(response_data, status=status.HTTP_200_OK)


from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Min, Prefetch, Q, Count
import math

def haversine_distance(lat1, lon1, lat2, lon2) -> Decimal:

    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers.
    return Decimal(str(c * r))


class ListHostsInRadiusAPIView(ListAPIView):
    serializer_class = HostPublicProfileSerializer
    permission_classes = [AllowAny]
    swagger_tags = ["Co-host"]

    def get_queryset(self):
        # This method will now return a list of User objects, not a queryset,
        # because the geo-filtering is done in Python.
        # This means DRF's filter_backends won't apply to the geo-filtered list.
        # Standard pagination will also be tricky.
        # A better approach if pagination is needed is to filter in list() method.

        # For now, let's make get_queryset do the work and acknowledge limitations.
        # It won't be a standard DRF queryset flow if heavy Python processing is done here.

        latitude_str = self.request.query_params.get('latitude')
        longitude_str = self.request.query_params.get('longitude')
        radius_str = self.request.query_params.get('radius', '25')

        if not latitude_str or not longitude_str:
            return User.objects.none()  # Return empty QuerySet if no geo provided

        try:
            search_lat = Decimal(latitude_str)
            search_lon = Decimal(longitude_str)
            radius_km = Decimal(radius_str)
        except (InvalidOperation, ValueError):
            return User.objects.none()

        # Fetch all active hosts with their UserProfile data
        # We prefetch UserProfile to access latitude and longitude
        all_active_hosts = User.objects.filter(
            u_type=UserTypeOption.HOST,
            is_active=True,
            is_available_for_cohosting = True
        ).select_related('userprofile')  # Use select_related for OneToOne

        print(all_active_hosts, " --- hosts ---")

        hosts_in_radius_with_distance = []
        for host in all_active_hosts:
            if hasattr(host, 'userprofile') and host.userprofile is not None:
                profile = host.userprofile
                print(" hi ", profile.longitude, profile.latitude)

                try:
                    host_lat = Decimal(str(profile.latitude))
                    host_lon = Decimal(str(profile.longitude))
                except (TypeError, InvalidOperation):
                    continue


                # if host_lat == Decimal('0.0') and host_lon == Decimal('0.0'):
                #     continue

                print(search_lat, search_lon, host_lat, host_lon)
                distance = haversine_distance(search_lat, search_lon, host_lat, host_lon)
                print(distance, " === ", distance <= radius_km)

                if distance <= radius_km:

                    setattr(host, 'calculated_distance_km', distance)
                    hosts_in_radius_with_distance.append(host)
            print(host, " ---------- ", )



        # Sort hosts by the calculated distance
        hosts_in_radius_with_distance.sort(key=lambda h: h.calculated_distance_km)

        host_ids_in_radius_list = [h.id for h in hosts_in_radius_with_distance]

        if not host_ids_in_radius_list:
            return User.objects.none()

        print(host_ids_in_radius_list, " -------- ")

        final_queryset = User.objects.filter(
            id__in=host_ids_in_radius_list
        ).annotate(
            annotated_total_active_listings=Count(
                'listing',
                filter=Q(listing__status=ListingStatusOption.PUBLISHED, listing__is_deleted=False)
            )
        ).select_related('userprofile')

        print(final_queryset)

        return User.objects.filter(
            u_type=UserTypeOption.HOST,
            is_active=True,
            is_available_for_cohosting=True
        ).annotate(
            annotated_total_active_listings=Count(
                'listing',
                filter=Q(listing__status=ListingStatusOption.PUBLISHED, listing__is_deleted=False)
            )
        ).select_related('userprofile').order_by('username')

    def list(self, request, *args, **kwargs):
        latitude_str = self.request.query_params.get('latitude')
        longitude_str = self.request.query_params.get('longitude')
        radius_str = self.request.query_params.get('radius', '25')

        if not latitude_str or not longitude_str:
            # If geo-filtering is the primary purpose, return error or empty
            return Response({"detail": "Latitude and Longitude are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            search_lat = Decimal(latitude_str)
            search_lon = Decimal(longitude_str)
            radius_km = Decimal(radius_str)
        except (InvalidOperation, ValueError):
            return Response({"detail": "Invalid geo parameters."}, status=status.HTTP_400_BAD_REQUEST)

        # Get the base queryset (all active hosts with annotations)
        queryset = self.get_queryset()

        # Python-side filtering for radius
        hosts_in_radius_with_distance_tuples = []
        for host in queryset:  # This iterates over all active hosts initially
            if hasattr(host, 'userprofile') and host.userprofile is not None:
                profile = host.userprofile
                try:
                    host_lat = Decimal(str(profile.latitude))
                    host_lon = Decimal(str(profile.longitude))
                except (TypeError, InvalidOperation):
                    continue

                    # Assuming (0,0) or (None, None) means location not set
                # if (profile.latitude is None or profile.longitude is None) or \
                #     (host_lat == Decimal('0.0') and host_lon == Decimal('0.0')):
                #     continue

                distance = haversine_distance(search_lat, search_lon, host_lat, host_lon)

                if distance <= radius_km:
                    hosts_in_radius_with_distance_tuples.append({'distance': distance, 'host_obj': host})

        # Sort hosts by the calculated distance
        hosts_in_radius_with_distance_tuples.sort(key=lambda item: item['distance'])

        # Extract sorted host objects
        sorted_hosts_in_radius = [item['host_obj'] for item in hosts_in_radius_with_distance_tuples]

        # Manually handle pagination if needed because we have a list, not a queryset
        page = self.paginate_queryset(sorted_hosts_in_radius)  # Pass the list to DRF's paginator
        if page is not None:
            # We need to pass the distance to the serializer context if it's not on the host_obj
            # Let's temporarily attach distance to host_obj for the serializer (not ideal but works)
            # Find a way to pass distance along with host object to serializer in context
            # For this example, HostPublicProfileSerializer will need to access 'distance' from the item
            # This requires a custom serializer or modifying how items are passed.

            # A simpler way for now: Serializer won't show distance if not annotated.
            # Or, if HostPublicProfileSerializer is updated to look for a context variable.
            # For now, we'll let the serializer use annotations if any were on host_obj.
            # The `annotated_total_active_listings` is already on host_obj from get_queryset().
            # The distance is not, because it was calculated in Python.

            # To get distance into the serializer, we could pass a list of dicts to it
            # where each dict includes the host and their calculated distance.
            # This means HostPublicProfileSerializer would need to handle that.

            # Let's simplify: the serializer will just show host data. Ordering is done.
            # If you need to *display* the distance, the serializer or this list method needs adjustment.

            # For now, let's assume HostPublicProfileSerializer is updated to take `distance` from context or a wrapper.
            # Or, we can prepare data for it.

            data_for_serializer = []
            for item in page:  # page is now a list of host objects after pagination
                host_data = HostPublicProfileSerializer(item, context=self.get_serializer_context()).data
                # Find the distance for this host from our sorted list (inefficient if page is large)
                # This is messy. It's better if distance is an attribute or passed via context per item.

                # A cleaner way is to adjust HostPublicProfileSerializer to accept an extra field
                # or modify the items before pagination.

                # Let's assume for now we just serialize the host objects from the page.
                # The `distance` field in the serializer based on `distance_from_search` will be None.
                data_for_serializer.append(host_data)

            return self.get_paginated_response(data_for_serializer)

        # If not paginated
        # Similar issue with getting distance into serializer here
        serializer = self.get_serializer(sorted_hosts_in_radius, many=True)
        return Response(serializer.data)
