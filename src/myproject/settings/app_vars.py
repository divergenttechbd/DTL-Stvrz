import os
from decimal import Decimal

from myproject.settings import BASE_DIR

# Django vars
AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "myproject/static")]
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520

print("DB_PORT:", os.environ.get("DB_PORT"))
print("DB_NAME:", os.environ.get("DB_NAME"))
# DATABASE ENV
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "drf")
DB_USER = os.getenv("DB_USER", "rootuser")
DB_PASS = os.getenv("DB_PASSWORD", "P@s$4ad3s23")
DB_PORT = os.getenv("DB_PORT", "5432")

# REDIS & CELERY ENV
REDIS_HOST = os.environ.get("REDIS_HOST")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 8))

# EMAIL ENV
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = os.environ.get("EMAIL_PORT")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL")

# AWS ENV
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION")


# SSL SMS
SSL_SID = os.environ.get("SSL_SID")
SSL_TOKEN = os.environ.get("SSL_TOKEN")
SSL_URL = os.environ.get("SSL_URL")


# PROJECT
PROJECT_TITLE = os.environ.get("PROJECT_TITLE")
PROJECT_VERSION = os.environ.get("PROJECT_VERSION")
ENVIRONMENT = os.environ.get("ENVIRONMENT")


GOOGLE_MAP_API_KEY = os.environ.get("GOOGLE_MAP_API_KEY")

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://btayverz.divergenttechbd.com")
WEB_FALLBACK_URL = os.getenv("WEB_FALLBACK_URL", "https://btayverz.divergenttechbd.com/")
IOS_STORE_URL = os.getenv("IOS_STORE_URL", "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
ANDROID_STORE_URL = os.getenv("ANDROID_STORE_URL", "https://play.google.com/store/apps/details?id=com.stayverz.stayverz")
SHORT_LINK_DOMAIN = os.getenv("SHORT_LINK_DOMAIN", "https://btayverz.divergenttechbd.com")


# SSL SMS
SSL_STORE_ID = os.environ.get("SSL_STORE_ID")
SSL_STORE_PASSWORD = os.environ.get("SSL_STORE_PASSWORD")
SSL_BASE_URL = os.environ.get("SSL_BASE_URL")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL")
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL")
FRONTEND_ADMIN_BASE_URL = os.environ.get("FRONTEND_ADMIN_BASE_URL")


# Bari Koi
BARIKOI_API_KEY = os.environ.get("BARIKOI_API_KEY")

AMQP_SERVER_URL = os.environ.get("AMQP_SERVER_URL")
MONGO_URL = os.environ.get("MONGO_URL")
MONGO_DB = os.environ.get("MONGO_DB")


FCM_SERVER_KEY_PATH = os.environ.get("FCM_SERVER_KEY_PATH")

LIFETIME_REFERRAL_EARNINGS_CAP_POINTS = 10000
LIFETIME_REFERRAL_EARNINGS_CAP_TAKA = Decimal('10000.00')
