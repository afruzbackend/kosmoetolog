/* Navbat olish: xizmat -> shifokor -> kun va soat -> ma'lumot */
(function () {
  const { T, money, escapeHtml } = window.Site;
  const $ = (id) => document.getElementById(id);
  const services = JSON.parse($("servicesData").textContent);
  const preselect = JSON.parse($("preselect").textContent);
  const info = JSON.parse($("siteInfo").textContent);

  const state = { service: null, doctor: null, date: null, time: null, month: null, category: "" };
  const panes = [...document.querySelectorAll("[data-pane]")];
  const steps = [...$("stepper").children];
  let current = 1;

  function go(step) {
    current = step;
    panes.forEach((pane) => { pane.hidden = Number(pane.dataset.pane) !== step; });
    steps.forEach((li, i) => {
      li.classList.toggle("is-active", i + 1 === step);
      li.classList.toggle("is-done", i + 1 < step);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const pad = (n) => String(n).padStart(2, "0");
  const dateLabel = (iso) => {
    const [y, m, d] = iso.split("-").map(Number);
    return `${d} ${T.months[m - 1]} ${y}`;
  };

  function renderSummary() {
    $("sumService").textContent = state.service ? state.service.name : "—";
    $("sumDoctor").textContent = state.doctor ? state.doctor.name : "—";
    $("sumDate").textContent = state.date ? dateLabel(state.date) : "—";
    $("sumTime").textContent = state.time || "—";
    $("sumPrice").textContent = state.service ? `${money(state.service.price)} ${T.sum}` : "—";
  }

  function renderServices() {
    const wantedDoctor = Number(preselect.doctor) || null;
    const rows = services.filter((s) => (!state.category || String(s.category) === state.category)
      && (!wantedDoctor || s.doctors.includes(wantedDoctor)));
    $("serviceList").innerHTML = rows.map((s) => `
      <button class="pick${state.service && state.service.id === s.id ? " is-active" : ""}" type="button" data-id="${s.id}">
        <img src="${escapeHtml(s.image)}" alt="">
        <span><b>${escapeHtml(s.name)}</b><small>${escapeHtml(s.short)}</small><em>${money(s.price)} ${T.sum}</em></span>
      </button>`).join("");
  }

  $("bookCats").addEventListener("click", (event) => {
    const pill = event.target.closest("[data-cat]");
    if (!pill) return;
    state.category = pill.dataset.cat;
    [...$("bookCats").children].forEach((c) => c.classList.toggle("is-active", c === pill));
    renderServices();
  });

  $("serviceList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-id]");
    if (button) chooseService(Number(button.dataset.id), preselect.doctor);
  });

  async function chooseService(id, doctorId) {
    state.service = services.find((s) => s.id === id) || null;
    if (!state.service) return;
    state.doctor = null;
    state.date = state.time = null;
    renderSummary();
    renderServices();
    const response = await fetch(`/api/doctors/?service=${id}`);
    const { doctors } = await response.json();
    state.doctors = doctors;
    const wanted = doctors.find((d) => String(d.id) === String(doctorId));
    if (wanted || doctors.length === 1) {
      chooseDoctor(wanted || doctors[0]);
      return;
    }
    $("doctorList").innerHTML = doctors.map((d) => `
      <button class="pick pick--doc" type="button" data-id="${d.id}">
        <img src="${escapeHtml(d.image)}" alt="">
        <span><b>${escapeHtml(d.name)}</b><small>${escapeHtml(d.specialty)}</small>
        <em>${d.next ? `${T.next_free}: ${dateLabel(d.next.date)}, ${d.next.time}` : T.no_free}</em></span>
      </button>`).join("");
    go(2);
  }

  $("doctorList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-id]");
    if (button) chooseDoctor(state.doctors.find((d) => d.id === Number(button.dataset.id)));
  });

  function chooseDoctor(doctor) {
    state.doctor = doctor;
    state.date = state.time = null;
    const start = doctor.next ? doctor.next.date : new Date().toISOString().slice(0, 10);
    const [y, m] = start.split("-").map(Number);
    state.month = { y, m };
    renderSummary();
    go(3);
    loadMonth().then(() => { if (doctor.next) pickDate(doctor.next.date); });
  }

  async function loadMonth() {
    const { y, m } = state.month;
    $("calTitle").textContent = `${T.months[m - 1]} ${y}`;
    const response = await fetch(`/api/month/?doctor=${state.doctor.id}&month=${y}-${pad(m)}`);
    const { days } = await response.json();
    const offset = (new Date(y, m - 1, 1).getDay() + 6) % 7;
    let html = "<span></span>".repeat(offset);
    Object.entries(days).forEach(([iso, status]) => {
      const n = Number(iso.slice(8));
      const disabled = status !== "free" ? "disabled" : "";
      const active = state.date === iso ? " is-active" : "";
      html += `<button class="day day--${status}${active}" type="button" data-date="${iso}" ${disabled}>${n}</button>`;
    });
    $("calDays").innerHTML = html;
    const now = new Date();
    $("calPrev").disabled = y === now.getFullYear() && m === now.getMonth() + 1;
  }

  $("calPrev").addEventListener("click", () => {
    const { y, m } = state.month;
    state.month = m === 1 ? { y: y - 1, m: 12 } : { y, m: m - 1 };
    loadMonth();
  });
  $("calNext").addEventListener("click", () => {
    const { y, m } = state.month;
    state.month = m === 12 ? { y: y + 1, m: 1 } : { y, m: m + 1 };
    loadMonth();
  });
  $("calDays").addEventListener("click", (event) => {
    const button = event.target.closest("[data-date]");
    if (button && !button.disabled) pickDate(button.dataset.date);
  });

  async function pickDate(iso) {
    state.date = iso;
    state.time = null;
    $("timeNext").disabled = true;
    document.querySelectorAll(".day").forEach((d) => d.classList.toggle("is-active", d.dataset.date === iso));
    renderSummary();
    $("slotsTitle").textContent = dateLabel(iso);
    const response = await fetch(`/api/slots/?doctor=${state.doctor.id}&date=${iso}`);
    const { slots } = await response.json();
    $("slotGrid").innerHTML = slots.length
      ? slots.map((s) => `<button class="slot" type="button" data-time="${s.time}" ${s.free ? "" : "disabled"}>${s.time}</button>`).join("")
      : `<p class="muted">${T.no_slots}</p>`;
  }

  $("slotGrid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-time]");
    if (!button || button.disabled) return;
    state.time = button.dataset.time;
    document.querySelectorAll(".slot").forEach((s) => s.classList.toggle("is-active", s === button));
    $("timeNext").disabled = false;
    renderSummary();
  });

  $("timeNext").addEventListener("click", () => go(4));

  document.querySelectorAll("[data-back]").forEach((button) => button.addEventListener("click", () => {
    const hasChoice = state.doctors && state.doctors.length > 1;
    go(current === 3 && !hasChoice ? 1 : current - 1);
  }));

  function showError(text) {
    const box = $("bookError");
    box.textContent = text;
    box.hidden = false;
  }

  function calendarLink(data) {
    const stamp = (iso, time) => iso.replace(/-/g, "") + "T" + time.replace(":", "") + "00";
    const params = new URLSearchParams({
      action: "TEMPLATE",
      text: `${state.service.name} — ${info.name}`,
      dates: `${stamp(data.date, data.time)}/${stamp(data.date, data.end)}`,
      details: `${state.doctor.name}. ${T.booking_code}: ${data.code}`,
      location: info.address,
      ctz: "Asia/Tashkent",
    });
    return `https://calendar.google.com/calendar/render?${params}`;
  }

  $("bookForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    $("bookError").hidden = true;
    if (form.name.value.trim().length < 2) {
      form.name.classList.add("is-invalid");
      form.name.focus();
      showError(T.err_bad_name);
      return;
    }
    if (!window.Masks.phoneComplete(form.phone.value)) {
      form.phone.classList.add("is-invalid");
      form.phone.focus();
      showError(T.err_bad_phone);
      return;
    }
    const submit = $("bookSubmit");
    submit.disabled = true;
    try {
      const response = await fetch("/api/book/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": $("csrf").value },
        body: JSON.stringify({
          service: state.service.id, doctor: state.doctor.id, date: state.date, time: state.time,
          name: form.name.value, phone: form.phone.value, note: form.note.value, website: form.website.value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || T.err_network);
        if (data.code === "slot_taken") {
          state.time = null;
          renderSummary();
          await loadMonth();
          await pickDate(state.date);
          go(3);
        }
        return;
      }
      $("doneCode").textContent = data.code;
      $("doneCalendar").href = calendarLink(data);
      $("summary").hidden = true;
      go(5);
    } catch (error) {
      showError(T.err_network);
    } finally {
      submit.disabled = false;
    }
  });

  renderServices();
  renderSummary();
  if (preselect.service) chooseService(Number(preselect.service), preselect.doctor);
})();
