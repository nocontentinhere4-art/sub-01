// SUB-01 · deck.js (every page, defer). Every page is one slide of the same deck (docs/design/decoded/SYSTEM.md):
// inserts the skip link, marks the current nav link, and moves to the previous / next slide on ← → (or [ ]).
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
})();
