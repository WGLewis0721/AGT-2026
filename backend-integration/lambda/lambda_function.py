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


def _normalized_headers(event: dict) -> dict:
    """Return a lowercase-keyed copy of the event headers dict."""
    return {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}


def _format_detailer_phone() -> str:
    """Return DETAILER_PHONE formatted as (NXX) NXX-XXXX for display."""
    display = (DETAILER_PHONE or "").replace("+1", "").strip()
    if len(display) == 10:
        display = f"({display[:3]}) {display[3:6]}-{display[6:]}"
    return display


def _extract_address_from_custom_fields(custom_fields: dict):
    """Return the first non-empty address value from a custom-fields dict."""
    address = (
        custom_fields.get("address-of-service")
        or custom_fields.get("addressOfService")
        or custom_fields.get("address_of_service")
        or custom_fields.get("address")
        or custom_fields.get("Address of Service")
        or custom_fields.get("location")
        or None
    )
    if address and not str(address).strip():
        return None
    return address


def _calculate_balance_due(service: str, deposit_paid: float):
    """Compute remaining balance; returns None when service price is unknown."""
    service_lower = service.lower().strip()
    full_price = SERVICE_PRICES.get(service_lower)
    if full_price is None:
        matched_keys = [key for key in SERVICE_PRICES if key in service_lower]
        if matched_keys:
            full_price = SERVICE_PRICES[max(matched_keys, key=len)]
    balance = round(full_price - deposit_paid, 2) if full_price else None
    return max(balance, 0) if balance is not None else None


def _build_detailer_sms(
    name, phone, email, service, addons, address, date, deposit_paid, balance_due
):
    divider = "──────────────────────────────────────────"
    addons_line = f"\nAdd-Ons:  {addons}" if addons else ""
    address_line = f"\nAddress:  {address}" if address else ""
    balance_line = f"${balance_due:.2f}" if balance_due is not None else "Not mapped"
    return (
        f"\U0001F697 NEW DETAIL BOOKING\n"
        f"{divider}\n"
        f"Name:     {name}\n"
        f"Phone:    {phone or 'No phone'}\n"
        f"Email:    {email}\n"
        f"{divider}\n"
        f"Service:  {service}{addons_line}{address_line}\n"
        f"Date:     {date}\n"
        f"{divider}\n"
        f"Deposit:  ${deposit_paid:.2f}\n"
        f"Balance:  {balance_line}\n"
        f"{divider}\n"
        f"Customer Phone: {phone or 'No phone'}"
    )


def _build_customer_sms(
    name, service, addons, address, date, deposit_paid, balance_due, detailer_phone_display
):
    divider = "──────────────────────────────────────────"
    addons_line = f"\nAdd-Ons:  {addons}" if addons else ""
    address_line = f"\nAddress:  {address}" if address else ""
    balance_str = (
        f"${balance_due:.2f} due after service"
        if balance_due is not None
        else "Contact us for balance details"
    )
    return (
        f"\U0001F697 Booking Confirmed!\n"
        f"A Gentlemen's Touch\n"
        f"{divider}\n"
        f"Hi {name}! Your detail is booked.\n"
        f"{divider}\n"
        f"Service:  {service}{addons_line}{address_line}\n"
        f"Date:     {date}\n"
        f"{divider}\n"
        f"Deposit:  ${deposit_paid:.2f} received\n"
        f"Balance:  {balance_str}\n"
        f"{divider}\n"
        f"Questions? Call {detailer_phone_display}"
    )


# ─── Cal.com helpers ───────────────────────────────────────────────────────────


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


def _calcom_response_value(responses: dict, *keys):
    """Return the first non-empty value from Cal.com responses by key list."""
    for key in keys:
        raw_value = responses.get(key)
        value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value

        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item not in (None, ""))

        if value not in (None, ""):
            return value

    return None


def _parse_calcom_contact(responses: dict, attendees: list) -> tuple:
    """Extract customer name, email, and normalised phone from Cal.com responses."""
    customer_name = (
        _calcom_response_value(responses, "name")
        or (attendees[0].get("name") if attendees else None)
        or "Unknown"
    )
    customer_email = (
        _calcom_response_value(responses, "email")
        or (attendees[0].get("email") if attendees else None)
        or "No email"
    )
    customer_phone = _normalize_phone_number(
        _calcom_response_value(responses, "attendeePhoneNumber", "phone", "smsReminderNumber")
    )
    return customer_name, customer_email, customer_phone


