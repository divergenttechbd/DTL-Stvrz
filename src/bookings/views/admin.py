import io
import xlsxwriter
import pytz
from django.utils.dateparse import parse_date
from datetime import date, datetime
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import F, Value
from django.db.models.functions import ExtractMonth, Concat, Substr
from django.db.models import Q, Count, Sum, When, IntegerField, Case, CharField
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from base.helpers.decorators import exception_handler
from base.helpers.utils import field_name_to_label
from base.permissions import IsStaff, IsSuperUser
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from base.type_choices import BookingStatusOption, PaymentStatusOption
from bookings.filters import AdminBookingFilter, BookingReviewFilter
from bookings.models import Booking, ListingBookingReview
from bookings.serializers import BookingReviewSerializer, BookingSerializer
import pandas as pd

class AdminLatestBookingListAPIView(APIView):
    permission_classes = (IsStaff,)
    serializer_class = BookingSerializer

    def get(self, request, *args, **kwargs):
        qs = (
            Booking.objects.exclude(status__in=[
        BookingStatusOption.INITIATED,
        BookingStatusOption.PENDING_CONFIRMATION,
        BookingStatusOption.DECLINED,
        BookingStatusOption.ACCEPTED,
    ])
            .filter()
            .select_related("listing", "guest", "host")
            .order_by("-updated_at")
        )[:5]

        data = BookingSerializer(
            qs, many=True, r_method_fields=["listing", "guest", "host"]
        ).data

        return Response({"data": data}, status=status.HTTP_200_OK)


