import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone

import requests
import stripe

# CloudWatch Logs Insights - AWS Console -> CloudWatch -> Logs Insights
# Log group: /aws/lambda/tra3-gentlemens-touch-{environment}-booking-webhook
#
# All processed bookings (last 7 days):
# fields @timestamp, @message
# | filter @message like /booking_processed|calcom_booking_processed/
# | sort @timestamp desc
# | limit 50
#
# Failed customer SMS alerts:
# fields @timestamp, @message
# | filter @message like /customer_sms_failed/
# | sort @timestamp desc
#
# All Stripe events received:
# fields @timestamp, @message
# | filter @message like /stripe_webhook_received/
# | sort @timestamp desc
#
# All Cal.com events received:
# fields @timestamp, @message
# | filter @message like /calcom_webhook_received/
# | sort @timestamp desc

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
CALCOM_WEBHOOK_SECRET = os.environ.get("CALCOM_WEBHOOK_SECRET", "")
TEXTBELT_API_KEY = os.environ.get("TEXTBELT_API_KEY")
DETAILER_PHONE = os.environ.get("DETAILER_PHONE")

SERVICE_PRICES = {
    "sm detail": 100.00,
    "md detail": 150.00,
    "lg detail": 200.00,
    "small": 100.00,
    "medium": 150.00,
    "large": 200.00,
    "full detail": 150.00,
}

BUSINESS_PHONE = "(334) 294-8228"


def _sanitize_string(value):
    sanitized = str(value)

    for secret in (
        STRIPE_SECRET_KEY,
        STRIPE_WEBHOOK_SECRET,
        CALCOM_WEBHOOK_SECRET,
        TEXTBELT_API_KEY,
        DETAILER_PHONE,
    ):
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")

    sanitized = re.sub(
        r"(https://textbelt\.com/whitelist\?key=)[^\s]+",
        r"\1[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(r"\+1\d{10}\b", "[REDACTED_PHONE]", sanitized)
    sanitized = re.sub(r"\(\d{3}\)\s*\d{3}-\d{4}", "[REDACTED_PHONE]", sanitized)

    return sanitized


def _sanitize_value(value):
    if isinstance(value, dict):
        return {key: _sanitize_value(val) for key, val in value.items()}

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, str):
        return _sanitize_string(value)

    return value


def _log(level, event, **fields):
    payload = {"level": level, "event": event}
    payload.update(fields)
    print(json.dumps(_sanitize_value(payload)))


def _response(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message}),
    }


def _send_sms(phone_number, message, recipient):
    try:
        response = requests.post(
            "https://textbelt.com/text",
            {
                "phone": phone_number,
                "message": message,
                "key": TEXTBELT_API_KEY,
            },
            timeout=30,
        )
        result = response.json()

        if not result.get("success"):
            raise Exception(result.get("error", "Textbelt send failed"))

        _log("INFO", f"{recipient}_sms_sent")
        return True
    except Exception as exc:
        _log("ERROR", f"{recipient}_sms_failed", detail=str(exc))
        return False


