/**
 * Cloudflare Worker: Cal.com -> Airtable -> SMS/Email notifications
 *
 * Endpoint: POST /webhooks/cal
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true, service: "agt-booking-worker" }, 200);
    }

    if (request.method !== "POST" || url.pathname !== "/webhooks/cal") {
      return json({ error: "Not found" }, 404);
    }

    const rawBody = await request.text();

    const verified = await verifyCalSignature(request.headers, rawBody, env);
    if (!verified) {
      return json({ error: "Invalid Cal.com signature" }, 401);
    }

    const payload = JSON.parse(rawBody);
    const eventType = getEventType(payload);

    if (!SUPPORTED_EVENTS.has(eventType)) {
      return json({ ok: true, skipped: eventType || "unknown_event" });
    }

    const record = mapCalPayload(payload, eventType);
    const airtableRecord = await upsertAirtableRecord(record, env);

    const message = formatSmsMessage(record);
    const emailHtml = formatEmailHtml(record);

    const [smsResult, emailResult] = await Promise.allSettled([
      sendSms(message, env),
      sendEmail(record, emailHtml, env),
    ]);

    return json({
      ok: true,
      eventType,
      airtableRecordId: airtableRecord?.id ?? null,
      sms: summarizeResult(smsResult),
      email: summarizeResult(emailResult),
    });
  },
};

const SUPPORTED_EVENTS = new Set(["BOOKING_CREATED", "BOOKING_RESCHEDULED", "BOOKING_CANCELLED"]);

function summarizeResult(result) {
  if (result.status === "fulfilled") return { ok: true, value: result.value };
  return { ok: false, error: String(result.reason) };
}

function getEventType(payload) {
  return (
    payload?.triggerEvent ||
    payload?.eventType ||
    payload?.type ||
    payload?.event ||
    payload?.payload?.triggerEvent ||
    payload?.payload?.eventType ||
    ""
  );
}

function mapCalPayload(payload, eventType) {
  const root = payload?.payload || payload?.data || payload || {};
  const booking = root?.booking || root;

  const attendees = booking?.attendees || root?.attendees || [];
  const firstAttendee = Array.isArray(attendees) && attendees.length > 0 ? attendees[0] : {};

  const customerName =
    firstAttendee?.name ||
    booking?.name ||
    root?.name ||
    booking?.responses?.name ||
    "Unknown";

  const customerEmail =
    firstAttendee?.email ||
    booking?.email ||
    root?.email ||
    booking?.responses?.email ||
    "";

  const customerPhone =
    firstAttendee?.phone ||
    booking?.responses?.phone ||
    booking?.phone ||
    root?.phone ||
    "";

  const serviceName =
    booking?.title ||
    booking?.eventType?.title ||
    booking?.eventType?.name ||
    root?.title ||
    "Detailing Appointment";

  const startTimeUtc = booking?.startTime || booking?.start || root?.startTime || root?.start || "";
  const endTimeUtc = booking?.endTime || booking?.end || root?.endTime || root?.end || "";

  const location =
    booking?.location ||
    booking?.metadata?.location ||
    booking?.responses?.address ||
    booking?.meetingUrl ||
    "";

  const notes = flattenNotes(booking, root);

  return {
    bookingStatus: toBookingStatus(eventType),
    eventType,
    provider: "Cal.com",
    externalBookingId: String(booking?.id || root?.id || ""),
    eventTypeId: String(booking?.eventTypeId || booking?.eventType?.id || ""),
    customerName,
    customerEmail,
    customerPhone,
    startTimeUtc,
    endTimeUtc,
    timezone: booking?.timeZone || root?.timeZone || "UTC",
    serviceName,
    location,
    notes,
    createdAt: new Date().toISOString(),
  };
}

function toBookingStatus(eventType) {
  if (eventType === "BOOKING_CANCELLED") return "Cancelled";
  if (eventType === "BOOKING_RESCHEDULED") return "Rescheduled";
  return "Scheduled";
}

function flattenNotes(booking, root) {
  const chunks = [];

  if (booking?.responses && typeof booking.responses === "object") {
    for (const [key, value] of Object.entries(booking.responses)) {
      if (value !== null && value !== undefined && String(value).trim() !== "") {
        chunks.push(`${key}: ${String(value)}`);
      }
    }
  }

  if (Array.isArray(booking?.metadata?.addons) && booking.metadata.addons.length > 0) {
    chunks.push(`addons: ${booking.metadata.addons.join(", ")}`);
  }

  if (chunks.length === 0 && root && typeof root === "object") {
    const fallback = safeJson(root);
    if (fallback) chunks.push(`payload: ${fallback.slice(0, 800)}`);
  }

  return chunks.join(" | ");
}

function safeJson(value) {
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

async function upsertAirtableRecord(record, env) {
  const endpoint = `https://api.airtable.com/v0/${env.AIRTABLE_BASE_ID}/${encodeURIComponent(env.AIRTABLE_TABLE_NAME)}`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.AIRTABLE_PAT}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      records: [
        {
          fields: {
            "Booking Status": record.bookingStatus,
            Provider: record.provider,
            "Event Type": record.eventType,
            "External Booking ID": record.externalBookingId,
            "Event Type ID": record.eventTypeId,
            "Customer Name": record.customerName,
            "Customer Email": record.customerEmail,
            "Customer Phone": record.customerPhone,
            "Start Time (UTC)": record.startTimeUtc,
            "End Time (UTC)": record.endTimeUtc,
            Timezone: record.timezone,
            Service: record.serviceName,
            Location: record.location,
            Notes: record.notes,
            "Created At": record.createdAt,
          },
        },
      ],
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Airtable write failed (${response.status}): ${body}`);
  }

  const jsonResponse = await response.json();
  return jsonResponse.records?.[0];
}

function formatSmsMessage(record) {
  return [
    `🚘 AGT ${record.bookingStatus.toUpperCase()}`,
    `${record.customerName} (${record.customerPhone || "No phone"})`,
    `${record.serviceName}`,
    `Start: ${record.startTimeUtc || "N/A"}`,
    `Location: ${record.location || "Not provided"}`,
    `Email: ${record.customerEmail || "N/A"}`,
    record.notes ? `Notes: ${record.notes}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

function formatEmailHtml(record) {
  return `
    <h2>🚘 AGT Booking ${escapeHtml(record.bookingStatus)}</h2>
    <table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse; font-family:Arial,sans-serif;">
      <tr><th align="left">Provider</th><td>${escapeHtml(record.provider)}</td></tr>
      <tr><th align="left">Event Type</th><td>${escapeHtml(record.eventType)}</td></tr>
      <tr><th align="left">Booking ID</th><td>${escapeHtml(record.externalBookingId || "N/A")}</td></tr>
      <tr><th align="left">Customer</th><td>${escapeHtml(record.customerName)}</td></tr>
      <tr><th align="left">Email</th><td>${escapeHtml(record.customerEmail)}</td></tr>
      <tr><th align="left">Phone</th><td>${escapeHtml(record.customerPhone || "N/A")}</td></tr>
      <tr><th align="left">Service</th><td>${escapeHtml(record.serviceName)}</td></tr>
      <tr><th align="left">Start (UTC)</th><td>${escapeHtml(record.startTimeUtc || "N/A")}</td></tr>
      <tr><th align="left">End (UTC)</th><td>${escapeHtml(record.endTimeUtc || "N/A")}</td></tr>
      <tr><th align="left">Timezone</th><td>${escapeHtml(record.timezone || "N/A")}</td></tr>
      <tr><th align="left">Location</th><td>${escapeHtml(record.location || "N/A")}</td></tr>
      <tr><th align="left">Notes</th><td>${escapeHtml(record.notes || "N/A")}</td></tr>
    </table>
  `;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function sendSms(message, env) {
  if (!env.TWILIO_ACCOUNT_SID || !env.TWILIO_AUTH_TOKEN || !env.TWILIO_FROM || !env.LEAD_DETAILER_PHONE) {
    return "SMS disabled: missing Twilio env vars";
  }

  const endpoint = `https://api.twilio.com/2010-04-01/Accounts/${env.TWILIO_ACCOUNT_SID}/Messages.json`;
  const auth = btoa(`${env.TWILIO_ACCOUNT_SID}:${env.TWILIO_AUTH_TOKEN}`);
  const body = new URLSearchParams({
    From: env.TWILIO_FROM,
    To: env.LEAD_DETAILER_PHONE,
    Body: message,
  });

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Twilio failed (${response.status}): ${error}`);
  }

  const jsonResponse = await response.json();
  return jsonResponse.sid;
}

async function sendEmail(record, html, env) {
  if (!env.RESEND_API_KEY || !env.NOTIFY_EMAIL_TO || !env.NOTIFY_EMAIL_FROM) {
    return "Email disabled: missing Resend env vars";
  }

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: env.NOTIFY_EMAIL_FROM,
      to: [env.NOTIFY_EMAIL_TO],
      subject: `[${record.bookingStatus}] ${record.customerName} · ${record.serviceName}`,
      html,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Resend failed (${response.status}): ${error}`);
  }

  const jsonResponse = await response.json();
  return jsonResponse.id;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function verifyCalSignature(headers, rawBody, env) {
  const secret = env.CALCOM_WEBHOOK_SECRET;
  const allowUnsigned = env.ALLOW_UNSIGNED_WEBHOOKS === "true";

  if (!secret) return allowUnsigned;

  const headerValue =
    headers.get("x-cal-signature-256") ||
    headers.get("x-cal-signature") ||
    headers.get("x-webhook-signature") ||
    "";

  if (!headerValue) return false;

  const provided = normalizeSignature(headerValue);
  const computed = await hmacSha256Hex(secret, rawBody);
  return timingSafeEqual(computed, provided);
}

function normalizeSignature(headerValue) {
  // Accept either "sha256=<hex>" or "<hex>"
  const trimmed = headerValue.trim();
  if (trimmed.startsWith("sha256=")) return trimmed.slice(7);
  return trimmed;
}

async function hmacSha256Hex(secret, rawBody) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const digest = await crypto.subtle.sign("HMAC", key, encoder.encode(rawBody));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i += 1) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}
