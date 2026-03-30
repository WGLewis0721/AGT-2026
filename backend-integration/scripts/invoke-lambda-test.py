#!/usr/bin/env python3
"""
End-to-end test: invoke the deployed Lambda directly with a synthetic Cal.com
BOOKING_PAYMENT_INITIATED event, triggering real SMS delivery.

The script:
  1. Builds a realistic Cal.com test payload
  2. Signs it with HMAC-SHA256 using the Cal.com webhook secret (read from SSM)
  3. Invokes the Lambda function via boto3 (bypasses API Gateway)
  4. Prints the Lambda response

Usage
-----
# Minimal — uses default client/env, pulls all secrets from SSM:
python invoke-lambda-test.py

# Full options:
python invoke-lambda-test.py \
    --client    gentlemens-touch \
    --env       dev \
    --region    us-east-1 \
    --phone     +13340000000       # override customer phone in test payload
    --calcom-secret-param /tra3/gentlemens-touch/dev/calcom_webhook_secret

Note: The Lambda function must already be deployed (run deploy.ps1 first).
      Your AWS credentials must have lambda:InvokeFunction permission.
"""

import argparse
import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone

import boto3


# ─── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_CLIENT = "gentlemens-touch"
DEFAULT_ENV = "dev"
DEFAULT_REGION = "us-east-1"
DEFAULT_CALCOM_SECRET_PARAM_TPL = "/tra3/{client}/{env}/calcom_webhook_secret"

LAMBDA_NAME_TPL = "tra3-{client}-{env}-booking-webhook"


# ─── SSM helpers ───────────────────────────────────────────────────────────────
def _ssm_get(name: str, region: str) -> str:
    ssm = boto3.client("ssm", region_name=region)
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


# ─── Payload builder ───────────────────────────────────────────────────────────
def _build_calcom_payload(customer_phone: str) -> dict:
    """Return a realistic BOOKING_PAYMENT_INITIATED event body."""
    now = datetime.now(timezone.utc)
    appt = now + timedelta(days=7)
    appt_str = appt.strftime("%A, %B %d, %Y at %I:%M %p")

    return {
        "triggerEvent": "BOOKING_PAYMENT_INITIATED",
        "payload": {
            "bookingId": 99999,
            "uid": "test-booking-uid-0000",
            "eventTitle": "mobile-detail-appointment-service-2",
            "startTime": appt.isoformat(),
            "price": 3000,  # cents ($30.00 deposit for MD Detail)
            "currency": "usd",
            "attendees": [
                {
                    "name": "Test Customer",
                    "email": "test@example.com",
                    "timeZone": "America/Chicago",
                }
            ],
            "responses": {
                "name": {"value": "Test Customer"},
                "email": {"value": "test@example.com"},
                "attendeePhoneNumber": {"value": customer_phone},
                "address-of-service": {"value": "123 Test Street, Montgomery AL 36109"},
                "service": {"value": "MD Detail"},
                "add-ons": {"value": ""},
            },
            "additionalNotes": "AGT automated test booking — ignore",
            "startTimeFormatted": appt_str,
        },
    }


# ─── Signature ─────────────────────────────────────────────────────────────────
def _sign(body: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ─── Lambda event wrapper ──────────────────────────────────────────────────────
def _wrap_api_gw_event(body: str, signature: str | None) -> dict:
    """Wrap body in an API Gateway HTTP v2 event so Lambda can parse it normally."""
    headers = {"content-type": "application/json"}
    if signature:
        headers["x-cal-signature-256"] = signature
    return {
        "version": "2.0",
        "routeKey": "POST /webhook",
        "rawPath": "/webhook",
        "headers": headers,
        "body": body,
        "isBase64Encoded": False,
    }


# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoke the deployed AGT Lambda with a synthetic Cal.com test event."
    )
    parser.add_argument("--client", default=DEFAULT_CLIENT,
                        help=f"Client slug (default: {DEFAULT_CLIENT})")
    parser.add_argument("--env", default=DEFAULT_ENV,
                        help=f"Environment: dev | prod (default: {DEFAULT_ENV})")
    parser.add_argument("--region", default=DEFAULT_REGION,
                        help=f"AWS region (default: {DEFAULT_REGION})")
    parser.add_argument("--phone", default="+15550000001",
                        help="Customer phone to embed in the test payload (E.164)")
    parser.add_argument("--calcom-secret-param", metavar="SSM_NAME",
                        help="SSM param name for Cal.com webhook secret "
                             "(omit to skip signature — only works if Lambda has no secret set)")
    args = parser.parse_args()

    function_name = LAMBDA_NAME_TPL.format(client=args.client, env=args.env)
    print(f"[INFO] Target Lambda: {function_name}")

    # 1. Build payload
    payload_dict = _build_calcom_payload(args.phone)
    body = json.dumps(payload_dict, separators=(",", ":"))

    # 2. Sign if secret param provided
    signature = None
    if args.calcom_secret_param:
        print(f"[SSM]  Reading Cal.com secret from {args.calcom_secret_param} …")
        secret = _ssm_get(args.calcom_secret_param, args.region)
        signature = _sign(body, secret)
        print(f"[INFO] Signature generated: {signature[:16]}…")
    else:
        # Try the default SSM path; fall back gracefully if not found
        default_param = DEFAULT_CALCOM_SECRET_PARAM_TPL.format(
            client=args.client, env=args.env
        )
        print(f"[SSM]  Attempting default param {default_param} …")
        try:
            secret = _ssm_get(default_param, args.region)
            signature = _sign(body, secret)
            print(f"[INFO] Signature generated from default param: {signature[:16]}…")
        except Exception as exc:
            print(f"[WARN] Could not read Cal.com secret ({exc}); invoking without signature.")
            print("[WARN] This will succeed only if CALCOM_WEBHOOK_SECRET is empty in Lambda.")

    # 3. Wrap in API Gateway event
    event = _wrap_api_gw_event(body, signature)

    # 4. Invoke Lambda
    print(f"[INVOKE] Calling {function_name} …")
    client = boto3.client("lambda", region_name=args.region)
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode(),
    )

    status_code = response.get("StatusCode")
    payload_bytes = response["Payload"].read()
    try:
        result = json.loads(payload_bytes)
    except Exception:
        result = payload_bytes.decode()

    print(f"\n[RESULT] HTTP status: {status_code}")
    print(f"[RESULT] Lambda response:\n{json.dumps(result, indent=2)}")

    if response.get("FunctionError"):
        print(f"\n[ERROR] Lambda function error: {response['FunctionError']}")
        sys.exit(1)

    lambda_status = result.get("statusCode") if isinstance(result, dict) else None
    if lambda_status and lambda_status >= 400:
        print(f"\n[FAIL]  Lambda returned HTTP {lambda_status}")
        sys.exit(1)

    print("\n[OK] Test invocation complete — check your phone for the SMS.")


if __name__ == "__main__":
    main()
