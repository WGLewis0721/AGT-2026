/**
 * Book Online.c5pg0.js — Service listing page for AGT Mobile Detailing.
 *
 * Emulates the DoorDash / Instacart menu-browsing experience:
 *  • A horizontally scrollable category pill-bar for quick filtering.
 *  • Service cards in a repeater with price, duration, and an "Add" button.
 *  • Tapping "Add" gives instant visual feedback and updates the cart without
 *    navigating away (just like adding food to a DoorDash order).
 *  • A sticky "View Order" bottom bar appears as soon as the cart is non-empty,
 *    showing the item count and subtotal with a single tap to checkout.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #categoryFilterRepeater — Horizontal repeater for category pills
 *     Each item: #pillLabel (Text), #pillButton (Button)
 *   #servicesRepeater — Repeater for service cards
 *     Each item: #serviceImage (Image), #serviceName (Text),
 *                #serviceDescription (Text), #servicePrice (Text),
 *                #serviceDuration (Text), #addButton (Button),
 *                #itemQtyBox (Box, hidden by default),
 *                #decreaseQty (Button), #itemQtyText (Text), #increaseQty (Button)
 *   #viewOrderBar    — Strip / box at bottom of page (sticky footer)
 *   #viewOrderCount  — Text inside #viewOrderBar showing item count
 *   #viewOrderTotal  — Text inside #viewOrderBar showing subtotal
 *   #viewOrderButton — Button inside #viewOrderBar to proceed to cart
 *   #searchInput     — Optional search text input
 */

import wixLocation from 'wix-location';
import { addItem, removeItem, updateQuantity, getCart,
         getCartCount, getCartTotal, formatPrice } from 'public/cartManager';
import { refreshCartBadge } from 'masterPage';

// ─── Service catalogue (replace with a Wix dataset/collection in production) ──

