import base64
import json
import os

import stripe


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


def _get_placeholder_booking(booking_id):
    return {
        "booking_id": booking_id,
        "package": "medium",
        "total": 150,
        "deposit": 30,
    }


def _create_session(booking_id, deposit_cents):
    stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    domain_url = os.environ.get("DOMAIN_URL", "").strip().rstrip("/")

    if not stripe_secret_key or not domain_url:
        raise RuntimeError("stripe configuration is missing")

    stripe.api_key = stripe_secret_key

    return stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Detailing Deposit",
                    },
                    "unit_amount": deposit_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=f"{domain_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{domain_url}/cancel",
        metadata={"booking_id": booking_id},
    )


def lambda_handler(event, context):
    del context

    try:
        payload = _parse_body(event)
        booking_id = payload.get("booking_id")

        if not _is_non_empty_string(booking_id):
            _log("create_checkout_session_bad_request", error="booking_id is required")
            return _response(400, {"message": "booking_id is required"})

        booking_id = booking_id.strip()
        booking = _get_placeholder_booking(booking_id)
        deposit_cents = int(booking["deposit"] * 100)

        session = _create_session(booking_id, deposit_cents)
        _log(
            "create_checkout_session_created",
            booking_id=booking_id,
            package=booking["package"],
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
