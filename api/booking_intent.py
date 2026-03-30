import base64
import json
import uuid
from datetime import datetime, timezone


VALID_PACKAGES = {"small", "medium", "large"}


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


def _normalize_year(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())

    return None


def _is_valid_iso_datetime(value):
    if not _is_non_empty_string(value):
        return False

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validate_payload(payload):
    errors = []

    package = payload.get("package")
    if not _is_non_empty_string(package):
        errors.append("package is required")
    elif package not in VALID_PACKAGES:
        errors.append("package must be one of: small, medium, large")

    addons = payload.get("addons")
    if not isinstance(addons, list):
        errors.append("addons must be an array")

    customer = payload.get("customer")
    if not isinstance(customer, dict):
        errors.append("customer is required")
    else:
        if not _is_non_empty_string(customer.get("name")):
            errors.append("customer.name is required")
        if not _is_non_empty_string(customer.get("phone")):
            errors.append("customer.phone is required")
        email = customer.get("email")
        if email is not None and not _is_non_empty_string(email):
            errors.append("customer.email must be a non-empty string when provided")

    vehicle = payload.get("vehicle")
    if not isinstance(vehicle, dict):
        errors.append("vehicle is required")
    else:
        if _normalize_year(vehicle.get("year")) is None:
            errors.append("vehicle.year is required")
        if not _is_non_empty_string(vehicle.get("make")):
            errors.append("vehicle.make is required")
        if not _is_non_empty_string(vehicle.get("model")):
            errors.append("vehicle.model is required")

    if not _is_non_empty_string(payload.get("address")):
        errors.append("address is required")

    if not _is_valid_iso_datetime(payload.get("appointment_time")):
        errors.append("appointment_time must be a valid ISO string")

    if payload.get("waiver_accepted") is not True:
        errors.append("waiver_accepted must be true")

    return errors


def _build_booking(payload):
    customer = payload["customer"]
    vehicle = payload["vehicle"]

    # Ready to persist once DynamoDB wiring is added.
    return {
        "booking_id": str(uuid.uuid4()),
        "status": "draft",
        "package": payload["package"].strip(),
        "addons": payload["addons"],
        "customer": {
            "name": customer["name"].strip(),
            "phone": customer["phone"].strip(),
            "email": customer.get("email", "").strip(),
        },
        "vehicle": {
            "year": _normalize_year(vehicle["year"]),
            "make": vehicle["make"].strip(),
            "model": vehicle["model"].strip(),
        },
        "address": payload["address"].strip(),
        "appointment_time": payload["appointment_time"],
        "waiver_accepted": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def lambda_handler(event, context):
    del context

    try:
        payload = _parse_body(event)
        errors = _validate_payload(payload)

        if errors:
            _log("booking_intent_validation_failed", errors=errors)
            return _response(
                400,
                {
                    "message": "invalid booking payload",
                    "errors": errors,
                },
            )

        booking = _build_booking(payload)
        _log(
            "booking_intent_created",
            booking_id=booking["booking_id"],
            status=booking["status"],
            package=booking["package"],
            addon_count=len(booking["addons"]),
        )

        return _response(
            200,
            {
                "booking_id": booking["booking_id"],
                "status": booking["status"],
                "message": "booking intent created",
            },
        )
    except ValueError as exc:
        _log("booking_intent_bad_request", error=str(exc))
        return _response(400, {"message": str(exc)})
    except Exception as exc:  # pragma: no cover - Lambda safety net
        _log("booking_intent_error", error=str(exc))
        return _response(500, {"message": "internal server error"})