def _parse_calcom_service(payload: dict, responses: dict) -> str:
    """Resolve service name from Cal.com payload, falling back to event title mapping."""
    service = _calcom_response_value(responses, "service", "Service", "serviceType", "service_type")
    if service:
        return service
    raw_title = payload.get("eventTitle") or payload.get("type") or ""
    title_map = {
        "mobile-detail-appointment-service-1": "SM Detail",
        "mobile-detail-appointment-service-2": "MD Detail",
        "mobile-detail-appointment-service-3": "LG Detail",
        "sm mobile detail appointment": "SM Detail",
        "md mobile detail appointment": "MD Detail",
        "lg mobile detail appointment": "LG Detail",
    }
    return title_map.get(raw_title.lower().strip()) or raw_title or "Not specified"


def _parse_calcom_addons(responses: dict, payload: dict):
    """Extract add-ons from Cal.com responses."""
    addons = (
        _calcom_response_value(responses, "add-ons", "addons", "Add-Ons", "add_ons", "additionalNotes")
        or payload.get("additionalNotes")
        or None
    )
    if addons and not addons.strip():
        return None
    return addons


def _parse_calcom_address(responses: dict):
    """Extract service address from Cal.com responses (values are nested dicts)."""
    keys = [
        "address-of-service", "addressOfService", "address_of_service",
        "address", "Address of Service", "location",
    ]
    for key in keys:
        value = (responses.get(key) or {}).get("value")
        if value and str(value).strip():
            return value
    return None


def _parse_calcom_appointment_date(payload: dict) -> str:
    """Format Cal.com startTime into a human-readable appointment date string."""
    start_time_raw = payload.get("startTime") or ""
    try:
        dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hour = dt.strftime("%I").lstrip("0") or "0"
        return (
            f"{dt.strftime('%a %b')} {dt.day} @ "
            f"{hour}:{dt.strftime('%M %p')} {dt.tzname() or 'UTC'}"
        )
    except Exception:
        return start_time_raw or "Not specified"


def _parse_calcom_booking(payload: dict) -> dict:
    """Extract and normalise booking fields from a Cal.com webhook payload."""
    responses = payload.get("responses") or {}
    attendees = payload.get("attendees") or []
    customer_name, customer_email, customer_phone = _parse_calcom_contact(responses, attendees)
    return {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "service": _parse_calcom_service(payload, responses),
        "addons": _parse_calcom_addons(responses, payload),
        "address": _parse_calcom_address(responses),
        "appointment_date": _parse_calcom_appointment_date(payload),
        "deposit_paid": _amount_to_dollars(payload.get("price"), "invalid_price_value"),
        "booking_uid": payload.get("uid") or "unknown",
    }


def _verify_calcom_request(event: dict, body: str) -> tuple:
    """Verify Cal.com signature and parse JSON body. Returns (data, err_response)."""
    headers = _normalized_headers(event)
    sig_header = headers.get("x-cal-signature-256", "")
    if CALCOM_WEBHOOK_SECRET and not _verify_calcom_signature(body, sig_header):
        _log("ERROR", "calcom_invalid_signature")
        return None, _response(400, "Invalid Cal.com signature")
    try:
        data = json.loads(body)
    except Exception as exc:
        _log("ERROR", "calcom_parse_error", detail=str(exc))
        return None, _response(400, "Invalid JSON")
    return data, None


def _send_calcom_sms(booking: dict, balance_due, detailer_phone_display: str) -> tuple:
    """Send detailer and customer SMS for a Cal.com booking. Returns (status, err_response)."""
    sms_detailer = _build_detailer_sms(
        booking["customer_name"], booking["customer_phone"], booking["customer_email"],
        booking["service"], booking["addons"], booking.get("address"),
        booking["appointment_date"], booking["deposit_paid"], balance_due,
    )
    if not _send_sms(DETAILER_PHONE, sms_detailer, "detailer"):
        return "failed", _response(500, "Detailer SMS failed")
    customer_sms_status = "skipped"
    if booking["customer_phone"]:
        sms_customer = _build_customer_sms(
            booking["customer_name"], booking["service"], booking["addons"],
            booking.get("address"), booking["appointment_date"],
            booking["deposit_paid"], balance_due, detailer_phone_display,
        )
        customer_sms_status = "sent" if _send_sms(
            booking["customer_phone"], sms_customer, "customer"
        ) else "failed"
    else:
        _log("INFO", "customer_sms_skipped", detail="no phone on file")
    return customer_sms_status, None


