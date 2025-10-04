-- ########## Step 1: Fix Existing Data and Constraints for 'accounts_user' ##########

-- Field: points_balance
UPDATE "accounts_user" SET "points_balance" = 0 WHERE "points_balance" IS NULL;
ALTER TABLE "accounts_user" ALTER COLUMN "points_balance" SET DEFAULT 0;
ALTER TABLE "accounts_user" ALTER COLUMN "points_balance" SET NOT NULL;

-- Field: host_referral_credit_balance
UPDATE "accounts_user" SET "host_referral_credit_balance" = 0.00 WHERE "host_referral_credit_balance" IS NULL;
ALTER TABLE "accounts_user" ALTER COLUMN "host_referral_credit_balance" SET DEFAULT 0.00;
ALTER TABLE "accounts_user" ALTER COLUMN "host_referral_credit_balance" SET NOT NULL;

-- Field: lifetime_referral_points_earned
UPDATE "accounts_user" SET "lifetime_referral_points_earned" = 0 WHERE "lifetime_referral_points_earned" IS NULL;
ALTER TABLE "accounts_user" ALTER COLUMN "lifetime_referral_points_earned" SET DEFAULT 0;
ALTER TABLE "accounts_user" ALTER COLUMN "lifetime_referral_points_earned" SET NOT NULL;

-- Field: lifetime_referral_taka_earned
UPDATE "accounts_user" SET "lifetime_referral_taka_earned" = 0.00 WHERE "lifetime_referral_taka_earned" IS NULL;
ALTER TABLE "accounts_user" ALTER COLUMN "lifetime_referral_taka_earned" SET DEFAULT 0.00;
ALTER TABLE "accounts_user" ALTER COLUMN "lifetime_referral_taka_earned" SET NOT NULL;

-- Field: is_available_for_cohosting
UPDATE "accounts_user" SET "is_available_for_cohosting" = false WHERE "is_available_for_cohosting" IS NULL;
ALTER TABLE "accounts_user" ALTER COLUMN "is_available_for_cohosting" SET DEFAULT false;
ALTER TABLE "accounts_user" ALTER COLUMN "is_available_for_cohosting" SET NOT NULL;


-- ########## Step 2: Fix Existing Data and Constraints for 'accounts_userprofile' ##########

-- Field: emergency_contact
UPDATE "accounts_userprofile" SET "emergency_contact" = '' WHERE "emergency_contact" IS NULL;
ALTER TABLE "accounts_userprofile" ALTER COLUMN "emergency_contact" SET DEFAULT '';
ALTER TABLE "accounts_userprofile" ALTER COLUMN "emergency_contact" SET NOT NULL;

-- Field: gender
UPDATE "accounts_userprofile" SET "gender" = '' WHERE "gender" IS NULL;
ALTER TABLE "accounts_userprofile" ALTER COLUMN "gender" SET DEFAULT '';
ALTER TABLE "accounts_userprofile" ALTER COLUMN "gender" SET NOT NULL;


-- ########## Step 3: Fix Existing Data and Constraints for 'bookings_booking' ##########

-- Field: discount_amount_applied
UPDATE "bookings_booking" SET "discount_amount_applied" = 0.00 WHERE "discount_amount_applied" IS NULL;
ALTER TABLE "bookings_booking" ALTER COLUMN "discount_amount_applied" SET DEFAULT 0.00;
ALTER TABLE "bookings_booking" ALTER COLUMN "discount_amount_applied" SET NOT NULL;


-- ########## Step 4: Fix Existing Data and Constraints for 'listings_amenity' ##########

-- Field: status
UPDATE "listings_amenity" SET "status" = false WHERE "status" IS NULL;
ALTER TABLE "listings_amenity" ALTER COLUMN "status" SET DEFAULT false;
-- Note: Your model allows status to be NULL, so we won't add a NOT NULL constraint. If you change it to default=False without null=True, add the line below.
-- ALTER TABLE "listings_amenity" ALTER COLUMN "status" SET NOT NULL;


-- ########## Step 5: Fix Existing Data and Constraints for 'listings_category' ##########

-- Field: status
UPDATE "listings_category" SET "status" = false WHERE "status" IS NULL;
ALTER TABLE "listings_category" ALTER COLUMN "status" SET DEFAULT false;
-- Note: Your model allows status to be NULL, so we won't add a NOT NULL constraint. If you change it to default=False without null=True, add the line below.
-- ALTER TABLE "listings_category" ALTER COLUMN "status" SET NOT NULL;


-- ########## Step 6: Fix Existing Data and Constraints for 'listings_listing' ##########

-- Field: is_deleted
UPDATE "listings_listing" SET "is_deleted" = false WHERE "is_deleted" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "is_deleted" SET DEFAULT false;
ALTER TABLE "listings_listing" ALTER COLUMN "is_deleted" SET NOT NULL;

-- Field: instant_booking_allowed
UPDATE "listings_listing" SET "instant_booking_allowed" = false WHERE "instant_booking_allowed" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "instant_booking_allowed" SET DEFAULT false;
ALTER TABLE "listings_listing" ALTER COLUMN "instant_booking_allowed" SET NOT NULL;

-- Field: require_guest_good_track_record
UPDATE "listings_listing" SET "require_guest_good_track_record" = false WHERE "require_guest_good_track_record" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "require_guest_good_track_record" SET DEFAULT false;
ALTER TABLE "listings_listing" ALTER COLUMN "require_guest_good_track_record" SET NOT NULL;

-- Fields: area, city, district, division (set to empty string)
UPDATE "listings_listing" SET "area" = '' WHERE "area" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "area" SET DEFAULT '';
ALTER TABLE "listings_listing" ALTER COLUMN "area" SET NOT NULL;

UPDATE "listings_listing" SET "city" = '' WHERE "city" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "city" SET DEFAULT '';
ALTER TABLE "listings_listing" ALTER COLUMN "city" SET NOT NULL;

UPDATE "listings_listing" SET "district" = '' WHERE "district" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "district" SET DEFAULT '';
ALTER TABLE "listings_listing" ALTER COLUMN "district" SET NOT NULL;

UPDATE "listings_listing" SET "division" = '' WHERE "division" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "division" SET DEFAULT '';
ALTER TABLE "listings_listing" ALTER COLUMN "division" SET NOT NULL;

-- Field: enable_length_of_stay_discount
UPDATE "listings_listing" SET "enable_length_of_stay_discount" = false WHERE "enable_length_of_stay_discount" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "enable_length_of_stay_discount" SET DEFAULT false;
ALTER TABLE "listings_listing" ALTER COLUMN "enable_length_of_stay_discount" SET NOT NULL;

-- Field: length_of_stay_discounts (JSONField)
UPDATE "listings_listing" SET "length_of_stay_discounts" = '{}'::jsonb WHERE "length_of_stay_discounts" IS NULL;
ALTER TABLE "listings_listing" ALTER COLUMN "length_of_stay_discounts" SET DEFAULT '{}'::jsonb;
ALTER TABLE "listings_listing" ALTER COLUMN "length_of_stay_discounts" SET NOT NULL;
