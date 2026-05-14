import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal

import boto3 as _boto3
import requests

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

SQUARE_ACCESS_TOKEN          = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQUARE_WEBHOOK_SIGNATURE_KEY = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
CALCOM_WEBHOOK_SECRET = os.environ.get("CALCOM_WEBHOOK_SECRET", "")
TEXTBELT_API_KEY = os.environ.get("TEXTBELT_API_KEY")
DETAILER_PHONE = os.environ.get("DETAILER_PHONE")
MARK_COMPLETE_SECRET = os.environ.get("MARK_COMPLETE_SECRET", "")
PUBLIC_API_BASE_URL = os.environ.get("PUBLIC_API_BASE_URL", "")

# ─── Inline DynamoDB (replaces booking_common) ─────────────────

_dynamodb = _boto3.resource("dynamodb")
_BOOKING_TABLE_NAME = os.environ.get("BOOKING_TABLE", "")


def _booking_table():
    return _dynamodb.Table(_BOOKING_TABLE_NAME)


def _get_booking(booking_id: str):
    if not booking_id or booking_id == "unknown":
        return None
    try:
        response = _booking_table().get_item(Key={"booking_id": booking_id})
        return response.get("Item")
    except Exception as exc:
        _log("ERROR", "booking_lookup_failed",
             booking_id=booking_id, detail=str(exc))
        return None


def _format_addons(addons) -> str:
    if not addons:
        return ""
    if isinstance(addons, list):
        return ", ".join(str(a) for a in addons if a)
    return str(addons)


# ─── Constants ─────────────────

# When TEST_MODE=true, mirror the micro prices used by pricing_lambda.py
# so SMS deposit/balance amounts match what Square actually charged.
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"

REAL_SERVICE_PRICES = {
    "sm detail": 100.00,
    "md detail": 150.00,
    "lg detail": 200.00,
    "full detail": 150.00,
    "small": 100.00,
    "medium": 150.00,
    "large": 200.00,
}

TEST_SERVICE_PRICES = {
    "sm detail": 0.01,
    "md detail": 0.10,
    "lg detail": 1.00,
    "full detail": 0.10,
    "small": 0.01,
    "medium": 0.10,
    "large": 1.00,
}

SERVICE_PRICES = TEST_SERVICE_PRICES if TEST_MODE else REAL_SERVICE_PRICES
DEPOSIT_RATE   = 1.00 if TEST_MODE else 0.20

BUSINESS_PHONE = "(334) 294-8228"


# ─── Utilities ─────────────────