def _verify_calcom_signature(body: str, signature: str) -> bool:
    """Verify Cal.com webhook signature using HMAC-SHA256."""
    if not CALCOM_WEBHOOK_SECRET or not signature:
        return False

    try:
        expected = hmac.new(
            CALCOM_WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as exc:
        _log("ERROR", "calcom_sig_error", detail=str(exc))
        return False


def _parse_calcom_booking(payload: dict) -> dict:
    """
    Extract booking details from Cal.com BOOKING_PAYMENT_INITIATED payload.
    Returns a normalized dict matching the SMS builder expectations.
    """
    responses = payload.get("responses") or {}
    attendees = payload.get("attendees") or []

    def _response_value(*keys):
        for key in keys:
            raw_value = responses.get(key)
            value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value

            if isinstance(value, list):
                value = ", ".join(str(item) for item in value if item not in (None, ""))

            if value not in (None, ""):
                return value

        return None

    customer_name = (
        _response_value("name")
        or (attendees[0].get("name") if attendees else None)
        or "Unknown"
    )

    customer_email = (
        _response_value("email")
        or (attendees[0].get("email") if attendees else None)
        or "No email"
    )

    customer_phone = _response_value(
        "attendeePhoneNumber",
        "phone",
        "smsReminderNumber",
    )

    service = (
        _response_value("service")
        or payload.get("eventTitle")
        or payload.get("type")
        or "Not specified"
    )

    addons = _response_value("add-ons", "addons", "Add-Ons")

    start_time_raw = payload.get("startTime") or ""
    try:
        dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hour = dt.strftime("%I").lstrip("0") or "0"
        appointment_date = (
            f"{dt.strftime('%a %b')} {dt.day} @ "
            f"{hour}:{dt.strftime('%M %p')} {dt.tzname() or 'UTC'}"
        )
    except Exception:
        appointment_date = start_time_raw or "Not specified"

    price_cents = payload.get("price") or 0
    deposit_paid = price_cents / 100

    return {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "service": service,
        "addons": addons,
        "appointment_date": appointment_date,
        "deposit_paid": deposit_paid,
        "booking_uid": payload.get("uid") or "unknown",
    }


def _handle_calcom_webhook(event: dict, body: str) -> dict:
    """
    Handle incoming Cal.com webhook.
    Verifies signature, parses booking, sends SMS.
    """
    headers = {
        str(key).lower(): value
        for key, value in (event.get("headers") or {}).items()
    }
    sig_header = headers.get("x-cal-signature-256", "")

    if CALCOM_WEBHOOK_SECRET and not _verify_calcom_signature(body, sig_header):
        _log("ERROR", "calcom_invalid_signature")
        return _response(400, "Invalid Cal.com signature")

    try:
        data = json.loads(body)
    except Exception as exc:
        _log("ERROR", "calcom_parse_error", detail=str(exc))
        return _response(400, "Invalid JSON")

    trigger = data.get("triggerEvent", "")
    payload = data.get("payload") or {}

    _log(
        "INFO",
        "calcom_webhook_received",
        trigger=trigger,
        booking_id=payload.get("bookingId"),
        event_title=payload.get("eventTitle"),
    )

    if trigger != "BOOKING_PAYMENT_INITIATED":
        _log("INFO", "calcom_ignored", trigger=trigger)
        return _response(200, f"Ignored: {trigger}")

    booking = _parse_calcom_booking(payload)

    _log(
        "INFO",
        "calcom_booking_parsed",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        has_phone=booking["customer_phone"] is not None,
    )

    service_lower = booking["service"].lower()
    full_price = next(
        (price for key, price in SERVICE_PRICES.items() if key in service_lower),
        None,
    )
    balance_due = round(full_price - booking["deposit_paid"], 2) if full_price else None
    balance_due = max(balance_due, 0) if balance_due is not None else None

    _log(
        "INFO",
        "balance_calculated",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
    )

    divider = "\u2500" * 22
    addons_line = f"\nAdd-Ons:  {booking['addons']}" if booking["addons"] else ""
    balance_line = f"\nBalance:  ${balance_due:.2f}" if balance_due is not None else ""

    sms_detailer = (
        f"\U0001F697 NEW DETAIL BOOKING\n"
        f"{divider}\n"
        f"Name:     {booking['customer_name']}\n"
        f"Phone:    {booking['customer_phone'] or 'No phone'}\n"
        f"Email:    {booking['customer_email']}\n"
        f"{divider}\n"
        f"Service:  {booking['service']}{addons_line}\n"
        f"Date:     {booking['appointment_date']}\n"
        f"{divider}\n"
        f"Deposit:  ${booking['deposit_paid']:.2f}{balance_line}"
    )

    if not _send_sms(DETAILER_PHONE, sms_detailer, "detailer"):
        return _response(500, "Detailer SMS failed")

    customer_sms_status = "skipped"
    if booking["customer_phone"]:
        if balance_due is not None:
            balance_customer = f"${balance_due:.2f} due after service"
        else:
            balance_customer = "collected after service"

        sms_customer = (
            f"\U0001F697 Booking Confirmed!\n"
            f"A Gentlemen's Touch\n"
            f"{divider}\n"
            f"Hi {booking['customer_name']}! Your detail is booked.\n"
            f"{divider}\n"
            f"Service:  {booking['service']}\n"
            f"Date:     {booking['appointment_date']}\n"
            f"{divider}\n"
            f"Deposit:  ${booking['deposit_paid']:.2f} received\n"
            f"Balance:  {balance_customer}\n"
            f"{divider}\n"
            f"Questions? Call {BUSINESS_PHONE}"
        )

        if _send_sms(booking["customer_phone"], sms_customer, "customer"):
            customer_sms_status = "sent"
        else:
            customer_sms_status = "failed"
    else:
        _log("INFO", "customer_sms_skipped", detail="no phone on file")

    _log(
        "INFO",
        "calcom_booking_processed",
        customer_name=booking["customer_name"],
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
        detailer_sms="sent",
        customer_sms=customer_sms_status,
        booking_uid=booking["booking_uid"],
    )

    return _response(200, "Cal.com booking processed")


def _handle_stripe_webhook(event: dict, body: str) -> dict:
    """Handle incoming Stripe webhook (checkout.session.completed)."""
    headers = {
        str(key).lower(): value
        for key, value in (event.get("headers") or {}).items()
    }
    sig_header = headers.get("stripe-signature", "")

    stripe.api_key = STRIPE_SECRET_KEY

    try:
        verified_event = stripe.Webhook.construct_event(
            body,
            sig_header,
            STRIPE_WEBHOOK_SECRET,
        )
        if hasattr(verified_event, "to_dict_recursive"):
            stripe_event = verified_event.to_dict_recursive()
        else:
            stripe_event = json.loads(body)
    except stripe.error.SignatureVerificationError as exc:
        _log("ERROR", "signature_verification_failed", detail=str(exc))
        return _response(400, "Invalid signature")
    except Exception as exc:
        _log("ERROR", "webhook_verification_failed", detail=str(exc))
        return _response(400, "Webhook error")

    try:
        session = stripe_event["data"]["object"]
        _log(
            "INFO",
            "stripe_webhook_received",
            stripe_event_id=stripe_event["id"],
            stripe_event_type=stripe_event["type"],
            livemode=stripe_event.get("livemode", False),
            session_id=session.get("id", "unknown"),
            payment_status=session.get("payment_status", "unknown"),
            amount_total=session.get("amount_total", 0),
        )

        if stripe_event["type"] != "checkout.session.completed":
            _log("INFO", "event_ignored", detail=f"Ignored event type: {stripe_event['type']}")
            return _response(200, "Ignored")

        customer_details = session.get("customer_details") or {}
        customer_name = customer_details.get("name") or "Unknown"
        customer_email = customer_details.get("email") or "No email"
        customer_phone = customer_details.get("phone") or "No phone"
        amount_total = session.get("amount_total") or 0
        deposit_paid = amount_total / 100

        custom_fields = {
            field["key"]: field.get("text", {}).get("value", "Not specified")
            for field in (session.get("custom_fields") or [])
            if "key" in field
        }
        service = custom_fields.get("service", "Not specified")
        date = custom_fields.get("date", "Not specified")
        location = custom_fields.get("location", "Not specified")

        service_lower = service.lower()
        full_price = next(
            (price for key, price in SERVICE_PRICES.items() if key in service_lower),
            None,
        )
        balance_due = round(full_price - deposit_paid, 2) if full_price else None
        balance_due = max(balance_due, 0) if balance_due is not None else None

        _log(
            "INFO",
            "balance_calculated",
            service=service,
            deposit_paid=deposit_paid,
            balance_due=balance_due,
        )

        divider = "\u2500" * 22
        sms_body_detailer = (
            f"\U0001F697 NEW DETAIL BOOKING\n"
            f"{divider}\n"
            f"Name:     {customer_name}\n"
            f"Phone:    {customer_phone}\n"
            f"Email:    {customer_email}\n"
            f"{divider}\n"
            f"Service:  {service}\n"
            f"Date:     {date}\n"
            f"Location: {location}\n"
            f"{divider}\n"
            f"Deposit:  ${deposit_paid:.2f}"
        )

        if balance_due is not None:
            sms_body_detailer += f"\nBalance:  ${balance_due:.2f}"

        if not _send_sms(DETAILER_PHONE, sms_body_detailer, "detailer"):
            return _response(500, "SMS failed")

        sms_divider = "\u2500" * 42
        sms_body_customer = (
            f"\U0001F697 Booking Confirmed \u2014 A Gentlemen's Touch\n"
            f"{sms_divider}\n"
            f"Hi {customer_name}! Your detail is booked.\n"
            f"{sms_divider}\n"
            f"Service:  {service}\n"
            f"Date:     {date}\n"
            f"Location: {location}\n"
            f"Deposit:  ${deposit_paid:.2f} \u2713 Received\n"
            f"{sms_divider}\n"
            f"After your service, your detailer will\n"
            f"send your balance link.\n"
            f"\n"
            f"{divider}\n"
            f"Deposit:  ${deposit_paid:.2f} received\n"
        )

        if balance_due is not None:
            sms_body_customer += f"Balance:  ${balance_due:.2f} due after service\n"
        else:
            sms_body_customer += "Balance collected after service.\n"

        sms_body_customer += (
            f"{divider}\n"
            f"Questions? Call {BUSINESS_PHONE}"
        )

        if not customer_phone or customer_phone == "No phone":
            _log("INFO", "customer_sms_skipped", detail="no phone on file")
        else:
            _send_sms(customer_phone, sms_body_customer, "customer")

        _log(
            "INFO",
            "booking_processed",
            customer=customer_name,
            service=service,
            deposit_paid=deposit_paid,
            balance_due=balance_due,
        )
        return _response(200, "SMS sent")
    except Exception as exc:
        _log("ERROR", "webhook_processing_failed", detail=str(exc))
        return _response(500, "Webhook processing failed")


def lambda_handler(event, context):
    """
    Routes incoming webhooks to the correct handler:
    - Cal.com webhooks: contain triggerEvent field in JSON body
    - Stripe webhooks: contain stripe-signature header
    """
    del context

    body = event.get("body", "") or ""
    headers = {
        str(key).lower(): value
        for key, value in (event.get("headers") or {}).items()
    }

    has_stripe_sig = "stripe-signature" in headers
    has_cal_sig = "x-cal-signature-256" in headers

    is_calcom = False
    if not has_stripe_sig:
        try:
            parsed = json.loads(body)
            if "triggerEvent" in parsed:
                is_calcom = True
        except Exception:
            pass

    if is_calcom or has_cal_sig:
        return _handle_calcom_webhook(event, body)

    return _handle_stripe_webhook(event, body)
