from datetime import datetime, timedelta
import io
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now
from django.contrib.auth.hashers import make_password
from django.utils.decorators import method_decorator
import pytz
from drf_yasg.utils import swagger_auto_schema
from rest_framework.renderers import JSONRenderer

from accounts.models import UserDTL
from base.cache.redis_cache import get_cache
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import (
    ListCreateAPIView,
    ListAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.permissions import IsAuthenticated
from accounts.fields import ADMIN_STAFF_FIELD_LIST

from accounts.filters import UserFilter
from accounts.serializers import (
    HostGuestUserSerializer,
    StatusUpdateSerializer,
    UserProfileSerializer,
    UserSerializer, UserIdentityVerificationSerializer, UserDTLSerializer,
)
from base.helpers.decorators import exception_handler
from base.helpers.mongo_query import create_user
from base.helpers.utils import entries_to_remove, field_name_to_label
from base.permissions import IsStaff, IsSuperUser
from base.type_choices import (
    BookingStatusOption,
    NotificationEventTypeOption,
    NotificationTypeOption,
    UserRoleOption,
    UserStatusOption,
    UserTypeOption,
)
from bookings.models import Booking
from notifications.models import FCMToken, Notification
from notifications.tasks.notification import (
    send_fcm_notification,
    send_fcm_notification_without_task,
)
from notifications.utils import create_notification, send_notification
from django.http import HttpResponse
import xlsxwriter
from io import BytesIO
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

User = get_user_model()


def UserDTLetail(request, pk):
    print('--------------------')
    dtl = UserDTL.objects.get(id=pk)
    print(dtl.name)
    ser = UserDTLSerializer(dtl)
    print(ser.data)
    data = JSONRenderer().render(ser.data)
    print(data)
    return HttpResponse(data, content_type='application/json')


class AdminStaffListCreateApiView(ListCreateAPIView):
    permission_classes = (IsStaff,)
    serializer_class = UserSerializer
    queryset = User.objects.filter(is_staff=True).order_by("-id")
    filterset_class = UserFilter
    swagger_tags = ["Admin Users"]

    def get_serializer(self, *args, **kwargs):
        kwargs["fields"] = ADMIN_STAFF_FIELD_LIST
        return self.serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        response = super().list(request, args, kwargs)
        response.data["user_status_count"] = list(
            User.objects.filter(is_staff=True)
            .values("status")
            .annotate(status_count=Count("status"))
            .order_by("status")
        )

        return response

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        if User.objects.filter(email=request.data["email"]).exists():
            return Response(
                {"message": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(phone_number=request.data["phone_number"]).exists():
            return Response(
                {"message": "Phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.data["is_active"] = True
        request.data["is_staff"] = True
        request.data["u_type"] = UserTypeOption.SYSTEM
        request.data["is_superuser"] = (
            request.data["role"] == UserRoleOption.SUPER_ADMIN
        )
        request.data["username"] = request.data["email"]
        request.data["password"] = make_password(request.data["password"])
        request.data["wishlist_listings"] = []
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        create_user(serializer.data)
        return Response({"message": "User created"}, status=status.HTTP_201_CREATED)
        # return super(AdminStaffListCreateApiView, self).create(request, *args, **kwargs)


class AdminStaffRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    permission_classes = (IsStaff,)
    serializer_class = UserSerializer
    queryset = User.objects.filter(is_staff=True)
    filterset_class = UserFilter
    swagger_tags = ["Admin Users"]
    removeable_keys = ("username", "password", "u_type")

    def get_serializer(self, *args, **kwargs):
        kwargs["fields"] = ADMIN_STAFF_FIELD_LIST
        return self.serializer_class(*args, **kwargs)

    @method_decorator(exception_handler)
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.data.get("email") and (
            User.objects.filter(email=request.data["email"])
            .exclude(id=instance.id)
            .exists()
        ):
            return Response(
                {"message": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.data.get("phone_number") and (
            User.objects.filter(phone_number=request.data["phone_number"])
            .exclude(id=instance.id)
            .exists()
        ):
            return Response(
                {"message": "Phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.id == instance.id:
            return Response(
                {"message": "You can not update your self"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # if instance.is_superuser and request.data.get("status") != "active":
        #     return Response(
        #         {"message": "Super user status can not be restricted"},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        updated_request_data = entries_to_remove(
            self.request.data, self.removeable_keys
        )
        request.data.update(updated_request_data)

        user_status = request.data.get("status", instance.status)
        request.data["status"] = user_status
        request.data["is_active"] = user_status == UserStatusOption.ACTIVE
        return super().patch(request, *args, **kwargs)


class AdminUserListApiView(ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = HostGuestUserSerializer
    queryset = User.objects.filter(is_staff=False).order_by("-created_at")
    filterset_class = UserFilter
    search_fields = (
        "email",
        "phone_number",
        "first_name",
        "last_name",
    )
    swagger_tags = ["Admin Users"]

    def list(self, request, *args, **kwargs):
        response = super().list(request, args, kwargs)

        if request.GET.get("report_download") == "true":
            queryset = self.filter_queryset(self.get_queryset()).values(
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "u_type",
                "identity_verification_status",
                "date_joined",
            )
            headers = headers = [
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "u_type",
                "identity_verification_status",
                "date_joined",
            ]
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            worksheet = workbook.add_worksheet("Data")
            for col_num, header in enumerate(headers):
                worksheet.write(0, col_num, header)
            for row_num, row_data in enumerate(queryset, 1):
                for col_num, header in enumerate(headers):
                    cell_value = row_data[header]
                    if isinstance(cell_value, (dict, list)):
                        cell_value = str(
                            cell_value
                        )  # Convert dicts and lists to strings
                    if isinstance(cell_value, datetime):
                        cell_value = str(
                            cell_value.astimezone(pytz.timezone("Asia/Dhaka")).strftime(
                                "%Y-%m-%d"
                            )
                        )  # str(cell_value).split("T")[0]
                    worksheet.write(row_num, col_num, cell_value)
            workbook.close()
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="data.xlsx"'
            return response
        if request.GET.get("stats"):
            response.data["user_status_count"] = list(
                User.objects.filter(is_staff=False)
                .values("status")
                .annotate(status_count=Count("status"))
                .order_by("status")
            )
        return response


class AdminUserRetrieveUpdateAPIView(APIView):
    permission_classes = (IsStaff,)

    def get(self, request, *args, **kwargs):
        print(request.data)
        user = User.objects.get(id=kwargs.get("pk"), is_staff=False)
        userx = User.objects.get(id=67)
        print(userx)
        user_data = HostGuestUserSerializer(user).data
        user_data["profile"] = (
            UserProfileSerializer(
                user.userprofile, fields=["id", "languages", "bio"]
            ).data
            if hasattr(user, "userprofile")
            else None
        )
        return Response(data=user_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(request_body=StatusUpdateSerializer)
    def patch(self, request, *args, **kwargs):
        serializer = StatusUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(id=kwargs.get("pk"), is_staff=False)
        validated_data = serializer.validated_data

        # --- 1. Determine what changed ---
        new_user_status = validated_data.get("user_status")
        new_identity_status = validated_data.get("identity_status")

        user_status_changed = new_user_status and new_user_status != user.status
        identity_status_changed = new_identity_status and new_identity_status != user.identity_verification_status

        print(user_status_changed, identity_status_changed, new_user_status, new_identity_status, " --------- ")
        if not user_status_changed and not identity_status_changed:

            pass


        user_message_parts = []
        if user_status_changed:
            user_message_parts.append(f"Your account status has been updated to '{new_user_status}'.")

        if identity_status_changed:
            identity_msg = f"Your identity verification status is now '{new_identity_status}'."

            if new_identity_status == "rejected":
                reason = validated_data.get("reject_reason")
                if reason:
                    identity_msg += f" Reason: {reason}"
            user_message_parts.append(identity_msg)

        final_user_message = " ".join(user_message_parts)

        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'phone_number' in validated_data:
            user.phone_number = validated_data['phone_number']
        if 'email' in validated_data:
            user.email = validated_data['email']

        if user_status_changed:
            user.status = new_user_status
            user.is_active = new_user_status == UserStatusOption.ACTIVE

        if identity_status_changed:
            user.identity_verification_status = new_identity_status
            user.identity_verification_reject_reason = (
                validated_data.get("reject_reason", "")
                if new_identity_status == "rejected"
                else ""
            )


        notifications_to_create = []
        print(" ----- final_user_message ", final_user_message)
        if final_user_message:

            user_notification_payload = create_notification(
                event_type=NotificationEventTypeOption.USER_VERIFICATION,
                data={
                    "identifier": str(user.id),
                    "message": final_user_message,
                    "link": "/user/profile",
                },
                n_type=NotificationTypeOption.USER_NOTIFICATION,
                user_id=user.id,
            )
            notifications_to_create.append(user_notification_payload)


            admin_message = f"Status update for {user.get_full_name()}: {final_user_message}"
            admin_notification_payload = create_notification(
                event_type=NotificationEventTypeOption.USER_VERIFICATION,
                data={
                    "identifier": str(user.id),
                    "message": admin_message,
                    "link": f"/user/{user.id}/edit",
                },
                n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
            )
            notifications_to_create.append(admin_notification_payload)


        with transaction.atomic():
            user.save()
            if notifications_to_create:
                Notification.objects.bulk_create(
                    [Notification(**item) for item in notifications_to_create]
                )


        if notifications_to_create:
            print(" ------- A -----------")
            send_notification(notification_data=notifications_to_create)

            host_device_token = FCMToken.objects.filter(user_id=user.id).first()
            print(" ---------- fcm -----------")
            if host_device_token:
                send_fcm_notification.delay(
                    device_token=host_device_token.token,
                    title="Account Update",
                    body=final_user_message,
                    data={"url": "/user/profile"}
                )

        return Response(
            {"message": "User updated successfully."}, status=status.HTTP_200_OK
        )


class AdminDashboardStatAPIView(APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Dashboard"]

    def get(self, request, *args, **kwargs):
        current_month = now().month
        current_year, current_week, _ = now().isocalendar()

        current_year = now().year

        query_type = request.GET.get("query_type", "MONTHLY")

        if query_type == "MONTHLY":
            filter_params = {
                "updated_at__month": current_month,
                "updated_at__year": current_year,
            }
            user_filter = {
                "created_at__month": current_month,
                "created_at__year": current_year,
            }
        elif query_type == "YEARLY":
            filter_params = {
                "updated_at__year": current_year,
            }
            user_filter = {
                "created_at__year": current_year,
            }
        else:
            filter_params = {
                "updated_at__week": current_week,
                "updated_at__year": current_year,
            }
            user_filter = {
                "created_at__week": current_week,
                "created_at__year": current_year,
            }

        cancelled_booking_count = Booking.objects.filter(
            **filter_params, status=BookingStatusOption.CANCELLED
        ).count()

        user_count = User.objects.filter(
            **user_filter,
            is_staff=False,
        ).count()

        total_profit_filter_params = {
            k.replace("updated", "created"): v for k, v in filter_params.items()
        }

        success_booking_count = Booking.objects.filter(
            **total_profit_filter_params, status=BookingStatusOption.CONFIRMED
        ).count()

        total_profit = (
            Booking.objects.filter(
                **total_profit_filter_params, status=BookingStatusOption.CONFIRMED
            )
            .aggregate(total_profit=Sum("total_profit"))
            .get("total_profit")
            or 0
        )

        result = {
            "success_booking_count": success_booking_count,
            "cancelled_booking_count": cancelled_booking_count,
            "total_profit": total_profit,
            "user_count": user_count,
        }
        return Response({"data": result}, status=status.HTTP_200_OK)


class AdminBestSellingHostListAPIView(APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Dashboard"]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'start_date',
                openapi.IN_QUERY,
                description="Filter from this date (format: YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
            ),
            openapi.Parameter(
                'end_date',
                openapi.IN_QUERY,
                description="Filter up to this date (format: YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATE,
            ),
            openapi.Parameter(
                'sort_by',
                openapi.IN_QUERY,
                # --- CHANGE 1: Added 'total_bookings' to the description ---
                description="Field to sort by: total_sell_amount | total_property | total_bookings | first_name | last_name",
                type=openapi.TYPE_STRING,
                default="total_sell_amount"
            ),
            openapi.Parameter(
                'order',
                openapi.IN_QUERY,
                description="Sort order: asc | desc",
                type=openapi.TYPE_STRING,
                default="desc"
            ),
        ],
        responses={200: "Best selling host list returned"},
    )
    def get(self, request, *args, **kwargs):
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        sort_by = request.GET.get("sort_by", "total_sell_amount")
        order = request.GET.get("order", "desc")

        # --- CHANGE 2: Add 'total_bookings' to the allowed fields ---
        allowed_sort_fields = ["total_sell_amount", "total_property", "total_bookings", "first_name", "last_name"]
        if sort_by not in allowed_sort_fields:
            return Response(
                {"error": f"Invalid sort_by field. Allowed fields: {', '.join(allowed_sort_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sort_order = f"-{sort_by}" if order.lower() == "desc" else sort_by

        # --- CHANGE 3: Build a separate filter for bookings ---
        # This will be used inside the annotation.
        booking_filter = Q()
        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

                booking_filter &= Q(host_bookings__created_at__gte=start_date)

            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                booking_filter &= Q(host_bookings__created_at__lt=end_date + timedelta(days=1))

        except ValueError:
            return Response(
                {"error": "Invalid date format. Please use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )


        qs = (
            User.objects.filter(u_type="host")
            .annotate(
                # Create a new field 'total_bookings' on each User object
                total_bookings=Count('host_bookings', filter=booking_filter)
            )
            .filter(total_bookings__gt=0)  # Optional: Only show hosts who had at least 1 booking in the period
            .order_by(sort_order)[:10]
        )

        data = UserSerializer(
            qs,
            many=True,
            fields=[
                "id",
                "username",
                "first_name",
                "last_name",
                "total_sell_amount",
                "total_property",
                "total_bookings",  # Add the new field here
            ],
        ).data

        return Response({"data": data}, status=status.HTTP_200_OK)
class AdminUserReportDownloadAPIView(APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Dashboard"]

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        formatted_filters = {}
        if request.GET.get("u_type"):
            formatted_filters["u_type"] = request.GET.get("u_type")
        if request.GET.get("identity_verification_status"):
            formatted_filters["identity_verification_status"] = request.GET.get(
                "identity_verification_status"
            )
        if (
            request.GET.get("date_joined_gte")
            and request.GET.get("date_joined_gte") != None
        ):
            utc_date_time = datetime.strptime(
                request.GET.get("date_joined_gte"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=pytz.utc)
            dhaka_timezone = pytz.timezone("Asia/Dhaka")
            dhaka_date_time = utc_date_time.astimezone(dhaka_timezone).date()
            formatted_filters["date_joined__gte"] = dhaka_date_time
        if (
            request.GET.get("date_joined_lte")
            and request.GET.get("date_joined_lte") != None
        ):
            utc_date_time = datetime.strptime(
                request.GET.get("date_joined_lte"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=pytz.utc)
            dhaka_timezone = pytz.timezone("Asia/Dhaka")
            dhaka_date_time = utc_date_time.astimezone(dhaka_timezone).date()
            formatted_filters["date_joined__lte"] = dhaka_date_time

        qs = User.objects.filter(**formatted_filters)

        qs = qs.values(
            "first_name",
            "last_name",
            "phone_number",
            "u_type",
            "identity_verification_status",
            "date_joined",
        )

        output = io.BytesIO()

        # Create a workbook and add a worksheet
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Define header titles
        headers = [
            "first_name",
            "last_name",
            "phone_number",
            "u_type",
            "identity_verification_status",
            "date_joined",
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, field_name_to_label(header))

        for row, obj in enumerate(qs, start=1):
            for col, column in enumerate(headers):
                if isinstance(obj[column], datetime):
                    obj[column] = obj[column].date()
                worksheet.write(row, col, str(obj[column]))

        workbook.close()

        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="user_report.xlsx"'
        output.seek(0)
        response.write(output.getvalue())

        return response