def _sanitize_string(value):
    sanitized = str(value)

    for secret in (
        SQUARE_ACCESS_TOKEN,
        SQUARE_WEBHOOK_SIGNATURE_KEY,
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


def _format_phone_display(phone_number):
    digits_only = "".join(character for character in str(phone_number or "") if character.isdigit())
    if len(digits_only) == 11 and digits_only.startswith("1"):
        digits_only = digits_only[1:]

    if len(digits_only) == 10:
        return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"

    return phone_number or BUSINESS_PHONE


def _format_appointment_time(value):
    if not value:
        return "Not specified"

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %I:%M %p %Z").strip()
    except Exception:
        return str(value)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
    return {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}


def _format_detailer_phone() -> str:
    display = (DETAILER_PHONE or "").replace("+1", "").strip()
    if len(display) == 10:
        display = f"({display[:3]}) {display[3:6]}-{display[6:]}"
    return display


def _service_full_price(service: str):
    service_lower = service.lower().strip()
    full_price = SERVICE_PRICES.get(service_lower)
    if full_price is None:
        matched_keys = [key for key in SERVICE_PRICES if key in service_lower]
        if matched_keys:
            full_price = SERVICE_PRICES[max(matched_keys, key=len)]
    return full_price


def _calculate_balance_due(service: str, deposit_paid: float):
    full_price = _service_full_price(service)
    balance_due = round(full_price - deposit_paid, 2) if full_price else None
    return max(balance_due, 0) if balance_due is not None else None


# ─── DynamoDB Operations ─────────────────

def _mark_booking_confirmed(
    booking_id,
    square_payment_id,
    square_order_id,
    amount_total_cents,
    detailer_sms_status,
    customer_sms_status,
    customer_name=None,
    customer_phone=None,
    customer_email=None,
    service=None,
    addons=None,
    address=None,
    appointment_date=None,
    deposit_paid=None,
    balance_due=None,
    source="square",
    environment=None,
    waiver_accepted_at=None,
):
    if not booking_id or booking_id == "unknown":
        return

    update_parts = [
        "#status = :status",
        "payment_status = :payment_status",
        "paid_at = :paid_at",
        "updated_at = :updated_at",
        "square_payment_id = :square_payment_id",
        "square_order_id = :square_order_id",
        "square_amount_total_cents = :amount_total_cents",
        "detailer_sms_status = :detailer_sms_status",
        "customer_sms_status = :customer_sms_status",
        "customer_name = :customer_name",
        "appointment_date = :appt_date",
        "deposit_paid = :deposit_paid",
        "source = :source",
        "#env = :environment",
    ]
    values = {
        ":status": "confirmed",
        ":payment_status": "paid",
        ":paid_at": datetime.now(timezone.utc).isoformat(),
        ":updated_at": datetime.now(timezone.utc).isoformat(),
        ":square_payment_id":  square_payment_id,
        ":square_order_id":    square_order_id,
        ":amount_total_cents": int(amount_total_cents or 0),
        ":detailer_sms_status": detailer_sms_status,
        ":customer_sms_status": customer_sms_status,
        ":customer_name":  customer_name or "Unknown",
        ":appt_date":      appointment_date or "Not specified",
        ":deposit_paid":   Decimal(str(deposit_paid)) if deposit_paid is not None else Decimal("0"),
        ":balance_due":    Decimal(str(balance_due)) if balance_due is not None else None,
        ":source":         source,
        ":environment":    environment or "unknown",
    }
    if values[":balance_due"] is not None:
        update_parts.append("balance_due = :balance_due")
    else:
        del values[":balance_due"]
    optional = {
        "customer_phone":     customer_phone,
        "customer_email":     customer_email,
        "service":            service,
        "addons":             addons,
        "address":            address,
        "waiver_accepted_at": waiver_accepted_at,
    }
    for field, value in optional.items():
        if value:
            update_parts.append(f"{field} = :{field}")
            values[f":{field}"] = value

    try:
        _booking_table().update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames={"#status": "status", "#env": "environment"},
            ExpressionAttributeValues=values,
        )
    except Exception as exc:
        _log("ERROR", "booking_update_failed", booking_id=booking_id, detail=str(exc))


def _find_booking_by_phone(customer_phone: str):
    """Find the most recent confirmed-but-not-yet-scheduled booking by phone."""
    if not customer_phone:
        return None
    try:
        response = _booking_table().scan(
            FilterExpression=(
                "customer_phone = :p AND #status = :s "
                "AND attribute_not_exists(appointment_at)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":p": customer_phone,
                ":s": "confirmed",
            },
        )
        items = response.get("Items") or []
        if not items:
            return None
        items.sort(key=lambda item: item.get("paid_at", ""), reverse=True)
        return items[0]
    except Exception as exc:
        _log("ERROR", "booking_scan_failed", detail=str(exc))
        return None


def _attach_calcom_to_booking(booking: dict):
    """Update the existing DynamoDB row with appointment + vehicle from Cal.com.
    Returns the matched booking_id (or None if no match)."""
    phone = booking.get("customer_phone")
    if not phone:
        _log("INFO", "calcom_attach_skipped", reason="no_phone")
        return None
    row = _find_booking_by_phone(phone)
    if not row:
        _log("INFO", "calcom_attach_no_match", phone=phone)
        return None

    update_parts = ["updated_at = :updated_at"]
    values = {":updated_at": datetime.now(timezone.utc).isoformat()}
    optional = {
        "appointment_at":      booking.get("appointment_at_iso") or None,
        "appointment_display": booking.get("appointment_date") or None,
        "vehicle_make":        booking.get("vehicle_make") or None,
        "vehicle_model":       booking.get("vehicle_model") or None,
        "calcom_booking_uid":  booking.get("booking_uid") or None,
        "customer_name":       booking.get("customer_name") or None,
        "address":             booking.get("address") or None,
    }
    for field, value in optional.items():
        if value:
            update_parts.append(f"{field} = :{field}")
            values[f":{field}"] = value

    try:
        _booking_table().update_item(
            Key={"booking_id": row["booking_id"]},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=values,
        )
        _log("INFO", "calcom_attached", booking_id=row["booking_id"])
        return row["booking_id"]
    except Exception as exc:
        _log("ERROR", "calcom_attach_failed",
             booking_id=row.get("booking_id"), detail=str(exc))
        return None


