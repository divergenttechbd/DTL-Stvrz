from base.cache.redis_cache import get_cache
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db.models import Count
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, ListAPIView, views
from base.helpers.decorators import exception_handler
from base.helpers.utils import identifier_builder
from base.permissions import IsStaff, IsSuperUser
from base.type_choices import (
    BookingStatusOption,
    NotificationEventTypeOption,
    NotificationTypeOption,
    PaymentStatusOption,
)
from bookings.models import Booking
from notifications.models import FCMToken, Notification
from notifications.tasks.notification import send_fcm_notification
from notifications.utils import create_notification, send_notification
from payments.filters import AdminHostPayMethodFilter, AdminHostPaymentFilter
from payments.models import HostPayMethod, HostPayment, HostPaymentItem
from payments.serializers import (
    HostPayMethodSerializer,
    HostPaymentItemSerializer,
    HostPaymentSerializer,
)


class AdminHostPayMethodListAPIView(ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = HostPayMethodSerializer
    queryset = HostPayMethod.objects.filter().order_by("-created_at")
    filterset_class = AdminHostPayMethodFilter
    swagger_tags = ["Admin Payments"]


class AdminHostPaymentListCreateAPIView(ListCreateAPIView):
    permission_classes = (IsStaff,)
    serializer_class = HostPaymentSerializer
    queryset = (
        HostPayment.objects.filter()
        .select_related("host", "pay_method")
        .order_by("-created_at")
    )
    filterset_class = AdminHostPaymentFilter
    search_fields = ("invoice_no",)
    http_method_names = ["get", "post"]
    swagger_tags = ["Admin Payments"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["host", "pay_method"]
        return self.serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        response = super().list(request, args, kwargs)

        stat_qs = HostPayment.objects.filter()
        if request.GET.get("host"):
            stat_qs = stat_qs.filter(host_id=request.GET.get("host"))

        response.data["status_count"] = list(
            stat_qs.values("status").annotate(status_count=Count("status"))
        )
        return response

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        booking_ids = request.data["booking_ids"]
        booking_objs = list(
            Booking.objects.exclude(status=BookingStatusOption.INITIATED)
            .filter(id__in=booking_ids)
            .values(
                "id",
                "host_pay_out",
                "host_id",
                "guest_count",
                "night_count",
                "reservation_code",
                "invoice_no",
            )
        )
        host_ids = [item["host_id"] for item in booking_objs]
        all_same_host_id = len(set(host_ids)) == 1

        if (
            len(booking_ids) != len(booking_objs)
            or HostPaymentItem.objects.filter(booking_id__in=booking_ids).exists()
        ):
            return Response(
                {"message": "Invalid booking ids"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not all_same_host_id:
            return Response(
                {"message": "Invalid host id"}, status=status.HTTP_400_BAD_REQUEST
            )

        total_amount = sum(item["host_pay_out"] for item in booking_objs)

        host_default_payment_method = HostPayMethod.objects.get(
            host_id=host_ids[0], is_default=True
        )
        with transaction.atomic():
            host_payment = HostPayment.objects.create(
                host_id=host_ids[0],
                invoice_no=identifier_builder(
                    table_name="payments_hostpayment", prefix="HP"
                ),
                pay_method_id=host_default_payment_method.id,
                total_amount=total_amount,
                status=PaymentStatusOption.UNPAID,
                payment_date=timezone.now().date(),
            )

            for item in booking_objs:
                item.pop("host_id")
                item["booking_id"] = item.pop("id")
                item["host_payment_id"] = host_payment.id
                item["amount"] = item.pop("host_pay_out")

            HostPaymentItem.objects.bulk_create(
                [HostPaymentItem(**item) for item in booking_objs], batch_size=1000
            )

        return Response(
            data={"host_payment_id": host_payment.invoice_no},
            status=status.HTTP_201_CREATED,
        )


class AdminHostPaymentRetrieveUpdateAPIView(views.APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Payments"]

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")

        instance = HostPayment.objects.select_related("host").get(invoice_no=invoice_no)

        related_fields = [
            {
                "serializer": HostPaymentItemSerializer(
                    source="hostpaymentitem_set",
                    read_only=True,
                    many=True,
                    fields=[
                        "id",
                        "reservation_code",
                        "night_count",
                        "guest_count",
                        "amount",
                    ],
                ),
                "name": "items",
            }
        ]

        payment_data = HostPaymentSerializer(
            instance, related_fields=related_fields, r_method_fields=["host"]
        ).data
        host_pay_method_qs = HostPayMethod.objects.filter(host_id=instance.host_id)
        host_pay_method_data = HostPayMethodSerializer(
            host_pay_method_qs, many=True
        ).data

        result = {
            "host_pay_method_data": host_pay_method_data,
            "payment_data": payment_data,
        }
        return Response(data=result, status=status.HTTP_200_OK)

    @method_decorator(exception_handler)
    def patch(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")
        instance = HostPayment.objects.get(invoice_no=invoice_no)

        if instance.status == "paid":
            return Response(
                data={"message": "Payment already done"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking_ids = list(
            HostPaymentItem.objects.filter(host_payment_id=instance.id).values_list(
                "booking_id", flat=True
            )
        )

        event_type = NotificationEventTypeOption.PAYOUT
        host_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(instance.id),
                "message": "Congratulations ! You’ve got a new payout from Stayverz",
                "link": f"/host-dashboard/earnings",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=instance.host_id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(instance.id),
                "message": f"A new payout is completed by {request.user.get_full_name()} for the {instance.host.get_full_name()}",
                "link": f"/payouts/{invoice_no}",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )

        notification_data = [
            host_notification,
            admin_notification,
        ]

        with transaction.atomic():
            instance.payment_date = request.data["payment_date"]
            instance.pay_method_id = request.data["pay_method"]
            instance.status = "paid"
            instance.save()
            Booking.objects.filter(id__in=booking_ids).update(
                host_payment_status=PaymentStatusOption.PAID
            )

            Notification.objects.bulk_create(
                [Notification(**item) for item in notification_data]
            )

        send_notification(notification_data=notification_data)

        host_device_token = FCMToken.objects.filter(user_id=instance.host_id).first()
        if host_device_token :
            title = "Payment Message"
            body = f"Congratulations ! You’ve got a new payout from Stayverz"
            data = {"url": "/host-dashboard/earnings", "key2": "value2"}
            send_fcm_notification.delay(host_device_token.token, title, body, data)

        return Response({"message": "Payment updated"}, status=status.HTTP_200_OK)
