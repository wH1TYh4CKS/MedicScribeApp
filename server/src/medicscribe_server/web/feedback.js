// Feedback form — collects, posts to /api/feedback, swaps to a thank-you.
(function () {
  "use strict";

  const form = document.getElementById("fbForm");
  const submitBtn = document.getElementById("submitBtn");
  const statusEl = document.getElementById("status");
  const thanks = document.getElementById("thanks");
  const thanksMsg = document.getElementById("thanksMsg");
  const starsGroup = document.getElementById("stars");
  const payGroup = document.getElementById("pay");
  const wantsBox = document.getElementById("wantsBox");
  const contactEl = document.getElementById("contact");
  const payNoteEl = document.getElementById("payNote");

  /* ---------- ARIA radiogroup (rating + pricing) ----------
     One tab stop per group (roving tabindex), arrow keys move and select,
     Home/End jump, Space/Enter selects. Exactly one aria-checked at a time. */

  function radiosIn(group) {
    return Array.prototype.slice.call(group.querySelectorAll('[role="radio"]'));
  }

  function checkedIndex(group) {
    return radiosIn(group).findIndex(function (r) {
      return r.getAttribute("aria-checked") === "true";
    });
  }

  function checkedValue(group) {
    const i = checkedIndex(group);
    return i < 0 ? "" : radiosIn(group)[i].dataset.v;
  }

  // Rating reads as a filled bar (1..N lit); pricing lights only the pick.
  function isLit(group, index, selected) {
    return group.dataset.fill === "cumulative" ? index <= selected : index === selected;
  }

  function paint(group, selected) {
    radiosIn(group).forEach(function (radio, i) {
      const on = i === selected;
      radio.setAttribute("aria-checked", on ? "true" : "false");
      radio.tabIndex = on ? 0 : -1;
      radio.classList.toggle("on", isLit(group, i, selected));
    });
  }

  function select(group, index) {
    paint(group, index);
    radiosIn(group)[index].focus();
  }

  function wrap(index, length) {
    return (index + length) % length;
  }

  const STEP = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

  function targetIndex(key, current, length) {
    if (key === "Home") return 0;
    if (key === "End") return length - 1;
    if (key in STEP) return wrap(current + STEP[key], length);
    return -1;
  }

  function onGroupKey(group, e) {
    const radios = radiosIn(group);
    const current = Math.max(0, radios.indexOf(document.activeElement));
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      select(group, current);
      return;
    }
    const next = targetIndex(e.key, current, radios.length);
    if (next < 0) return;
    e.preventDefault();
    select(group, next);
  }

  function bindGroup(group) {
    group.addEventListener("click", function (e) {
      const radio = e.target.closest('[role="radio"]');
      if (!radio) return;
      select(group, radiosIn(group).indexOf(radio));
    });
    group.addEventListener("keydown", function (e) {
      onGroupKey(group, e);
    });
  }

  bindGroup(starsGroup);
  bindGroup(payGroup);

  /* ---------- payload ---------- */

  // The backend has one pricing string (`would_pay`), so the anchored band, the
  // clinic-box intent and the free-text note share it. Band goes first: if the
  // server clips the field, the comparable answer is the part that survives.
  function composePay() {
    const parts = [];
    const band = checkedValue(payGroup);
    const note = payNoteEl.value.trim();
    if (band) parts.push(band);
    if (wantsBox.checked) parts.push("wants a clinic box");
    if (note) parts.push("note: " + note);
    return parts.join(" | ");
  }

  function ratingValue() {
    const v = checkedValue(starsGroup);
    return v ? Number(v) : null;
  }

  function collect() {
    return {
      rating: ratingValue(),
      role: document.getElementById("role").value,
      liked: document.getElementById("liked").value,
      issues: document.getElementById("issues").value,
      would_pay: composePay(),
      contact: contactEl.value,
    };
  }

  function isEmpty(p) {
    return (
      p.rating === null &&
      !p.role.trim() &&
      !p.liked.trim() &&
      !p.issues.trim() &&
      !p.would_pay.trim()
    );
  }

  // Returns an actionable message, or "" when the payload is good to send.
  function problemWith(payload) {
    if (isEmpty(payload)) return "Add a rating or a note before sending.";
    if (wantsBox.checked && !payload.contact.trim()) {
      return "Add an email or phone so we can reach you about a clinic box.";
    }
    return "";
  }

  function setStatus(msg, isErr) {
    statusEl.textContent = msg;
    statusEl.classList.toggle("err", !!isErr);
  }

  async function send(payload) {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function showThanks() {
    if (wantsBox.checked) {
      thanksMsg.textContent =
        "Your feedback is in, and we'll be in touch about a box for your clinic, " +
        "usually within a working day.";
    }
    form.style.display = "none";
    thanks.style.display = "block";
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const payload = collect();

    const problem = problemWith(payload);
    if (problem) {
      setStatus(problem, true);
      return;
    }

    submitBtn.disabled = true;
    setStatus("Sending…", false);
    try {
      await send(payload);
      showThanks();
    } catch (err) {
      submitBtn.disabled = false;
      setStatus("Couldn't send. Check your connection and try again.", true);
    }
  });

  /* ---------- arriving from the scribe page's "put this in your clinic" card ----------
     They clicked an offer, not a feedback link: pre-tick the intent (visibly, and
     they can untick it) and put the cursor where their enquiry actually needs input. */

  function syncSubmitLabel() {
    submitBtn.textContent = wantsBox.checked ? "Send enquiry" : "Send feedback";
  }

  function primeClinicIntent() {
    if (window.location.hash !== "#clinic") return;
    wantsBox.checked = true;
    contactEl.focus({ preventScroll: true });
  }

  wantsBox.addEventListener("change", syncSubmitLabel);
  primeClinicIntent();
  syncSubmitLabel();
})();
