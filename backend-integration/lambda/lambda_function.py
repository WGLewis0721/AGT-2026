# ─────────────────────────────────────────────────────────────
# TRA3 — Booking Webhook Handler
# A Gentlemen's Touch Mobile Detailing
#
# Flow: Stripe checkout.session.completed
#   → verify signature
#   → parse booking details
#   → calculate balance due
#   → SMS detailer (booking details + balance)
#   → SMS customer (confirmation + balance)
#
# CloudWatch Logs Insights Queries
# Log group: /aws/lambda/tra3-{client}-{env}-booking-webhook
#
# All processed bookings:
# fields @timestamp, @message
# | filter @message like /booking_processed/
# | sort @timestamp desc
# | limit 50
#
# Failed SMS:
# fields @timestamp, @message
# | filter @message like /sms_failed/
# | sort @timestamp desc
#
# All Stripe events received:
# fields @timestamp, @message
# | filter @message like /stripe_webhook_received/
# | sort @timestamp desc
# ─────────────────────────────────────────────────────────────

import json
import os
import stripe
import requests

# Config — read from Lambda environment variables
STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
TEXTBELT_API_KEY      = os.environ.get("TEXTBELT_API_KEY")
DETAILER_PHONE        = os.environ.get("DETAILER_PHONE")
ENVIRONMENT           = os.environ.get("ENVIRONMENT", "prod")

# Service price map — used to calculate balance due
# Keys are matched as substrings of the lowercased service field
SERVICE_PRICES = {
    "sm detail":   100.00,
    "md detail":   150.00,
    "lg detail":   200.00,
    "small":       100.00,
    "medium":      150.00,
    "large":       200.00,
    "full detail": 150.00,
}

BUSINESS_PHONE = "(334) 294-8228"


def _response(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message})
    }


def _send_sms(phone, message, recipient_label):
    """
    Send SMS via Textbelt.
    Returns True on success, False on failure.
    Never raises — caller decides how to handle failure.
    Do NOT include URLs in message — Textbelt blocks them.
    """
    try:
        response = requests.post(
            "https://textbelt.com/text",
            {
                "phone": phone,
                "message": message,
                "key": TEXTBELT_API_KEY
            },
            timeout=10
        )
        result = response.json()
        if result.get("success"):
            print(json.dumps({
                "level": "INFO",
                "event": f"{recipient_label}_sms_sent",
                "detail": f"textId={result.get('textId')} quotaRemaining={result.get('quotaRemaining')}"
            }))
            return True
        else:
            print(json.dumps({
                "level": "ERROR",
                "event": f"{recipient_label}_sms_failed",
                "detail": result.get("error", "unknown error")
            }))
            return False
    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "event": f"{recipient_label}_sms_failed",
            "detail": str(e)
        }))
        return False


