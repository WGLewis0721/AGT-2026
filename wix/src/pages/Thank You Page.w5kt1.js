/**
 * Thank You Page.w5kt1.js — Booking confirmation page for AGT Mobile Detailing.
 *
 * Mirrors the DoorDash order-confirmation / live-tracking screen:
 *  • A large animated checkmark and "Booking Confirmed!" headline.
 *  • Booking confirmation number prominently displayed.
 *  • Order summary (services, address, vehicle, scheduled time).
 *  • A live-updating progress tracker that moves through four stages:
 *      Confirmed → Technician Assigned → En Route → Detail In Progress
 *    (stages auto-advance on a timer to simulate real-time feedback during
 *    the current session; in production you would poll a status field).
 *  • "Add to Calendar" CTA (opens device calendar via deep-link).
 *  • "Book Another" link back to Book Online.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #confirmationBadge   — Box / strip: animated success badge
 *   #confirmationId      — Text: booking confirmation number
 *   #summaryAddress      — Text: service address
 *   #summaryVehicle      — Text: vehicle info
 *   #summaryDateTime     — Text: scheduled date & time
 *   #summaryServices     — Text: comma-joined list of booked services
 *   #trackerRepeater     — Repeater for the 4 progress steps
 *     Each item: #trackerIcon (Text/Image), #trackerLabel (Text),
 *                #trackerLine (Box: connector line after step)
 *   #addToCalendarButton — Button: deep-link to device calendar
 *   #bookAnotherButton   — Button: navigate back to Book Online
 */

import wixLocation from 'wix-location';
import { getBooking } from 'backend/bookingUtils';

const TRACKER_STEPS = [
    { id: 'confirmed',   label: 'Booking Confirmed',     icon: '✅' },
    { id: 'assigned',    label: 'Technician Assigned',   icon: '🧑‍🔧' },
    { id: 'en_route',    label: 'Technician En Route',   icon: '🚐' },
    { id: 'in_progress', label: 'Detail In Progress',    icon: '✨' },
];

let activeStepIndex = 0; // 0 = Confirmed (always the starting state)

$w.onReady(async function () {
    const params         = wixLocation.query;
    const confirmationId = params.confirmationId || '';

    // Display confirmation details
    if ($w('#confirmationId').length) {
        $w('#confirmationId').text = confirmationId
            ? `Confirmation #${confirmationId}`
            : 'Booking Confirmed!';
    }

    // Load full booking details from the backend
    if (confirmationId) {
        try {
            const booking = await getBooking(confirmationId);
            if (booking) {
                _populateBookingSummary(booking);
            }
        } catch {
            // Non-critical: summary may not render if backend unavailable
        }
    }

    // Render the initial tracker state
    _renderTracker();

    // Simulate live progress updates (demo mode — replace with real polling)
    _startProgressSimulation();

    // "Add to Calendar" button
    if ($w('#addToCalendarButton').length) {
        $w('#addToCalendarButton').onClick(_addToCalendar);
    }

    // "Book Another" button
    if ($w('#bookAnotherButton').length) {
        $w('#bookAnotherButton').onClick(() => {
            wixLocation.to('/book-online');
        });
    }
});

// ─── Booking summary ──────────────────────────────────────────────────────────

function _populateBookingSummary(booking) {
    if ($w('#summaryAddress').length) {
        $w('#summaryAddress').text = booking.address || '—';
    }
    if ($w('#summaryVehicle').length) {
        $w('#summaryVehicle').text = booking.vehicleInfo || '—';
    }
    if ($w('#summaryDateTime').length) {
        const d = new Date(booking.scheduledDate);
        $w('#summaryDateTime').text = _formatDateTime(d);
    }
    if ($w('#summaryServices').length) {
        try {
            const services = JSON.parse(booking.services || '[]');
            $w('#summaryServices').text = services.map(s => s.name).join(', ') || '—';
        } catch {
            $w('#summaryServices').text = '—';
        }
    }
}

// ─── Progress tracker ─────────────────────────────────────────────────────────

function _renderTracker() {
    if (!$w('#trackerRepeater').length) return;

    $w('#trackerRepeater').data = TRACKER_STEPS;
    $w('#trackerRepeater').onItemReady(($item, step, index) => {
        $item('#trackerIcon').text  = step.icon;
        $item('#trackerLabel').text = step.label;

        const isCompleted = index < activeStepIndex;
        const isActive    = index === activeStepIndex;

        $item('#trackerIcon').style.opacity  = isCompleted || isActive ? '1' : '0.3';
        $item('#trackerLabel').style.opacity = isCompleted || isActive ? '1' : '0.3';
        $item('#trackerLabel').style.fontWeight = isActive ? 'bold' : 'normal';

        // Colour the connector line between steps
        if ($item('#trackerLine').length) {
            $item('#trackerLine').style.backgroundColor =
                isCompleted ? '#27AE60' : '#DDDDDD';
        }
    });
}

/**
 * Simulate live tracker advancement so the page feels dynamic on the day of
 * the appointment. Replace this with a real-time poll or push update in prod.
 */
function _startProgressSimulation() {
    // Advance the tracker at fixed intervals (for demo: every 8 seconds).
    const interval = setInterval(() => {
        if (activeStepIndex < TRACKER_STEPS.length - 1) {
            activeStepIndex++;
            _renderTracker();
        } else {
            clearInterval(interval);
        }
    }, 8000);
}

// ─── Add to calendar ──────────────────────────────────────────────────────────

function _addToCalendar() {
    // Build a basic Google Calendar deep-link; the user can also use other
    // calendar apps — this is the most universally accessible approach.
    const title    = encodeURIComponent('AGT Mobile Detailing Appointment');
    const details  = encodeURIComponent('Your mobile detailing appointment is confirmed. See you soon!');
    const url      = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&details=${details}`;
    wixLocation.to(url);
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function _formatDateTime(date) {
    const months = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];
    const days   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    let h   = date.getHours();
    const m = String(date.getMinutes()).padStart(2, '0');
    const ampm = h < 12 ? 'AM' : 'PM';
    if (h === 0) h = 12;
    else if (h > 12) h -= 12;
    return `${days[date.getDay()]}, ${months[date.getMonth()]} ${date.getDate()} at ${h}:${m} ${ampm}`;
}
