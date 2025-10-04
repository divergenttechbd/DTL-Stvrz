-- Adding new tables

-- Table: a_category


-- Table: a_subcategory

-- Table: accounts_superhoststatushistory
CREATE TABLE "accounts_superhoststatushistory" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "tier_key" VARCHAR(20),
    "tier_name" VARCHAR(50),
    "assessment_period_start" DATE NOT NULL,
    "assessment_period_end" DATE NOT NULL,
    "status_achieved_on" TIMESTAMPTZ NOT NULL,
    "metrics_snapshot" JSONB NOT NULL,
    "host_id" BIGINT NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    UNIQUE ("host_id", "assessment_period_start", "assessment_period_end")
);

-- Table: coupons_coupon
CREATE TABLE "coupons_coupon" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "code" VARCHAR(30) NOT NULL UNIQUE,
    "description" TEXT NOT NULL,
    "discount_type" VARCHAR(30) NOT NULL,
    "discount_value" DECIMAL(10, 2) NOT NULL,
    "valid_to" TIMESTAMPTZ,
    "max_use" INTEGER NOT NULL,
    "uses_count" INTEGER NOT NULL,
    "is_active" BOOLEAN NOT NULL,
    "threshold_amount" DECIMAL(10, 2),
    "valid_from" TIMESTAMPTZ NOT NULL
);

-- Table: links_link
CREATE TABLE "links_link" (
    "id" BIGSERIAL PRIMARY KEY,
    "code" VARCHAR(64) NOT NULL UNIQUE,
    "target_url" VARCHAR(200) NOT NULL,
    "deep_link_scheme" VARCHAR(512),
    "ios_store_url" VARCHAR(200),
    "android_store_url" VARCHAR(200),
    "title" VARCHAR(255),
    "meta" JSONB,
    "clicks" BIGINT NOT NULL,
    "is_active" BOOLEAN NOT NULL,
    "expire_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL
);

-- Table: links_click
CREATE TABLE "links_click" (
    "id" BIGSERIAL PRIMARY KEY,
    "ip" INET,
    "ua" TEXT,
    "referer" TEXT,
    "country" VARCHAR(64),
    "created_at" TIMESTAMPTZ NOT NULL,
    "link_id" BIGINT NOT NULL REFERENCES "links_link" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Table: listings_listingcohost
CREATE TABLE "listings_listingcohost" (
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "listing_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "listings_listing" ("id") DEFERRABLE INITIALLY DEFERRED,
    "access_level" VARCHAR(10) NOT NULL,
    "commission_percentage" DECIMAL(5, 2),
    "is_active" BOOLEAN NOT NULL,
    "co_host_user_id" BIGINT REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "primary_host_id" BIGINT REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Table: quick_reply_quickreply
CREATE TABLE "quick_reply_quickreply" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "title" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "host_id" BIGINT NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Table: referrals_referral
CREATE TABLE "referrals_referral" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "referral_code" UUID NOT NULL UNIQUE,
    "status" VARCHAR(20) NOT NULL,
    "rewarded_booking_count" INTEGER NOT NULL,
    "referred_user_id" BIGINT UNIQUE REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "referrer_id" BIGINT REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "max_rewardable_bookings" INTEGER NOT NULL,
    "referral_type" VARCHAR(20) NOT NULL
);

-- Table: referrals_coupon
CREATE TABLE "referrals_coupon" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "code" VARCHAR(50) NOT NULL UNIQUE,
    "amount" DECIMAL(10, 2) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "used_at" TIMESTAMPTZ,
    "claimed_by_id" BIGINT NOT NULL REFERENCES "accounts_user" ("id") DEferrable INITIALLY DEFERRED,
    "used_by_id" BIGINT REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "used_on_booking_id" BIGINT REFERENCES "bookings_booking" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Table: referrals_referralreward
CREATE TABLE "referrals_referralreward" (
    "id" BIGSERIAL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "amount" DECIMAL(10, 2) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "booking_id" BIGINT REFERENCES "bookings_booking" ("id") DEFERRABLE INITIALLY DEFERRED,
    "claimed_coupon_id" BIGINT REFERENCES "referrals_coupon" ("id") DEFERRABLE INITIALLY DEFERRED,
    "referral_id" BIGINT NOT NULL REFERENCES "referrals_referral" ("id") DEFERRABLE INITIALLY DEFERRED,
    "user_id" BIGINT NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Modifying existing tables

-- Table: accounts_user
ALTER TABLE "accounts_user"
ADD COLUMN "points_balance" INTEGER NULL,
ADD COLUMN "host_referral_credit_balance" DECIMAL(12, 2) NULL,
ADD COLUMN "current_superhost_tier" VARCHAR(20) NULL,
ADD COLUMN "superhost_metrics_updated_at" TIMESTAMPTZ NULL,
ADD COLUMN "lifetime_referral_points_earned" INTEGER NULL,
ADD COLUMN "lifetime_referral_taka_earned" DECIMAL(12, 2) NULL,
ADD COLUMN "is_available_for_cohosting" BOOLEAN NULL;

-- Table: accounts_userprofile
ALTER TABLE "accounts_userprofile"
ADD COLUMN "emergency_contact" VARCHAR(50) NULL,
ADD COLUMN "gender" VARCHAR(50) NULL;

-- Table: bookings_booking
ALTER TABLE "bookings_booking"
ADD COLUMN "applied_admin_coupon_id" BIGINT NULL REFERENCES "coupons_coupon" ("id") DEFERRABLE INITIALLY DEFERRED,
ADD COLUMN "applied_coupon_code" VARCHAR(50) NULL,
ADD COLUMN "applied_coupon_type" VARCHAR(20) NULL,
ADD COLUMN "applied_referral_coupon_id" BIGINT NULL REFERENCES "referrals_coupon" ("id") DEFERRABLE INITIALLY DEFERRED,
ADD COLUMN "discount_amount_applied" DECIMAL(10, 2) NULL,
ADD COLUMN "price_after_discount" DECIMAL(10, 2) NULL,
ADD COLUMN "invoice_generated_at" TIMESTAMPTZ NULL,
ADD COLUMN "invoice_pdf" VARCHAR(100) NULL;

-- Table: listings_amenity
ALTER TABLE "listings_amenity"
ADD COLUMN "icon_mobile" VARCHAR(255) NULL,
ADD COLUMN "status" BOOLEAN NULL;

-- Table: listings_category
ALTER TABLE "listings_category"
ADD COLUMN "icon_mobile" VARCHAR(255) NULL,
ADD COLUMN "status" BOOLEAN NULL;

-- Table: listings_listing
ALTER TABLE "listings_listing"
ADD COLUMN "deleted_at" TIMESTAMPTZ NULL,
ADD COLUMN "is_deleted" BOOLEAN NULL,
ADD COLUMN "instant_booking_allowed" BOOLEAN NULL,
ADD COLUMN "require_guest_good_track_record" BOOLEAN NULL,
ADD COLUMN "area" VARCHAR(255) NULL,
ADD COLUMN "city" VARCHAR(255) NULL,
ADD COLUMN "district" VARCHAR(255) NULL,
ADD COLUMN "division" VARCHAR(255) NULL,
ADD COLUMN "enable_length_of_stay_discount" BOOLEAN NULL,
ADD COLUMN "length_of_stay_discounts" JSONB NULL;

