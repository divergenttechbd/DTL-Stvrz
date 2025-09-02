import datetime

import jwt
from accounts.models import User
from django.conf import settings


def generate_access_token(user: User) -> str:
    token_data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "u_type": user.u_type,
        "phone_number": user.phone_number,
        "is_active": user.is_active,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(weeks=4),
        "token_type": "access",
    }
    raw_token = jwt.encode(
        payload=token_data,
        key=settings.SECRET_KEY,
        algorithm="HS256",
    )
    # token = raw_token.decode('utf-8')
    return raw_token


def generate_refresh_token(user: User) -> str:
    token_data = {
        "username": user.username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(weeks=8),
        "token_type": "refresh",
    }
    raw_token = jwt.encode(
        payload=token_data, key=settings.SECRET_KEY, algorithm="HS256"
    )
    # token = raw_token.decode('utf-8')
    return raw_token


def create_tokens(user: User) -> tuple[str, str]:
    return generate_access_token(user=user), generate_refresh_token(user=user)


def generate_cookie_data(access_token: str) -> dict:
    domain = "stayverz.com" if settings.ENVIRONMENT == "dev" else "stayverz.com"

    return {
        "key": "cookie_token",
        "value": access_token,
        "expires": datetime.datetime.utcnow() + datetime.timedelta(weeks=4),
        "secure": True,
        "httponly": True,
        "samesite": "None",
        "domain": domain,
    }
