/**
 * Checkout.s8k0z.js — Final checkout page for AGT Mobile Detailing.
 *
 * Mirrors the DoorDash / Instacart checkout screen:
 *  • Read-only order summary (services + totals) on the left / top.
 *  • Booking details recap (address, vehicle, date/time) with edit links.
 *  • Payment method selector (card on file, pay on arrival).
 *  • Special instructions carry-over from Booking Form.
 *  • A single "Place Order" button that calls the backend submitBooking() and
 *    redirects to the Thank You page with the confirmation ID.
 *  • Step 3 of 3 progress indicator.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #stepIndicator       — Text: "Step 3 of 3 — Review & Confirm"
 *   #orderSummaryRepeater — Repeater for cart line items (read-only)
 *     Each item: #summaryItemName (Text), #summaryItemQty (Text),
 *                #summaryItemPrice (Text)
 *   #summarySubtotal     — Text
 *   #summaryTax          — Text
 *   #summaryTotal        — Text
 *   #addressDisplay      — Text: service address
 *   #vehicleDisplay      — Text: vehicle info
 *   #dateTimeDisplay     — Text: scheduled date/time
 *   #editDetailsLink     — Button/Link back to Booking Form
 *   #editTimeLink        — Button/Link back to Booking Calendar
 *   #paymentSelector     — RadioButtonGroup: payment method
 *   #specialNotesDisplay — Text: customer notes
 *   #placeOrderButton    — Primary CTA
 *   #loadingSpinner      — Element shown while submitting
 *   #errorMessage        — Text shown if submission fails
 */

import wixLocation from 'wix-location';
import { session } from 'wix-storage';
import { getCart, getCartTotal, clearCart, getBookingInfo,
         clearBookingInfo, formatPrice } from 'public/cartManager';
import { submitBooking } from 'backend/bookingUtils';

const TAX_RATE = 0.08;

$w.onReady(function () {
    if ($w('#stepIndicator').length) {
        $w('#stepIndicator').text = 'Step 3 of 3 — Review & Confirm';
    }

    _renderOrderSummary();
    _renderBookingDetails();

    if ($w('#editDetailsLink').length) {
        $w('#editDetailsLink').onClick(() => wixLocation.to('/booking-form'));
    }
    if ($w('#editTimeLink').length) {
        $w('#editTimeLink').onClick(() => wixLocation.to('/booking-calendar'));
    }

    $w('#placeOrderButton').onClick(_placeOrder);
});

// ─── Order summary ────────────────────────────────────────────────────────────

function _renderOrderSummary() {
    const cart     = getCart();
    const subtotal = getCartTotal();
    const tax      = subtotal * TAX_RATE;
    const total    = subtotal + tax;

    if ($w('#orderSummaryRepeater').length) {
        $w('#orderSummaryRepeater').data = cart;
        $w('#orderSummaryRepeater').onItemReady(($item, line) => {
            $item('#summaryItemName').text  = line.name;
            $item('#summaryItemQty').text   = `x${line.quantity || 1}`;
            $item('#summaryItemPrice').text = formatPrice(line.price * (line.quantity || 1));
        });
    }

    if ($w('#summarySubtotal').length) $w('#summarySubtotal').text = formatPrice(subtotal);
    if ($w('#summaryTax').length)      $w('#summaryTax').text      = formatPrice(tax);
    if ($w('#summaryTotal').length)    $w('#summaryTotal').text    = formatPrice(total);
}

// ─── Booking details recap ────────────────────────────────────────────────────

function _renderBookingDetails() {
    const info      = getBookingInfo();
    const dateStr   = session.getItem('agt_selected_date') || '';
    const timeStr   = session.getItem('agt_selected_time') || '';

    const vehicle = [info.vehicleYear, info.vehicleMake, info.vehicleModel]
        .filter(Boolean).join(' ');

    const dateTime = dateStr && timeStr
        ? `${_formatDate(dateStr)} at ${_to12Hour(timeStr)}`
        : 'Not selected';

    if ($w('#addressDisplay').length)  $w('#addressDisplay').text  = info.address    || '—';
    if ($w('#vehicleDisplay').length)  $w('#vehicleDisplay').text  = vehicle         || '—';
    if ($w('#dateTimeDisplay').length) $w('#dateTimeDisplay').text = dateTime;

    if ($w('#specialNotesDisplay').length) {
        $w('#specialNotesDisplay').text = info.notes || 'None';
    }
}

// ─── Place order ──────────────────────────────────────────────────────────────

async function _placeOrder() {
    $w('#placeOrderButton').disable();
    if ($w('#loadingSpinner').length) $w('#loadingSpinner').show();
    if ($w('#errorMessage').length)   $w('#errorMessage').hide();

    try {
        const info      = getBookingInfo();
        const cart      = getCart();
        const subtotal  = getCartTotal();
        const tax       = subtotal * TAX_RATE;
        const total     = subtotal + tax;
        const dateStr   = session.getItem('agt_selected_date') || '';
        const timeStr   = session.getItem('agt_selected_time') || '';

        const result = await submitBooking({
            cart,
            bookingInfo:  info,
            selectedDate: dateStr,
            selectedTime: timeStr,
            total,
        });

        // Clear session state
        clearCart();
        clearBookingInfo();
        session.removeItem('agt_selected_date');
        session.removeItem('agt_selected_time');

        // Navigate to confirmation page
        wixLocation.to(`/thank-you?confirmationId=${result.confirmationId}`);
    } catch (err) {
        if ($w('#errorMessage').length) {
            $w('#errorMessage').text = '⚠️ Something went wrong. Please try again.';
            $w('#errorMessage').show();
        }
        $w('#placeOrderButton').enable();
        if ($w('#loadingSpinner').length) $w('#loadingSpinner').hide();
    }
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function _to12Hour(time24) {
    const [hStr, mStr] = time24.split(':');
    let h = parseInt(hStr, 10);
    const ampm = h < 12 ? 'AM' : 'PM';
    if (h === 0) h = 12;
    else if (h > 12) h -= 12;
    return `${h}:${mStr} ${ampm}`;
}

function _formatDate(dateStr) {
    const months = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];
    const d = new Date(dateStr + 'T12:00:00');
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}
