/* Brauzerning standart elementlari o'rniga dizaynga mos select, sana tanlash va tasdiqlash oynasi. */
(function () {
  const source = document.getElementById("i18n");
  const T = source ? JSON.parse(source.textContent) : {};
  const MONTHS = T.months || ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"];
  const DAYS = [T.mon || "Du", T.tue || "Se", T.wed || "Ch", T.thu || "Pa", T.fri || "Ju", T.sat || "Sh", T.sun || "Ya"];
  const TEXT = { yes: T.yes || "Ha", no: T.no || "Yo'q", today: T.today || "Bugun", clear: T.clear || "Tozalash", pick: T.pick_date_short || "Sanani tanlang" };

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const icon = (name) => `<svg class="i i--sm" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const pad = (n) => String(n).padStart(2, "0");

  let openPopup = null;
  function closePopup() {
    if (!openPopup) return;
    openPopup.classList.remove("is-open");
    openPopup = null;
  }
  function togglePopup(box) {
    const wasOpen = box === openPopup;
    closePopup();
    if (!wasOpen) {
      box.classList.add("is-open");
      box.classList.toggle("is-right", box.getBoundingClientRect().left + 300 > window.innerWidth);
      openPopup = box;
    }
  }
  document.addEventListener("click", (event) => {
    if (openPopup && !openPopup.contains(event.target)) closePopup();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closePopup(); });

  function enhanceSelect(select) {
    if (select.multiple || select.dataset.ui) return;
    select.dataset.ui = "1";
    const box = el("div", "sel" + (select.dataset.plain !== undefined ? " sel--plain" : ""));
    const button = el("button", "sel__btn");
    button.type = "button";
    button.setAttribute("aria-haspopup", "listbox");
    const label = el("span", "sel__text");
    button.append(label);
    button.insertAdjacentHTML("beforeend", icon("chevron"));
    const list = el("ul", "sel__list");
    list.setAttribute("role", "listbox");

    function render() {
      list.innerHTML = "";
      [...select.options].forEach((option) => {
        const item = el("li", option.selected ? "is-active" : "", option.textContent);
        item.setAttribute("role", "option");
        item.dataset.value = option.value;
        item.tabIndex = -1;
        list.append(item);
      });
      label.textContent = select.selectedOptions[0]?.textContent ?? "";
      label.classList.toggle("is-empty", !select.value);
    }
    function pick(value) {
      select.value = value;
      render();
      closePopup();
      button.focus();
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    button.addEventListener("click", () => togglePopup(box));
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      if (box !== openPopup) togglePopup(box);
      (list.querySelector(".is-active") || list.firstElementChild)?.focus();
    });
    list.addEventListener("click", (event) => {
      event.preventDefault(); // select <label> ichida bo'lsa, ro'yxat qayta ochilmasin
      const item = event.target.closest("li");
      if (item) pick(item.dataset.value);
    });
    list.addEventListener("keydown", (event) => {
      const item = document.activeElement;
      if (event.key === "ArrowDown") { event.preventDefault(); item.nextElementSibling?.focus(); }
      if (event.key === "ArrowUp") { event.preventDefault(); item.previousElementSibling?.focus(); }
      if (event.key === "Enter") { event.preventDefault(); pick(item.dataset.value); }
    });
    select.hidden = true;
    select.after(box);
    box.append(button, list);
    render();
  }

  function enhanceDate(input) {
    if (input.dataset.ui) return;
    input.dataset.ui = "1";
    const optional = !input.required;
    input.type = "hidden";
    const box = el("div", "dp");
    const button = el("button", "dp__btn");
    button.type = "button";
    const label = el("span");
    button.innerHTML = icon("calendar");
    button.append(label);
    const pop = el("div", "dp__pop");
    const now = new Date();
    const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    let view = null;

    const showLabel = () => {
      const [y, m, d] = (input.value || "").split("-");
      label.textContent = input.value ? `${d}.${m}.${y}` : TEXT.pick;
      label.classList.toggle("is-empty", !input.value);
    };
    function render() {
      const first = new Date(view.y, view.m, 1);
      const offset = (first.getDay() + 6) % 7;
      const count = new Date(view.y, view.m + 1, 0).getDate();
      let days = "";
      for (let i = 0; i < offset; i++) days += "<span></span>";
      for (let d = 1; d <= count; d++) {
        const iso = `${view.y}-${pad(view.m + 1)}-${pad(d)}`;
        const classes = [iso === input.value ? "is-active" : "", iso === todayIso ? "is-today" : ""].join(" ");
        days += `<button type="button" class="${classes}" data-date="${iso}">${d}</button>`;
      }
      pop.innerHTML = `
        <div class="dp__head">
          <button type="button" data-step="-1" aria-label="Oldingi oy">${icon("left")}</button>
          <b>${MONTHS[view.m]} ${view.y}</b>
          <button type="button" data-step="1" aria-label="Keyingi oy">${icon("right")}</button>
        </div>
        <div class="dp__grid dp__grid--head">${DAYS.map((d) => `<span>${d}</span>`).join("")}</div>
        <div class="dp__grid">${days}</div>
        <div class="dp__foot">
          <button type="button" data-date="${todayIso}">${TEXT.today}</button>
          ${optional ? `<button type="button" data-date="">${TEXT.clear}</button>` : ""}
        </div>`;
    }
    function choose(value) {
      input.value = value;
      showLabel();
      closePopup();
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    button.addEventListener("click", () => {
      const base = (input.value || todayIso).split("-").map(Number);
      view = { y: base[0], m: base[1] - 1 };
      render();
      togglePopup(box);
    });
    pop.addEventListener("click", (event) => {
      event.preventDefault();
      const target = event.target.closest("button");
      if (!target) return;
      if (target.dataset.step) {
        const date = new Date(view.y, view.m + Number(target.dataset.step), 1);
        view = { y: date.getFullYear(), m: date.getMonth() };
        render();
      } else {
        choose(target.dataset.date);
      }
    });
    input.after(box);
    box.append(button, pop);
    showLabel();
  }

  function ask(text) {
    return new Promise((resolve) => {
      const overlay = el("div", "modal");
      overlay.setAttribute("role", "alertdialog");
      overlay.setAttribute("aria-modal", "true");
      const card = el("div", "modal__card");
      const yes = el("button", "btn btn--primary", TEXT.yes);
      const no = el("button", "btn btn--outline", TEXT.no);
      yes.type = no.type = "button";
      const row = el("div", "modal__row");
      row.append(no, yes);
      card.append(el("p", "", text), row);
      overlay.append(card);
      document.body.append(overlay);
      yes.focus();
      const done = (value) => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(value);
      };
      const onKey = (event) => { if (event.key === "Escape") done(false); };
      document.addEventListener("keydown", onKey);
      yes.addEventListener("click", () => done(true));
      no.addEventListener("click", () => done(false));
      overlay.addEventListener("click", (event) => { if (event.target === overlay) done(false); });
    });
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-confirm]");
    if (!button) return;
    if (button.dataset.confirmed) {
      delete button.dataset.confirmed;
      return;
    }
    event.preventDefault();
    if (await ask(button.dataset.confirm)) {
      button.dataset.confirmed = "1";
      button.click();
    }
  });

  function apply(root = document) {
    root.querySelectorAll("select").forEach(enhanceSelect);
    root.querySelectorAll('input[type="date"]').forEach(enhanceDate);
  }
  apply();
  window.UI = { ask, apply };
})();