def _handle_calcom_webhook(event: dict, body: str) -> dict:
    """Handle incoming Cal.com webhook. Verifies signature, parses booking, sends SMS."""
    data, err = _verify_calcom_request(event, body)
    if err:
        return err

    trigger = data.get("triggerEvent", "")
    payload = data.get("payload") or {}
    _log(
        "INFO", "calcom_webhook_received",
        trigger=trigger,
        booking_id=payload.get("bookingId"),
        event_title=payload.get("eventTitle"),
    )

    if trigger != "BOOKING_PAYMENT_INITIATED":
        _log("INFO", "calcom_ignored", trigger=trigger)
        return _response(200, f"Ignored: {trigger}")

    booking = _parse_calcom_booking(payload)
    _log(
        "INFO", "calcom_booking_parsed",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        has_phone=booking["customer_phone"] is not None,
    )
    balance_due = _calculate_balance_due(booking["service"], booking["deposit_paid"])
    _log(
        "INFO", "balance_calculated",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
    )
    customer_sms_status, sms_err = _send_calcom_sms(booking, balance_due, _format_detailer_phone())
    if sms_err:
        return sms_err
    _log(
        "INFO", "calcom_booking_processed",
        customer_name=booking["customer_name"],
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
        detailer_sms="sent",
        customer_sms=customer_sms_status,
        booking_uid=booking["booking_uid"],
    )
    return _response(200, "Cal.com booking processed")


# ─── Stripe helpers ────────────────────────────────────────────────────────────


def _verify_stripe_event(event: dict, body: str) -> tuple:
    """Verify Stripe webhook signature. Returns (stripe_event_dict, err_response)."""
    sig_header = _normalized_headers(event).get("stripe-signature", "")
    stripe.api_key = STRIPE_SECRET_KEY
    try:
        verified_event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
        if hasattr(verified_event, "to_dict_recursive"):
            return verified_event.to_dict_recursive(), None
        return json.loads(body), None
    except stripe.error.SignatureVerificationError as exc:
        _log("ERROR", "signature_verification_failed", detail=str(exc))
        return None, _response(400, "Invalid signature")
    except Exception as exc:
        _log("ERROR", "webhook_verification_failed", detail=str(exc))
        return None, _response(400, "Webhook error")


def _extract_stripe_booking(session: dict) -> dict:
    """Extract booking fields from a Stripe checkout session object."""
    customer_details = session.get("customer_details") or {}
    custom_fields = {
        field["key"]: field.get("text", {}).get("value", "Not specified")
        for field in (session.get("custom_fields") or [])
        if "key" in field
    }
    return {
        "customer_name": customer_details.get("name") or "Unknown",
        "customer_email": customer_details.get("email") or "No email",
        "customer_phone": _normalize_phone_number(customer_details.get("phone") or None),
        "service": custom_fields.get("service", "Not specified"),
        "addons": custom_fields.get("add-ons") or custom_fields.get("addons"),
        "address": _extract_address_from_custom_fields(custom_fields),
        "appointment_date": custom_fields.get("date", "Not specified"),
    }


def _process_stripe_session(session: dict) -> dict:
    """Extract booking from session, calculate balance, and send SMS notifications."""
    booking = _extract_stripe_booking(session)
    deposit_paid = _amount_to_dollars(session.get("amount_total"), "invalid_amount_value")
    balance_due = _calculate_balance_due(booking["service"], deposit_paid)
    _log(
        "INFO", "balance_calculated",
        service=booking["service"],
        deposit_paid=deposit_paid,
        balance_due=balance_due,
    )
    sms_detailer = _build_detailer_sms(
        booking["customer_name"], booking["customer_phone"], booking["customer_email"],
        booking["service"], booking["addons"], booking["address"],
        booking["appointment_date"], deposit_paid, balance_due,
    )
    if not _send_sms(DETAILER_PHONE, sms_detailer, "detailer"):
        return _response(500, "SMS failed")
    if not booking["customer_phone"]:
        _log("INFO", "customer_sms_skipped", detail="no phone on file")
    else:
        sms_customer = _build_customer_sms(
            booking["customer_name"], booking["service"], booking["addons"],
            booking["address"], booking["appointment_date"],
            deposit_paid, balance_due, _format_detailer_phone(),
        )
        _send_sms(booking["customer_phone"], sms_customer, "customer")
    _log(
        "INFO", "booking_processed",
        customer=booking["customer_name"],
        service=booking["service"],
        deposit_paid=deposit_paid,
        balance_due=balance_due,
    )
    return _response(200, "SMS sent")


def _handle_stripe_webhook(event: dict, body: str) -> dict:
    """Handle incoming Stripe webhook (checkout.session.completed)."""
    stripe_event, err = _verify_stripe_event(event, body)
    if err:
        return err

    try:
        session = stripe_event["data"]["object"]
        _log(
            "INFO", "stripe_webhook_received",
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
        return _process_stripe_session(session)
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
    headers = _normalized_headers(event)

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
