/**
 * Home.cfspp.js — Homepage for AGT Mobile Detailing.
 *
 * Delivers the app-like "above the fold" experience customers expect from
 * DoorDash or Instacart:
 *  • A prominent hero with a single "Book Now" CTA.
 *  • Quick-select service category tiles that jump straight to the
 *    Book Online page with the relevant category pre-filtered.
 *  • A live "next available" time hint to create urgency.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #bookNowButton      — Primary CTA button in the hero section
 *   #nextAvailableText  — Text element showing next open slot
 *   #serviceCategoryRepeater — Repeater of category cards
 *     Each repeated item should contain:
 *       #categoryImage  — Image
 *       #categoryName   — Text (bound to data field "name")
 *       #categoryPrice  — Text (bound to data field "startingPrice")
 *       #selectCategory — Button / click target
 */

import wixLocation from 'wix-location';

$w.onReady(function () {
    // ── "Book Now" hero button ────────────────────────────────────────────────
    $w('#bookNowButton').onClick(() => {
        wixLocation.to('/book-online');
    });

    // ── Service category quick-select tiles ───────────────────────────────────
    // Each tile navigates to the Book Online page with a ?category= query param
    // so the service list can pre-filter to the tapped category.
    const categories = [
        { id: 'exterior', name: 'Exterior Detail',  startingPrice: 'From $79',  emoji: '🚗' },
        { id: 'interior', name: 'Interior Detail',  startingPrice: 'From $99',  emoji: '🪑' },
        { id: 'full',     name: 'Full Detail',       startingPrice: 'From $149', emoji: '✨' },
        { id: 'premium',  name: 'Premium Package',   startingPrice: 'From $249', emoji: '💎' },
    ];

    if ($w('#serviceCategoryRepeater').length) {
        $w('#serviceCategoryRepeater').data = categories;

        $w('#serviceCategoryRepeater').onItemReady(($item, itemData) => {
            $item('#categoryName').text    = `${itemData.emoji}  ${itemData.name}`;
            $item('#categoryPrice').text   = itemData.startingPrice;
            $item('#selectCategory').onClick(() => {
                wixLocation.to(`/book-online?category=${itemData.id}`);
            });
        });
    }

    // ── Next-available hint (makes the experience feel live / real-time) ──────
    _setNextAvailableText();
});

/**
 * Compute and display the next available booking window.
 * In production this would call getAvailableSlots() from the backend;
 * here we derive a same-day or next-day estimate on the client side.
 */
function _setNextAvailableText() {
    if (!$w('#nextAvailableText').length) return;

    const now  = new Date();
    const hour = now.getHours();

    let hint;
    if (hour < 8) {
        hint = 'Available today from 8:00 AM';
    } else if (hour < 16) {
        // Still slots left today
        const nextHour = hour + 1;
        const ampm     = nextHour < 12 ? 'AM' : 'PM';
        const h12      = nextHour > 12 ? nextHour - 12 : nextHour;
        hint = `Next slot today at ${h12}:00 ${ampm}`;
    } else {
        // After business hours — point to tomorrow
        hint = 'Available tomorrow from 8:00 AM';
    }

    $w('#nextAvailableText').text = `⏱  ${hint}`;
}
