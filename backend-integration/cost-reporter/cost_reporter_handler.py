import json
import os
from datetime import date, timedelta

import boto3


COST_EXPLORER = boto3.client("ce", region_name="us-east-1")
SNS = boto3.client("sns")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
REPORT_SCOPE = os.environ.get("REPORT_SCOPE", "unknown")
CREDIT_FILTER = {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit"]}}


def _log(event_name, **fields):
    payload = {"event": event_name}
    payload.update(fields)
    print(json.dumps(payload))


def _cost_amount(start_date, end_date, granularity, filter_expression=None):
    request = {
        "TimePeriod": {
            "Start": start_date.isoformat(),
            "End": end_date.isoformat(),
        },
        "Granularity": granularity,
        "Metrics": ["UnblendedCost"],
    }
    if filter_expression:
        request["Filter"] = filter_expression

    result = COST_EXPLORER.get_cost_and_usage(**request)
    results = result.get("ResultsByTime") or []
    if not results:
        return 0.0

    amount = results[0]["Total"]["UnblendedCost"]["Amount"]
    return float(amount)


def _net_amount(cost_amount, credit_amount):
    return cost_amount + credit_amount if credit_amount <= 0 else cost_amount - credit_amount


def _report_message(today, yesterday_cost, yesterday_credit, month_cost, month_credit):
    yesterday_net = _net_amount(yesterday_cost, yesterday_credit)
    month_net = _net_amount(month_cost, month_credit)

    return "\n".join(
        [
            f"AGT AWS cost report for {REPORT_SCOPE}",
            "",
            f"Generated: {today.isoformat()} UTC",
            "",
            f"Yesterday cost: ${yesterday_cost:.2f}",
            f"Yesterday credits applied: ${abs(yesterday_credit):.2f}",
            f"Yesterday net: ${yesterday_net:.2f}",
            "",
            f"Month-to-date cost: ${month_cost:.2f}",
            f"Month-to-date credits applied: ${abs(month_credit):.2f}",
            f"Month-to-date net: ${month_net:.2f}",
        ]
    )


def _setup_error_message(error_text):
    return "\n".join(
        [
            f"AGT AWS cost report for {REPORT_SCOPE}",
            "",
            "Daily billing email is configured, but Cost Explorer access is not ready yet.",
            "Enable IAM access to Billing and Cost Management / Cost Explorer, then invoke again.",
            "",
            f"Last error: {error_text}",
        ]
    )


def lambda_handler(event, context):
    del event
    del context

    subject = f"AGT AWS Cost Report - {REPORT_SCOPE}"
    try:
        today = date.today()
        yesterday = today - timedelta(days=1)
        month_start = today.replace(day=1)

        yesterday_cost = _cost_amount(yesterday, today, "DAILY")
        yesterday_credit = _cost_amount(yesterday, today, "DAILY", CREDIT_FILTER)
        month_cost = _cost_amount(month_start, today, "MONTHLY")
        month_credit = _cost_amount(month_start, today, "MONTHLY", CREDIT_FILTER)
        message = _report_message(
            today,
            yesterday_cost,
            yesterday_credit,
            month_cost,
            month_credit,
        )
        status = "ok"
        event_name = "cost_report_sent"
        log_fields = {
            "report_scope": REPORT_SCOPE,
            "month_cost": month_cost,
            "month_credit": month_credit,
        }
    except Exception as exc:
        message = _setup_error_message(str(exc))
        status = "degraded"
        event_name = "cost_report_failed"
        subject = f"AGT AWS Cost Report Setup Required - {REPORT_SCOPE}"
        log_fields = {
            "report_scope": REPORT_SCOPE,
            "error": str(exc),
        }

    response = SNS.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
    _log(event_name, message_id=response["MessageId"], **log_fields)
    return {"status": status, "message_id": response["MessageId"]}
