import json
import os

import requests
import stripe


STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
TEXTBELT_API_KEY = os.environ.get("TEXTBELT_API_KEY")
DETAILER_PHONE = os.environ.get("DETAILER_PHONE")


def _log(level, event, detail):
    print(json.dumps({"level": level, "event": event, "detail": detail}))


def _response(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message}),
    }


def lambda_handler(event, context):
    del context

    body = event.get("body") or ""
    headers = event.get("headers") or {}
    sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""

    stripe.api_key = STRIPE_SECRET_KEY

    try:
        stripe_event = stripe.Webhook.construct_event(
            body,
            sig_header,
            STRIPE_WEBHOOK_SECRET,
        )
        _log("INFO", "webhook_verified", "Stripe signature verified successfully")
    except stripe.error.SignatureVerificationError as exc:
        _log("ERROR", "signature_verification_failed", str(exc))
        return _response(400, "Invalid signature")
    except Exception as exc:
        _log("ERROR", "webhook_verification_failed", str(exc))
        return _response(400, "Webhook error")

    try:
        if stripe_event["type"] != "checkout.session.completed":
            _log("INFO", "event_ignored", f"Ignored event type: {stripe_event['type']}")
            return _response(200, "Ignored")

        session = stripe_event["data"]["object"]
        customer_details = (
            session["customer_details"]
            if "customer_details" in session and session["customer_details"]
            else {}
        )
        customer_name = (
            customer_details["name"]
            if "name" in customer_details and customer_details["name"]
            else "Unknown"
        )
        customer_email = (
            customer_details["email"]
            if "email" in customer_details and customer_details["email"]
            else "No email"
        )
        customer_phone = (
            customer_details["phone"]
            if "phone" in customer_details and customer_details["phone"]
            else "No phone"
        )
        amount_total = (
            session["amount_total"]
            if "amount_total" in session and session["amount_total"]
            else 0
        )
        amount_paid = amount_total / 100

        custom_fields = {
            field["key"]: (
                field["text"]["value"]
                if "text" in field and field["text"] and "value" in field["text"]
                else "Not specified"
            )
            for field in (
                session["custom_fields"]
                if "custom_fields" in session and session["custom_fields"]
                else []
            )
            if "key" in field
        }
        service = custom_fields["service"] if "service" in custom_fields else "Not specified"
        date = custom_fields["date"] if "date" in custom_fields else "Not specified"
        location = custom_fields["location"] if "location" in custom_fields else "Not specified"
        divider = "\u2500" * 22

        sms_body = (
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
            f"Paid:     ${amount_paid:.2f}"
        )

        try:
            response = requests.post(
                "https://textbelt.com/text",
                {
                    "phone": DETAILER_PHONE,
                    "message": sms_body,
                    "key": TEXTBELT_API_KEY,
                },
                timeout=30,
            )
            result = response.json()

            if result.get("success"):
                detail = (
                    f"textId: {result.get('textId', 'unknown')} "
                    f"quotaRemaining: {result.get('quotaRemaining', 'unknown')}"
                )
                _log("INFO", "sms_sent", detail)
                return _response(200, "SMS sent")

            error_message = result.get("error", "Textbelt send failed")
            _log("ERROR", "sms_failed", error_message)
            return _response(500, "SMS failed")
        except Exception as exc:
            _log("ERROR", "textbelt_exception", str(exc))
            return _response(500, str(exc))
    except Exception as exc:
        _log("ERROR", "webhook_processing_failed", str(exc))
        return _response(500, "Webhook processing failed")
