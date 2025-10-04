from datetime import timedelta, date, datetime
from decimal import ROUND_HALF_UP, Decimal
import re
import uuid
import boto3
from django.db import connection
import random
from django.conf import settings
from botocore.exceptions import ClientError
import requests


def create_slug(title: str, random_str: str = None) -> str:
    clean_title = re.sub("[^A-Za-z ]+", " ", title).lower().strip()
    clean_title = re.sub(" +", "-", clean_title)

    if not clean_title:
        clean_title = re.sub("[,_।]", "", title)
        clean_title = clean_title.replace(" ", "-")
    if random_str:
        return clean_title + "-" + random_str
    return clean_title


def my_random_string(string_length=10):
    """Returns a random string of length string_length."""
    random = str(uuid.uuid4())
    random = random.upper()
    random = random.replace("-", "")
    return random[0:string_length]


def create_presigned_url(key: str) -> str:
    print(key)
    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="ap-southeast-1",
    )

    try:
        response = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": key,  # Use the parameter value
            },
            ExpiresIn=36000,
        )
        return response
    except ClientError as e:
        print(f"Error: {e}")
        return None


def get_text_choices_values(text_choices_enum):
    return [choice.value for choice in text_choices_enum]


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)


def entries_to_remove(data: dict, removeable_keys: tuple) -> dict:
    for k in removeable_keys:
        data.pop(k, None)
    return data


def calculate_days_between_dates(start_date: date, end_date: date) -> int:
    date_difference = end_date - start_date
    num_days = date_difference.days
    return num_days


def identifier_builder(table_name: str, prefix: str = None) -> str:
    with connection.cursor() as cur:
        query = f"SELECT id FROM {table_name} ORDER BY id DESC LIMIT 1;"
        cur.execute(query)
        row = cur.fetchone()
    try:
        seq_id = str(row[0] + 1)
    except Exception:
        seq_id = "1"
    random_suffix = random.randint(10, 99)
    if not prefix:
        return seq_id.rjust(8, "0") + str(random_suffix)
    return prefix + seq_id.rjust(8, "0") + str(random_suffix)

def identifier_builder_payment(prefix: str) -> str:
    unique_part = str(uuid.uuid4()).replace('-', '')[:12].upper()
    return f"{prefix}{unique_part}"

def format_date(date: str) -> str:
    try:
        date_object = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        date_object = datetime.strptime(date, "%Y-%m-%d")
    formatted_date = date_object.strftime("%b %-d")

    return formatted_date


def field_name_to_label(value):
    value = value.replace("_", " ")
    return value.title()


def custom_round(value: float | Decimal, precision: int = 2) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal(f"1e-{precision}"), rounding=ROUND_HALF_UP
    )
