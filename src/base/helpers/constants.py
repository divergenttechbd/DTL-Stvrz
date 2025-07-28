from enum import Enum
from django.conf import settings

if settings.ENVIRONMENT != "prod":
    HOST = "https://dapcxdqknn4nj.cloudfront.net"
else:
    HOST = "https://d26o11dgjud8ta.cloudfront.net"


PLACE_TYPE_ICON_MAPPING = {
    "entire_place": f"{HOST}/icons/privacy_types/EntirePlace.svg",
    "single_room": f"{HOST}/icons/privacy_types/Room.svg",
    "shared_room": f"{HOST}/icons/privacy_types/SharedRoom.svg",
}
PLACE_TYPE_ICON_MOBILE_MAPPING = {
    "entire_place": f"https://dapcxdqknn4nj.cloudfront.net/icons/aminity/98b61e3594ea494d9b5d2c9790fff256-entire-place.gif",
    "single_room": f"https://dapcxdqknn4nj.cloudfront.net/icons/aminity/c0482009cc5a4e70b8cb64ddb6e118d6-Single-room.gif",
    "shared_room": f"https://d26o11dgjud8ta.cloudfront.net/icons/privacy_types/00defb1030684a36abf9677abe7c1a8e-shared.png",
}

PLACE_TYPE_DESCRIPTION_MAPPING = {
    "entire_place": "Guests have the whole place to themselves",
    "single_room": "Guests have their own room in home, plus accessed to shared spaces",
    "shared_room": "Guests Sleep in a room or common area that may be shared with you or others",
}


IMAGE_CHAR_REPLACE = {" ": "", "_": ""}


class OtpScopeOption(str, Enum):
    LOGIN = "login"
    RESET_PASSWORD = "reset_password"
    REGISTER = "register"
    EMAIL_VERIFY = "email_verify"
    PAYMENT_METHOD = "payment_method"


USER_OTP_EXP_MESSAGE = {"email_verify": "Email already taken"}
