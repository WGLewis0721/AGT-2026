import base64
import json
import os

import stripe
from booking_common import booking_table, get_booking, utc_now_iso


def _log(event_name, **fields):
    payload = {"event": event_name}
    payload.update(fields)
    print(json.dumps(payload))


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _is_non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _parse_body(event):
    if not isinstance(event, dict):
        raise ValueError("event must be an object")

    body = event.get("body", event)
    if body is None:
        raise ValueError("request body is required")

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ValueError("request body must be valid base64-encoded JSON") from exc

    if isinstance(body, str):
        if not body.strip():
            raise ValueError("request body is required")
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc

    if not isinstance(body, dict):
        raise ValueError("request body must be a JSON object")

    return body


def _build_redirect_url(domain_url, status_value, session_token):
    return (
        f"{domain_url}/?checkout={status_value}"
        f"&session_id={session_token}"
    )


def _create_session(booking):
    stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    domain_url = os.environ.get("DOMAIN_URL", "").strip().rstrip("/")

    if not stripe_secret_key or not domain_url:
        raise RuntimeError("stripe configuration is missing")

    stripe.api_key = stripe_secret_key

    pricing = booking.get("pricing") or {}
    deposit = int(pricing.get("deposit") or 0)
    if deposit <= 0:
        raise RuntimeError("booking deposit is invalid")

    booking_id = booking["booking_id"]
    customer = booking.get("customer") or {}
    addon_labels = booking.get("addon_labels") or []
    addon_summary = ", ".join(addon_labels)

    metadata = {
        "booking_id": booking_id,
        "package": booking.get("package", ""),
        "appointment_time": booking.get("appointment_time", ""),
        "address": booking.get("address", ""),
    }
    if addon_summary:
        metadata["addons"] = addon_summary

    session_params = {
        "mode": "payment",
        "client_reference_id": booking_id,
        "payment_method_types": ["card"],
        "phone_number_collection": {"enabled": True},
        "line_items": [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"{booking.get('package_label', 'Detailing')} Deposit",
                        "description": "20% booking deposit collected at checkout.",
                    },
                    "unit_amount": deposit * 100,
                },
                "quantity": 1,
            }
        ],
        "success_url": _build_redirect_url(
            domain_url,
            "success",
            "{CHECKOUT_SESSION_ID}",
        ),
        "cancel_url": _build_redirect_url(
            domain_url,
            "cancelled",
            "{CHECKOUT_SESSION_ID}",
        ),
        "metadata": metadata,
    }
    if customer.get("email"):
        session_params["customer_email"] = customer["email"]

    return stripe.checkout.Session.create(**session_params)


def lambda_handler(event, context):
    del context

    try:
        payload = _parse_body(event)
        booking_id = payload.get("booking_id")

        if not _is_non_empty_string(booking_id):
            _log("create_checkout_session_bad_request", error="booking_id is required")
            return _response(400, {"message": "booking_id is required"})

        booking_id = booking_id.strip()
        booking = get_booking(booking_id)
        if not booking:
            _log("create_checkout_session_not_found", booking_id=booking_id)
            return _response(404, {"message": "booking not found"})

        if booking.get("status") == "confirmed":
            _log("create_checkout_session_conflict", booking_id=booking_id)
            return _response(409, {"message": "booking is already confirmed"})

        session = _create_session(booking)
        now = utc_now_iso()

        booking_table().update_item(
            Key={"booking_id": booking_id},
            UpdateExpression=(
                "SET updated_at = :updated_at, "
                "stripe_checkout_session_id = :session_id, "
                "stripe_checkout_url = :checkout_url, "
                "payment_status = :payment_status"
            ),
            ExpressionAttributeValues={
                ":updated_at": now,
                ":session_id": getattr(session, "id", ""),
                ":checkout_url": session.url,
                ":payment_status": "pending",
            },
        )

        pricing = booking.get("pricing") or {}
        deposit_cents = int(pricing.get("deposit", 0)) * 100
        _log(
            "create_checkout_session_created",
            booking_id=booking_id,
            package=booking.get("package"),
            deposit_cents=deposit_cents,
            checkout_session_id=getattr(session, "id", None),
        )

        return _response(
            200,
            {
                "checkout_url": session.url,
                "booking_id": booking_id,
            },
        )
    except ValueError as exc:
        _log("create_checkout_session_bad_request", error=str(exc))
        return _response(400, {"message": str(exc)})
    except stripe.error.StripeError as exc:
        _log("create_checkout_session_stripe_error", error=str(exc))
        return _response(500, {"message": "stripe checkout session creation failed"})
    except Exception as exc:  # pragma: no cover - Lambda safety net
        _log("create_checkout_session_error", error=str(exc))
        return _response(500, {"message": "internal server error"})
