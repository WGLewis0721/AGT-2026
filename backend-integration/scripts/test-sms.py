#!/usr/bin/env python3
"""
Quick test: send a real SMS via Textbelt using the same credentials as the Lambda.

Usage
-----
# Pull API key + phone from AWS SSM (mirrors Lambda runtime):
python test-sms.py \
    --api-key-param  /tra3/gentlemens-touch/dev/textbelt_api_key \
    --phone-param    /tra3/gentlemens-touch/dev/detailer_phone_number

# Or supply values directly (no AWS needed):
python test-sms.py \
    --api-key  YOUR_TEXTBELT_KEY \
    --phone    +13340000000

Options
-------
--region      AWS region (default: us-east-1)
--message     Override the default test message text
"""

import argparse
import sys

import boto3
import requests


DEFAULT_MESSAGE = (
    "AGT TEST — This is a test SMS from the A Gentlemen's Touch booking system. "
    "If you received this, Textbelt delivery is working correctly."
)


def _get_ssm_value(name: str, region: str) -> str:
    ssm = boto3.client("ssm", region_name=region)
    param = ssm.get_parameter(Name=name, WithDecryption=True)
    return param["Parameter"]["Value"]


def _send_sms(api_key: str, phone: str, message: str) -> dict:
    response = requests.post(
        "https://textbelt.com/text",
        data={"phone": phone, "message": message, "key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a test SMS via Textbelt (mirrors Lambda behavior)."
    )

    # Credential sources — SSM or direct
    cred_group = parser.add_argument_group("credentials (choose one source)")
    cred_group.add_argument("--api-key-param", metavar="SSM_NAME",
                            help="SSM parameter name for Textbelt API key")
    cred_group.add_argument("--phone-param", metavar="SSM_NAME",
                            help="SSM parameter name for detailer phone number")
    cred_group.add_argument("--api-key", metavar="KEY",
                            help="Textbelt API key (direct, no SSM lookup)")
    cred_group.add_argument("--phone", metavar="E164",
                            help="Destination phone in E.164 format, e.g. +13341234567")

    parser.add_argument("--region", default="us-east-1",
                        help="AWS region for SSM lookups (default: us-east-1)")
    parser.add_argument("--message", default=DEFAULT_MESSAGE,
                        help="Override the SMS message body")

    args = parser.parse_args()

    # Resolve API key
    if args.api_key:
        api_key = args.api_key
    elif args.api_key_param:
        print(f"[SSM] Reading API key from {args.api_key_param} …")
        api_key = _get_ssm_value(args.api_key_param, args.region)
    else:
        parser.error("Provide --api-key or --api-key-param")

    # Resolve destination phone
    if args.phone:
        phone = args.phone
    elif args.phone_param:
        print(f"[SSM] Reading phone number from {args.phone_param} …")
        phone = _get_ssm_value(args.phone_param, args.region)
    else:
        parser.error("Provide --phone or --phone-param")

    print(f"[SMS] Sending test message to {phone[:3]}***{phone[-4:]} …")

    result = _send_sms(api_key, phone, args.message)

    if result.get("success"):
        print(f"[OK]  SMS queued — textId={result.get('textId')}")
        sys.exit(0)
    else:
        print(f"[ERR] Textbelt error: {result.get('error')}")
        print(f"      Full response: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
