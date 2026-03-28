# Prompt 02 — Write Lambda Function
# Tool: GitHub.com Copilot
# Repo: WGLewis0721/AGT-2026
# No AWS calls. No deploys. File writing only.

---

## SCOPE

Write two files:
  backend-integration/lambda/lambda_function.py
  backend-integration/lambda/requirements.txt
  backend-integration/layer/requirements.txt

Replace existing contents of these files entirely.

---

## FILE: lambda/requirements.txt

```
stripe==7.10.0
requests==2.31.0
```

---

## FILE: layer/requirements.txt

```
stripe==7.10.0
requests==2.31.0
```

---

## FILE: lambda/lambda_function.py

Write the complete file exactly as specified below.

### Comment block at top of file (copy verbatim):

```python
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
```

### Imports:

```python
import json
import os
import stripe
import requests
```

### Module-level constants:

```python
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
```

### Helper: _response(status_code, message)

```python
def _response(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message})
    }
```

### Helper: _send_sms(phone, message, recipient_label)

```python
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
```

### Main handler: lambda_handler(event, context)

Implement exactly this order of operations:

**Step 1 — Extract request data:**
```python
body       = event.get("body", "")
sig_header = event.get("headers", {}).get("stripe-signature", "")
stripe.api_key = STRIPE_SECRET_KEY
```

**Step 2 — Verify Stripe signature:**
Use stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
Use bracket access on stripe_event — NOT .get()
On SignatureVerificationError: log + return _response(400, "Invalid signature")
On any other exception: log + return _response(400, "Webhook error")

**Step 3 — Log stripe_webhook_received:**
```python
print(json.dumps({
    "level": "INFO",
    "event": "stripe_webhook_received",
    "stripe_event_id": stripe_event["id"],
    "stripe_event_type": stripe_event["type"],
    "livemode": stripe_event.get("livemode", False),
    "payment_status": stripe_event["data"]["object"].get("payment_status", "unknown"),
    "amount_total": stripe_event["data"]["object"].get("amount_total", 0),
}))
```

**Step 4 — Filter event type:**
If stripe_event["type"] != "checkout.session.completed":
  log ignored event, return _response(200, f"Ignored: {stripe_event['type']}")

**Step 5 — Extract session and customer details:**
```python
session          = stripe_event["data"]["object"]
customer_details = session.get("customer_details") or {}
customer_name    = customer_details.get("name")  or "Unknown"
customer_email   = customer_details.get("email") or "No email"
customer_phone   = customer_details.get("phone") or None
deposit_paid     = (session.get("amount_total") or 0) / 100
```

**Step 6 — Extract custom fields:**
```python
custom_fields = {
    field["key"]: field.get("text", {}).get("value", "Not specified")
    for field in (session.get("custom_fields") or [])
}
service  = custom_fields.get("service",  "Not specified")
date     = custom_fields.get("date",     "Not specified")
location = custom_fields.get("location", "Not specified")
```

**Step 7 — Calculate balance:**
```python
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
```

**Step 8 — Build and send detailer SMS:**

If balance_due is not None:
```
🚗 NEW DETAIL BOOKING
──────────────────────
Name:     {customer_name}
Phone:    {customer_phone or 'No phone'}
Email:    {customer_email}
──────────────────────
Service:  {service}
Date:     {date}
Location: {location}
──────────────────────
Deposit:  ${deposit_paid:.2f}
Balance:  ${balance_due:.2f}
```

If balance_due is None (service not in price map):
Same format but omit the Balance line.

Send via _send_sms(DETAILER_PHONE, sms_body, "detailer")
If returns False: return _response(500, "Detailer SMS failed")

**Step 9 — Build and send customer SMS:**

If customer_phone is None or empty string:
```python
print(json.dumps({"level": "INFO", "event": "customer_sms_skipped", "detail": "no phone on file"}))
customer_sms_status = "skipped"
```

Else build customer SMS:

If balance_due is not None:
```
🚗 Booking Confirmed!
A Gentlemen's Touch
──────────────────────
Hi {customer_name}! Your detail is booked.
──────────────────────
Service:  {service}
Date:     {date}
Location: {location}
──────────────────────
Deposit:  ${deposit_paid:.2f} received
Balance:  ${balance_due:.2f} due after service
──────────────────────
Questions? Call (334) 294-8228
```

If balance_due is None:
Same but replace Balance line with:
"Balance collected after service."

Send via _send_sms(customer_phone, sms_body, "customer")
If returns False: log error, set customer_sms_status = "failed", continue (do NOT return 500)
If returns True: set customer_sms_status = "sent"

**Step 10 — Log booking_processed summary:**
```python
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
```

**Step 11 — Return 200:**
```python
return _response(200, "Booking processed")
```

---

## IMPORTANT RULES

- Use bracket access on stripe_event and stripe_event["data"]["object"]
- Use .get() with fallbacks on session fields (they can be None in test events)
- NEVER include URLs in any SMS body
- NEVER log TEXTBELT_API_KEY, STRIPE_SECRET_KEY, or STRIPE_WEBHOOK_SECRET
- NEVER log full phone numbers
- All print statements must be json.dumps structured logs
- Customer SMS failure must NOT cause a 500 — booking is confirmed, detailer SMS sent
- Detailer SMS failure MUST return 500 — booking notification is critical

---

## VALIDATION

After writing:
  python -m py_compile backend-integration/lambda/lambda_function.py

Report pass or fail.

## DEFINITION OF DONE

- [ ] lambda_function.py written with all 11 steps
- [ ] Comment block with CloudWatch queries at top
- [ ] _response() helper implemented
- [ ] _send_sms() helper implemented
- [ ] SERVICE_PRICES dict at module level
- [ ] Balance calculation correct
- [ ] Detailer SMS has no URLs
- [ ] Customer SMS has no URLs
- [ ] Customer SMS skipped gracefully if no phone
- [ ] Customer SMS failure does not return 500
- [ ] All log events use structured JSON
- [ ] python -m py_compile passes
- [ ] No "rosie" anywhere in the file
- [ ] requirements.txt and layer/requirements.txt written
