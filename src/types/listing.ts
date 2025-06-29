// ----------------------------------------------------------------------

export type ITourFilterValue = string | string[] | Date | IListingGuide[] | null;

export type IListingFilters = {
  verification_status: 'verified' | 'unverified' | '';
  status: string;
  created_at_after: Date | null;
  created_at_before: Date | null;
  page_size: number;
  page: string | number;
  category: string | number;
  sort_by: string;
  host: { label: string; value: string } | null;
  latitude: string;
  longitude: string;
  radius: number;
  district: string;
  sub_disctrict: string;
};

// ----------------------------------------------------------------------

export type IListingGuide = {
  id: string;
  name: string;
  avatarUrl: string;
  phoneNumber: string;
};

export type IListingBooker = {
  id: string;
  name: string;
  avatarUrl: string;
  guests: number;
};

export type IListingItem = {
  id: number | string;
  created_at: string;
  updated_at: string;
  unique_id: string;
  title: string;
  owner: {
    email: string;
    full_name: string;
    id: number;
  };
  amenities: {
    id: number;
    amenity: {
      name: string;
      a_type: string;
      icon: string;
      id: number;
    };
  }[];
  description: string;
  price: number;
  cover_photo: string;
  images: string[];
  place_type: string;
  status: string;
  verification_status: string;
  guest_count: number;
  bedroom_count: number;
  bed_count: number;
  bathroom_count: number;
  minimum_nights: number;
  maximum_nights: number;
  address: string;
  avg_rating: number;
  total_rating_count: number;
  total_booking_count: number;
  instant_booking_allowed: boolean;
  latitude: number;
  longitude: number;
  category: {
    name: string;
    id: number;
  };
  cancellation_policy: {
    id: number;
    description: string;
    policy_name: string;
    refund_percentage: number;
  };
  check_in: string;
  check_out: string;
  pet_allowed: boolean;
  smoking_allowed: boolean;
  media_allowed: boolean;
  event_allowed: boolean;
  unmarried_couples_allowed: boolean;
  host: number
};