class AdminBookingListAPIView(generics.ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = BookingSerializer
    # queryset = (
    #     Booking.objects.exclude(status=BookingStatusOption.INITIATED)
    #     .filter()
    #     .select_related("listing", "guest", "host")
    #     .order_by("-created_at")
    # )
    search_fields = (
        "guest__phone_number",
        "host__phone_number",
        "reservation_code",
        "guest__first_name",
        "host__first_name",
        "listing__title",
    )
    filterset_class = AdminBookingFilter
    swagger_tags = ["Admin Bookings"]

    def get_queryset(self):
        current_date = date.today()
        query_param = self.request.GET.get("event_type")
        qs = Booking.objects.exclude(status__in=[
        BookingStatusOption.INITIATED,
        BookingStatusOption.PENDING_CONFIRMATION,
        BookingStatusOption.DECLINED,
        BookingStatusOption.ACCEPTED,
    ])
        # qs = Booking.objects.filter(status=BookingStatusOption.CONFIRMED)

        # qs = Booking.objects.filter()

        if self.request.GET.get("bookings"):
            if query_param == "currently_hosting":
                qs = qs.filter(
                    Q(check_in__lte=current_date) & Q(check_out__gte=current_date),
                    status=BookingStatusOption.CONFIRMED,
                )
            elif query_param == "completed":
                qs = qs.filter(
                    status=BookingStatusOption.CONFIRMED,
                    check_out__lt=current_date,
                )
            elif query_param == "upcoming":
                qs = qs.filter(
                    status=BookingStatusOption.CONFIRMED,
                    check_in__gt=current_date,
                )
            elif query_param == "cancelled":
                qs = qs.filter(
                    status=BookingStatusOption.CANCELLED,
                    # check_in__gt=current_date,
                )
            else:
                qs = qs  # qs.filter(status=BookingStatusOption.CONFIRMED)
        else:
            qs = qs.filter(
                check_in__lte=current_date, status=BookingStatusOption.CONFIRMED
            )

            # check_out__lt=current_date, status=BookingStatusOption.CONFIRMED

        return qs.select_related("listing", "guest", "host").order_by("-created_at")

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["listing", "guest", "host"]
        return self.serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        response = super().list(request, args, kwargs)

        if request.GET.get("transactions"):
            current_date = timezone.now().date()
            seven_days_ago = current_date - timezone.timedelta(days=7)

            paid_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_payment_status=PaymentStatusOption.PAID,
                check_in__lte=current_date,
            )

            unpaid_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_payment_status=PaymentStatusOption.UNPAID,
                check_in__lte=current_date,
            )

            overdue_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_payment_status=PaymentStatusOption.UNPAID,
            ).filter(
                check_in__lte=seven_days_ago
            )  # check_out__lte=seven_days_ago

            paid_sum_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_payment_status=PaymentStatusOption.PAID,
                check_in__lte=current_date,
            )

            unpaid_sum_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_payment_status=PaymentStatusOption.UNPAID,
                check_in__lte=current_date,
            )

            overdue_sum_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                check_in__lte=seven_days_ago,
                host_payment_status=PaymentStatusOption.UNPAID,
            )

            if request.GET.get("host"):
                paid_qs = paid_qs.filter(host_id=request.GET.get("host"))
                overdue_qs = overdue_qs.filter(host_id=request.GET.get("host"))
                unpaid_qs = unpaid_qs.filter(host_id=request.GET.get("host"))

                paid_sum_qs = paid_qs.filter(host_id=request.GET.get("host"))
                unpaid_sum_qs = unpaid_qs.filter(host_id=request.GET.get("host"))
                overdue_sum_qs = overdue_qs.filter(host_id=request.GET.get("host"))

            paid_count = paid_qs.count()
            unpaid_count = unpaid_qs.count()
            overdue_count = overdue_qs.count()

            paid_sum = paid_sum_qs.aggregate(total=Sum("host_pay_out"))["total"]
            unpaid_sum = unpaid_sum_qs.aggregate(total=Sum("host_pay_out"))["total"]
            overdue_sum = overdue_sum_qs.aggregate(overdue_sum=Sum("host_pay_out"))[
                "overdue_sum"
            ]

            response.data["host_payment_status_count"] = [
                {
                    "host_payment_status": "overdue",
                    "status_count": overdue_count,
                },
                {
                    "host_payment_status": "unpaid",
                    "status_count": unpaid_count,
                },
                {
                    "host_payment_status": "paid",
                    "status_count": paid_count,
                },
            ]

            host_payment_status_sum = [
                {
                    "host_payment_status": "paid",
                    "total_pay_out": paid_sum,
                },
                {
                    "host_payment_status": "unpaid",
                    "total_pay_out": unpaid_sum,
                },
                {
                    "host_payment_status": "overdue",
                    "total_pay_out": overdue_sum,
                },
            ]

            response.data["host_payment_status_sum"] = host_payment_status_sum
        else:
            current_date = date.today()

            currently_hosting_qs = Booking.objects.filter(
                Q(check_in__lte=current_date) & Q(check_out__gte=current_date),
                status=BookingStatusOption.CONFIRMED,
            )
            # if request.GET.get("host"):
            #     currently_hosting_qs = currently_hosting_qs.filter(
            #         host_id=request.GET.get("host")
            #     )

            # currently_hosting_count = currently_hosting_qs.count()

            upcoming_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED, check_in__gt=current_date
            )
            completed_qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED, check_out__lt=current_date
            )
            cancelled_qs = Booking.objects.filter(status=BookingStatusOption.CANCELLED)

            if request.GET.get("host"):
                currently_hosting_qs = currently_hosting_qs.filter(
                    host_id=request.GET.get("host")
                )
                upcoming_qs = upcoming_qs.filter(host_id=request.GET.get("host"))
                completed_qs = completed_qs.filter(host_id=request.GET.get("host"))
                cancelled_qs = cancelled_qs.filter(host_id=request.GET.get("host"))

            if request.GET.get("guest"):
                currently_hosting_qs = currently_hosting_qs.filter(
                    guest_id=request.GET.get("guest")
                )
                upcoming_qs = upcoming_qs.filter(guest_id=request.GET.get("guest"))
                completed_qs = completed_qs.filter(guest_id=request.GET.get("guest"))
                cancelled_qs = cancelled_qs.filter(guest_id=request.GET.get("guest"))

            currently_hosting_count = currently_hosting_qs.count()
            upcoming_count = upcoming_qs.count()
            completed_count = completed_qs.count()
            cancelled_count = cancelled_qs.count()

            response.data["event_stats"] = {
                "currently_hosting_count": currently_hosting_count,
                "upcoming_count": upcoming_count,
                "completed_count": completed_count,
                "cancelled_count": cancelled_count,
            }
        return response


