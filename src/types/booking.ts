export type IBookingTableFilterValue = string | string[] | Date | null;

export type IBookingTableFilters = {
  search: string;
  created_at_after: Date | null;
  created_at_before: Date | null;
  status: string;
  host: { label: string; value: string } | null;
  guest?: { label: string; value: string } | null;
};

type PriceInfo = {
  [date: string]: {
    id: number;
    price: number;
    is_booked: boolean;
    is_blocked: boolean;
  };
};

type CalendarInfo = {
  price: number;
  end_date: string;
  is_booked: boolean;
  base_price: number;
  is_blocked: boolean;
  listing_id: number;
  start_date: string;
};

export type IBookingItem = {
  id: number;
  created_at: string;
  updated_at: string;
  invoice_no: string;
  pgw_transaction_number: string;
  reservation_code: string;
  check_in: string;
  check_out: string;
  night_count: number;
  children_count: number;
  infant_count: number;
  adult_count: number;
  guest_count: number;
  price: number;
  applied_coupon_code: string;
  applied_coupon_type: string;
  discount_amount_applied: string;
  total_profit: number;
  guest_service_charge: number;
  total_price: number;
  paid_amount: number;
  host_service_charge: number;
  host_payment_status: string;
  host_pay_out: number;
  price_info: PriceInfo;
  payment_status: string;
  status: string;
  calendar_info: CalendarInfo[];
  guest: {
    id: number;
    full_name: string;
    phone_number: string;
  };
  host: {
    id: number;
    full_name: string;
    phone_number: string;
  };
  listing: {
    id: number;
    title: string;
    cover_photo: string;
    avg_rating: number;
    total_rating_count: number;
    cancellation_policy: {
      id: number;
      description: string;
      policy_name: string;
      refund_percentage: number;
    };
    address: string;
  };
  reviews: {
    booking: number;
    id: number;
    is_guest_review: boolean;
    is_host_review: boolean;
    listing: number;
    rating: number;
    review: string;
    review_by: number;
    review_for: number;
  }[];
};
