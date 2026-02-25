/**
 * Side Cart.o63p3.js — Slide-in cart panel for AGT Mobile Detailing.
 *
 * Behaves like DoorDash's right-side cart drawer:
 *  • Lists every item in the cart with its quantity and line price.
 *  • Inline +/− controls to update quantities without leaving the page.
 *  • Shows a running subtotal at the bottom.
 *  • A single "Proceed to Checkout" button that advances to the cart page.
 *
 * This page is typically rendered as a Wix "Side Panel" lightbox or a
 * fixed-position strip on desktop. On mobile it slides in from the bottom.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #cartItemsRepeater  — Repeater for cart line items
 *     Each item: #itemName (Text), #itemQty (Text), #itemPrice (Text),
 *                #decreaseBtn (Button), #increaseBtn (Button),
 *                #removeBtn   (Button)
 *   #subtotalText       — Text: formatted subtotal
 *   #itemCountText      — Text: "X item(s) in your order"
 *   #checkoutButton     — Button to proceed to Cart Page / Checkout
 *   #emptyCartMessage   — Box/Text shown when cart is empty
 */

import wixLocation from 'wix-location';
import { getCart, removeItem, updateQuantity,
         getCartCount, getCartTotal, formatPrice } from 'public/cartManager';
import { refreshCartBadge } from 'masterPage';

$w.onReady(function () {
    _renderCart();

    $w('#checkoutButton').onClick(() => {
        wixLocation.to('/cart-page');
    });
});

// ─── Render cart ──────────────────────────────────────────────────────────────

function _renderCart() {
    const cart  = getCart();
    const count = getCartCount();

    if (!$w('#cartItemsRepeater').length) return;

    if (count === 0) {
        $w('#cartItemsRepeater').hide();
        $w('#checkoutButton').disable();
        if ($w('#emptyCartMessage').length) $w('#emptyCartMessage').show();
        if ($w('#subtotalText').length)     $w('#subtotalText').text = formatPrice(0);
        if ($w('#itemCountText').length)    $w('#itemCountText').text = 'Your cart is empty';
        return;
    }

    if ($w('#emptyCartMessage').length) $w('#emptyCartMessage').hide();
    $w('#cartItemsRepeater').show();
    $w('#checkoutButton').enable();

    $w('#cartItemsRepeater').data = cart;
    $w('#cartItemsRepeater').onItemReady(($item, lineItem) => {
        $item('#itemName').text  = lineItem.name;
        $item('#itemQty').text   = String(lineItem.quantity || 1);
        $item('#itemPrice').text = formatPrice(lineItem.price * (lineItem.quantity || 1));

        $item('#decreaseBtn').onClick(() => {
            const newQty = (lineItem.quantity || 1) - 1;
            if (newQty <= 0) {
                removeItem(lineItem.id);
            } else {
                updateQuantity(lineItem.id, newQty);
            }
            refreshCartBadge();
            _renderCart();
        });

        $item('#increaseBtn').onClick(() => {
            updateQuantity(lineItem.id, (lineItem.quantity || 1) + 1);
            refreshCartBadge();
            _renderCart();
        });

        $item('#removeBtn').onClick(() => {
            removeItem(lineItem.id);
            refreshCartBadge();
            _renderCart();
        });
    });

    if ($w('#subtotalText').length) {
        $w('#subtotalText').text = formatPrice(getCartTotal());
    }
    if ($w('#itemCountText').length) {
        $w('#itemCountText').text = `${count} item${count !== 1 ? 's' : ''} in your order`;
    }
}
