# invoices/services.py (create this app or put in a suitable existing app like 'bookings')
import os
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from decimal import Decimal

from weasyprint import HTML, CSS

from accounts.models import UserProfile
# from weasyprint.fonts import FontConfiguration  # If using custom fonts

# Your models
from bookings.models import Booking


# from accounts.models import UserProfile # If guest address is there

from decimal import Decimal
from django.template.loader import render_to_string
from weasyprint import HTML
import logging

logger = logging.getLogger(__name__)


def generate_invoice_pdf_content(booking) -> bytes:
    """
    Generate PDF invoice content for a booking.

    Args:
        booking: Booking instance

    Returns:
        bytes: PDF file content

    Raises:
        Exception: If PDF generation fails
    """

    try:
        # Calculate financial details
        financial_data = _calculate_invoice_financials(booking)

        # Get guest address safely
        guest_address = _get_guest_address(booking)

        # Prepare template context
        context = {
            'booking': booking,
            'guest_address': guest_address,
            'subtotal_stay': financial_data['subtotal_stay'],
            'price_before_gateway_fee': financial_data['price_before_gateway_fee'],
            'base_price_per_night': financial_data['base_price_per_night'],
            'night_count': financial_data['night_count'],
        }

        # Generate HTML from template
        html_string = render_to_string('invoices/invoice_template.html', context)

        # Generate PDF
        html = HTML(string=html_string)
        pdf_content = html.write_pdf()

        logger.info(f"Successfully generated PDF for booking {booking.invoice_no}")
        return pdf_content

    except Exception as e:
        logger.error(f"Failed to generate PDF for booking {booking.invoice_no}: {str(e)}")
        raise Exception(f"PDF generation failed: {str(e)}")


def _calculate_invoice_financials(booking) -> dict:
    """
    Calculate all financial details for the invoice.

    Args:
        booking: Booking instance

    Returns:
        dict: Dictionary containing calculated financial values
    """

    # Convert to Decimal for precise calculations
    booking_price = Decimal(str(booking.price))
    night_count = Decimal(str(booking.night_count)) +1
    guest_service_charge = Decimal(str(booking.guest_service_charge or 0))
    discount_amount = Decimal(str(booking.discount_amount_applied or 0))
    gateway_fee = Decimal(str(booking.gateway_fee or 0))

    # Calculate subtotal (total stay cost)
    subtotal_stay = booking_price

    # Calculate base price per night
    # Use listing price if available, otherwise calculate from booking price
    if hasattr(booking.listing, 'price') and booking.listing.price:
        base_price_per_night = Decimal(str(booking.listing.price))
    else:
        base_price_per_night = booking_price / night_count if night_count > 0 else Decimal('0')

    print(" --- ", booking)
    print(" ---- ", booking.listing)
    print(" --- ", base_price_per_night)
    # Calculate price before gateway fee
    price_before_gateway_fee = subtotal_stay + guest_service_charge - discount_amount

    return {
        'subtotal_stay': subtotal_stay,
        'base_price_per_night': base_price_per_night,
        'price_before_gateway_fee': price_before_gateway_fee,
        'guest_service_charge': guest_service_charge,
        'discount_amount': discount_amount,
        'gateway_fee': gateway_fee,
        "night_count":night_count
    }


def _get_guest_address(booking) -> str:
    default_address = "Address not available"

    try:
        if not hasattr(booking, 'guest') or not booking.guest:
            return default_address

        guest = booking.guest
        print(" ----- guest -- ", guest)

        try:
            profile = guest.userprofile
            print("Guest Profile:", profile)
            print("Address:", profile.address)
            print("School:", profile.school)
            print("Work:", profile.work)
            if profile and profile.address and profile.address.strip():
                return profile.address.strip()
        except UserProfile.DoesNotExist:
            logger.warning(f"UserProfile not found for guest {guest.id}")

        # Fallback
        address_parts = []

        if guest.first_name and guest.last_name:
            address_parts.append(f"{guest.first_name} {guest.last_name}")

        if guest.email:
            address_parts.append(guest.email)

        if address_parts:
            return ", ".join(address_parts)

    except Exception as e:
        logger.warning(f"Error retrieving guest address for booking {booking.invoice_no}: {str(e)}")

    return default_address