class AdminBookingRetrieveAPIView(generics.RetrieveAPIView):
    permission_classes = (IsStaff,)
    serializer_class = BookingSerializer
    queryset = (
        Booking.objects.filter()
        .select_related("listing", "guest")
        .order_by("-created_at")
    )
    swagger_tags = ["Admin Bookings"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["listing", "guest"]
        return self.serializer_class(*args, **kwargs)


class AdminBookingStatisticsAPIView(APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Bookings"]

    def get(self, request, *args, **kwargs):

        year = request.GET.get("year", timezone.now().year)

        booking_statuses = [
            "confirmed",
            "cancelled",
            "initiated",
        ]

        monthly_booking_counts = {
            month: {status: 0 for status in booking_statuses} for month in range(1, 13)
        }
        monthly_booking_data = (
            Booking.objects.filter(created_at__year=year)
            .annotate(month=ExtractMonth("created_at"))
            .values("month", "status")
            .annotate(count=Count("id"))
        )
        for entry in monthly_booking_data:
            month = entry["month"]
            b_status = entry["status"]
            count = entry["count"]
            monthly_booking_counts[month][b_status] += count

        return Response({"data": monthly_booking_counts}, status=status.HTTP_200_OK)


class AdminListingBookingReviewsAPIView(generics.ListAPIView):
    permission_classes = (IsStaff,)
    serializer_class = BookingReviewSerializer
    queryset = (
        ListingBookingReview.objects.filter()
        .select_related("review_by", "review_for")
        .order_by("-created_at")
    )
    search_fields = ("review", "review_by__first_name", "review_by__last_name")
    filterset_class = BookingReviewFilter
    swagger_tags = ["Admin Bookings"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["review_by", "review_for", "booking", "listing"]
        return self.serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        response = super().list(request, args, kwargs)
        response.data["stats"] = ListingBookingReview.objects.aggregate(
            host_review_count=Count(
                Case(When(is_host_review=True, then=1), output_field=IntegerField())
            ),
            guest_review_count=Count(
                Case(When(is_guest_review=True, then=1), output_field=IntegerField())
            ),
        )

        return response


class ExportBookingReviewsAPIView(APIView):
    permission_classes = (IsStaff,)
    http_method_names = ["get"]
    swagger_tags = ["Admin Bookings"]

    @swagger_auto_schema(
        operation_summary="Export Booking Reviews",
        operation_description="Export all listing booking reviews with related booking, guest, host, and listing data in Excel or CSV format.",
        responses={200: "File download"}
    )
    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        print("----------------------------")
        format = request.query_params.get("format", "excel").lower()
        reviews = ListingBookingReview.objects.select_related(
            "booking", "review_by", "review_for", "listing"
        ).all()
        print(reviews)
        data = []
        for review in reviews:
            serializer = BookingReviewSerializer(
                review,
                context={"request": request},
                r_method_fields=["review_by", "review_for", "listing", "booking"]
            )
            serialized_data = serializer.data

            data.append({
                "Review ID": review.id,
                "Rating": review.rating,
                "Review": review.review,
                "Review By": serialized_data["review_by"]["full_name"],
                "Review For": serialized_data["review_for"]["full_name"],
                "Listing Title": serialized_data["listing"]["title"],
                "Invoice No": serialized_data["booking"]["invoice_no"],
                "Check In": serialized_data["booking"]["check_in"],
                "Check Out": serialized_data["booking"]["check_out"],
                "Total Price": serialized_data["booking"]["total_price"],
                "Guest Count": serialized_data["booking"]["guest_count"],
                "Status": serialized_data["booking"]["status"],
            })

        df = pd.DataFrame(data)

        if format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = "attachment; filename=booking_reviews.csv"
            df.to_csv(path_or_buf=response, index=False)
        else:
            response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = "attachment; filename=booking_reviews.xlsx"
            df.to_excel(response, index=False)

        return response

class AdminBookingReportDownloadAPIView(APIView):
    permission_classes = (IsStaff,)
    swagger_tags = ["Admin Bookings"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        ids = request.data.get("ids")

        formatted_filters = {}
        if request.data.get("ids"):
            formatted_filters["id__in"] = request.data.get("ids")
        if request.data.get("host_id"):
            formatted_filters["host_id"] = request.data.get("host_id")
        if (
            request.data.get("created_at_gte")
            and request.data.get("created_at_gte") != None
        ):
            utc_date_time = datetime.strptime(
                request.data.get("created_at_gte"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=pytz.utc)
            dhaka_timezone = pytz.timezone("Asia/Dhaka")
            dhaka_date_time = utc_date_time.astimezone(dhaka_timezone).date()
            formatted_filters["created_at__gte"] = dhaka_date_time
        if (
            request.data.get("created_at_lte")
            and request.data.get("created_at_lte") != None
        ):
            utc_date_time = datetime.strptime(
                request.data.get("created_at_lte"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=pytz.utc)
            dhaka_timezone = pytz.timezone("Asia/Dhaka")
            dhaka_date_time = utc_date_time.astimezone(dhaka_timezone).date()
            formatted_filters["created_at__lte"] = dhaka_date_time

        qs = Booking.objects.exclude(status__in=[
        BookingStatusOption.INITIATED,
        BookingStatusOption.PENDING_CONFIRMATION,
        BookingStatusOption.DECLINED,
        BookingStatusOption.ACCEPTED,
    ]).filter(
            **formatted_filters
        )

        if request.GET.get("event_type"):
            current_date = timezone.now().date()
            if request.GET.get("event_type") == "currently_hosting":
                qs = qs.filter(
                    Q(check_in__lte=current_date) & Q(check_out__gte=current_date),
                    status=BookingStatusOption.CONFIRMED,
                )
            elif request.GET.get("event_type") == "completed":
                qs = qs.filter(
                    status=BookingStatusOption.CONFIRMED,
                    check_out__lt=current_date,
                )

        qs = qs.annotate(
            guest_full_name=Concat(
                F("guest__first_name"),
                Value(" "),
                F("guest__last_name"),
            ),
            host_full_name=Concat(
                F("host__first_name"),
                Value(" "),
                F("host__last_name"),
            ),
        ).values(
            "check_in",
            "check_out",
            "reservation_code",
            "paid_amount",
            "guest_service_charge",
            "host_pay_out",
            "host_service_charge",
            "total_profit",
            "status",
            guest_username=F("guest__username"),
            host_username=F("host__username"),
            booked_on=F("created_at"),
            listing_name=F("listing__title"),
            guest_full_name=F("guest_full_name"),
            host_full_name=F("host_full_name"),
        )

        output = io.BytesIO()

        # Create a workbook and add a worksheet
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Define header titles
        headers = [
            "guest_username",
            "guest_full_name",
            "host_username",
            "host_full_name",
            "booked_on",
            "listing_name",
            "total_profit",
            "host_service_charge",
            "guest_service_charge",
            "host_pay_out",
            "paid_amount",
            "reservation_code",
            "check_in",
            "check_out",
            "status",
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, field_name_to_label(header))

        for row, obj in enumerate(qs, start=1):
            for col, column in enumerate(headers):
                # Split guest_username and host_username on "_" and get the first part
                if column == "guest_username" and "_" in obj[column]:
                    obj[column] = obj[column].split("_")[0]
                elif column == "host_username" and "_" in obj[column]:
                    obj[column] = obj[column].split("_")[0]

                # Format datetime fields
                if isinstance(obj[column], datetime):
                    obj[column] = str(
                        obj[column]
                        .astimezone(pytz.timezone("Asia/Dhaka"))
                        .strftime("%Y-%m-%d")
                    )

                # Write to the worksheet
                worksheet.write(row, col, str(obj[column]))

        workbook.close()

        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="booking_report.xlsx"'
        output.seek(0)
        response.write(output.getvalue())

        return response
