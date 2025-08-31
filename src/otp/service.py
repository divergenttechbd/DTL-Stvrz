import random
from accounts.tasks.users import send_sms
from base.cache.redis_cache import delete_cache, get_cache, set_cache
from base.helpers.email import send_email_using_default_django_backend, send_email
from base.helpers.constants import OtpScopeOption
from django.template.loader import get_template


class OtpService:
    @staticmethod
    def create_otp(
        username: str,
        scope: OtpScopeOption,
        is_sms: bool = False,
        is_email: bool = False,
        ttl: int = 120,
        to_phone_number: str | None = None,
        to_email: str | None = None,
    ) -> bool:
        key = f"{username}_{scope}_otp"
        otp = random.randint(10000, 99999)

        print(otp)
        if not set_cache(key=key, value=otp, ttl=ttl):
            return False

        if is_sms:
            # print("send sms")
            send_sms(username=to_phone_number, message=f"Your otp is {otp}")

        if is_email:
            html_content = get_template("email/email_otp.html").render({"otp": otp})
            send_email_using_default_django_backend(
                to_email, "OTP Verification", html_content
            )

        return True

    @staticmethod
    def get_otp(
        username: str,
        scope: OtpScopeOption,
    ) -> bool:
        key = f"{username}_{scope}_otp"
        return get_cache(key)

    @staticmethod
    def validate_otp(
        input_otp: str,
        username: str,
        scope: OtpScopeOption,
    ) -> bool:
        key = f"{username}_{scope}_otp"
        otp = get_cache(key)
        print(otp)
        return True #input_otp == str(otp)

    @staticmethod
    def delete_otp(
        username: str,
        scope: OtpScopeOption,
    ) -> bool:
        key = f"{username}_{scope}_otp"
        return delete_cache(key=key)
