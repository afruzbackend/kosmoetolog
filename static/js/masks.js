/* Kiritish qoliplari: telefon, narx, vaqt, ism, kod. Sayt va panelda bir xil ishlaydi. */
(function () {
  const PREFIX = "+998 ";

  const onlyDigits = (value) => value.replace(/\D/g, "");

  function localDigits(value) {
    let digits = onlyDigits(value);
    if (digits.startsWith("998")) digits = digits.slice(3);
    return digits.slice(0, 9);
  }

  function formatPhone(digits) {
    let out = PREFIX + digits.slice(0, 2);
    if (digits.length > 2) out += " " + digits.slice(2, 5);
    if (digits.length > 5) out += " " + digits.slice(5, 7);
    if (digits.length > 7) out += " " + digits.slice(7, 9);
    return out;
  }

  // Formatlangandan keyin kursor o'sha raqam yonida qolishi uchun
  function caretAfterDigits(text, count) {
    let seen = 0;
    for (let i = 0; i < text.length; i++) {
      if (/\d/.test(text[i])) seen++;
      if (seen === count) return i + 1;
    }
    return text.length;
  }

  function bindPhone(input) {
    input.setAttribute("maxlength", "17");
    if (input.value) input.value = formatPhone(localDigits(input.value));

    input.addEventListener("focus", () => {
      if (!input.value) input.value = PREFIX;
      requestAnimationFrame(() => {
        const end = input.value.length;
        input.setSelectionRange(end, end);
      });
    });
    input.addEventListener("blur", () => {
      if (localDigits(input.value).length === 0) input.value = "";
    });
    input.addEventListener("keydown", (event) => {
      const start = input.selectionStart;
      const end = input.selectionEnd;
      if (start !== end) return;
      if ((event.key === "Backspace" && start <= PREFIX.length) || (event.key === "ArrowLeft" && start <= PREFIX.length)) {
        event.preventDefault();
      }
      // Probel ustidan o'chirganda oldingi raqam o'chadi
      if (event.key === "Backspace" && input.value[start - 1] === " " && start > PREFIX.length) {
        event.preventDefault();
        const before = input.value.slice(0, start - 2);
        const digitsBefore = localDigits(before).length;
        const digits = localDigits(before + input.value.slice(start));
        input.value = formatPhone(digits);
        const pos = digitsBefore ? caretAfterDigits(input.value, digitsBefore + 3) : PREFIX.length;
        input.setSelectionRange(pos, pos);
      }
    });
    input.addEventListener("input", () => {
      const caret = input.selectionStart;
      const typedBefore = onlyDigits(input.value.slice(0, caret)).length;
      const raw = input.value;
      const digits = localDigits(raw);
      input.value = formatPhone(digits);
      const keepsPrefix = onlyDigits(raw).startsWith("998");
      const local = keepsPrefix ? Math.max(typedBefore - 3, 0) : typedBefore;
      const pos = local ? caretAfterDigits(input.value, local + 3) : PREFIX.length;
      input.setSelectionRange(pos, pos);
      input.classList.remove("is-invalid");
    });
  }

  function bindMoney(input) {
    const format = () => {
      const digits = onlyDigits(input.value).replace(/^0+(?=\d)/, "");
      input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    };
    format();
    input.addEventListener("input", () => {
      const fromEnd = input.value.length - input.selectionStart;
      format();
      const pos = Math.max(input.value.length - fromEnd, 0);
      input.setSelectionRange(pos, pos);
    });
  }

  function bindTime(input) {
    input.setAttribute("maxlength", "5");
    if (input.value) input.value = input.value.slice(0, 5);
    input.addEventListener("input", () => {
      let digits = onlyDigits(input.value).slice(0, 4);
      if (digits.length >= 1 && Number(digits[0]) > 2) digits = "0" + digits;
      if (digits.length >= 2 && Number(digits.slice(0, 2)) > 23) digits = "23" + digits.slice(2);
      if (digits.length >= 3 && Number(digits[2]) > 5) digits = digits.slice(0, 2) + "5" + digits.slice(3);
      input.value = digits.length > 2 ? digits.slice(0, 2) + ":" + digits.slice(2) : digits;
    });
    input.addEventListener("blur", () => {
      const digits = onlyDigits(input.value);
      if (digits.length === 2) input.value = digits + ":00";
    });
  }

  function bindName(input) {
    input.addEventListener("input", () => {
      const caret = input.selectionStart;
      const cleaned = input.value
        .replace(/[^\p{L}\s'‘’ʻ`-]/gu, "")
        .replace(/\s{2,}/g, " ")
        .replace(/(^|[\s-])(\p{L})/gu, (_, sep, ch) => sep + ch.toLocaleUpperCase());
      if (cleaned !== input.value) {
        input.value = cleaned;
        input.setSelectionRange(caret, caret);
      }
      input.classList.remove("is-invalid");
    });
  }

  function bindCode(input) {
    input.setAttribute("maxlength", "6");
    input.addEventListener("input", () => { input.value = onlyDigits(input.value).slice(0, 6); });
  }

  const binders = { phone: bindPhone, money: bindMoney, time: bindTime, name: bindName, code: bindCode };

  function apply(root) {
    root.querySelectorAll("[data-mask]").forEach((input) => {
      if (input.dataset.masked) return;
      input.dataset.masked = "1";
      binders[input.dataset.mask]?.(input);
    });
  }

  document.addEventListener("DOMContentLoaded", () => apply(document));
  if (document.readyState !== "loading") apply(document);
  window.Masks = { apply, phoneComplete: (value) => localDigits(value).length === 9 };
})();
