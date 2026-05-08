"""
TRA3 Pricing API — Square Payment Link Creator
Client: A Gentlemen's Touch (AGT) Mobile Detailing
Lambda: tra3-gentlemens-touch-{env}-pricing-api

Receives: POST /create-checkout with package + addon selections
Returns:  { "url": "https://squareup.com/pay/..." }

Security:
  - Server-side price recalculation (never trust browser amounts)
  - CORS restricted to AGT GitHub Pages domain
  - Square Payment Link created with exact deposit amount
  - Metadata carries booking context through Square to SMS Lambda
"""

import json
import os
import uuid
from square.client import Client as SquareClient

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SQUARE_ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQUARE_LOCATION_ID  = os.environ.get("SQUARE_LOCATION_ID", "")
ENVIRONMENT         = os.environ.get("ENVIRONMENT", "dev")
# Supports comma-separated list of allowed origins
# e.g. "https://agt-detailing.com,https://wglewis0721.github.io,http://localhost:5500"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGIN", "https://agt-detailing.com").split(",")
    if o.strip()
]

# Success and cancel URLs — derived from DOMAIN_URL env var so they follow
# the active deployment domain without requiring a code change.
_DOMAIN_URL = os.environ.get("DOMAIN_URL", "https://agt-detailing.com").rstrip("/")
SUCCESS_URL = f"{_DOMAIN_URL}/success.html"
CANCEL_URL  = f"{_DOMAIN_URL}/"

# ─── PRICING TABLE (server-side — source of truth) ───────────────────────────

PACKAGES = {
    "sm_detail": {"name": "Small Vehicle Detail",   "price": 100.00},
    "md_detail": {"name": "Medium Vehicle Detail",  "price": 150.00},
    "lg_detail": {"name": "Large / SUV / Truck",    "price": 200.00},
}

ADDONS = {
    "pet_hair":   {"name": "Pet Hair Removal",       "price": 20.00},
    "shampooing": {"name": "Interior Shampooing",    "price": 15.00},
    "upholstery": {"name": "Upholstery Shampoo",     "price": 15.00},
    "wax":        {"name": "Hand Wax Upgrade",       "price": 20.00},
    "steam":      {"name": "Steam Cleaning",         "price": 10.00},
    "polishing":  {"name": "Machine Polishing",      "price": 20.00},
    "headlights": {"name": "Headlight Restoration",  "price": 15.00},
    "odor":       {"name": "Odor Removal",           "price": 10.00},
    "engine_bay": {"name": "Engine Bay Cleaning",    "price": 15.00},
    "leather":    {"name": "Leather Treatment",      "price": 15.00},
}

DEPOSIT_RATE = 0.20  # 20%

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _response(status_code: int, body: dict, origin: str = "") -> dict:
    """Build API Gateway response with CORS headers.
    Reflects request origin back if it is in the ALLOWED_ORIGINS whitelist.
    Falls back to the first allowed origin if not matched.
    """
    if origin and origin in ALLOWED_ORIGINS:
        allowed = origin
    else:
        allowed = ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": allowed,
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
        "body": json.dumps(body),
    }


def _calculate_price(package_key: str, addon_keys: list) -> dict:
    """
    Server-side price calculation.
    Never trust browser-submitted amounts.
    Returns dict with total, deposit, line items.
    """
    if package_key not in PACKAGES:
        raise ValueError(f"Unknown package: {package_key}")

    pkg         = PACKAGES[package_key]
    pkg_price   = pkg["price"]
    addon_total = 0.0
    addon_names = []
    invalid     = []

    for key in addon_keys:
        if key not in ADDONS:
            invalid.append(key)
            continue
        addon_total += ADDONS[key]["price"]
        addon_names.append(ADDONS[key]["name"])

    if invalid:
        raise ValueError(f"Unknown addon keys: {invalid}")

    total         = round(pkg_price + addon_total, 2)
    deposit       = round(total * DEPOSIT_RATE, 2)
    balance       = round(total - deposit, 2)
    deposit_cents = int(deposit * 100)

    return {
        "package_name":  pkg["name"],
        "package_price": pkg_price,
        "addon_names":   addon_names,
        "addon_total":   addon_total,
        "total":         total,
        "deposit":       deposit,
        "balance":       balance,
        "deposit_cents": deposit_cents,
    }