# ─── Mark-Complete ─────────────────

def _complete_token(booking_id: str) -> str:
    if not MARK_COMPLETE_SECRET or not booking_id:
        return ""
    return hmac.new(
        MARK_COMPLETE_SECRET.encode("utf-8"),
        booking_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


def _complete_link(booking_id: str) -> str:
    if not booking_id or not PUBLIC_API_BASE_URL:
        return ""
    return f"{PUBLIC_API_BASE_URL}/complete?id={booking_id}&t={_complete_token(booking_id)}"


def _handle_complete_link(event: dict) -> dict:
    qs = event.get("queryStringParameters") or {}
    booking_id = qs.get("id") or ""
    token      = qs.get("t") or ""
    expected   = _complete_token(booking_id)
    if not expected or not hmac.compare_digest(expected, token):
        _log("ERROR", "complete_invalid_token", booking_id=booking_id)
        return _html_response(403, "<h1>Invalid or expired link</h1>")
    try:
        _booking_table().update_item(
            Key={"booking_id": booking_id},
            UpdateExpression=(
                "SET #status = :status, "
                "completed_at = if_not_exists(completed_at, :now), "
                "updated_at = :now"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":now":    datetime.now(timezone.utc).isoformat(),
            },
        )
        _log("INFO", "booking_completed", booking_id=booking_id)
    except Exception as exc:
        _log("ERROR", "complete_update_failed",
             booking_id=booking_id, detail=str(exc))
        return _html_response(500, "<h1>Could not mark complete</h1>")
    return _html_response(
        200,
        "<html><body style=\"font-family:sans-serif;text-align:center;"
        "padding:60px 20px;background:#0a0a0a;color:#F0EDE8;\">"
        "<h1 style=\"color:#C9A84C;\">\u2713 Marked complete</h1>"
        "<p>Thanks. You can close this page.</p></body></html>",
    )


def _html_response(status: int, body: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": body,
    }


# ─── SMS ─────────────────

def _send_sms(phone_number, message, recipient):
    try:
        response = requests.post(
            "https://textbelt.com/text",
            {
                "phone": phone_number,
                "message": str(message),
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


def _send_sms_to_detailers(message: str) -> bool:
    if not DETAILER_PHONE:
        _log("INFO", "detailer_sms_skipped", detail="DETAILER_PHONE not configured")
        return False
    return _send_sms(DETAILER_PHONE, message, "detailer")


def _build_detailer_sms(booking: dict, balance_due, divider: str, complete_url: str = "") -> str:
    addons_line = f"\nAdd-Ons:  {booking['addons']}" if booking.get("addons") else ""
    address_line = f"\nAddress:  {booking['address']}" if booking.get("address") else ""
    vehicle_line = f"\nVehicle:  {booking['vehicle']}" if booking.get("vehicle") else ""
    balance_line = f"${balance_due:.2f}" if balance_due is not None else "Not mapped"
    complete_line = f"\n{divider}\nMark complete: {complete_url}" if complete_url else ""
    appointment_time = booking.get("appointment_time", "")
    if appointment_time:
        date_display = f"{booking['appointment_date']} at {appointment_time}"
    else:
        date_display = booking["appointment_date"] or "Not specified"
    return (
        f"\U0001F697 NEW DETAIL BOOKING\n"
        f"{divider}\n"
        f"Name:     {booking['customer_name']}\n"
        f"Phone:    {booking['customer_phone'] or 'No phone'}\n"
        f"Email:    {booking['customer_email']}\n"
        f"{divider}\n"
        f"Service:  {booking['service']}{addons_line}{address_line}{vehicle_line}\n"
        f"Date:     {date_display}\n"
        f"{divider}\n"
        f"Deposit:  ${booking['deposit_paid']:.2f}\n"
        f"Balance:  {balance_line}"
        f"{complete_line}"
    )


def _build_customer_sms(booking: dict, balance_due, detailer_phone_display: str, divider: str) -> str:
    balance_customer = (
        f"${balance_due:.2f} due after service"
        if balance_due is not None
        else "Contact us for balance details"
    )
    addons_line = f"\nAdd-Ons:  {booking['addons']}" if booking.get("addons") else ""
    address_line = f"\nAddress:  {booking['address']}" if booking.get("address") else ""
    vehicle_line = f"\nVehicle:  {booking['vehicle']}" if booking.get("vehicle") else ""
    appointment_time = booking.get("appointment_time", "")
    if appointment_time:
        date_display = f"{booking['appointment_date']} at {appointment_time}"
    else:
        date_display = booking["appointment_date"] or "Not specified"
    return (
        f"\U0001F697 Booking Confirmed!\n"
        f"A Gentlemen's Touch\n"
        f"{divider}\n"
        f"Hi {booking['customer_name']}! Your detail is confirmed.\n"
        f"{divider}\n"
        f"Service:  {booking['service']}{addons_line}{address_line}{vehicle_line}\n"
        f"Date:     {date_display}\n"
        f"{divider}\n"
        f"Deposit:  ${booking['deposit_paid']:.2f} received\n"
        f"Balance:  {balance_customer}\n"
        f"{divider}\n"
        f"Questions? Call {detailer_phone_display}"
    )


# ─── Cal.com Webhook ─────────────────

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
    """Look up the first non-empty value from Cal.com responses by key."""
    for key in keys:
        raw_value = responses.get(key)
        value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item not in (None, ""))
        if value not in (None, ""):
            return value
    return None


def _parse_calcom_contact(responses: dict, attendees: list) -> tuple:
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
    customer_phone = _calcom_response_value(
        responses, "attendeePhoneNumber", "phone", "smsReminderNumber"
    )
    return customer_name, customer_email, _normalize_phone_number(customer_phone)


def _parse_calcom_service(payload: dict, responses: dict) -> str:
    service = _calcom_response_value(responses, "service", "Service", "serviceType", "service_type")
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
    return service


def _parse_calcom_address(responses: dict):
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
    return address


def _parse_calcom_appointment_date(payload: dict) -> str:
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
    """
    Extract booking details from Cal.com BOOKING_CREATED payload.
    Returns a normalized dict matching the SMS builder expectations.
    """
    responses = payload.get("responses") or {}
    attendees = payload.get("attendees") or []
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
    addons = (
        _calcom_response_value(responses, "add-ons", "addons", "Add-Ons", "add_ons", "additionalNotes")
        or payload.get("additionalNotes")
        or None
    )
    if addons and not addons.strip():
        addons = None
    vehicle_make = _calcom_response_value(
        responses, "vehicle-make", "vehicle_make", "vehicleMake", "Vehicle Make", "make"
    )
    vehicle_model = _calcom_response_value(
        responses, "vehicle-model", "vehicle_model", "vehicleModel", "Vehicle Model", "model"
    )
    service = _parse_calcom_service(payload, responses)
    # Square handles payment, not Cal.com. Always derive the deposit from
    # the configured deposit rate on the package full price; payload.price
    # is ignored because it reflects whatever was last configured on the
    # Cal.com event type, not what Square actually charged.
    full_price = _service_full_price(service)
    deposit_paid = round(full_price * DEPOSIT_RATE, 2) if full_price else 0.0
    return {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "service": service,
        "addons": addons,
        "address": _parse_calcom_address(responses),
        "appointment_date": _parse_calcom_appointment_date(payload),
        "appointment_at_iso": payload.get("startTime") or "",
        "vehicle_make": vehicle_make,
        "vehicle_model": vehicle_model,
        "deposit_paid": deposit_paid,
        "booking_uid": payload.get("uid") or "unknown",
    }


def _parse_and_verify_calcom(event: dict, body: str) -> tuple:
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


def _check_calcom_trigger(data: dict):
    trigger = data.get("triggerEvent", "")
    payload = data.get("payload") or {}
    _log(
        "INFO",
        "calcom_webhook_received",
        trigger=trigger,
        booking_id=payload.get("bookingId"),
        event_title=payload.get("eventTitle"),
    )
    if trigger != "BOOKING_CREATED":
        _log("INFO", "calcom_ignored", trigger=trigger)
        return _response(200, f"Ignored: {trigger}")
    return None


def _send_calcom_sms(booking: dict, balance_due, detailer_phone_display: str, complete_url: str = "") -> tuple:
    divider = "\u2500" * 42
    sms_detailer = _build_detailer_sms(booking, balance_due, divider, complete_url)
    if not _send_sms(DETAILER_PHONE, sms_detailer, "detailer"):
        return None, _response(500, "Detailer SMS failed")
    customer_sms_status = "skipped"
    if booking["customer_phone"]:
        sms_customer = _build_customer_sms(booking, balance_due, detailer_phone_display, divider)
        if _send_sms(booking["customer_phone"], sms_customer, "customer"):
            customer_sms_status = "sent"
        else:
            customer_sms_status = "failed"
    else:
        _log("INFO", "customer_sms_skipped", detail="no phone on file")
    return customer_sms_status, None


def _handle_calcom_webhook(event: dict, body: str) -> dict:
    """Handle incoming Cal.com webhook. Verifies signature, parses booking, sends SMS."""
    data, err = _parse_and_verify_calcom(event, body)
    if err:
        return err
    trigger_err = _check_calcom_trigger(data)
    if trigger_err:
        return trigger_err
    payload = data.get("payload") or {}
    booking = _parse_calcom_booking(payload)
    detailer_phone_display = _format_detailer_phone()
    _log(
        "INFO",
        "calcom_booking_parsed",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        has_phone=booking["customer_phone"] is not None,
    )
    balance_due = _calculate_balance_due(booking["service"], booking["deposit_paid"])
    _log(
        "INFO",
        "balance_calculated",
        service=booking["service"],
        deposit_paid=booking["deposit_paid"],
        balance_due=balance_due,
    )
    matched_booking_id = _attach_calcom_to_booking(booking)
    complete_url = _complete_link(matched_booking_id) if matched_booking_id else ""
    customer_sms_status, sms_err = _send_calcom_sms(
        booking, balance_due, detailer_phone_display, complete_url
    )
    if sms_err:
        return sms_err
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


# ─── Square Webhook ─────────────────

def _verify_square_signature(body: str, signature: str, url: str) -> bool:
    """Verify Square webhook signature using HMAC-SHA256."""
    if not SQUARE_WEBHOOK_SIGNATURE_KEY or not signature:
        return False
    try:
        message = url + body
        expected = hmac.new(
            SQUARE_WEBHOOK_SIGNATURE_KEY.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        import base64
        expected_b64 = base64.b64encode(expected).decode("utf-8")
        return hmac.compare_digest(expected_b64, signature)
    except Exception as exc:
        _log("ERROR", "square_sig_error", detail=str(exc))
        return False


PACKAGE_DISPLAY = {
    "sm_detail": "Essential Detail",
    "md_detail": "Signature Detail",
    "lg_detail": "Executive Detail",
}

ADDON_DISPLAY = {
    "pet_hair":      "Pet Hair Removal",
    "shampooing":    "Interior Shampooing",
    "upholstery":    "Upholstery Shampoo",
    "wax":           "Hand Wax Upgrade",
    "steam":         "Steam Cleaning",
    "polishing":     "Machine Polishing",
    "headlights":    "Headlight Restore",
    "odor":          "Odor Elimination",
    "engine_bay":    "Engine Bay Clean",
    "tire_dressing": "Tire Dressing",
    "leather":       "Leather Treatment",
}


def _format_iso_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        day = str(dt.day)
        return dt.strftime(f"%a, %b {day}, %Y")
    except ValueError:
        return date_str


def _format_24h_time(time_str: str) -> str:
    if not time_str:
        return ""
    try:
        dt = datetime.strptime(time_str.strip(), "%H:%M")
        hour = str(dt.hour % 12 or 12)
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{hour}:{dt.strftime('%M')} {ampm}"
    except ValueError:
        return time_str


def _format_addon_display(raw_addons: str) -> str:
    if not raw_addons:
        return None
    keys = [k.strip() for k in raw_addons.split(",") if k.strip()]
    names = [ADDON_DISPLAY.get(k, k) for k in keys]
    return ", ".join(names) if names else None


def _extract_square_booking(payment: dict) -> dict:
    """
    Extract booking fields from a Square payment.updated event.
    Reads booking context from the pipe-delimited note field written
    by pricing_lambda.py at checkout creation time.
    """
    note = (
        payment.get("note")
        or payment.get("payment_note")
        or (payment.get("order") or {}).get("note")
        or ""
    )
    import sys
    print(json.dumps({
        "level": "DEBUG",
        "event": "payment_note_debug",
        "note_length": len(note),
        "note_preview": note[:200] if note else "EMPTY"
    }), file=sys.stdout, flush=True)
    context = {}
    for part in note.split("|"):
        if "=" in part:
            key, _, value = part.partition("=")
            context[key.strip()] = value.strip()

    amount_cents = (
        (payment.get("amount_money") or {}).get("amount") or 0
    )
    deposit_paid = round(amount_cents / 100, 2)

    balance = context.get("balance")
    balance_due = _to_float(balance) if balance else None

    buyer = payment.get("buyer_email_address") or "No email"
    # Square Payment Links don't collect name at checkout — only email and phone.
    # Customer name comes from Cal.com webhook when the appointment is scheduled.
    return {
        "customer_name":  context.get("customer_name") or "Square Checkout",
        "customer_email": context.get("customer_email") or buyer,
        "customer_phone": _normalize_phone_number(
            context.get("customer_phone")
            or payment.get("buyer_phone_number")
            or None
        ),
        "service":              PACKAGE_DISPLAY.get(context.get("package", ""), context.get("package") or "Not specified"),
        "addons":               _format_addon_display(context.get("addons") or ""),
        "address":              context.get("customer_address") or None,
        "appointment_date":     _format_iso_date(context.get("appointment_date") or "") or "Not specified",
        "appointment_time":     _format_24h_time(context.get("appointment_time") or ""),
        "vehicle":              context.get("vehicle") or "",
        "special_instructions": context.get("special_instructions") or "",
        "deposit_paid":         deposit_paid,
        "balance_due":          balance_due,
        "order_id":             context.get("order_id") or "unknown",
        "cal_url":              context.get("cal_url") or "",
        "waiver_accepted_at":   context.get("waiver") or None,
    }


def _handle_square_webhook(event: dict, body: str) -> dict:
    """Handle incoming Square webhook (payment.updated)."""
    headers  = _normalized_headers(event)
    signature = headers.get("x-square-hmacsha256-signature", "")
    url = (
        (event.get("requestContext") or {})
        .get("domainName", "")
    )
    if url:
        path = (event.get("requestContext") or {}).get("path", "/webhook")
        url = f"https://{url}{path}"

    if SQUARE_WEBHOOK_SIGNATURE_KEY and not _verify_square_signature(body, signature, url):
        _log("ERROR", "square_invalid_signature")
        return _response(400, "Invalid signature")

    try:
        data = json.loads(body)
    except Exception as exc:
        _log("ERROR", "square_parse_error", detail=str(exc))
        return _response(400, "Invalid JSON")

    event_type = data.get("type", "")
    payment    = (data.get("data") or {}).get("object", {}).get("payment", {})
    payment_id = payment.get("id", "unknown")
    order_id   = payment.get("order_id", "unknown")

    _log(
        "INFO",
        "square_webhook_received",
        event_type=event_type,
        payment_id=payment_id,
        order_id=order_id,
    )

    if event_type != "payment.updated":
        _log("INFO", "event_ignored", detail=f"Ignored event type: {event_type}")
        return _response(200, "Ignored")

    payment_status = payment.get("status", "")
    if payment_status != "COMPLETED":
        _log("INFO", "payment_not_completed", status=payment_status)
        return _response(200, "Ignored")

    booking = _extract_square_booking(payment)

    deposit_paid = booking["deposit_paid"]
    balance_due  = (
        booking["balance_due"]
        if booking["balance_due"] is not None
        else _calculate_balance_due(booking["service"], deposit_paid)
    )

    _log(
        "INFO",
        "square_payment_confirmed",
        payment_id=payment_id,
        order_id=order_id,
        deposit_paid=deposit_paid,
        balance_due=balance_due,
        customer_email=booking["customer_email"],
    )

    _mark_booking_confirmed(
        booking_id=order_id,
        square_payment_id=payment_id,
        square_order_id=order_id,
        amount_total_cents=int(deposit_paid * 100),
        detailer_sms_status="pending",
        customer_sms_status="pending",
        customer_name=booking.get("customer_name"),
        customer_phone=booking.get("customer_phone"),
        customer_email=booking.get("customer_email"),
        service=booking.get("service"),
        addons=booking.get("addons"),
        address=booking.get("address"),
        appointment_date=booking.get("appointment_date"),
        deposit_paid=deposit_paid,
        balance_due=balance_due,
        source="square",
        environment=os.environ.get("ENVIRONMENT", "unknown"),
    )

    _log("INFO", "booking_record_persisted",
         booking_id=order_id,
         customer_name=booking["customer_name"],
         service=booking["service"],
         deposit_paid=deposit_paid,
         source="square")

    divider = "\u2500" * 34
    detailer_phone_display = _format_detailer_phone()

    detailer_sms_ok = _send_sms_to_detailers(
        _build_detailer_sms(booking, balance_due, divider)
    )
    detailer_sms_status = "sent" if detailer_sms_ok else "failed"

    customer_sms_status = "skipped"
    if booking["customer_phone"]:
        customer_sms_ok = _send_sms(
            booking["customer_phone"],
            _build_customer_sms(booking, balance_due,
                                detailer_phone_display, divider),
            "customer",
        )
        customer_sms_status = "sent" if customer_sms_ok else "failed"
    else:
        _log("INFO", "customer_sms_skipped",
             detail="no phone in payment note")

    _log("INFO", "booking_processed",
         booking_id=order_id,
         customer_name=booking["customer_name"],
         service=booking["service"],
         deposit_paid=deposit_paid,
         balance_due=balance_due,
         detailer_sms=detailer_sms_status,
         customer_sms=customer_sms_status,
         source="square")

    return _response(200, "Payment confirmed")


# ─── Lambda Handler ─────────────────

def lambda_handler(event, context):
    """
    Routes incoming requests:
    - GET  /complete: detailer mark-complete link (HMAC-signed)
    - Cal.com webhooks: contain triggerEvent field in JSON body
    - Square webhooks: contain x-square-hmacsha256-signature header
    """
    del context

    method = (
        (event.get("requestContext") or {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or ""
    ).upper()
    raw_path = (
        (event.get("requestContext") or {}).get("http", {}).get("path")
        or event.get("rawPath")
        or event.get("path")
        or ""
    )
    if method == "GET" and raw_path.endswith("/complete"):
        return _handle_complete_link(event)

    body = event.get("body", "") or ""
    headers = _normalized_headers(event)

    has_square_sig = "x-square-hmacsha256-signature" in headers
    has_cal_sig    = "x-cal-signature-256" in headers

    is_calcom = has_cal_sig
    if not has_square_sig and not has_cal_sig:
        try:
            parsed = json.loads(body)
            if "triggerEvent" in parsed:
                is_calcom = True
        except Exception:
            pass

    if is_calcom:
        return _handle_calcom_webhook(event, body)

    return _handle_square_webhook(event, body)
