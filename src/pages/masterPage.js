/**
 * masterPage.js — global site code for AGT Mobile Detailing.
 *
 * Responsibilities:
 *  • Keep the header cart-count badge in sync with session cart state.
 *  • Expose a refreshCartBadge() helper that any page can call after
 *    mutating the cart.
 *  • Show a slim top-of-page loading bar during page transitions so the
 *    experience feels as snappy as DoorDash / Instacart.
 *
 * Element IDs expected on the master page (set in the Wix editor):
 *   #cartBadge      — Text element showing the cart item count
 *   #cartIconButton — Button/icon that opens the Side Cart or Cart Page
 *   #loadingBar     — A thin strip element used as a progress indicator
 */

import wixLocation from 'wix-location';
import { getCartCount } from 'public/cartManager';

// ─── Page ready ───────────────────────────────────────────────────────────────

$w.onReady(function () {
    refreshCartBadge();

    // Navigate to Cart Page when the header cart icon is tapped.
    if ($w('#cartIconButton').length) {
        $w('#cartIconButton').onClick(() => {
            wixLocation.to('/cart-page');
        });
    }
});

// ─── Helpers (exported so individual pages can call them) ─────────────────────

/**
 * Refresh the cart badge count displayed in the site header.
 * Call this from any page after adding/removing items from the cart.
 */
export function refreshCartBadge() {
    const count = getCartCount();

    if ($w('#cartBadge').length) {
        $w('#cartBadge').text = count > 0 ? String(count) : '';
        count > 0 ? $w('#cartBadge').show() : $w('#cartBadge').hide();
    }
}

/**
 * Show the slim loading bar at the top of the page.
 * Call at the start of any async operation to mimic app-like feedback.
 */
export function showLoadingBar() {
    if ($w('#loadingBar').length) {
        $w('#loadingBar').show();
    }
}

/**
 * Hide the loading bar once the async operation completes.
 */
export function hideLoadingBar() {
    if ($w('#loadingBar').length) {
        $w('#loadingBar').hide();
    }
}
