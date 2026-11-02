// SUB-01 · deck.js (every page, defer). Every page is one slide of the same deck (docs/design/decoded/SYSTEM.md):
// inserts the skip link, marks the current nav link, moves to the previous / next slide on ← → (or [ ]), and places the
// moving parts of the controls (v3: the nav pill, the segmented thumb, the panel light, the magnet, the tooltip; window.SUB01UI).
// <body data-keys>: the page owns ← → (a frame viewer, say); [ ] still move between slides there.
// The crossfade between pages is CSS (ui.css: @view-transition). Missing elements are fine: nothing here throws.
(() => {
  "use strict";
  const DECK = ["/", "/brain", "/room", "/diary", "/world.html", "/about.html"];
  // other spellings of the same pages (the server serves or redirects all of them)
  const ALIAS = {"/index.html":"/brain", "/brain.html":"/brain", "/room.html":"/room", "/diary.html":"/diary",
    "/live":"/", "/live.html":"/", "/home":"/", "/index":"/", "/sees":"/world.html", "/world":"/world.html",
    "/about":"/about.html", "/life":"/life.html", "/map":"/life.html", "/tastes":"/tastes.html", "/fibres":"/fibres.html"};
  const norm = p => {
    p = String(p || "/");
    if (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
    return ALIAS[p] || p || "/";
  };
  const body = document.body;
  const here = norm(location.pathname);

  // skip link: first child of body, hidden off-screen by ui.css until it takes focus; a page without <main id="main"> gets a link that does nothing
  try {
    if (body && !document.querySelector("a.ui-skip")) {
      const skip = document.createElement("a");
      skip.className = "ui-skip"; skip.href = "#main"; skip.textContent = "skip to content";
      skip.addEventListener("click", e => {
        const m = document.getElementById("main");
        if (!m) { e.preventDefault(); return; }
        e.preventDefault();
        if (!m.hasAttribute("tabindex")) m.setAttribute("tabindex", "-1");
        m.focus({ preventScroll: true }); m.scrollIntoView();
      });
      body.insertBefore(skip, body.firstChild);
    }
  } catch (e) { /* no body yet */ }

  // the current nav link (by pathname; "/" only for "/")
  try {
    const links = [...document.querySelectorAll(".ui-nav a[href]")];
    const mine = links.filter(a => {
      let u; try { u = new URL(a.getAttribute("href"), location.href); } catch (e) { return false; }
      return u.origin === location.origin && norm(u.pathname) === here;
    });
    if (mine.length) for (const a of links) {
      const on = mine.includes(a);
      a.classList.toggle("on", on);
      if (on) a.setAttribute("aria-current", "page"); else if (a.getAttribute("aria-current") === "page") a.removeAttribute("aria-current");
    }
  } catch (e) { /* a page without a nav */ }

  // the slide: body[data-deck] ("02"), else the pathname's place in the deck; secondary pages are notes ("—")
  const declared = body ? parseInt(body.getAttribute("data-deck"), 10) : NaN;
  const slide = declared >= 1 && declared <= DECK.length ? declared : 0;
  const at = slide || (DECK.indexOf(here) + 1);          // the keys also work on a deck page that has not declared itself

  // ← → and [ ]: the previous / next slide, unless the key belongs to something else on the page
  const typing = el => !!el && el instanceof Element && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) ||
    !!el.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])"));
  const modalOpen = () => !!document.querySelector("dialog[open], #intro:not([hidden]), [aria-modal='true']:not([hidden])");
  document.addEventListener("keydown", e => {
    if (!at || e.defaultPrevented || e.repeat || e.isComposing) return;
    const k = e.key, arrow = k === "ArrowRight" || k === "ArrowLeft", bracket = k === "[" || k === "]";
    // arrows: no modifier at all (alt+← is the browser's back). [ ]: whatever the layout needs to type them (Option on an
    // Italian Mac, AltGr = Ctrl+Alt on Windows), but not a Cmd / Ctrl shortcut
    if (arrow ? e.altKey || e.ctrlKey || e.metaKey || e.shiftKey : !bracket || e.metaKey || (e.ctrlKey && !e.altKey)) return;
    if (arrow && body && body.hasAttribute("data-keys")) return;   // <body data-keys>: the page owns ← →; [ ] still move
    const step = k === "ArrowRight" || k === "]" ? 1 : k === "ArrowLeft" || k === "[" ? -1 : 0;
    if (!step || typing(e.target) || typing(document.activeElement) || modalOpen()) return;
    const to = at - 1 + step;
    if (to < 0 || to >= DECK.length) return;              // the deck does not wrap
    // a page handler registered after this one may still claim the key: decide once the event has finished
    setTimeout(() => { if (!e.defaultPrevented) location.href = DECK[to]; }, 0);
  });

  // ---- v3 · controls that answer (window.SUB01UI; ui.css v3). The nav pill, the segmented thumb, the panel spotlight,
  // the magnetic primary, the tooltip, the toast, the stateful button, the swap. Pointer things only on fine pointers;
  // everything still under reduced motion; nothing here throws on a page without the element.
  const RM = matchMedia("(prefers-reduced-motion: reduce)"), FINE = matchMedia("(hover: hover) and (pointer: fine)");
  const UI = window.SUB01UI = window.SUB01UI || {};
  const place = (el, t, now) => {                       // a sliding marker onto a target, in the target's offset parent
    if (!t || !t.offsetWidth) { el.style.opacity = "0"; return; }
    if (now) el.style.transition = "none";
    el.style.opacity = "1"; el.style.width = t.offsetWidth + "px"; el.style.height = t.offsetHeight + "px";
    el.style.transform = `translate(${t.offsetLeft}px, ${t.offsetTop}px)`;
    if (now) { void el.offsetWidth; el.style.transition = ""; }
  };
  const settle = fn => { fn(true); addEventListener("load", () => fn(true)); setTimeout(() => fn(true), 350); addEventListener("resize", () => fn(true)); };

  // the nav pill: home on the current page, under the hovered or focused link meanwhile
  try {
    const nav = document.querySelector(".ui-nav");
    if (nav && nav.querySelector(":scope > a.on")) {
      const pill = document.createElement("i"); pill.className = "ui-nav-pill"; pill.setAttribute("aria-hidden", "true");
      nav.insertBefore(pill, nav.firstChild); nav.classList.add("has-pill");
      const home = now => place(pill, nav.querySelector(":scope > a.on"), now);
      settle(home);
      const to = e => { const a = e.target.closest && e.target.closest(".ui-nav > a"); if (a) place(pill, a); };
      if (FINE.matches) { nav.addEventListener("pointerover", to); nav.addEventListener("pointerleave", () => home()); }
      nav.addEventListener("focusin", to); nav.addEventListener("focusout", () => home());
    }
  } catch (e) { /* a page without the nav */ }

  // the segmented thumb: on the one chosen button; a control with several chosen buttons keeps the static fill
  try {
    for (const seg of document.querySelectorAll(".ui-seg")) {
      const chosen = () => [...seg.querySelectorAll(":scope > button")].filter(b => b.classList.contains("on") || b.getAttribute("aria-pressed") === "true");
      if (chosen().length !== 1) continue;
      const th = document.createElement("i"); th.className = "ui-seg-thumb"; th.setAttribute("aria-hidden", "true");
      seg.insertBefore(th, seg.firstChild); seg.classList.add("has-thumb");
      const home = now => { const c = chosen(); if (c.length !== 1) { seg.classList.remove("has-thumb"); th.style.opacity = "0"; return; }
        seg.classList.add("has-thumb"); place(th, c[0], now); };
      settle(home);
      // (the thumb's own style changes are ours: ignoring them keeps this from re-firing itself forever)
      new MutationObserver(ms => { if (ms.some(m => m.target !== th)) home(); }).observe(seg, {subtree:true, attributes:true, attributeFilter:["class", "aria-pressed", "hidden", "style"]});
      seg.addEventListener("pointerenter", () => home(true));
      if (typeof IntersectionObserver === "function") new IntersectionObserver(es => { if (es.some(x => x.isIntersecting)) home(true); }).observe(seg);
    }
  } catch (e) { /* no segmented control */ }

  // panels: the light follows the pointer
  try {
    if (FINE.matches) {
      for (const p of document.querySelectorAll(".ui-panel")) { if (getComputedStyle(p).position === "static") p.style.position = "relative"; p.classList.add("has-spot"); }
      document.addEventListener("pointermove", e => {
        const p = e.target.closest && e.target.closest(".ui-panel.has-spot"); if (!p) return;
        const r = p.getBoundingClientRect(); p.style.setProperty("--mx", (e.clientX - r.left) + "px"); p.style.setProperty("--my", (e.clientY - r.top) + "px");
      }, {passive:true});
    }
  } catch (e) { /* no panels */ }

  // the magnetic primary: it leans a few pixels toward the pointer and settles back
  try {
    if (FINE.matches && !RM.matches) {
      const SEL = ".ui-btn.primary, .btn-primary";
      document.addEventListener("pointerover", e => {
        const b = e.target.closest && e.target.closest(SEL); if (!b || b._uiMag || b.disabled) return; b._uiMag = true;
        let down = false;
        const move = ev => { const r = b.getBoundingClientRect(), dx = (ev.clientX - r.left - r.width / 2) / (r.width / 2), dy = (ev.clientY - r.top - r.height / 2) / (r.height / 2);
          b.style.transform = `translate(${(dx * 3).toFixed(1)}px, ${(dy * 2 - 1).toFixed(1)}px)${down ? " scale(.97)" : ""}`; };
        b.addEventListener("pointermove", move); b.addEventListener("pointerdown", ev => { down = true; move(ev); }); b.addEventListener("pointerup", ev => { down = false; move(ev); });
        b.addEventListener("pointerleave", () => { down = false; b.style.transform = ""; });
        b.style.transition = "transform .35s cubic-bezier(.2,.7,.2,1), background .18s, border-color .18s, color .18s";
      });
    }
  } catch (e) { /* no primary */ }

  // the tooltip: title= on a control becomes a tooltip in the system (the title moves to data-tip on first hover)
  try {
    if (FINE.matches) {
      const SEL = "button[title], a[title], .ui-chip[title], summary[title], [data-tip]";
      let tip = null, cur = null;
      const text = el => { if (el.hasAttribute("title")) { el.dataset.tip = el.getAttribute("title"); el.removeAttribute("title"); } return el.dataset.tip || ""; };
      const show = el => {
        const t = text(el); if (!t) return;
        if (!tip) { tip = document.createElement("div"); tip.className = "ui-tip"; tip.id = "ui-tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip); }
        if (cur && cur !== el) cur.removeAttribute("aria-describedby");
        tip.textContent = t; tip.hidden = false; tip.classList.remove("below"); cur = el; el.setAttribute("aria-describedby", "ui-tip");
        const r = el.getBoundingClientRect(); tip.style.left = "0px"; tip.style.top = "0px";
        const w = tip.offsetWidth, h = tip.offsetHeight;
        let x = r.left + r.width / 2, y = r.top - h - 8; if (y < 6) { y = r.bottom + 8; tip.classList.add("below"); }
        x = Math.max(w / 2 + 6, Math.min(innerWidth - w / 2 - 6, x)); tip.style.left = x + "px"; tip.style.top = y + "px";
      };
      const hide = () => { if (!tip || tip.hidden) return; tip.hidden = true; if (cur) cur.removeAttribute("aria-describedby"); cur = null; };
      document.addEventListener("pointerover", e => { const el = e.target.closest && e.target.closest(SEL); if (el) { if (el !== cur) show(el); } else hide(); });
      document.addEventListener("pointerdown", hide, true);
      document.addEventListener("focusin", e => { const el = e.target.closest && e.target.closest(SEL); if (el) show(el); else hide(); });
      document.addEventListener("focusout", hide);
      document.addEventListener("keydown", e => { if (e.key === "Escape") hide(); });
      addEventListener("scroll", hide, {passive:true, capture:true});
    }
  } catch (e) { /* no pointer */ }

  // helpers for the pages
  UI.toast = (text, ms = 1600) => { try {
    const old = document.querySelector(".ui-toast"); if (old) old.remove();
    const t = document.createElement("div"); t.className = "ui-toast"; t.setAttribute("role", "status"); t.textContent = text; document.body.appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 350); }, ms);
  } catch (e) { /* no body */ } };
  UI.state = (btn, state, text, ms = 1200) => { try {
    if (!btn) return;
    if (!("uiLabel" in btn.dataset)) btn.dataset.uiLabel = btn.textContent;
    clearTimeout(btn._uiT);
    if (!state) { delete btn.dataset.state; btn.textContent = btn.dataset.uiLabel; return; }
    btn.dataset.state = state;
    btn.textContent = text || ({busy:"sending…", done:"sent ✓", fail:"not sent"})[state] || btn.dataset.uiLabel;
    if (state !== "busy") btn._uiT = setTimeout(() => UI.state(btn, null), ms);
  } catch (e) { /* no button */ } };
  UI.swap = (el, fn) => { try {
    if (typeof fn === "function") fn();
    if (!el || RM.matches) return;
    el.classList.remove("ui-swap"); void el.offsetWidth; el.classList.add("ui-swap");
  } catch (e) { /* no element */ } };
})();
