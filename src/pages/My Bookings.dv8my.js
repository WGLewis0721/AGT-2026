/**
 * My Bookings.dv8my.js — Customer booking history dashboard.
 *
 * Similar to the "Orders" tab in DoorDash or Instacart:
 *  • A list of all past and upcoming bookings for the logged-in member.
 *  • Each card shows confirmation ID, service names, date/time, status badge.
 *  • "Re-book" shortcut that pre-fills the cart with the same services.
 *  • A "Book New Detail" CTA when there are no bookings or at the top.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #bookingsDataset    — Wix dataset connected to the "Bookings" collection,
 *                         filtered by the current member's email (set in editor).
 *   #bookingsRepeater   — Repeater bound to #bookingsDataset
 *     Each item: #bookingConfirmId (Text), #bookingServices (Text),
 *                #bookingDateTime (Text), #bookingStatus (Text),
 *                #statusBadge (Box), #rebookButton (Button)
 *   #noBookingsMessage  — Box shown when the member has no bookings
 *   #newBookingButton   — Button: navigate to Book Online
 *   #loadingText        — Text: shown while the dataset is loading
 */

import wixLocation from 'wix-location';
import wixUsers from 'wix-users';
import { addItem } from 'public/cartManager';
import { refreshCartBadge } from 'masterPage';

// Status → display label & colour mapping
const STATUS_MAP = {
    confirmed:   { label: '⏳ Upcoming',     color: '#2980B9' },
    completed:   { label: '✅ Completed',    color: '#27AE60' },
    cancelled:   { label: '❌ Cancelled',    color: '#E74C3C' },
    in_progress: { label: '🔧 In Progress',  color: '#F39C12' },
};

$w.onReady(function () {
    // Redirect anonymous visitors to the login page
    if (!wixUsers.currentUser.loggedIn) {
        wixLocation.to('/account/login');
        return;
    }

    if ($w('#newBookingButton').length) {
        $w('#newBookingButton').onClick(() => wixLocation.to('/book-online'));
    }

    // The dataset loads asynchronously; bind the repeater once it is ready.
    if ($w('#bookingsDataset').length) {
        $w('#bookingsDataset').onReady(() => {
            const count = $w('#bookingsDataset').getTotalCount();

            if ($w('#loadingText').length) $w('#loadingText').hide();

            if (count === 0) {
                if ($w('#noBookingsMessage').length) $w('#noBookingsMessage').show();
                if ($w('#bookingsRepeater').length)  $w('#bookingsRepeater').hide();
                return;
            }

            if ($w('#noBookingsMessage').length) $w('#noBookingsMessage').hide();
            if ($w('#bookingsRepeater').length)  $w('#bookingsRepeater').show();

            _bindRepeater();
        });
    }
});

// ─── Repeater binding ─────────────────────────────────────────────────────────

function _bindRepeater() {
    if (!$w('#bookingsRepeater').length) return;

    $w('#bookingsRepeater').onItemReady(($item, booking) => {
        // Confirmation ID
        if ($item('#bookingConfirmId').length) {
            $item('#bookingConfirmId').text = `#${booking.confirmationId || '—'}`;
        }

        // Services list
        if ($item('#bookingServices').length) {
            try {
                const services = JSON.parse(booking.services || '[]');
                $item('#bookingServices').text = services.map(s => s.name).join(', ') || '—';
            } catch {
                $item('#bookingServices').text = '—';
            }
        }

        // Date / time
        if ($item('#bookingDateTime').length) {
            const d = new Date(booking.scheduledDate);
            $item('#bookingDateTime').text = _formatDateTime(d);
        }

        // Status badge
        const statusInfo = STATUS_MAP[booking.status] || { label: booking.status, color: '#888' };
        if ($item('#bookingStatus').length) {
            $item('#bookingStatus').text = statusInfo.label;
        }
        if ($item('#statusBadge').length) {
            $item('#statusBadge').style.backgroundColor = statusInfo.color;
        }

        // "Re-book" — re-adds the same services to the cart
        if ($item('#rebookButton').length) {
            $item('#rebookButton').onClick(() => {
                try {
                    const services = JSON.parse(booking.services || '[]');
                    services.forEach(s => addItem(s));
                    refreshCartBadge();
                    wixLocation.to('/cart-page');
                } catch {
                    wixLocation.to('/book-online');
                }
            });
        }
    });
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function _formatDateTime(date) {
    if (!(date instanceof Date) || isNaN(date)) return '—';
    const months = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'];
    let h   = date.getHours();
    const m = String(date.getMinutes()).padStart(2, '0');
    const ampm = h < 12 ? 'AM' : 'PM';
    if (h === 0) h = 12;
    else if (h > 12) h -= 12;
    return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()} — ${h}:${m} ${ampm}`;
}
