(function () {
  const T = JSON.parse(document.getElementById("i18n").textContent);
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  window.Site = { T, money, escapeHtml };

  // Sarlavha: bosh sahifada aylantirilganda oq bo'ladi
  const header = $("#siteHeader");
  if (document.body.classList.contains("has-hero")) {
    const update = () => header.classList.toggle("is-solid", window.scrollY > 40);
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  // Til menyusi
  const lang = $("#langMenu");
  const langBtn = $(".lang__btn", lang);
  langBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    langBtn.setAttribute("aria-expanded", String(lang.classList.toggle("is-open")));
  });
  document.addEventListener("click", () => {
    lang.classList.remove("is-open");
    langBtn.setAttribute("aria-expanded", "false");
  });

  // Mobil menyu
  const drawer = $("#drawer");
  $("#menuOpen").addEventListener("click", () => { drawer.hidden = false; });
  $("#menuClose").addEventListener("click", () => { drawer.hidden = true; });
  drawer.addEventListener("click", (event) => {
    if (event.target === drawer || event.target.closest("a")) drawer.hidden = true;
  });

  // Qidiruv
  const search = $("#search");
  const input = $("#searchInput");
  const results = $("#searchResults");
  const hints = $("#searchHints");
  let timer = null;
  let active = -1;
  let lastQuery = "";

  function openSearch() {
    search.hidden = false;
    document.body.style.overflow = "hidden";
    input.focus();
  }
  function closeSearch() {
    search.hidden = true;
    document.body.style.overflow = "";
  }
  function item(href, image, title, sub, right) {
    return `<a class="search__item" href="${href}"><img src="${escapeHtml(image)}" alt=""><span><b>${escapeHtml(title)}</b><small>${escapeHtml(sub)}</small></span>${right ? `<em>${right}</em>` : ""}</a>`;
  }
  async function runSearch(query) {
    lastQuery = query;
    if (!query) {
      results.innerHTML = "";
      hints.hidden = false;
      return;
    }
    const response = await fetch(`/api/search/?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    if (query !== lastQuery) return;
    hints.hidden = true;
    active = -1;
    let html = "";
    if (data.services.length) {
      html += `<p class="search__group">${T.nav_services}</p>`;
      html += data.services.map((s) => item(`/xizmat/${s.id}/`, s.image, s.name, s.category, `${money(s.price)} ${T.sum}`)).join("");
    }
    if (data.doctors.length) {
      html += `<p class="search__group">${T.nav_doctors}</p>`;
      html += data.doctors.map((d) => item(`/shifokor/${d.id}/`, d.image, d.name, d.specialty, "")).join("");
    }
    results.innerHTML = html || `<div class="search__empty"><b>${T.search_empty}</b><p class="muted">${T.search_try}</p></div>`;
  }

  $("#searchOpen").addEventListener("click", openSearch);
  $("#searchClose").addEventListener("click", closeSearch);
  search.addEventListener("click", (event) => { if (event.target === search) closeSearch(); });
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(input.value.trim()), 160);
  });
  $$("[data-hint]").forEach((chip) => chip.addEventListener("click", () => {
    input.value = chip.dataset.hint;
    runSearch(input.value);
    input.focus();
  }));
  input.addEventListener("keydown", (event) => {
    const links = $$(".search__item", results);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!links.length) return;
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
      links.forEach((link, i) => link.classList.toggle("is-active", i === active));
      links[active].scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      links[active].click();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { closeSearch(); drawer.hidden = true; }
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") || (event.key === "/" && !typing)) {
      event.preventDefault();
      openSearch();
    }
  });

  // Banner karuseli
  const hero = $("#hero");
  if (hero) {
    const slides = $$(".hero__slide", hero);
    const dots = $$(".hero__dots button", hero);
    let index = 0;
    let auto = null;
    const show = (next) => {
      index = (next + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
      dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
    };
    const start = () => { if (slides.length > 1) auto = setInterval(() => show(index + 1), 6000); };
    const stop = () => clearInterval(auto);
    dots.forEach((dot, i) => dot.addEventListener("click", () => { show(i); stop(); start(); }));
    [["#heroPrev", -1], ["#heroNext", 1]].forEach(([id, step]) => {
      $(id, hero)?.addEventListener("click", () => { show(index + step); stop(); start(); });
    });
    hero.addEventListener("mouseenter", stop);
    hero.addEventListener("mouseleave", start);
    let touchX = null;
    hero.addEventListener("touchstart", (event) => { touchX = event.touches[0].clientX; stop(); }, { passive: true });
    hero.addEventListener("touchend", (event) => {
      const delta = event.changedTouches[0].clientX - touchX;
      if (Math.abs(delta) > 40) show(index + (delta < 0 ? 1 : -1));
      start();
    });
    start();
  }

  // Kategoriya strelkalari
  $$("[data-scroll]").forEach((button) => button.addEventListener("click", () => {
    const row = $(button.dataset.scroll);
    row.scrollBy({ left: Number(button.dataset.dir) * (row.clientWidth * 0.7), behavior: "smooth" });
  }));

  // Xarita: Google / Yandex almashishi
  const frame = $("#mapFrame");
  $$("[data-map]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-map]").forEach((b) => b.classList.toggle("is-active", b === button));
    frame.src = button.dataset.map;
  }));

  // Saralash va filtrlar
  $$("[data-autosubmit]").forEach((select) => select.addEventListener("change", () => select.form.submit()));
  const filtersToggle = $("#filtersToggle");
  if (filtersToggle) filtersToggle.addEventListener("click", () => $("#filtersForm").classList.toggle("is-open"));
})();
