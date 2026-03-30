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
# | limit 50....
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


def _normalize_phone_number(phone_number):
    if not phone_number:
        return None

    phone_text = str(phone_number).strip()
    digits_only = "".join(character for character in phone_text if character.isdigit())

    if len(digits_only) == 10:
        return f"+1{digits_only}"

    if len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"

    if phone_text.startswith("+") and 10 <= len(digits_only) <= 15:
        return f"+{digits_only}"

    _log("WARN", "invalid_phone_format", detail="phone not E.164 compatible")
    return None


def _amount_to_dollars(value, warning_event):
    try:
        return float(value) / 100 if value is not None else 0.0
    except (TypeError, ValueError):
        _log("WARN", warning_event, detail=str(value))
        return 0.0


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
    customer_phone = _normalize_phone_number(customer_phone)

    service = _response_value("service", "Service", "serviceType", "service_type")
    if not service:
        raw_title = payload.get("eventTitle") or payload.get("type") or ""
        title_map = {
            "mobile-detail-appointment-service-1": "SM Detail",
            "mobile-detail-appointment-service-2": "MD Detail",
            "mobile-detail-appointment-service-3": "LG Detail",
            "sm mobile detail appointment": "SM Detail",
            "md mobile detail appointment": "MD Detail",
            "lg mobile detail appointment": "LG Detail",
        }
        service = title_map.get(raw_title.lower().strip()) or raw_title or "Not specified"

    addons = (
        _response_value("add-ons", "addons", "Add-Ons", "add_ons", "additionalNotes")
        or payload.get("additionalNotes")
        or None
    )
    if addons and not addons.strip():
        addons = None

    address = (
        (responses.get("address-of-service") or {}).get("value")
        or (responses.get("addressOfService") or {}).get("value")
        or (responses.get("address_of_service") or {}).get("value")
        or (responses.get("address") or {}).get("value")
        or (responses.get("Address of Service") or {}).get("value")
        or (responses.get("location") or {}).get("value")
        or None
    )
    if address and not str(address).strip():
        address = None

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

    price_cents = payload.get("price")
    deposit_paid = _amount_to_dollars(price_cents, "invalid_price_value")

    return {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "service": service,
        "addons": addons,
        "address": address,
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
    detailer_phone_display = (DETAILER_PHONE or "").replace("+1", "").strip()
    if len(detailer_phone_display) == 10:
        detailer_phone_display = (
            f"({detailer_phone_display[:3]}) "
            f"{detailer_phone_display[3:6]}-"
            f"{detailer_phone_display[6:]}"
        )

    _log(
        "INFO",
        "calcom_booking_parsed",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        has_phone=booking["customer_phone"] is not None,
    )

    service_lower = booking["service"].lower().strip()
    full_price = SERVICE_PRICES.get(service_lower)
    if full_price is None:
        matched_keys = [key for key in SERVICE_PRICES if key in service_lower]
        if matched_keys:
            full_price = SERVICE_PRICES[max(matched_keys, key=len)]
    balance_due = round(full_price - booking["deposit_paid"], 2) if full_price else None
    balance_due = max(balance_due, 0) if balance_due is not None else None

    _log(
        "INFO",
        "balance_calculated",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
    )

    addons = booking["addons"]
    divider = "──────────────────────────────────────────"
    addons_line = f"\nAdd-Ons:  {addons}" if addons else ""
    address_line = f"\nAddress:  {booking['address']}" if booking.get("address") else ""
    balance_line = f"${balance_due:.2f}" if balance_due is not None else "Not mapped"

    sms_detailer = (
        f"\U0001F697 NEW DETAIL BOOKING\n"
        f"{divider}\n"
        f"Name:     {booking['customer_name']}\n"
        f"Phone:    {booking['customer_phone'] or 'No phone'}\n"
        f"Email:    {booking['customer_email']}\n"
        f"{divider}\n"
        f"Service:  {booking['service']}{addons_line}{address_line}\n"
        f"Date:     {booking['appointment_date']}\n"
        f"{divider}\n"
        f"Deposit:  ${booking['deposit_paid']:.2f}\n"
        f"Balance:  {balance_line}\n"
        f"{divider}\n"
        f"Customer Phone: {booking['customer_phone'] or 'No phone'}"
    )

    if not _send_sms(DETAILER_PHONE, sms_detailer, "detailer"):
        return _response(500, "Detailer SMS failed")

    customer_sms_status = "skipped"
    if booking["customer_phone"]:
        balance_customer = (
            f"${balance_due:.2f} due after service"
            if balance_due is not None
            else "Contact us for balance details"
        )
        addons_customer_line = f"\nAdd-Ons:  {addons}" if addons else ""
        address_customer_line = f"\nAddress:  {booking['address']}" if booking.get("address") else ""

        sms_customer = (
            f"\U0001F697 Booking Confirmed!\n"
            f"A Gentlemen's Touch\n"
            f"{divider}\n"
            f"Hi {booking['customer_name']}! Your detail is booked.\n"
            f"{divider}\n"
            f"Service:  {booking['service']}{addons_customer_line}{address_customer_line}\n"
            f"Date:     {booking['appointment_date']}\n"
            f"{divider}\n"
            f"Deposit:  ${booking['deposit_paid']:.2f} received\n"
            f"Balance:  {balance_customer}\n"
            f"{divider}\n"
            f"Questions? Call {detailer_phone_display}"
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
        metadata = session.get("metadata") or {}
        booking_id = str(metadata.get("booking_id") or "").strip() or "unknown"
        _log(
            "INFO",
            "stripe_webhook_received",
            stripe_event_id=stripe_event["id"],
            stripe_event_type=stripe_event["type"],
            livemode=stripe_event.get("livemode", False),
            session_id=session.get("id", "unknown"),
            payment_status=session.get("payment_status", "unknown"),
            amount_total=session.get("amount_total", 0),
            booking_id=booking_id,
        )

        if stripe_event["type"] != "checkout.session.completed":
            _log("INFO", "event_ignored", detail=f"Ignored event type: {stripe_event['type']}")
            return _response(200, "Ignored")

        customer_details = session.get("customer_details") or {}
        customer_name = customer_details.get("name") or "Unknown"
        customer_email = customer_details.get("email") or "No email"
        customer_phone = _normalize_phone_number(customer_details.get("phone") or None)
        detailer_phone_display = (DETAILER_PHONE or "").replace("+1", "").strip()
        if len(detailer_phone_display) == 10:
            detailer_phone_display = (
                f"({detailer_phone_display[:3]}) "
                f"{detailer_phone_display[3:6]}-"
                f"{detailer_phone_display[6:]}"
            )
        amount_total = session.get("amount_total")
        deposit_paid = _amount_to_dollars(amount_total, "invalid_amount_value")

        def _nonempty(val):
            """Return val if non-empty and not the placeholder 'Not specified', else None."""
            if val is None:
                return None
            s = str(val).strip()
            return s if s and s.lower() != "not specified" else None

        custom_fields = {
            field["key"]: _nonempty(field.get("text", {}).get("value"))
            for field in (session.get("custom_fields") or [])
            if "key" in field
        }
        service = (
            _nonempty(custom_fields.get("service"))
            or _nonempty(metadata.get("service"))
            or "Not specified"
        )
        addons = (
            _nonempty(custom_fields.get("add-ons"))
            or _nonempty(custom_fields.get("addons"))
            or _nonempty(metadata.get("add-ons"))
            or _nonempty(metadata.get("addons"))
            or _nonempty(metadata.get("add_ons"))
        )
        address = (
            _nonempty(custom_fields.get("address-of-service"))
            or _nonempty(custom_fields.get("addressOfService"))
            or _nonempty(custom_fields.get("address_of_service"))
            or _nonempty(custom_fields.get("address"))
            or _nonempty(custom_fields.get("Address of Service"))
            or _nonempty(custom_fields.get("location"))
            or _nonempty(metadata.get("address-of-service"))
            or _nonempty(metadata.get("addressOfService"))
            or _nonempty(metadata.get("address_of_service"))
            or _nonempty(metadata.get("address"))
            or _nonempty(metadata.get("location"))
        )
        date = (
            _nonempty(custom_fields.get("date"))
            or _nonempty(metadata.get("date"))
            or "Not specified"
        )

        service_lower = service.lower().strip()
        full_price = SERVICE_PRICES.get(service_lower)
        if full_price is None:
            matched_keys = [key for key in SERVICE_PRICES if key in service_lower]
            if matched_keys:
                full_price = SERVICE_PRICES[max(matched_keys, key=len)]
        balance_due = round(full_price - deposit_paid, 2) if full_price else None
        balance_due = max(balance_due, 0) if balance_due is not None else None

        _log(
            "INFO",
            "balance_calculated",
            service=service,
            deposit_paid=deposit_paid,
            balance_due=balance_due,
        )

        divider = "──────────────────────────────────────────"
        addons_line = f"\nAdd-Ons:  {addons}" if addons else ""
        address_line = f"\nAddress:  {address}" if address else ""
        balance_line = f"${balance_due:.2f}" if balance_due is not None else "Not mapped"
        sms_body_detailer = (
            f"\U0001F697 NEW DETAIL BOOKING\n"
            f"{divider}\n"
            f"Name:     {customer_name}\n"
            f"Phone:    {customer_phone or 'No phone'}\n"
            f"Email:    {customer_email}\n"
            f"{divider}\n"
            f"Service:  {service}{addons_line}{address_line}\n"
            f"Date:     {date}\n"
            f"{divider}\n"
            f"Deposit:  ${deposit_paid:.2f}\n"
            f"Balance:  {balance_line}\n"
            f"{divider}\n"
            f"Customer Phone: {customer_phone or 'No phone'}"
        )

        detailer_sms_ok = _send_sms(DETAILER_PHONE, sms_body_detailer, "detailer")
        if not detailer_sms_ok:
            _log(
                "ERROR",
                "detailer_sms_failed",
                phone=DETAILER_PHONE,
            )

        balance_customer = (
            f"${balance_due:.2f} due after service"
            if balance_due is not None
            else "Contact us for balance details"
        )
        addons_customer_line = f"\nAdd-Ons:  {addons}" if addons else ""
        address_customer_line = f"\nAddress:  {address}" if address else ""
        sms_body_customer = (
            f"\U0001F697 Booking Confirmed!\n"
            f"A Gentlemen's Touch\n"
            f"{divider}\n"
            f"Hi {customer_name}! Your detail is booked.\n"
            f"{divider}\n"
            f"Service:  {service}{addons_customer_line}{address_customer_line}\n"
            f"Date:     {date}\n"
            f"{divider}\n"
            f"Deposit:  ${deposit_paid:.2f} received\n"
            f"Balance:  {balance_customer}\n"
            f"{divider}\n"
            f"Questions? Call {detailer_phone_display}"
        )

        customer_sms_status = "skipped"
        if not customer_phone:
            _log("INFO", "customer_sms_skipped", detail="no phone on file")
        else:
            customer_sms_ok = _send_sms(customer_phone, sms_body_customer, "customer")
            if customer_sms_ok:
                customer_sms_status = "sent"
            else:
                customer_sms_status = "failed"
                _log("ERROR", "customer_sms_failed", phone=customer_phone)

        _log(
            "INFO",
            "booking_processed",
            customer=customer_name,
            service=service,
            deposit_paid=deposit_paid,
            balance_due=balance_due,
            booking_id=booking_id,
            customer_sms=customer_sms_status,
        )
        _log("INFO", "booking_confirmed", booking_id=booking_id)
        return _response(200, "Webhook processed")
    except Exception as exc:
        _log("ERROR", "webhook_processing_failed", detail=str(exc))
        return _response(500, "Webhook processed with errors")


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

    is_calcom = has_cal_sig
    if not has_stripe_sig and not has_cal_sig:
        try:
            parsed = json.loads(body)
            if "triggerEvent" in parsed:
                is_calcom = True
        except Exception:
            pass

    if is_calcom:
        return _handle_calcom_webhook(event, body)

    return _handle_stripe_webhook(event, body)
