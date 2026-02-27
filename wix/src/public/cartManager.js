/**
 * cartManager.js — shared cart state for the mobile detailing booking flow.
 *
 * Uses Wix session storage so the cart persists across pages within a single
 * browsing session but is cleared when the browser tab is closed.
 *
 * Import this module into any page with:
 *   import { getCart, addItem, removeItem, updateQuantity,
 *            clearCart, getCartTotal, getCartCount } from 'public/cartManager';
 */

import { session } from 'wix-storage';

const CART_KEY = 'agt_cart';
const BOOKING_INFO_KEY = 'agt_booking_info';

// ─── Cart helpers ─────────────────────────────────────────────────────────────

/** Return the current cart array from session storage. */
export function getCart() {
    try {
        const raw = session.getItem(CART_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

/** Persist the cart array to session storage. */
function saveCart(cart) {
    session.setItem(CART_KEY, JSON.stringify(cart));
}

/**
 * Add a service item to the cart.
 * @param {{ id: string, name: string, price: number, duration: string, addOns: Array }} item
 */
export function addItem(item) {
    const cart = getCart();
    const existing = cart.find(i => i.id === item.id);
    if (existing) {
        existing.quantity = (existing.quantity || 1) + 1;
    } else {
        cart.push({ ...item, quantity: 1 });
    }
    saveCart(cart);
    return getCart();
}

/**
 * Remove an item from the cart by its id.
 */
export function removeItem(itemId) {
    const cart = getCart().filter(i => i.id !== itemId);
    saveCart(cart);
    return cart;
}

/**
 * Update the quantity of an item. Removes the item if quantity ≤ 0.
 */
export function updateQuantity(itemId, quantity) {
    let cart = getCart();
    if (quantity <= 0) {
        cart = cart.filter(i => i.id !== itemId);
    } else {
        const item = cart.find(i => i.id === itemId);
        if (item) item.quantity = quantity;
    }
    saveCart(cart);
    return cart;
}

/** Empty the cart. */
export function clearCart() {
    session.removeItem(CART_KEY);
}

/** Return the total number of items (sum of quantities). */
export function getCartCount() {
    return getCart().reduce((sum, i) => sum + (i.quantity || 1), 0);
}

/** Return the subtotal price. */
export function getCartTotal() {
    return getCart().reduce((sum, i) => sum + i.price * (i.quantity || 1), 0);
}

/** Return a human-readable price string, e.g. "$149.00". */
export function formatPrice(cents) {
    return `$${Number(cents).toFixed(2)}`;
}

// ─── Booking info helpers ─────────────────────────────────────────────────────

/** Save address / vehicle / contact info collected on the booking form. */
export function saveBookingInfo(info) {
    session.setItem(BOOKING_INFO_KEY, JSON.stringify(info));
}

/** Retrieve previously saved booking info. */
export function getBookingInfo() {
    try {
        const raw = session.getItem(BOOKING_INFO_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
}

/** Clear booking info (e.g. after checkout). */
export function clearBookingInfo() {
    session.removeItem(BOOKING_INFO_KEY);
}
