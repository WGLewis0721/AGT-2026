/**
 * Cart Page.u25lg.js — Full cart review page for AGT Mobile Detailing.
 *
 * Mirrors the Instacart / DoorDash cart review screen:
 *  • Every cart item is listed with quantity controls and a remove button.
 *  • A promo-code input field with instant discount feedback.
 *  • Itemised price breakdown (subtotal, discount, estimated tax, total).
 *  • A single prominent "Schedule Your Detail" CTA to advance the flow.
 *  • An "Add More Services" link back to Book Online.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #cartRepeater       — Repeater for cart line items
 *     Each item: #lineItemName (Text), #lineItemQty (Text),
 *                #lineItemPrice (Text), #lineDecreaseBtn (Button),
 *                #lineIncreaseBtn (Button), #lineRemoveBtn (Button)
 *   #promoInput         — TextInput for promo code
 *   #applyPromoButton   — Button to apply promo code
 *   #promoMessage       — Text feedback ("Code applied!" or error)
 *   #subtotalText       — Text: subtotal before discount
 *   #discountText       — Text: discount amount (hidden when 0)
 *   #discountRow        — Box containing discount label + amount (hidden when 0)
 *   #taxText            — Text: estimated tax
 *   #totalText          — Text: grand total
 *   #scheduleButton     — Primary CTA button
 *   #addMoreLink        — Link / Button back to Book Online
 *   #emptyCartMessage   — Shown when cart is empty
 *   #cartContents       — Box wrapping repeater + totals (hidden when empty)
 */

import wixLocation from 'wix-location';
import { getCart, removeItem, updateQuantity,
         getCartTotal, getCartCount, formatPrice } from 'public/cartManager';
import { refreshCartBadge } from 'masterPage';

// Valid promo codes — in production, validate these server-side via a web module.
const PROMO_CODES = {
    'FIRSTDETAIL': 0.15,  // 15 % off
    'SUMMER10':    0.10,  // 10 % off
    'AGT20':       0.20,  // 20 % off
};

const TAX_RATE = 0.08; // 8 % estimated tax

let appliedDiscount = 0; // fraction (e.g. 0.15 for 15 %)

$w.onReady(function () {
    _renderCart();

    // Promo code
    $w('#applyPromoButton').onClick(_applyPromo);

    // CTA — advance to booking form
    $w('#scheduleButton').onClick(() => {
        wixLocation.to('/booking-form');
    });

    // Back to menu
    if ($w('#addMoreLink').length) {
        $w('#addMoreLink').onClick(() => {
            wixLocation.to('/book-online');
        });
    }
});

// ─── Cart rendering ───────────────────────────────────────────────────────────

function _renderCart() {
    const cart  = getCart();
    const count = getCartCount();

    if (count === 0) {
        if ($w('#emptyCartMessage').length) $w('#emptyCartMessage').show();
        if ($w('#cartContents').length)     $w('#cartContents').hide();
        $w('#scheduleButton').disable();
        return;
    }

    if ($w('#emptyCartMessage').length) $w('#emptyCartMessage').hide();
    if ($w('#cartContents').length)     $w('#cartContents').show();
    $w('#scheduleButton').enable();

    if (!$w('#cartRepeater').length) return;

    $w('#cartRepeater').data = cart;
    $w('#cartRepeater').onItemReady(($item, lineItem) => {
        $item('#lineItemName').text  = lineItem.name;
        $item('#lineItemQty').text   = String(lineItem.quantity || 1);
        $item('#lineItemPrice').text = formatPrice(lineItem.price * (lineItem.quantity || 1));

        $item('#lineDecreaseBtn').onClick(() => {
            const newQty = (lineItem.quantity || 1) - 1;
            newQty <= 0 ? removeItem(lineItem.id) : updateQuantity(lineItem.id, newQty);
            refreshCartBadge();
            _renderCart();
        });

        $item('#lineIncreaseBtn').onClick(() => {
            updateQuantity(lineItem.id, (lineItem.quantity || 1) + 1);
            refreshCartBadge();
            _renderCart();
        });

        $item('#lineRemoveBtn').onClick(() => {
            removeItem(lineItem.id);
            refreshCartBadge();
            _renderCart();
        });
    });

    _updateTotals();
}

// ─── Totals breakdown ─────────────────────────────────────────────────────────

function _updateTotals() {
    const subtotal  = getCartTotal();
    const discount  = subtotal * appliedDiscount;
    const taxable   = subtotal - discount;
    const tax       = taxable * TAX_RATE;
    const total     = taxable + tax;

    if ($w('#subtotalText').length)  $w('#subtotalText').text  = formatPrice(subtotal);
    if ($w('#taxText').length)       $w('#taxText').text       = formatPrice(tax);
    if ($w('#totalText').length)     $w('#totalText').text     = formatPrice(total);

    if ($w('#discountRow').length) {
        if (appliedDiscount > 0) {
            $w('#discountRow').show();
            $w('#discountText').text = `-${formatPrice(discount)}`;
        } else {
            $w('#discountRow').hide();
        }
    }
}

// ─── Promo code ───────────────────────────────────────────────────────────────

function _applyPromo() {
    if (!$w('#promoInput').length) return;

    const code = ($w('#promoInput').value || '').trim().toUpperCase();
    const rate  = PROMO_CODES[code];

    if (rate !== undefined) {
        appliedDiscount = rate;
        const pct = Math.round(rate * 100);
        if ($w('#promoMessage').length) {
            $w('#promoMessage').text  = `✅  Code applied — ${pct}% off!`;
            $w('#promoMessage').style.color = '#27AE60';
            $w('#promoMessage').show();
        }
    } else {
        appliedDiscount = 0;
        if ($w('#promoMessage').length) {
            $w('#promoMessage').text  = '❌  Invalid promo code. Please try again.';
            $w('#promoMessage').style.color = '#E74C3C';
            $w('#promoMessage').show();
        }
    }

    _updateTotals();
}