def _create_square_payment_link(
    price_data: dict,
    package_key: str,
    addon_keys: list,
    cal_url: str,
) -> str:
    """Create Square Payment Link and return checkout URL."""
    client = SquareClient(
        access_token=SQUARE_ACCESS_TOKEN,
        environment="sandbox" if ENVIRONMENT == "dev" else "production",
    )

    addon_desc = (
        ", ".join(price_data["addon_names"])
        if price_data["addon_names"]
        else "No add-ons"
    )

    order_id = str(uuid.uuid4())

    note = "|".join([
        f"package={package_key}",
        f"addons={','.join(addon_keys)}",
        f"total={price_data['total']}",
        f"deposit={price_data['deposit']}",
        f"balance={price_data['balance']}",
        f"cal_url={cal_url}",
        f"order_id={order_id}",
        f"client=gentlemens-touch",
        f"environment={ENVIRONMENT}",
    ])

    result = client.checkout.create_payment_link({
        "idempotency_key": order_id,
        "order": {
            "location_id": SQUARE_LOCATION_ID,
            "line_items": [{
                "name": f"AGT Deposit — {price_data['package_name']}",
                "quantity": "1",
                "note": addon_desc,
                "base_price_money": {
                    "amount": price_data["deposit_cents"],
                    "currency": "USD",
                },
            }],
            "metadata": {
                "order_id":    order_id,
                "environment": ENVIRONMENT,
            },
        },
        "checkout_options": {
            "redirect_url": SUCCESS_URL,
        },
        "payment_note": note,
    })

    if result.is_error():
        raise RuntimeError(f"Square error: {result.errors}")

    return result.body["payment_link"]["url"]


# ─── MAIN HANDLER ─────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    TRA3 Pricing API handler.
    POST /create-checkout → creates Square Payment Link → returns URL
    OPTIONS /create-checkout → CORS preflight
    """
    origin  = (event.get("headers") or {}).get("origin", "")
    method  = event.get("httpMethod") or event.get("requestContext", {}).get(
                "http", {}).get("method", "POST")

    # Handle CORS preflight
    if method == "OPTIONS":
        return _response(200, {}, origin)

    if method != "POST":
        return _response(405, {"error": "Method not allowed"}, origin)

    # Parse request body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON"}, origin)

    package_key = body.get("package", "")
    addon_keys  = body.get("addons", [])
    cal_url     = body.get("cal_url", "")
    # Note: total and deposit from browser are intentionally ignored.
    # Server recalculates both from PACKAGES/ADDONS — never trust browser amounts.

    print(json.dumps({
        "level":   "INFO",
        "event":   "checkout_request_received",
        "package": package_key,
        "addons":  addon_keys,
        "env":     ENVIRONMENT,
    }))

    # Validate inputs
    if not package_key:
        return _response(400, {"error": "package is required"}, origin)

    if not isinstance(addon_keys, list):
        return _response(400, {"error": "addons must be a list"}, origin)

    # Server-side price calculation
    try:
        price_data = _calculate_price(package_key, addon_keys)
    except ValueError as e:
        print(json.dumps({
            "level":  "ERROR",
            "event":  "invalid_selection",
            "detail": str(e),
        }))
        return _response(400, {"error": str(e)}, origin)

    print(json.dumps({
        "level":         "INFO",
        "event":         "price_calculated",
        "package":       package_key,
        "total":         price_data["total"],
        "deposit":       price_data["deposit"],
        "deposit_cents": price_data["deposit_cents"],
    }))

    # Create Square Payment Link
    try:
        checkout_url = _create_square_payment_link(
            price_data, package_key, addon_keys, cal_url
        )
    except RuntimeError as e:
        print(json.dumps({
            "level":  "ERROR",
            "event":  "square_error",
            "detail": str(e),
        }))
        return _response(500, {"error": "Payment system error"}, origin)

    print(json.dumps({
        "level":  "INFO",
        "event":  "payment_link_created",
        "package": package_key,
        "deposit": price_data["deposit"],
    }))

    return _response(200, {"url": checkout_url}, origin)
