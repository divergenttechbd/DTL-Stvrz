import calendar

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
)
from rest_framework.views import APIView
from base.helpers.constants import OtpScopeOption
from base.helpers.decorators import exception_handler
from base.permissions import HostUserHasObjectAccess, IsHostUser
from base.type_choices import NotificationEventTypeOption, NotificationTypeOption, BookingStatusOption, \
    PaymentStatusOption
from notifications.models import Notification
from notifications.utils import create_notification, send_notification
from otp.service import OtpService
from payments.filters import HostPaymentFilter
from payments.models import HostPayMethod, HostPayment, HostPaymentItem
from payments.serializers import (
    HostPayMethodSerializer,
    HostPaymentItemSerializer,
    HostPaymentSerializer, HostFinanceReportDataSerializer, Last6MonthsPayoutBreakdownSerializer,
    MonthlyEarningsDetailSerializer,
)


class HostPayMethodListCreateAPIView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    serializer_class = HostPayMethodSerializer
    http_method_names = ["get", "post"]
    swagger_tags = ["Host Payments"]

    def get_queryset(self):
        return HostPayMethod.objects.filter(
            host_id=self.request.user.id,
        ).order_by("-created_at")

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        if not OtpService.validate_otp(
            input_otp=request.data["otp"],
            username=request.user.username,
            scope=OtpScopeOption.PAYMENT_METHOD,
        ):
            return Response(
                {"message": "Invalid otp"}, status=status.HTTP_400_BAD_REQUEST
            )

        request.data["host"] = request.user.id
        serializer = HostPayMethodSerializer(data=request.data)

        event_type = NotificationEventTypeOption.PAYMENT_METHOD
        host_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": "",
                "message": "Congratulations ! Your payment method is added successfully",
                "link": f"/host-dashboard/payouts",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=request.user.id,
        )

        if serializer.is_valid(raise_exception=True):
            if serializer.validated_data.get("is_default", False):
                HostPayMethod.objects.filter(host_id=request.user.id).update(
                    is_default=False
                )

            serializer.save()
            Notification.objects.create(**host_notification)

            OtpService.delete_otp(
                username=request.user.username, scope=OtpScopeOption.PAYMENT_METHOD
            )

            send_notification(notification_data=[host_notification])

            return Response(serializer.data, status=status.HTTP_201_CREATED)


class HostPayMethodRetrieveUpdateAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, IsHostUser, HostUserHasObjectAccess)
    queryset = HostPayMethod.objects.filter()
    serializer_class = HostPayMethodSerializer
    removeable_keys = (
        "host",
        "m_type",
    )
    swagger_tags = ["Host Payments"]

    @method_decorator(exception_handler)
    def patch(self, request, *args, **kwargs):
        if not OtpService.validate_otp(
            input_otp=request.data["otp"],
            username=request.user.username,
            scope=OtpScopeOption.PAYMENT_METHOD,
        ):
            return Response(
                {"message": "Invalid otp"}, status=status.HTTP_400_BAD_REQUEST
            )

        instance = self.get_object()
        serializer = HostPayMethodSerializer(
            instance,
            data=request.data,
            partial=True,
            exclude_fields=self.removeable_keys,
        )
        if serializer.is_valid(raise_exception=True):
            if serializer.validated_data.get("is_default", False):
                HostPayMethod.objects.filter(host_id=request.user.id).update(
                    is_default=False
                )
            serializer.save()
            OtpService.delete_otp(
                username=request.user.username, scope=OtpScopeOption.PAYMENT_METHOD
            )
            return Response({"message": "Updated"}, status=status.HTTP_200_OK)

    @method_decorator(exception_handler)
    def delete(self, request, *args, **kwargs):
        if HostPayment.objects.filter(pay_method_id=kwargs.get("pk")).exists():
            return Response(
                {"message": "This pay method is already used for payments"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        HostPayMethod.objects.filter(id=kwargs.get("pk")).delete()
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


class HostPaymentListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    serializer_class = HostPaymentSerializer
    filterset_class = HostPaymentFilter
    search_fields = ("invoice_no",)
    http_method_names = ["get"]
    swagger_tags = ["Host Payments"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["host", "pay_method"]
        return self.serializer_class(*args, **kwargs)

    def get_queryset(self):
        return (
            HostPayment.objects.filter(host_id=self.request.user.id)
            .select_related("host", "pay_method")
            .order_by("-created_at")
        )


class HostPaymentDetailAPIView(APIView):
    permission_classes = (IsAuthenticated, IsHostUser, HostUserHasObjectAccess)
    swagger_tags = ["Host Payments"]

    def get(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")
        instance = HostPayment.objects.get(invoice_no=invoice_no)

        self.check_object_permissions(request, instance)

        host_payment_items = HostPaymentItem.objects.filter(host_payment_id=instance.id)
        host_payment_item_data = HostPaymentItemSerializer(
            host_payment_items, many=True
        ).data

        return Response(host_payment_item_data, status=status.HTTP_200_OK)


# ------------------------ fin report -----------------------


from django.db.models import Sum, Q, Count, F, ExpressionWrapper, DecimalField, IntegerField, DateField, Case, When, \
    FloatField, Avg
from django.db.models.functions import Coalesce, ExtractYear, ExtractMonth, TruncMonth, Cast
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from datetime import timedelta, date

from base.permissions import IsHostUser
from base.type_choices import BookingStatusOption, PaymentStatusOption # Make sure this is correct
from bookings.models import Booking, ListingBookingReview # Import ListingBookingReview
from payments.models import HostPayment
from referrals.models import ReferralReward, ReferralType
from listings.models import Listing # Import Listing if needed for review scope

# Import your serializers


class HostFinanceReportAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsHostUser]

    def get_month_year_range(self, num_months_back, from_date=None):
        start_calc_date = (from_date or timezone.now().date()).replace(day=1)
        months = []
        for i in range(num_months_back):
            current_year = start_calc_date.year
            current_month_val = start_calc_date.month - i
            while current_month_val <= 0:
                current_month_val += 12
                current_year -= 1
            months.append(date(current_year, current_month_val, 1))
        return sorted(months)

    def get(self, request, *args, **kwargs):
        host = request.user
        today = timezone.now().date()
        current_year, current_month_num = today.year, today.month
        previous_year = current_year - 1


        first_day_current_month = today.replace(day=1)

        start_month_for_12m_period = first_day_current_month.month - 11
        start_year_for_12m_period = first_day_current_month.year
        if start_month_for_12m_period <= 0:
            start_month_for_12m_period += 12
            start_year_for_12m_period -= 1
        twelve_months_ago_period_start = date(start_year_for_12m_period, start_month_for_12m_period, 1)

        # --- BASE QUERYSETS (filtered by host, common statuses) ---
        host_bookings_base_qs = Booking.objects.filter(
            host=host,
            # Earnings are typically from confirmed/completed bookings
            status__in=[BookingStatusOption.CONFIRMED]
        )


        host_referral_rewards_base_qs = ReferralReward.objects.filter(
            user=host,
            referral__referral_type=ReferralType.HOST_TO_HOST  # Or other types host can earn from
        )

        host_payouts_base_qs = HostPayment.objects.filter(
            host=host,
            status=PaymentStatusOption.PAID
        )

        # --- Monthly Aggregations (based on check_in for bookings, payment_date for payouts) ---
        monthly_booking_earnings_data = host_bookings_base_qs.filter(
            check_in__gte=twelve_months_ago_period_start, check_in__lte=today  # Up to today for current month data
        ).annotate(
            year=ExtractYear('check_in'), month=ExtractMonth('check_in')
        ).values('year', 'month').annotate(
            total_booking_payout=Coalesce(Sum(Cast('host_pay_out', DecimalField(max_digits=12, decimal_places=2))),
                                          Decimal('0.00')),
            total_booking_price=Coalesce(Sum(Cast('price', DecimalField(max_digits=12, decimal_places=2))),
                                         Decimal('0.00'))
        ).order_by('year', 'month')


        monthly_suggestion_rewards_data = host_referral_rewards_base_qs.filter(
            created_at__gte=twelve_months_ago_period_start, created_at__lte=today
        ).annotate(
            year=ExtractYear('created_at'), month=ExtractMonth('created_at')
        ).values('year', 'month').annotate(
            total_suggestion_rewards=Coalesce(Sum('amount'), Decimal('0.00'))
        ).order_by('year', 'month')

        monthly_payouts_data = host_payouts_base_qs.filter(
            payment_date__gte=twelve_months_ago_period_start, payment_date__lte=today
        ).annotate(
            year=ExtractYear('payment_date'), month=ExtractMonth('payment_date')
        ).values('year', 'month').annotate(
            total_payouts=Coalesce(Sum(Cast('total_amount', DecimalField(max_digits=12, decimal_places=2))),
                                   Decimal('0.00'))
        ).order_by('year', 'month')

        # --- Dictionaries for easy lookup ---
        booking_earnings_dict = {(d['year'], d['month']): d['total_booking_payout'] for d in
                                 monthly_booking_earnings_data}
        booking_price_dict = {(d['year'], d['month']): d['total_booking_price'] for d in monthly_booking_earnings_data}
        suggestion_rewards_dict = {(d['year'], d['month']): d['total_suggestion_rewards'] for d in
                                   monthly_suggestion_rewards_data}
        payouts_dict = {(d['year'], d['month']): d['total_payouts'] for d in monthly_payouts_data}

        # --- Initialize Report Data ---
        report_data = {
            "current_month_total_earnings": Decimal('0.00'),
            "summary_previous_year_booking_earnings": Decimal('0.00'),
            "summary_lifetime_suggestion_rewards": Decimal('0.00'),
            "last_12_months_payments_overview": [],
            "last_6_months_received_payments_graph": [],
            "total_earnings_last_6_months_from_payouts": Decimal('0.00'),
            "current_year_monthly_booking_amounts": [],
            "previous_year_monthly_booking_amounts": [],
            "current_year_total_income": Decimal('0.00'),
            "previous_year_total_income": Decimal('0.00'),
            "last_12_months_income_payments_graph": [],
            "historical_yearly_income_summary": [],
            "insights": {
                "last_7_days_nights_booked": 0,
                "last_30_days_booking_value": Decimal('0.00'),  # This will be host_pay_out from check_in based bookings
                "last_365_days_5_star_rating_percentage": 0.0
            }
        }

        # --- Lifetime & Previous Year Summaries ---
        report_data["summary_lifetime_suggestion_rewards"] = host_referral_rewards_base_qs.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'))
        )['total']

        report_data["summary_previous_year_booking_earnings"] = host_bookings_base_qs.filter(
            check_in__year=previous_year
        ).aggregate(
            total=Coalesce(Sum(Cast('host_pay_out', DecimalField(max_digits=14, decimal_places=2))), Decimal('0.00'))
        )['total']

        # --- Populate Monthly Data for Last 12 Months (including current) ---
        # The get_month_year_range now correctly gives the 12 months ending with current month's start.
        last_12_calendar_months = self.get_month_year_range(12, from_date=today)

        for month_date_obj in last_12_calendar_months:
            y, m = month_date_obj.year, month_date_obj.month
            month_key = (y, m)
            month_label = calendar.month_name[m]

            # Booking earnings for this month (based on check_in)
            booking_earning_for_month = booking_earnings_dict.get(month_key, Decimal('0.00'))
            # Suggestion rewards for this month (based on reward creation date)
            suggestion_reward_for_month = suggestion_rewards_dict.get(month_key, Decimal('0.00'))
            gross_earning_for_month = booking_earning_for_month + suggestion_reward_for_month

            payout_for_month = payouts_dict.get(month_key, Decimal('0.00'))

            report_data["last_12_months_income_payments_graph"].append({
                "year": y, "month": m, "month_name": month_label,
                "booking_related_earnings": booking_earning_for_month,
                "suggestion_rewards_earned": suggestion_reward_for_month,
                "gross_total_earnings": gross_earning_for_month
            })

            report_data["last_12_months_payments_overview"].append({  # Now based on price instead of payout
                "year": y, "month": m, "month_name": month_label,
                "received_payment_amount": booking_price_dict.get(month_key, Decimal('0.00'))
            })

            if y == current_year and m == current_month_num:
                report_data["current_month_total_earnings"] = gross_earning_for_month

            if y == current_year:
                report_data["current_year_total_income"] += gross_earning_for_month
            # previous_year_total_income will be calculated fully below to avoid partial sums from 12-month window

        # Full Previous Year Gross Income
        prev_year_booking_total = report_data["summary_previous_year_booking_earnings"]  # Already calculated
        prev_year_referral_total = host_referral_rewards_base_qs.filter(created_at__year=previous_year).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'))
        )['total']
        report_data["previous_year_total_income"] = prev_year_booking_total + prev_year_referral_total

        # --- Last 6 Months Payouts & Sum ---
        last_6_calendar_months = self.get_month_year_range(6, from_date=today)
        for month_date_obj in last_6_calendar_months:
            y, m = month_date_obj.year, month_date_obj.month
            payout_for_month = payouts_dict.get((y, m), Decimal('0.00'))
            report_data["last_6_months_received_payments_graph"].append({
                "year": y, "month": m, "month_name": calendar.month_name[m],
                "received_payment_amount": payout_for_month
            })
            report_data["total_earnings_last_6_months_from_payouts"] += payout_for_month

        # --- Current and Previous Year Monthly Booking Amounts (host_pay_out from check_in) ---
        for year_to_process in [current_year, previous_year]:
            target_list = "current_year_monthly_booking_amounts" if year_to_process == current_year else "previous_year_monthly_booking_amounts"
            monthly_booking_amounts = host_bookings_base_qs.filter(
                check_in__year=year_to_process
            ).annotate(
                month=ExtractMonth('check_in')
            ).values('month').annotate(
                monthly_total=Coalesce(Sum(Cast('price', DecimalField(max_digits=12, decimal_places=2))),
                                       Decimal('0.00'))
            ).order_by('month')

            monthly_amounts_dict = {d['month']: d['monthly_total'] for d in monthly_booking_amounts}
            for m_num in range(1, 13):
                report_data[target_list].append({
                    "year": year_to_process, "month": m_num, "month_name": calendar.month_name[m_num],
                    "booking_amount_earned": monthly_amounts_dict.get(m_num, Decimal('0.00'))
                })

        # --- Historical Yearly Income Summary (Gross: Booking Payout (check_in based) + Referral (created_at based)) ---
        num_historical_years = 4
        report_data["historical_yearly_income_summary"] = []  # Clear before populating
        for i in range(num_historical_years):
            hist_year = current_year - i

            yearly_booking_e = host_bookings_base_qs.filter(check_in__year=hist_year).aggregate(
                total=Coalesce(Sum(Cast('host_pay_out', DecimalField(max_digits=14, decimal_places=2))),
                               Decimal('0.00'))
            )['total']
            yearly_suggestion_r = host_referral_rewards_base_qs.filter(created_at__year=hist_year).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']

            report_data["historical_yearly_income_summary"].append({
                "year": hist_year, "total_income": yearly_booking_e + yearly_suggestion_r
            })
        report_data["historical_yearly_income_summary"].reverse()

        # --- Insights ---
        seven_days_ago = today - timedelta(days=6)
        thirty_days_ago = today - timedelta(days=29)
        three_sixty_five_days_ago = today - timedelta(days=364)

        # Nights booked for listings where check_in was in last 7 days
        report_data["insights"]["last_7_days_nights_booked"] = Booking.objects.filter(
            host=host,
            status=BookingStatusOption.CONFIRMED,
            check_out__range=[today - timedelta(days=7), today]
        ).aggregate(nights=Coalesce(Sum('night_count'), 0))['nights']

        # Host pay_out from bookings with check_in in last 30 days
        report_data["insights"]["last_30_days_booking_value"] = Booking.objects.filter(
        host=host,
        status__in=[BookingStatusOption.CONFIRMED],
        check_in__range=[today - timedelta(days=30), today]
        ).aggregate(
            value=Coalesce(
                Cast(Sum('price'), DecimalField(max_digits=14, decimal_places=2)),
                Decimal('0.00')
            )
        )['value']

        # 5-star rating percentage in last 365 days for this host's listings
        # Assuming ListingBookingReview.review_for points to the host User
        # If it points to Listing, then filter by listing__host
        reviews_in_last_365_days = ListingBookingReview.objects.filter(
            # review_for=host, # If review_for is the host User
            listing__host=host,  # If review is on listing, and listing has host
            is_guest_review=True,
            created_at__gte=three_sixty_five_days_ago, created_at__lte=today
        )
        total_reviews_count = reviews_in_last_365_days.count()
        five_star_reviews_count = reviews_in_last_365_days.filter(rating=5).count()

        if total_reviews_count > 0:
            report_data["insights"]["last_365_days_5_star_rating_percentage"] = round(
                (five_star_reviews_count / total_reviews_count) * 100, 1
            )
        # else it remains 0.0 from initialization

        serializer = HostFinanceReportDataSerializer(data=report_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)





class HostLast6MonthsPayoutBreakdownAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsHostUser]
    serializer_class = Last6MonthsPayoutBreakdownSerializer

    def get_start_of_n_months_ago(self, n_months, from_date=None):
        """
        Calculates the first day of the month, N months ago from the from_date.
        """
        current_date = from_date or timezone.now().date()
        target_month_start = current_date.replace(day=1) # Start with the first of the current month

        year = target_month_start.year
        month = target_month_start.month - (n_months -1) # Go back (n-1) months to get the start of the Nth month period

        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    def get(self, request, *args, **kwargs):
        host = request.user
        today = timezone.now().date()

        # Determine the period for "Last 6 Months"
        # Start date: First day of the month, 5 months ago from current month's first day (to get 6 full months window)
        period_start_date = self.get_start_of_n_months_ago(6, from_date=today)
        # End date: Could be today, or the last day of the most recent full month in the range.
        # For "Jan 1 - Jun 30" if current month is June, use last day of current month.
        # If current month is July 15, "last 6 months" could be Jan 1 - Jun 30, or Feb 1 - July 15.
        # Let's assume "up to today" for a rolling 6-month window for payouts.
        period_end_date = today

        # 1. Get payouts made to the host within this period
        payouts_in_period = HostPayment.objects.filter(
            host=host,
            status=PaymentStatusOption.PAID,
            payment_date__gte=period_start_date,
            payment_date__lte=period_end_date
        )

        total_received_payouts = payouts_in_period.aggregate(
            total=Coalesce(Sum(Cast('total_amount', DecimalField(max_digits=14, decimal_places=2))), Decimal('0.00'))
        )['total']

        # 2. Get Booking IDs associated with these payouts
        booking_ids_for_payouts = HostPaymentItem.objects.filter(
            host_payment__in=payouts_in_period # Link back to the filtered HostPayment records
        ).values_list('booking_id', flat=True).distinct() # Get distinct booking IDs

        # 3. Aggregate from these specific bookings
        gross_earnings_from_bookings = Decimal('0.00')
        host_service_fee_from_bookings = Decimal('0.00')

        if booking_ids_for_payouts: # Check if there are any bookings to aggregate from
            associated_bookings_qs = Booking.objects.filter(id__in=list(booking_ids_for_payouts))

            gross_earnings_from_bookings = associated_bookings_qs.aggregate(
                total=Coalesce(Sum(Cast('price', DecimalField(max_digits=14, decimal_places=2))), Decimal('0.00')) # Sum of Booking.price
            )['total']

            host_service_fee_from_bookings = associated_bookings_qs.aggregate(
                total=Coalesce(Sum(Cast('host_service_charge', DecimalField(max_digits=14, decimal_places=2))), Decimal('0.00'))
            )['total']

        # Prepare data for the serializer
        data_for_serializer = {
            "period_start_date": period_start_date,
            "period_end_date": period_end_date, # Can also be last day of 'today.month' if preferred for display
            "gross_earnings_from_included_bookings": gross_earnings_from_bookings,
            "host_service_fee_from_included_bookings": host_service_fee_from_bookings,
            "total_received_payouts_in_period": total_received_payouts
        }

        serializer = self.serializer_class(data=data_for_serializer)
        serializer.is_valid(raise_exception=True) # Should be valid as we constructed it
        return Response(serializer.data, status=status.HTTP_200_OK)


class HostMonthlyEarningsDetailAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsHostUser]
    # serializer_class = MonthlyEarningsDetailSerializer # For Swagger

    def get(self, request, year=None, month=None, *args, **kwargs): # year and month from URL
        host = request.user

        # Validate or default year and month
        if year is None or month is None:
            # This block would be used if you also have a URL pattern without year/month
            # to default to the current month.
            today = timezone.now().date()
            year = year or today.year
            month = month or today.month
        else:
            # Year and month are provided in the URL, they are already integers
            # due to <int:year> and <int:month> in the URL pattern.
            # Basic validation for month range. Year can be any valid integer.
            if not (1 <= month <= 12):
                return Response({"error": "Month must be between 1 and 12."},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                # Check if the date is valid, e.g., not year 0 or too far in past/future if needed
                date(year, month, 1)
            except ValueError:
                return Response({"error": "Invalid year or month provided."},
                                status=status.HTTP_400_BAD_REQUEST)


        # Base queryset for bookings in the selected month by this host (check_in based)
        bookings_in_selected_month_qs = Booking.objects.filter(
            host=host,
            status__in=[BookingStatusOption.CONFIRMED],
            check_in__year=year,
            check_in__month=month
        )

        # ... (rest of your existing logic for calculating earnings, stats, listings)
        # All the logic below this point remains the same as in your last correct version,
        # as 'year' and 'month' variables are now correctly populated.

        # 1. "You earned X" - Total Net Earnings for the month
        monthly_booking_payout_sum = bookings_in_selected_month_qs.aggregate(
            total=Coalesce(Sum(Cast('host_pay_out', DecimalField(max_digits=12, decimal_places=2))), Decimal('0.00'))
        )['total']
        monthly_referral_rewards_sum = ReferralReward.objects.filter(
            user=host,
            referral__referral_type=ReferralType.HOST_TO_HOST,
            created_at__year=year,
            created_at__month=month
        ).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'))
        )['total']
        total_net_earnings_for_month = monthly_booking_payout_sum + monthly_referral_rewards_sum

        # 2. Breakdown Section
        gross_booking_earnings = bookings_in_selected_month_qs.aggregate(
            total=Coalesce(Sum(Cast('price', DecimalField(max_digits=12, decimal_places=2))), Decimal('0.00'))
        )['total']
        total_host_service_fee = bookings_in_selected_month_qs.aggregate(
            total=Coalesce(Sum(Cast('host_service_charge', DecimalField(max_digits=12, decimal_places=2))), Decimal('0.00'))
        )['total']
        net_from_bookings_for_month = gross_booking_earnings - total_host_service_fee

        # 3. Performance Stats for the month
        performance_aggregates = bookings_in_selected_month_qs.aggregate(
            total_nights=Coalesce(Sum('night_count'), 0),
            avg_nights=Coalesce(Avg('night_count', output_field=FloatField()), 0.0)
        )
        performance_stats_data = {
            "total_nights_booked_for_month": performance_aggregates['total_nights'],
            "average_nights_per_stay_for_month": round(performance_aggregates['avg_nights'], 1) if performance_aggregates['avg_nights'] else 0.0
        }

        # 4. Listings Contributing to Earnings in that Month
        listings_data = []
        earnings_per_listing = bookings_in_selected_month_qs.values(
            'listing__id',
            'listing__title',
            'listing__cover_photo'
        ).annotate(
            listing_earning_for_month=Coalesce(Sum(Cast('host_pay_out', DecimalField(max_digits=12, decimal_places=2))), Decimal('0.00'))
        ).filter(listing_earning_for_month__gt=Decimal('0.00'))

        for item in earnings_per_listing:
            cover_photo = item['listing__cover_photo']
            listings_data.append({
                "listing_id": item['listing__id'],
                "listing_title": item['listing__title'],
                "listing_cover_photo": cover_photo if cover_photo else None,
                "earnings_from_this_listing_for_month": item['listing_earning_for_month']
            })

        response_data = {
            "selected_year": year,
            "selected_month": month,
            "selected_month_name": calendar.month_name[month],
            "total_net_earnings_for_month": total_net_earnings_for_month,
            "gross_booking_earnings_for_month": gross_booking_earnings,
            "total_host_service_fee_for_month": total_host_service_fee,
            "net_from_bookings_for_month": net_from_bookings_for_month,
            "performance_stats": performance_stats_data,
            "listings_contributing_to_earnings": listings_data
        }

        serializer = MonthlyEarningsDetailSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
