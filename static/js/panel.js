(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const side = $("#side");
  const open = $("#sideOpen");
  if (open) {
    open.addEventListener("click", (event) => { event.stopPropagation(); side.classList.toggle("is-open"); });
    document.addEventListener("click", (event) => { if (!side.contains(event.target)) side.classList.remove("is-open"); });
  }

  $$("[data-autosubmit]").forEach((el) => el.addEventListener("change", () => el.form.submit()));
  $$("[data-print]").forEach((el) => el.addEventListener("click", () => window.print()));

  // Til yorliqlari
  $$("[data-langs]").forEach((box) => {
    $$("[data-lang]", box).forEach((tab) => tab.addEventListener("click", () => {
      $$("[data-lang]", box).forEach((t) => t.classList.toggle("is-active", t === tab));
      $$("[data-lang-pane]", box).forEach((pane) => { pane.hidden = pane.dataset.langPane !== tab.dataset.lang; });
    }));
  });

  // Yangi rasm tanlanganda darhol ko'rsatiladi
  $$("[data-preview]").forEach((input) => input.addEventListener("change", () => {
    const file = input.files[0];
    if (file) $("[data-preview-img]", input.closest(".imgf")).src = URL.createObjectURL(file);
  }));

  // Navbat formasi
  const form = $("#appointmentForm");
  if (form) {
    const prices = JSON.parse($("#prices").textContent);
    const f = form.elements;
    const params = new URLSearchParams(location.search);

    if (params.get("phone") && !f.phone.value) {
      f.phone.value = params.get("phone");
      f.phone.dispatchEvent(new Event("input"));
    }
    const chips = $("#timeChips");

    function setPrice() {
      if (f.service.value && !form.dataset.editing) {
        f.price.value = prices[f.service.value] ?? "";
        f.price.dispatchEvent(new Event("input"));
      }
    }
    async function loadSlots() {
      chips.innerHTML = "";
      if (!f.doctor.value || !f.date.value) return;
      const response = await fetch(`/api/slots/?doctor=${f.doctor.value}&date=${f.date.value}`);
      const { slots } = await response.json();
      slots.forEach((slot) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = slot.time;
        const mine = slot.time === f.time.value.slice(0, 5);
        button.disabled = !slot.free && !mine;
        button.addEventListener("click", () => { f.time.value = slot.time; });
        chips.append(button);
      });
    }
    async function findClient() {
      const digits = f.phone.value.replace(/\D/g, "");
      if (digits.length !== 12 || f.name.value) return;
      const response = await fetch(`/panel/api/mijoz/?phone=${digits}`);
      const { name } = await response.json();
      if (name) f.name.value = name;
    }
    if (f.price.value) form.dataset.editing = "1";
    f.service.addEventListener("change", () => { delete form.dataset.editing; setPrice(); });
    f.doctor.addEventListener("change", loadSlots);
    f.date.addEventListener("change", loadSlots);
    f.phone.addEventListener("blur", findClient);
    loadSlots();
    findClient();
  }

  // Sozlamalar: xarita tanlash
  const picker = $("#mapPicker");
  if (picker) {
    const lat = $("#id_latitude");
    const lng = $("#id_longitude");
    const hint = $("#mapHint");
    const fix = (value) => Number(value).toFixed(6);
    let map = null;
    let marker = null;

    function updateLinks() {
      $("#openGoogle").href = `https://www.google.com/maps/search/?api=1&query=${lat.value},${lng.value}`;
      $("#openYandex").href = `https://yandex.uz/maps/?pt=${lng.value},${lat.value}&z=16&l=map`;
    }
    function place(a, b, moveMap = true) {
      lat.value = fix(a);
      lng.value = fix(b);
      updateLinks();
      if (map) {
        marker.setLatLng([a, b]);
        if (moveMap) map.setView([a, b], 16);
      }
    }
    function parseLink(text) {
      const value = decodeURIComponent(text.trim());
      const yandex = /yandex\./.test(value);
      let match = value.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
      if (match) return [match[1], match[2]];
      match = value.match(/[?&](?:ll|pt|whatshere\[point\])=(-?\d+\.\d+),(-?\d+\.\d+)/);
      if (match) return yandex ? [match[2], match[1]] : [match[1], match[2]];
      match = value.match(/[?&](?:q|query|center|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)/);
      if (match) return [match[1], match[2]];
      match = value.match(/^(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)$/);
      return match ? [match[1], match[2]] : null;
    }

    updateLinks();
    $("#mapLink").addEventListener("input", (event) => {
      const found = parseLink(event.target.value);
      if (found) {
        place(Number(found[0]), Number(found[1]));
        hint.textContent = "Joy aniqlandi.";
      } else if (event.target.value) {
        hint.textContent = "Bu havoladan koordinata topilmadi. To'liq havolani qo'ying yoki xaritani bosing.";
      }
    });
    $("#myLocation").addEventListener("click", () => {
      navigator.geolocation?.getCurrentPosition(
        (position) => place(position.coords.latitude, position.coords.longitude),
        () => { hint.textContent = "Brauzer joylashuvga ruxsat bermadi."; },
      );
    });
    [lat, lng].forEach((input) => input.addEventListener("change", () => place(Number(lat.value), Number(lng.value))));

    window.addEventListener("load", () => {
      if (!window.L) {
        picker.hidden = true;
        hint.textContent = "Xarita yuklanmadi. Havola yoki koordinatalarni kiriting.";
        return;
      }
      const start = [Number(lat.value), Number(lng.value)];
      map = L.map(picker).setView(start, 16);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "&copy; OpenStreetMap",
      }).addTo(map);
      marker = L.circleMarker(start, { radius: 10, color: "#fff", weight: 3, fillColor: "#E0117F", fillOpacity: 1 }).addTo(map);
      map.on("click", (event) => place(event.latlng.lat, event.latlng.lng, false));
    });
  }
})();
