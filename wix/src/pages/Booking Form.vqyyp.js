/**
 * Booking Form.vqyyp.js — Address, vehicle, and contact info collection.
 *
 * Mirrors the DoorDash delivery-address / Instacart delivery-details screen:
 *  • A "Use My Location" button that auto-fills the address via the browser
 *    Geolocation API.
 *  • Vehicle year / make / model dropdowns for quick selection.
 *  • Contact fields (name, phone, email).
 *  • A special-instructions text area.
 *  • Client-side validation with inline error messages before advancing.
 *  • Progress stepper at the top (Step 1 of 3: Your Details).
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #stepIndicator      — Text: "Step 1 of 3 — Your Details"
 *   #addressInput       — TextInput for service address
 *   #useLocationButton  — Button to auto-detect address
 *   #locationStatusText — Text feedback while geo-locating
 *   #vehicleYear        — Dropdown: vehicle year
 *   #vehicleMake        — Dropdown: vehicle make (Wix Dropdown element)
 *   #vehicleModel       — TextInput: vehicle model
 *   #customerName       — TextInput: full name
 *   #customerPhone      — TextInput: phone number
 *   #customerEmail      — TextInput: email address
 *   #specialNotes       — TextBox: special instructions
 *   #continueButton     — Button to advance to Booking Calendar
 *   #addressError       — Text (hidden): address validation message
 *   #nameError          — Text (hidden): name validation message
 *   #contactError       — Text (hidden): phone/email validation message
 */

import wixLocation from 'wix-location';
import wixWindow from 'wix-window';
import { saveBookingInfo, getBookingInfo } from 'public/cartManager';

const CURRENT_YEAR = new Date().getFullYear();

const VEHICLE_YEARS = Array.from({ length: 30 }, (_, i) => {
    const yr = CURRENT_YEAR - i;
    return { value: String(yr), label: String(yr) };
});

const VEHICLE_MAKES = [
    'Acura','Audi','BMW','Buick','Cadillac','Chevrolet','Chrysler',
    'Dodge','Ford','Genesis','GMC','Honda','Hyundai','Infiniti',
    'Jeep','Kia','Lexus','Lincoln','Mazda','Mercedes-Benz','Nissan',
    'Ram','Subaru','Tesla','Toyota','Volkswagen','Volvo','Other',
].map(m => ({ value: m, label: m }));

$w.onReady(function () {
    // Step indicator
    if ($w('#stepIndicator').length) {
        $w('#stepIndicator').text = 'Step 1 of 3 — Your Details';
    }

    // Pre-fill from session if the user navigated back
    const saved = getBookingInfo();
    if (saved.address  && $w('#addressInput').length)  $w('#addressInput').value  = saved.address;
    if (saved.name     && $w('#customerName').length)  $w('#customerName').value  = saved.name;
    if (saved.phone    && $w('#customerPhone').length) $w('#customerPhone').value = saved.phone;
    if (saved.email    && $w('#customerEmail').length) $w('#customerEmail').value = saved.email;
    if (saved.notes    && $w('#specialNotes').length)  $w('#specialNotes').value  = saved.notes;

    // Populate dropdowns
    if ($w('#vehicleYear').length) $w('#vehicleYear').options = VEHICLE_YEARS;
    if ($w('#vehicleMake').length) $w('#vehicleMake').options = VEHICLE_MAKES;
    if (saved.vehicleYear  && $w('#vehicleYear').length) $w('#vehicleYear').value  = saved.vehicleYear;
    if (saved.vehicleMake  && $w('#vehicleMake').length) $w('#vehicleMake').value  = saved.vehicleMake;
    if (saved.vehicleModel && $w('#vehicleModel').length) $w('#vehicleModel').value = saved.vehicleModel;

    // Geolocation button
    if ($w('#useLocationButton').length) {
        $w('#useLocationButton').onClick(_useMyLocation);
    }

    // Continue button
    $w('#continueButton').onClick(_validateAndContinue);
});

// ─── Geolocation ──────────────────────────────────────────────────────────────

async function _useMyLocation() {
    if (!$w('#locationStatusText').length) return;
    $w('#locationStatusText').text = '📍 Detecting your location…';
    $w('#locationStatusText').show();

    try {
        const position = await wixWindow.getCurrentGeolocation();
        const { latitude, longitude } = position.coords;

        // Reverse-geocode using the browser's built-in method (Wix allows this).
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
        );
        const data = await response.json();
        const address = data.display_name || `${latitude}, ${longitude}`;

        if ($w('#addressInput').length) $w('#addressInput').value = address;
        $w('#locationStatusText').text = '✅ Location detected';
    } catch {
        $w('#locationStatusText').text = '⚠️ Could not detect location. Please enter manually.';
    }
}

// ─── Validation & navigation ──────────────────────────────────────────────────

function _validateAndContinue() {
    let valid = true;

    // Hide previous errors
    ['#addressError', '#nameError', '#contactError'].forEach(id => {
        if ($w(id).length) $w(id).hide();
    });

    const address = $w('#addressInput').length ? ($w('#addressInput').value || '').trim() : '';
    const name    = $w('#customerName').length  ? ($w('#customerName').value  || '').trim() : '';
    const phone   = $w('#customerPhone').length ? ($w('#customerPhone').value || '').trim() : '';
    const email   = $w('#customerEmail').length ? ($w('#customerEmail').value || '').trim() : '';

    if (!address) {
        valid = false;
        if ($w('#addressError').length) {
            $w('#addressError').text = '⚠️ Please enter your service address.';
            $w('#addressError').show();
        }
    }

    if (!name) {
        valid = false;
        if ($w('#nameError').length) {
            $w('#nameError').text = '⚠️ Please enter your full name.';
            $w('#nameError').show();
        }
    }

    if (!phone && !email) {
        valid = false;
        if ($w('#contactError').length) {
            $w('#contactError').text = '⚠️ Please enter a phone number or email address.';
            $w('#contactError').show();
        }
    }

    if (!valid) return;

    saveBookingInfo({
        address,
        name,
        phone,
        email,
        vehicleYear:  $w('#vehicleYear').length  ? $w('#vehicleYear').value  : '',
        vehicleMake:  $w('#vehicleMake').length  ? $w('#vehicleMake').value  : '',
        vehicleModel: $w('#vehicleModel').length ? $w('#vehicleModel').value : '',
        notes:        $w('#specialNotes').length ? $w('#specialNotes').value : '',
    });

    wixLocation.to('/booking-calendar');
}
