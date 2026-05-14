(function () {
  const TEST_MODE = false;

  const REAL_PACKAGES = {
    sm_detail: { name: 'Essential Detail', size: 'Small Vehicle', price: 140 },
    md_detail: { name: 'Signature Detail', size: 'Mid-Size Vehicle', price: 175 },
    lg_detail: { name: 'Executive Detail', size: 'Large / SUV', price: 220 },
  };

  const REAL_ADDONS = {
    pet_hair: { name: 'Pet Hair Removal', price: 30 },
    wax: { name: 'Hand Wax Upgrade', price: 50 },
    odor: { name: 'Odor Elimination', price: 25 },
    engine_bay: { name: 'Engine Bay Clean', price: 40 },
    tire_dressing: { name: 'Tire Dressing', price: 20 },
    headlights: { name: 'Headlight Restore', price: 35 },
    shampooing: { name: 'Interior Shampooing', price: 15 },
    upholstery: { name: 'Upholstery Shampoo', price: 15 },
    steam: { name: 'Steam Cleaning', price: 10 },
    polishing: { name: 'Machine Polishing', price: 20 },
    leather: { name: 'Leather Treatment', price: 15 },
  };

  const TEST_PACKAGES = {
    sm_detail: { name: 'Essential Detail', size: 'Small Vehicle', price: 0.01 },
    md_detail: { name: 'Signature Detail', size: 'Mid-Size Vehicle', price: 0.1 },
    lg_detail: { name: 'Executive Detail', size: 'Large / SUV', price: 1.0 },
  };

  const TEST_ADDONS = Object.fromEntries(
    Object.entries(REAL_ADDONS).map(([k, v]) => [k, { name: v.name, price: 0.01 }])
  );

  const PACKAGES = TEST_MODE ? TEST_PACKAGES : REAL_PACKAGES;
  const ADDONS = TEST_MODE ? TEST_ADDONS : REAL_ADDONS;
  const DEPOSIT_RATE = TEST_MODE ? 1.0 : 0.2;

  const CAL_URLS = {
    sm_detail: 'https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-1',
    md_detail: 'https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-2',
    lg_detail: 'https://cal.com/william-g.-lewis-ai51kb/mobile-detail-appointment-service-3',
  };

  const PRICING_API_URL = 'https://c4eki550u8.execute-api.us-east-1.amazonaws.com/create-checkout';

  let selectedPackage = null;
  let selectedAddons = new Set();
  let pendingCalUrl = '';
  let pendingStripeUrl = '';

  const capturedSlot = {
    appointment_date: '',
    appointment_time: '',
    cal_event_id: '',
    cal_url: '',
  };

  let waiverAgreed = false;
  const TODAY = new Date();
  const TODAY_START = new Date(TODAY.getFullYear(), TODAY.getMonth(), TODAY.getDate());
  let calendarMonth = new Date(TODAY.getFullYear(), TODAY.getMonth(), 1);
  const TIME_SLOTS = [
    { label: '9:00 AM', value: '09:00' },
    { label: '11:00 AM', value: '11:00' },
    { label: '1:00 PM', value: '13:00' },
    { label: '3:00 PM', value: '15:00' },
  ];

  function _isBookingPage() {
    return document.body && document.body.dataset.page === 'booking';
  }

  function _money(value) {
    const n = Number(value);
    return Number.isInteger(n) ? ('$' + n) : ('$' + n.toFixed(2));
  }

  function _formatDateIso(dateObj) {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function _formatLongDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'long', day: 'numeric' });
  }

  function _calcOrder() {
    const pkgPrice = selectedPackage ? PACKAGES[selectedPackage].price : 0;
    const addonTotal = [...selectedAddons].reduce((sum, key) => sum + (ADDONS[key] ? ADDONS[key].price : 0), 0);
    const total = pkgPrice + addonTotal;
    const deposit = TEST_MODE
      ? Math.round(total * DEPOSIT_RATE * 100) / 100
      : Math.round(total * DEPOSIT_RATE);
    const balance = Math.max(0, Math.round((total - deposit) * 100) / 100);
    return { total, deposit, balance };
  }

  function _renderPriceDisplay() {
    document.querySelectorAll('[data-pkg-display]').forEach((el) => {
      const key = el.dataset.pkgDisplay;
      if (PACKAGES[key]) el.textContent = _money(PACKAGES[key].price);
    });

    document.querySelectorAll('.pkg-card[data-pkg] .package-price').forEach((el) => {
      const card = el.closest('.pkg-card');
      if (!card) return;
      const key = card.dataset.pkg;
      if (PACKAGES[key]) el.textContent = _money(PACKAGES[key].price);
    });

    document.querySelectorAll('.addon-pill[data-addon] .addon-pill-price').forEach((el) => {
      const pill = el.closest('.addon-pill');
      if (!pill) return;
      const key = pill.dataset.addon;
      if (ADDONS[key]) el.textContent = '+' + _money(ADDONS[key].price);
    });
  }

  function _renderAddonStates() {
    document.querySelectorAll('.addon-pill[data-addon]').forEach((pill) => {
      const on = selectedAddons.has(pill.dataset.addon);
      pill.classList.toggle('active', on);
      pill.classList.toggle('selected', on);
    });
  }

  function _renderCalendar() {
    if (!_isBookingPage()) return;
    const monthLabel = document.getElementById('calendar-month-label');
    const dayGrid = document.getElementById('calendar-days');
    if (!monthLabel || !dayGrid) return;

    monthLabel.textContent = calendarMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    dayGrid.innerHTML = '';

    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    for (let i = 0; i < firstDay; i += 1) {
      const filler = document.createElement('div');
      filler.className = 'calendar-empty';
      dayGrid.appendChild(filler);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateObj = new Date(year, month, day);
      const iso = _formatDateIso(dateObj);
      const isPast = dateObj < TODAY_START;
      const isToday = iso === _formatDateIso(TODAY_START);
      const isSelected = iso === capturedSlot.appointment_date;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'calendar-day';
      btn.textContent = String(day);

      if (isPast) {
        btn.disabled = true;
        btn.classList.add('past');
      }
      if (isToday) btn.classList.add('today');
      if (isSelected) btn.classList.add('selected');

      btn.addEventListener('click', function () {
        capturedSlot.appointment_date = iso;
        capturedSlot.appointment_time = '';
        capturedSlot.cal_event_id = '';
        _renderCalendar();
        _renderTimeSlots();
        _renderDateConfirmation();
        _renderReview();
        _updateBookingReadiness();
      });

      dayGrid.appendChild(btn);
    }
  }

  function _renderTimeSlots() {
    if (!_isBookingPage()) return;
    const wrap = document.getElementById('time-slot-wrap');
    const grid = document.getElementById('time-slots');
    if (!wrap || !grid) return;

    if (!capturedSlot.appointment_date) {
      wrap.style.display = 'none';
      grid.innerHTML = '';
      return;
    }

    wrap.style.display = 'block';
    grid.innerHTML = '';

    TIME_SLOTS.forEach((slot) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'time-slot-btn';
      btn.textContent = slot.label;
      if (capturedSlot.appointment_time === slot.value) btn.classList.add('selected');

      btn.addEventListener('click', function () {
        capturedSlot.appointment_time = slot.value;
        capturedSlot.cal_event_id = '';
        _renderTimeSlots();
        _renderDateConfirmation();
        _unlockSection('section-package');
        _smoothScrollTo('section-package');
        _renderReview();
        _updateBookingReadiness();
      });

      grid.appendChild(btn);
    });
  }

  function _timeLabelFrom24(value) {
    const match = TIME_SLOTS.find((slot) => slot.value === value);
    return match ? match.label : value;
  }

  function _renderDateConfirmation() {
    if (!_isBookingPage()) return;
    const pill = document.getElementById('date-confirm-pill');
    const pillText = document.getElementById('date-confirm-text');
    if (!pill || !pillText) return;

    if (!capturedSlot.appointment_date || !capturedSlot.appointment_time) {
      pill.hidden = true;
      return;
    }

    const text = `${_formatLongDate(capturedSlot.appointment_date)} at ${_timeLabelFrom24(capturedSlot.appointment_time)}`;
    pillText.textContent = text;
    pill.hidden = false;
  }

  function _renderPackageConfirmation() {
    if (!_isBookingPage()) return;
    const pill = document.getElementById('package-confirm-pill');
    const textEl = document.getElementById('package-confirm-text');
    if (!pill || !textEl) return;

    if (!selectedPackage || !PACKAGES[selectedPackage]) {
      pill.hidden = true;
      return;
    }

    const pkg = PACKAGES[selectedPackage];
    textEl.textContent = `${pkg.name} — ${pkg.size} · ${_money(pkg.price)}`;
    pill.hidden = false;
  }

  function _unlockSection(id) {
    const section = document.getElementById(id);
    if (!section) return;
    section.classList.remove('locked');
    section.classList.add('ready');
  }

  function _smoothScrollTo(id) {
    const el = document.getElementById(id);
    if (!el) return;
    setTimeout(function () {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);
  }

  function _renderReview() {
    if (!_isBookingPage()) return;
    const appointmentValue = document.getElementById('review-appointment');
    const packageValue = document.getElementById('review-package');
    const addonsRow = document.getElementById('review-addons-row');
    const addonsValue = document.getElementById('review-addons');
    const subtotalValue = document.getElementById('review-subtotal');
    const balanceValue = document.getElementById('review-balance');
    const depositValue = document.getElementById('review-deposit');

    const { total, deposit, balance } = _calcOrder();

    if (appointmentValue) {
      appointmentValue.textContent = (capturedSlot.appointment_date && capturedSlot.appointment_time)
        ? `${_formatLongDate(capturedSlot.appointment_date)} at ${_timeLabelFrom24(capturedSlot.appointment_time)}`
        : '—';
    }

    if (packageValue) {
      packageValue.textContent = selectedPackage
        ? `${PACKAGES[selectedPackage].name} (${PACKAGES[selectedPackage].size})`
        : '—';
    }

    if (addonsRow && addonsValue) {
      const addonNames = [...selectedAddons].map((key) => ADDONS[key] && ADDONS[key].name).filter(Boolean);
      if (addonNames.length) {
        addonsRow.hidden = false;
        addonsValue.textContent = addonNames.join(', ');
      } else {
        addonsRow.hidden = true;
        addonsValue.textContent = '';
      }
    }

    if (subtotalValue) subtotalValue.textContent = _money(total);
    if (balanceValue) balanceValue.textContent = _money(balance);
    if (depositValue) depositValue.textContent = _money(deposit);
  }

  function _updateBookingReadiness() {
    const checkoutBtn = document.getElementById('checkout-btn');
    if (!checkoutBtn) return;

    const { deposit } = _calcOrder();

    if (_isBookingPage()) {
      const ready = Boolean(
        selectedPackage &&
        capturedSlot.appointment_date &&
        capturedSlot.appointment_time &&
        waiverAgreed
      );

      checkoutBtn.disabled = !ready;
      checkoutBtn.textContent = ready
        ? `Pay ${_money(deposit)} Deposit — Secure Booking`
        : 'Pay Deposit — Secure Booking';
      return;
    }

    checkoutBtn.disabled = !selectedPackage;
    checkoutBtn.textContent = selectedPackage
      ? `Book Now — Pay ${_money(deposit)} Deposit`
      : 'Select a Package to Continue';
  }

  function selectPackage(key) {
    if (!PACKAGES[key]) return;
    selectedPackage = key;

    document.querySelectorAll('.pkg-card[data-pkg]').forEach((card) => {
      card.classList.toggle('selected', card.dataset.pkg === key);
    });

    const pkgLine = document.getElementById('pkg-line');
    const pkgLineName = document.getElementById('pkg-line-name');
    const pkgLinePrice = document.getElementById('pkg-line-price');
    if (pkgLine) pkgLine.style.display = 'flex';
    if (pkgLineName) pkgLineName.textContent = PACKAGES[key].name;
    if (pkgLinePrice) pkgLinePrice.textContent = _money(PACKAGES[key].price);

    if (_isBookingPage()) {
      _unlockSection('section-review');
      _renderPackageConfirmation();
      _smoothScrollTo('section-review');
    }

    updatePriceSummary();
  }

  function toggleAddon(keyOrEl) {
    if (typeof keyOrEl === 'string') {
      if (!ADDONS[keyOrEl]) return;
      if (selectedAddons.has(keyOrEl)) selectedAddons.delete(keyOrEl);
      else selectedAddons.add(keyOrEl);

      _renderAddonStates();
      updatePriceSummary();
      return;
    }

    if (keyOrEl && keyOrEl.classList) {
      keyOrEl.classList.toggle('selected');
    }
  }

  function updatePriceSummary() {
    const { total, deposit } = _calcOrder();
    const totalEl = document.getElementById('total-amount');
    const depositEl = document.getElementById('deposit-amount');
    const addonLinesEl = document.getElementById('addon-lines');

    if (totalEl) totalEl.textContent = _money(total);
    if (depositEl) depositEl.textContent = _money(deposit);

    if (addonLinesEl) {
      addonLinesEl.innerHTML = [...selectedAddons]
        .filter((key) => ADDONS[key])
        .map((key) => (`
          <div class="summary-line">
            <span>${ADDONS[key].name}</span>
            <span>${_money(ADDONS[key].price)}</span>
          </div>
        `))
        .join('');
    }

    _renderReview();
    _updateBookingReadiness();
  }

  async function initiateCheckout() {
    if (!selectedPackage) return;
    const btn = document.getElementById('checkout-btn');
    const { deposit, total } = _calcOrder();

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Preparing your checkout...';
    }

    try {
      const response = await fetch(PRICING_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          package: selectedPackage,
          addons: [...selectedAddons],
          cal_url: CAL_URLS[selectedPackage] || pendingCalUrl || '',
          client: 'gentlemens-touch',
        }),
      });

      if (!response.ok) throw new Error('Checkout creation failed');

      const data = await response.json();
      const balance = Math.max(0, Math.round((total - deposit) * 100) / 100);

      sessionStorage.setItem('agt_cal_url', CAL_URLS[selectedPackage] || '');
      sessionStorage.setItem('agt_package', selectedPackage);
      sessionStorage.setItem('agt_addons', [...selectedAddons].join(','));
      sessionStorage.setItem('agt_deposit', deposit.toFixed(2));
      sessionStorage.setItem('agt_balance', balance.toFixed(2));

      window.location.href = data.url;
    } catch (err) {
      console.error('Checkout error:', err);
      if (btn) {
        btn.disabled = false;
        btn.textContent = `Book Now — Pay ${_money(deposit)} Deposit`;
      }
      alert('Something went wrong. Please try again or call (334) 294-8228.');
    }
  }

  async function initiateCheckoutWithSlot() {
    if (!selectedPackage) return;
    if (!capturedSlot.appointment_date || !capturedSlot.appointment_time) return;
    if (!waiverAgreed) return;

    const btn = document.getElementById('checkout-btn');
    const { deposit, total } = _calcOrder();

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Preparing your checkout...';
    }

    try {
      capturedSlot.cal_url = CAL_URLS[selectedPackage] || '';

      const response = await fetch(PRICING_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          package: selectedPackage,
          addons: [...selectedAddons],
          cal_url: capturedSlot.cal_url,
          appointment_date: capturedSlot.appointment_date,
          appointment_time: capturedSlot.appointment_time,
          cal_event_id: capturedSlot.cal_event_id || '',
        }),
      });

      if (!response.ok) throw new Error('Checkout creation failed');

      const data = await response.json();
      const balance = Math.max(0, Math.round((total - deposit) * 100) / 100);

      sessionStorage.setItem('agt_cal_url', capturedSlot.cal_url);
      sessionStorage.setItem('agt_package', selectedPackage);
      sessionStorage.setItem('agt_addons', [...selectedAddons].join(','));
      sessionStorage.setItem('agt_deposit', deposit.toFixed(2));
      sessionStorage.setItem('agt_balance', balance.toFixed(2));

      window.location.href = data.url;
    } catch (err) {
      console.error('Checkout error:', err);
      if (btn) {
        btn.disabled = false;
        btn.textContent = `Pay ${_money(deposit)} Deposit — Secure Booking`;
      }
      alert('Something went wrong. Please try again or call (334) 294-8228.');
    }
  }

  function openBookingModal(url, stripeUrl) {
    pendingCalUrl = url || '';
    pendingStripeUrl = stripeUrl || '';
    const modal = document.getElementById('waiver-modal');
    const agreeBtn = document.getElementById('waiver-agree-btn');
    if (modal) modal.classList.add('open');
    if (agreeBtn) agreeBtn.style.display = 'inline-block';
    document.body.style.overflow = 'hidden';
  }

  function openWaiverOnly() {
    pendingCalUrl = '';
    pendingStripeUrl = '';
    const modal = document.getElementById('waiver-modal');
    const agreeBtn = document.getElementById('waiver-agree-btn');
    if (modal) modal.classList.add('open');
    if (agreeBtn) agreeBtn.style.display = 'none';
    document.body.style.overflow = 'hidden';
  }

  function agreeAndBook() {
    closeWaiverModal();
    if (selectedPackage && !_isBookingPage()) {
      initiateCheckout();
    }
  }

  function closeWaiverModal() {
    pendingCalUrl = '';
    pendingStripeUrl = '';
    const modal = document.getElementById('waiver-modal');
    const agreeBtn = document.getElementById('waiver-agree-btn');
    if (modal) modal.classList.remove('open');
    if (agreeBtn) agreeBtn.style.display = 'inline-block';
    document.body.style.overflow = '';
  }

  function _initBookingPage() {
    if (!_isBookingPage()) return;

    const prev = document.getElementById('calendar-prev-btn');
    const next = document.getElementById('calendar-next-btn');
    if (prev) {
      prev.addEventListener('click', function () {
        calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1);
        _renderCalendar();
      });
    }
    if (next) {
      next.addEventListener('click', function () {
        calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1);
        _renderCalendar();
      });
    }

    const waiverRow = document.getElementById('waiver-row');
    const waiverBox = document.getElementById('waiver-checkbox');
    const waiverLink = document.getElementById('waiver-link');

    if (waiverRow && waiverBox) {
      waiverRow.addEventListener('click', function (event) {
        if (event.target === waiverBox) return;
        waiverBox.checked = !waiverBox.checked;
        waiverAgreed = waiverBox.checked;
        _updateBookingReadiness();
      });

      waiverBox.addEventListener('change', function () {
        waiverAgreed = waiverBox.checked;
        _updateBookingReadiness();
      });
    }

    if (waiverLink) {
      waiverLink.addEventListener('click', function (event) {
        event.preventDefault();
        openWaiverOnly();
      });
    }

    const payBtn = document.getElementById('checkout-btn');
    if (payBtn) {
      payBtn.addEventListener('click', function () {
        initiateCheckoutWithSlot();
      });
    }

    _renderCalendar();
    _renderTimeSlots();
    _renderDateConfirmation();
    _renderPackageConfirmation();
    _renderReview();
    _updateBookingReadiness();
  }

  document.addEventListener('DOMContentLoaded', function () {
    _renderPriceDisplay();
    _renderAddonStates();
    updatePriceSummary();

    const modal = document.getElementById('waiver-modal');
    if (modal) {
      modal.addEventListener('click', function (event) {
        if (event.target === modal) closeWaiverModal();
      });
    }

    _initBookingPage();
  });

  window.TEST_MODE = TEST_MODE;
  window.PACKAGES = PACKAGES;
  window.ADDONS = ADDONS;
  window.DEPOSIT_RATE = DEPOSIT_RATE;
  window.CAL_URLS = CAL_URLS;
  window.selectedAddons = selectedAddons;
  window.selectPackage = selectPackage;
  window.toggleAddon = toggleAddon;
  window.updatePriceSummary = updatePriceSummary;
  window.initiateCheckout = initiateCheckout;
  window.initiateCheckoutWithSlot = initiateCheckoutWithSlot;
  window.openBookingModal = openBookingModal;
  window.openWaiverOnly = openWaiverOnly;
  window.agreeAndBook = agreeAndBook;
  window.closeWaiverModal = closeWaiverModal;
})();
