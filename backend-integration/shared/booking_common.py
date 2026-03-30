import os
from datetime import datetime, timezone

import boto3


PACKAGE_CATALOG = {
    "small": {
        "label": "Small Vehicle Detail",
        "price": 100,
        "deposit": 20,
    },
    "medium": {
        "label": "Medium Vehicle Detail",
        "price": 150,
        "deposit": 30,
    },
    "large": {
        "label": "Large Vehicle Detail",
        "price": 200,
        "deposit": 40,
    },
}

ADDON_CATALOG = {
    "engine_bay": {
        "label": "Engine Bay Cleaning",
        "price": 40,
    },
    "odor_elim": {
        "label": "Odor Elimination",
        "price": 30,
    },
    "headlight_rst": {
        "label": "Headlight Restoration",
        "price": 50,
    },
    "tire_dressing": {
        "label": "Tire Shine & Dressing",
        "price": 15,
    },
    "pet_hair": {
        "label": "Pet Hair Removal",
        "price": 25,
    },
}

ADDON_ALIASES = {
    "engine-bay": "engine_bay",
    "engine bay": "engine_bay",
    "engine_bay_cleaning": "engine_bay",
    "odor-elim": "odor_elim",
    "odor elim": "odor_elim",
    "odor_elimination": "odor_elim",
    "headlight-rst": "headlight_rst",
    "headlight rst": "headlight_rst",
    "headlight_restoration": "headlight_rst",
    "tire-dressing": "tire_dressing",
    "tire dressing": "tire_dressing",
    "tire_shine": "tire_dressing",
    "pet-hair": "pet_hair",
    "pet hair": "pet_hair",
    "pet_hair_removal": "pet_hair",
}

_DYNAMODB_RESOURCE = None


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_package(value):
    package = str(value or "").strip().lower()
    if package not in PACKAGE_CATALOG:
        raise ValueError("package must be one of: small, medium, large")
    return package


def normalize_addons(values):
    if not isinstance(values, list):
        raise ValueError("addons must be an array")

    normalized = []
    seen = set()

    for value in values:
        addon_text = str(value or "").strip()
        if not addon_text:
            raise ValueError("addons must contain non-empty strings")

        addon_key = addon_text.lower().replace("-", "_").replace(" ", "_")
        addon_key = ADDON_ALIASES.get(addon_key, addon_key)
        if addon_key not in ADDON_CATALOG:
            raise ValueError(f"unsupported addon: {addon_text}")

        if addon_key in seen:
            continue

        seen.add(addon_key)
        normalized.append(addon_key)

    return normalized


def format_addons(addon_ids):
    labels = [ADDON_CATALOG[addon_id]["label"] for addon_id in addon_ids if addon_id in ADDON_CATALOG]
    return ", ".join(labels)


def pricing_for(package_name, addon_ids):
    package_key = normalize_package(package_name)
    addon_keys = normalize_addons(addon_ids)

    package_config = PACKAGE_CATALOG[package_key]
    addon_total = sum(ADDON_CATALOG[addon_id]["price"] for addon_id in addon_keys)
    total = package_config["price"] + addon_total
    deposit = package_config["deposit"]

    return {
        "package": package_key,
        "package_label": package_config["label"],
        "package_total": package_config["price"],
        "addon_total": addon_total,
        "total": total,
        "deposit": deposit,
        "balance_due": max(total - deposit, 0),
        "addon_labels": [ADDON_CATALOG[addon_id]["label"] for addon_id in addon_keys],
    }


def booking_table():
    global _DYNAMODB_RESOURCE

    table_name = os.environ.get("BOOKING_TABLE", "").strip()
    if not table_name:
        raise RuntimeError("BOOKING_TABLE is not configured")

    if _DYNAMODB_RESOURCE is None:
        _DYNAMODB_RESOURCE = boto3.resource("dynamodb")

    return _DYNAMODB_RESOURCE.Table(table_name)


def get_booking(booking_id):
    response = booking_table().get_item(Key={"booking_id": booking_id})
    return response.get("Item")