def _generate_reservation_code(booking) -> str:
    """
    Generate or retrieve reservation code for booking.

    Args:
        booking: Booking instance

    Returns:
        str: Reservation code
    """

    if booking.reservation_code:
        return booking.reservation_code

    # Generate reservation code if not exists
    # Format: First 4 chars of invoice_no + last 4 digits of booking ID
    invoice_prefix = booking.invoice_no[:4] if booking.invoice_no else "BOOK"
    booking_suffix = str(booking.id).zfill(4)[-4:]

    return f"{invoice_prefix}{booking_suffix}"


# Optional: Enhanced version with additional features
def generate_invoice_pdf_content_enhanced(booking, include_qr_code=False, custom_template=None) -> bytes:
    """
    Enhanced version of PDF generation with additional features.

    Args:
        booking: Booking instance
        include_qr_code: Whether to include QR code in invoice
        custom_template: Custom template path if different from default

    Returns:
        bytes: PDF file content
    """

    try:
        # Calculate financial details
        financial_data = _calculate_invoice_financials(booking)

        # Get guest address safely
        guest_address = _get_guest_address(booking)

        # Generate reservation code if missing
        reservation_code = booking.reservation_code or _generate_reservation_code(booking)

        # Prepare enhanced context
        context = {
            'booking': booking,
            'guest_address': guest_address,
            'reservation_code': reservation_code,
            'subtotal_stay': financial_data['subtotal_stay'],
            'price_before_gateway_fee': financial_data['price_before_gateway_fee'],
            'base_price_per_night': financial_data['base_price_per_night'],
            'include_qr_code': include_qr_code,
            'night_count': financial_data['night_count'],
        }

        # Add QR code data if requested
        if include_qr_code:
            qr_data = f"Invoice: {booking.invoice_no}, Amount: {booking.paid_amount}, Code: {reservation_code}"
            context['qr_code_data'] = qr_data

        # Use custom template if provided
        template_path = custom_template or 'invoices/invoice_template.html'

        # Generate HTML from template
        html_string = render_to_string(template_path, context)

        # Generate PDF with custom options
        html = HTML(string=html_string)
        pdf_content = html.write_pdf(
            stylesheets=None,  # Add custom CSS if needed
            presentational_hints=True,
            optimize_images=True,
        )

        logger.info(f"Successfully generated enhanced PDF for booking {booking.invoice_no}")
        return pdf_content

    except Exception as e:
        logger.error(f"Failed to generate enhanced PDF for booking {booking.invoice_no}: {str(e)}")
        raise Exception(f"Enhanced PDF generation failed: {str(e)}")

def send_invoice_email(booking: Booking, pdf_content: bytes):
    """Sends the invoice PDF via email to guest and host."""
    subject = f"Your Stayverz Invoice {booking.invoice_no} for booking {booking.reservation_code}"
    body = render_to_string('invoices/invoice_email_body.txt', {'booking': booking})  # Simple text body

    from_email = settings.DEFAULT_FROM_EMAIL


    # Email to Guest
    # if booking.guest.email:
    #     email_guest = EmailMessage(subject, body, from_email, [booking.guest.email])
    #     email_guest.attach(f'Invoice_{booking.invoice_no}.pdf', pdf_content, 'application/pdf')
    #     try:
    #         email_guest.send(fail_silently=False)
    #         print(f"Invoice email sent to guest: {booking.guest.email}")
    #     except Exception as e:
    #         print(f"Error sending invoice email to guest {booking.guest.email}: {e}")
    #
    # # Email to Host
    # if booking.host.email:
    #     email_host = EmailMessage(subject, body, from_email, [booking.host.email])
    #     email_host.attach(f'Invoice_{booking.invoice_no}.pdf', pdf_content, 'application/pdf')
    #     try:
    #         email_host.send(fail_silently=False)
    #         print(f"Invoice email sent to host: {booking.host.email}")
    #     except Exception as e:
    #         print(f"Error sending invoice email to host {booking.host.email}: {e}")
