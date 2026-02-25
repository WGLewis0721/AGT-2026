/**
 * Service Page.zapqr.js — Individual service detail page.
 *
 * Like the item detail modal on DoorDash, this page shows:
 *  • Full service description and an image.
 *  • Optional add-on checkboxes (e.g. engine bay cleaning, odor treatment).
 *  • A quantity stepper.
 *  • A sticky "Add to Order" footer button that reflects the real-time price.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #serviceImage       — Image of the service
 *   #serviceName        — Text: service name
 *   #serviceDescription — Text: full description
 *   #basePrice          — Text: base price
 *   #durationText       — Text: estimated duration
 *   #addOnsRepeater     — Repeater of add-on options
 *     Each item: #addOnName (Text), #addOnPrice (Text), #addOnCheckbox (Checkbox)
 *   #decreaseQty        — Button (−)
 *   #quantityText       — Text showing current quantity
 *   #increaseQty        — Button (+)
 *   #addToOrderButton   — Primary CTA at bottom: "Add 1 to Order • $149.00"
 *   #totalPriceText     — Text showing running total in footer
 */

import wixLocation from 'wix-location';
import { addItem, updateQuantity, getCart,
         getCartCount, formatPrice } from 'public/cartManager';
import { refreshCartBadge } from 'masterPage';

// Add-ons available for any service
const ADD_ONS = [
    { id: 'engine-bay',    name: 'Engine Bay Cleaning',  price: 40 },
    { id: 'odor-elim',     name: 'Odor Elimination',     price: 30 },
    { id: 'headlight-rst', name: 'Headlight Restoration',price: 50 },
    { id: 'tire-dressing', name: 'Tire Shine & Dressing', price: 15 },
    { id: 'pet-hair',      name: 'Pet Hair Removal',      price: 25 },
];

// Page-level state
let quantity        = 1;
let selectedAddOns  = new Set();
let baseServicePrice = 0;
let serviceId        = '';
let serviceName      = '';

// ─── Page ready ───────────────────────────────────────────────────────────────

$w.onReady(function () {
    // Wix Bookings / dataset will populate the service fields automatically
    // when the page is connected to the Bookings dataset. We read the values
    // back from the rendered elements to avoid coupling this code to a specific
    // dataset field mapping.
    const priceEl = $w('#basePrice');
    if (priceEl.length) {
        baseServicePrice = parseFloat(priceEl.text.replace(/[^0-9.]/g, '')) || 0;
    }

    // Retrieve service id and name from query params (passed by Book Online page
    // or the Wix Bookings router: /service-page?serviceId=xxx&name=yyy)
    const q = wixLocation.query;
    serviceId   = q.serviceId || '';
    serviceName = $w('#serviceName').length ? $w('#serviceName').text : q.name || '';

    // Quantity controls
    $w('#decreaseQty').onClick(_decreaseQty);
    $w('#increaseQty').onClick(_increaseQty);

    // Add-on repeater
    if ($w('#addOnsRepeater').length) {
        $w('#addOnsRepeater').data = ADD_ONS;
        $w('#addOnsRepeater').onItemReady(($item, addOn) => {
            $item('#addOnName').text  = addOn.name;
            $item('#addOnPrice').text = `+${formatPrice(addOn.price)}`;

            $item('#addOnCheckbox').onChange(event => {
                if (event.target.checked) {
                    selectedAddOns.add(addOn.id);
                } else {
                    selectedAddOns.delete(addOn.id);
                }
                _updateFooter();
            });
        });
    }

    // "Add to Order" CTA
    $w('#addToOrderButton').onClick(_addToOrder);

    _updateFooter();
});

// ─── Quantity helpers ─────────────────────────────────────────────────────────

function _decreaseQty() {
    if (quantity > 1) {
        quantity--;
        _updateFooter();
    }
}

function _increaseQty() {
    quantity++;
    _updateFooter();
}

// ─── Footer CTA update ────────────────────────────────────────────────────────

function _updateFooter() {
    if ($w('#quantityText').length) {
        $w('#quantityText').text = String(quantity);
    }

    const addOnTotal = [...selectedAddOns].reduce((sum, id) => {
        const ao = ADD_ONS.find(a => a.id === id);
        return sum + (ao ? ao.price : 0);
    }, 0);

    const lineTotal = (baseServicePrice + addOnTotal) * quantity;

    if ($w('#addToOrderButton').length) {
        $w('#addToOrderButton').label =
            `Add ${quantity} to Order  •  ${formatPrice(lineTotal)}`;
    }
    if ($w('#totalPriceText').length) {
        $w('#totalPriceText').text = formatPrice(lineTotal);
    }
}

// ─── Add to cart ──────────────────────────────────────────────────────────────

function _addToOrder() {
    if (!serviceId) return;

    const addOnTotal = [...selectedAddOns].reduce((sum, id) => {
        const ao = ADD_ONS.find(a => a.id === id);
        return sum + (ao ? ao.price : 0);
    }, 0);

    const unitPrice = baseServicePrice + addOnTotal;

    // Add the item; if it already exists, updateQuantity handles merging.
    const cart    = getCart();
    const existing = cart.find(i => i.id === serviceId);
    if (existing) {
        updateQuantity(serviceId, existing.quantity + quantity);
    } else {
        addItem({
            id:       serviceId,
            name:     serviceName,
            price:    unitPrice,
            addOns:   [...selectedAddOns],
        });
        if (quantity > 1) updateQuantity(serviceId, quantity);
    }

    refreshCartBadge();
    wixLocation.to('/cart-page');
}
