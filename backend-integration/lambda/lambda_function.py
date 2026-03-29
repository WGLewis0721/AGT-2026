import json
import os
import re

import requests
import stripe

# ─────────────────────────────────────────────────────────────
# CloudWatch Logs Insights — AWS Console → CloudWatch → Logs Insights
# Log group: /aws/lambda/tra3-gentlemens-touch-{environment}-booking-webhook
#
# All processed bookings (last 7 days):
# fields @timestamp, @message
# | filter @message like /booking_processed/
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
# ─────────────────────────────────────────────────────────────

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
TEXTBELT_API_KEY = os.environ.get("TEXTBELT_API_KEY")
DETAILER_PHONE = os.environ.get("DETAILER_PHONE")

BUSINESS_PHONE = "(334) 294-8228"

SERVICE_PRICES = {
    "sm detail": 100.00,
    "md detail": 150.00,
    "lg detail": 200.00,
    "small": 100.00,
    "medium": 150.00,
    "large": 200.00,
    "full detail": 150.00,
}


def _sanitize_string(value):
    sanitized = str(value)

    for secret in (
        STRIPE_SECRET_KEY,
        STRIPE_WEBHOOK_SECRET,
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


def _send_textbelt_sms(phone_number, message):
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

    return result


def lambda_handler(event, context):
    del context

    body = event.get("body") or ""
    headers = event.get("headers") or {}
    sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""

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

        try:
            _send_textbelt_sms(DETAILER_PHONE, sms_body_detailer)
            _log("INFO", "detailer_sms_sent")
        except Exception as exc:
            _log("ERROR", "detailer_sms_failed", detail=str(exc))
            return _response(500, "SMS failed")

        sms_body_customer = (
            f"\U0001F697 Booking Confirmed!\n"
            f"A Gentlemen's Touch Mobile Detailing\n"
            f"{divider}\n"
            f"Hi {customer_name}! Your detail is booked.\n"
            f"{divider}\n"
            f"Service:  {service}\n"
            f"Date:     {date}\n"
            f"Location: {location}\n"
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
            try:
                _send_textbelt_sms(customer_phone, sms_body_customer)
                _log("INFO", "customer_sms_sent")
            except Exception as exc:
                _log("ERROR", "customer_sms_failed", detail=str(exc))

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
