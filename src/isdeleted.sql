-- deleted account
ALTER TABLE "accounts_user" ADD COLUMN "is_deleted" boolean NOT NULL DEFAULT false;
