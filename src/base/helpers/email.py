from django.conf import settings
from python_http_client.exceptions import HTTPError
from sendgrid import SendGridAPIClient
from django.core.mail import EmailMultiAlternatives
from sendgrid.helpers.mail import (
    Mail,
)


def send_email(to_email: str, subject: str, text: str) -> None:
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=text,
    )
    try:
        return None
        # sg = SendGridAPIClient(settings.EMAIL_HOST_PASSWORD)
        # response = sg.send(message)
        # print(response.status_code)
        # print(response.body)
        # print(response.headers)
    except HTTPError as e:
        print(e.to_dict)


def send_email_using_default_django_backend(
    to_email: str, subject: str, text_content: str
) -> None:
    try:
        # email = EmailMultiAlternatives(subject, text_content,settings.FROM_EMAIL , [to_email])
        # email.attach_alternative(text_content, "text/html")
        # email.send()
        print("-- send --- email. ")
        return None
    except HTTPError as e:
        print(e.to_dict)