const ALL_SERVICES = [
    {
        id: 'ext-basic', category: 'exterior',
        name: 'Basic Exterior Wash',
        description: 'Hand wash, rinse, and blow-dry of the full exterior.',
        price: 79, duration: '45 min',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
    {
        id: 'ext-clay', category: 'exterior',
        name: 'Exterior Detail + Clay Bar',
        description: 'Full exterior wash, clay-bar decontamination, and spray wax.',
        price: 129, duration: '1.5 hrs',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
    {
        id: 'int-basic', category: 'interior',
        name: 'Interior Vacuum & Wipe-Down',
        description: 'Full vacuum, dashboard and door-panel wipe-down, glass cleaning.',
        price: 99, duration: '1 hr',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
    {
        id: 'int-deep', category: 'interior',
        name: 'Deep Interior Detail',
        description: 'Steam clean, shampoo carpets/seats, full leather or fabric conditioning.',
        price: 169, duration: '2 hrs',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
    {
        id: 'full-standard', category: 'full',
        name: 'Full Detail',
        description: 'Complete exterior and interior detail — our most popular package.',
        price: 199, duration: '2.5 hrs',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
    {
        id: 'premium-pkg', category: 'premium',
        name: 'Premium Showroom Package',
        description: 'Full detail + paint correction, ceramic coating, and odor elimination.',
        price: 349, duration: '4–5 hrs',
        image: 'https://static.wixstatic.com/media/placeholder.jpg',
    },
];

const CATEGORIES = [
    { id: 'all',      label: 'All Services' },
    { id: 'exterior', label: 'Exterior' },
    { id: 'interior', label: 'Interior' },
    { id: 'full',     label: 'Full Detail' },
    { id: 'premium',  label: 'Premium' },
];

let activeCategory = 'all';
let searchQuery    = '';

// ─── Page ready ───────────────────────────────────────────────────────────────

$w.onReady(function () {
    // Honor ?category= query param from the Home page category tiles.
    const params = wixLocation.query;
    if (params.category) {
        activeCategory = params.category;
    }

    _renderCategoryPills();
    _renderServices();
    _refreshOrderBar();

    // Optional live search
    if ($w('#searchInput').length) {
        $w('#searchInput').onInput(event => {
            searchQuery = event.target.value.toLowerCase().trim();
            _renderServices();
        });
    }
});

// ─── Category pill-bar ─────────────────────────────────────────────────────────

function _renderCategoryPills() {
    if (!$w('#categoryFilterRepeater').length) return;

    $w('#categoryFilterRepeater').data = CATEGORIES;
    $w('#categoryFilterRepeater').onItemReady(($item, cat) => {
        $item('#pillLabel').text = cat.label;
        _updatePillStyle($item, cat.id);

        $item('#pillButton').onClick(() => {
            activeCategory = cat.id;
            _renderCategoryPills(); // re-render to update active style
            _renderServices();
        });
    });
}

function _updatePillStyle($item, catId) {
    // Active pill gets a highlighted style; inactive pills get a muted style.
    // Swap the IDs for the actual styleId / className you use in the editor.
    if (catId === activeCategory) {
        $item('#pillButton').style.backgroundColor = '#1A1A2E';
        $item('#pillLabel').style.color = '#FFFFFF';
    } else {
        $item('#pillButton').style.backgroundColor = '#F0F0F0';
        $item('#pillLabel').style.color = '#1A1A2E';
    }
}

// ─── Service card repeater ────────────────────────────────────────────────────

function _renderServices() {
    if (!$w('#servicesRepeater').length) return;

    const filtered = ALL_SERVICES.filter(s => {
        const catMatch  = activeCategory === 'all' || s.category === activeCategory;
        const textMatch = !searchQuery
            || s.name.toLowerCase().includes(searchQuery)
            || s.description.toLowerCase().includes(searchQuery);
        return catMatch && textMatch;
    });

    $w('#servicesRepeater').data = filtered;
    $w('#servicesRepeater').onItemReady(($item, service) => {
        $item('#serviceName').text        = service.name;
        $item('#serviceDescription').text = service.description;
        $item('#servicePrice').text       = formatPrice(service.price);
        $item('#serviceDuration').text    = `⏱ ${service.duration}`;

        const cartItem = getCart().find(i => i.id === service.id);
        if (cartItem) {
            _showQtyControls($item, cartItem.quantity);
        } else {
            _showAddButton($item);
        }

        // "Add" button — instantly adds to cart with haptic-like feedback
        $item('#addButton').onClick(() => {
            addItem({ id: service.id, name: service.name, price: service.price,
                      duration: service.duration });
            _showQtyControls($item, 1);
            _refreshOrderBar();
            refreshCartBadge();
        });

        // Quantity decrease
        $item('#decreaseQty').onClick(() => {
            const current = getCart().find(i => i.id === service.id);
            const newQty  = current ? current.quantity - 1 : 0;
            if (newQty <= 0) {
                removeItem(service.id);
                _showAddButton($item);
            } else {
                updateQuantity(service.id, newQty);
                $item('#itemQtyText').text = String(newQty);
            }
            _refreshOrderBar();
            refreshCartBadge();
        });

        // Quantity increase
        $item('#increaseQty').onClick(() => {
            const current = getCart().find(i => i.id === service.id);
            const newQty  = current ? current.quantity + 1 : 1;
            updateQuantity(service.id, newQty);
            $item('#itemQtyText').text = String(newQty);
            _refreshOrderBar();
            refreshCartBadge();
        });
    });
}

function _showAddButton($item) {
    $item('#addButton').show();
    $item('#itemQtyBox').hide();
}

function _showQtyControls($item, qty) {
    $item('#addButton').hide();
    $item('#itemQtyBox').show();
    $item('#itemQtyText').text = String(qty);
}

// ─── Sticky "View Order" bottom bar ──────────────────────────────────────────

function _refreshOrderBar() {
    if (!$w('#viewOrderBar').length) return;

    const count = getCartCount();
    if (count === 0) {
        $w('#viewOrderBar').hide();
        return;
    }

    $w('#viewOrderCount').text = `${count} item${count !== 1 ? 's' : ''}`;
    $w('#viewOrderTotal').text = formatPrice(getCartTotal());
    $w('#viewOrderBar').show();

    $w('#viewOrderButton').onClick(() => {
        wixLocation.to('/cart-page');
    });
}