def lambda_handler(event, context):
    # Step 1 — Extract request data
    body       = event.get("body", "")
    sig_header = event.get("headers", {}).get("stripe-signature", "")
    stripe.api_key = STRIPE_SECRET_KEY

    # Step 2 — Verify Stripe signature
    try:
        stripe_event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as e:
        print(json.dumps({"level": "ERROR", "event": "signature_verification_failed", "detail": str(e)}))
        return _response(400, "Invalid signature")
    except Exception as e:
        print(json.dumps({"level": "ERROR", "event": "webhook_error", "detail": str(e)}))
        return _response(400, "Webhook error")

    # Step 3 — Log stripe_webhook_received
    print(json.dumps({
        "level": "INFO",
        "event": "stripe_webhook_received",
        "stripe_event_id": stripe_event["id"],
        "stripe_event_type": stripe_event["type"],
        "livemode": stripe_event.get("livemode", False),
        "payment_status": stripe_event["data"]["object"].get("payment_status", "unknown"),
        "amount_total": stripe_event["data"]["object"].get("amount_total", 0),
    }))

    # Step 4 — Filter event type
    if stripe_event["type"] != "checkout.session.completed":
        print(json.dumps({"level": "INFO", "event": "event_ignored", "stripe_event_type": stripe_event["type"]}))
        return _response(200, f"Ignored: {stripe_event['type']}")

    # Step 5 — Extract session and customer details
    session          = stripe_event["data"]["object"]
    customer_details = session.get("customer_details") or {}
    customer_name    = customer_details.get("name")  or "Unknown"
    customer_email   = customer_details.get("email") or "No email"
    customer_phone   = customer_details.get("phone") or None
    deposit_paid     = (session.get("amount_total") or 0) / 100

    # Step 6 — Extract custom fields
    custom_fields = {
        field["key"]: field.get("text", {}).get("value", "Not specified")
        for field in (session.get("custom_fields") or [])
    }
    service  = custom_fields.get("service",  "Not specified")
    date     = custom_fields.get("date",     "Not specified")
    location = custom_fields.get("location", "Not specified")

    # Step 7 — Calculate balance
    service_lower = service.lower()
    full_price = next(
        (price for key, price in SERVICE_PRICES.items() if key in service_lower),
        None
    )
    balance_due = round(full_price - deposit_paid, 2) if full_price else None
    balance_due = max(balance_due, 0) if balance_due is not None else None

    print(json.dumps({
        "level": "INFO",
        "event": "balance_calculated",
        "service": service,
        "deposit_paid": deposit_paid,
        "balance_due": balance_due,
    }))

    # Step 8 — Build and send detailer SMS
    if balance_due is not None:
        detailer_sms = (
            f"\U0001f697 NEW DETAIL BOOKING\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Name:     {customer_name}\n"
            f"Phone:    {customer_phone or 'No phone'}\n"
            f"Email:    {customer_email}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Service:  {service}\n"
            f"Date:     {date}\n"
            f"Location: {location}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Deposit:  ${deposit_paid:.2f}\n"
            f"Balance:  ${balance_due:.2f}"
        )
    else:
        detailer_sms = (
            f"\U0001f697 NEW DETAIL BOOKING\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Name:     {customer_name}\n"
            f"Phone:    {customer_phone or 'No phone'}\n"
            f"Email:    {customer_email}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Service:  {service}\n"
            f"Date:     {date}\n"
            f"Location: {location}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Deposit:  ${deposit_paid:.2f}"
        )

    if not _send_sms(DETAILER_PHONE, detailer_sms, "detailer"):
        return _response(500, "Detailer SMS failed")

    # Step 9 — Build and send customer SMS
    if not customer_phone:
        print(json.dumps({"level": "INFO", "event": "customer_sms_skipped", "detail": "no phone on file"}))
        customer_sms_status = "skipped"
    else:
        if balance_due is not None:
            customer_sms = (
                f"\U0001f697 Booking Confirmed!\n"
                f"A Gentlemen's Touch\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Hi {customer_name}! Your detail is booked.\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Service:  {service}\n"
                f"Date:     {date}\n"
                f"Location: {location}\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Deposit:  ${deposit_paid:.2f} received\n"
                f"Balance:  ${balance_due:.2f} due after service\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Questions? Call {BUSINESS_PHONE}"
            )
        else:
            customer_sms = (
                f"\U0001f697 Booking Confirmed!\n"
                f"A Gentlemen's Touch\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Hi {customer_name}! Your detail is booked.\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Service:  {service}\n"
                f"Date:     {date}\n"
                f"Location: {location}\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Deposit:  ${deposit_paid:.2f} received\n"
                f"Balance collected after service.\n"
                f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                f"Questions? Call {BUSINESS_PHONE}"
            )

        if not _send_sms(customer_phone, customer_sms, "customer"):
            print(json.dumps({"level": "ERROR", "event": "customer_sms_failed", "detail": "SMS delivery failed but booking is confirmed"}))
            customer_sms_status = "failed"
        else:
            customer_sms_status = "sent"

    # Step 10 — Log booking_processed summary
    print(json.dumps({
        "level": "INFO",
        "event": "booking_processed",
        "environment": ENVIRONMENT,
        "customer_name": customer_name,
        "service": service,
        "deposit_paid": deposit_paid,
        "balance_due": balance_due,
        "detailer_sms": "sent",
        "customer_sms": customer_sms_status,
    }))

    # Step 11 — Return 200
    return _response(200, "Booking processed")
