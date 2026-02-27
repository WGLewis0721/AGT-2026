/**
 * Booking Calendar.s9swq.js — Date and time-slot selection page.
 *
 * Emulates the scheduling picker found in DoorDash scheduled deliveries
 * and service apps like Handy:
 *  • A horizontally scrollable strip of the next 14 days (day + date pills).
 *  • A grid of available time slots that updates instantly when the date changes.
 *  • Unavailable (already-booked) slots are visually greyed out.
 *  • A sticky "Confirm Time" button enabled only when a slot is selected.
 *  • Step 2 of 3 progress indicator.
 *
 * Element IDs expected on this page (configure in the Wix editor):
 *   #stepIndicator      — Text: "Step 2 of 3 — Pick a Time"
 *   #datePillRepeater   — Repeater for the 14-day date strip
 *     Each item: #dayLabel (Text, e.g. "Mon"), #dateLabel (Text, e.g. "Mar 3"),
 *                #datePillButton (Button / Box clickable)
 *   #timeSlotRepeater   — Repeater for available/unavailable time slots
 *     Each item: #timeSlotLabel (Text), #timeSlotButton (Button / Box)
 *   #selectedDateText   — Text showing currently selected date
 *   #confirmTimeButton  — Button to advance to Checkout
 *   #loadingSlotsText   — Text shown while fetching slots
 */

import wixLocation from 'wix-location';
import { session } from 'wix-storage';
import { getAvailableSlots } from 'backend/bookingUtils';

const SESSION_DATE_KEY = 'agt_selected_date';
const SESSION_TIME_KEY = 'agt_selected_time';

const DAY_NAMES  = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const MONTH_ABBR = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'];

let selectedDateStr = '';
let selectedTimeStr = '';

// ─── Page ready ───────────────────────────────────────────────────────────────

$w.onReady(async function () {
    if ($w('#stepIndicator').length) {
        $w('#stepIndicator').text = 'Step 2 of 3 — Pick a Time';
    }

    // Pre-select today's date
    const today = new Date();
    selectedDateStr = _toDateStr(today);

    _renderDateStrip();

    // Restore previous selection if navigating back
    const prevDate = session.getItem(SESSION_DATE_KEY);
    const prevTime = session.getItem(SESSION_TIME_KEY);
    if (prevDate) selectedDateStr = prevDate;
    if (prevTime) selectedTimeStr = prevTime;

    await _loadSlots(selectedDateStr);

    $w('#confirmTimeButton').onClick(_confirmAndContinue);
    _updateConfirmButton();
});

// ─── Date strip ───────────────────────────────────────────────────────────────

function _renderDateStrip() {
    if (!$w('#datePillRepeater').length) return;

    const days = [];
    for (let i = 0; i < 14; i++) {
        const d = new Date();
        d.setDate(d.getDate() + i);
        days.push({
            _id:      _toDateStr(d),
            dayLabel: DAY_NAMES[d.getDay()],
            dateLabel:`${MONTH_ABBR[d.getMonth()]} ${d.getDate()}`,
            dateStr:  _toDateStr(d),
        });
    }

    $w('#datePillRepeater').data = days;
    $w('#datePillRepeater').onItemReady(($item, dayData) => {
        $item('#dayLabel').text  = dayData.dayLabel;
        $item('#dateLabel').text = dayData.dateLabel;
        _updateDatePillStyle($item, dayData.dateStr);

        $item('#datePillButton').onClick(async () => {
            selectedDateStr = dayData.dateStr;
            selectedTimeStr = '';
            _renderDateStrip(); // refresh active styles
            _updateConfirmButton();
            await _loadSlots(selectedDateStr);
        });
    });
}

function _updateDatePillStyle($item, dateStr) {
    const isActive = dateStr === selectedDateStr;
    $item('#datePillButton').style.backgroundColor = isActive ? '#1A1A2E' : '#F0F0F0';
    $item('#dayLabel').style.color  = isActive ? '#FFFFFF' : '#555555';
    $item('#dateLabel').style.color = isActive ? '#FFFFFF' : '#1A1A2E';
}

// ─── Time slot grid ───────────────────────────────────────────────────────────

async function _loadSlots(dateStr) {
    if (!$w('#timeSlotRepeater').length) return;

    if ($w('#loadingSlotsText').length) {
        $w('#loadingSlotsText').show();
        $w('#loadingSlotsText').text = 'Loading available times…';
    }

    if ($w('#selectedDateText').length) {
        const d = new Date(dateStr + 'T12:00:00');
        $w('#selectedDateText').text =
            `${DAY_NAMES[d.getDay()]}, ${MONTH_ABBR[d.getMonth()]} ${d.getDate()}`;
    }

    let available = [];
    try {
        available = await getAvailableSlots(dateStr);
    } catch {
        available = ['08:00','09:00','10:00','11:00','12:00','13:00','14:00','15:00','16:00'];
    }

    if ($w('#loadingSlotsText').length) $w('#loadingSlotsText').hide();

    // All fixed slots so we can show unavailable ones greyed out
    const allSlots = ['08:00','09:00','10:00','11:00','12:00','13:00','14:00','15:00','16:00'];
    const slotData = allSlots.map(t => ({
        _id:       t,
        time:      t,
        available: available.includes(t),
        display:   _to12Hour(t),
    }));

    $w('#timeSlotRepeater').data = slotData;
    $w('#timeSlotRepeater').onItemReady(($item, slot) => {
        $item('#timeSlotLabel').text = slot.display;

        if (!slot.available) {
            $item('#timeSlotButton').disable();
            $item('#timeSlotButton').style.backgroundColor = '#DDDDDD';
            $item('#timeSlotLabel').style.color = '#AAAAAA';
        } else {
            $item('#timeSlotButton').enable();
            const isSelected = slot.time === selectedTimeStr;
            $item('#timeSlotButton').style.backgroundColor = isSelected ? '#1A1A2E' : '#FFFFFF';
            $item('#timeSlotLabel').style.color = isSelected ? '#FFFFFF' : '#1A1A2E';

            $item('#timeSlotButton').onClick(() => {
                selectedTimeStr = slot.time;
                _loadSlots(selectedDateStr); // re-render to update selected style
                _updateConfirmButton();
            });
        }
    });
}

// ─── Confirm button ───────────────────────────────────────────────────────────

function _updateConfirmButton() {
    if (!$w('#confirmTimeButton').length) return;

    if (selectedDateStr && selectedTimeStr) {
        $w('#confirmTimeButton').enable();
        $w('#confirmTimeButton').label =
            `Confirm — ${_to12Hour(selectedTimeStr)}`;
    } else {
        $w('#confirmTimeButton').disable();
        $w('#confirmTimeButton').label = 'Select a time to continue';
    }
}

function _confirmAndContinue() {
    if (!selectedDateStr || !selectedTimeStr) return;
    session.setItem(SESSION_DATE_KEY, selectedDateStr);
    session.setItem(SESSION_TIME_KEY, selectedTimeStr);
    wixLocation.to('/checkout');
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function _toDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function _to12Hour(time24) {
    const [hStr, mStr] = time24.split(':');
    let h = parseInt(hStr, 10);
    const ampm = h < 12 ? 'AM' : 'PM';
    if (h === 0) h = 12;
    else if (h > 12) h -= 12;
    return `${h}:${mStr} ${ampm}`;
}
