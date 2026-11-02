# SUB-01 design system v2: "one deck" (2026-11-02, coordinator)

Every page is one slide of the same deck. Same chrome, same tokens, same motion, same voice. Black ground, bold
white Helvetica headlines with tight tracking, small uppercase mono captions. Red = live, teal = projected,
blue = the brain at baseline. No orange anywhere. No shadows; hairline borders. A model, not a mind; the character
is fiction; no "AI" wording; plain sentences, no punch fragments. The line "not measured from anyone" is out (owner, 11-02): readouts are "model readouts", nothing more.
References (Refero): Active Theory and cthdrl (void canvas, peripheral HUD, mono notation), Gt-planar (outlined
mono tags, hairlines), Julia Krantz (contact sheet with 1 px seams), Luma Genie (full-bleed 3D with a quiet HUD),
Dovetail (compact command-center density), plus the owner's "Humans Decoded" screenshots in ref/.

## Deck order and the header (identical markup on every page)
01 live `/` · 02 brain `/brain` · 03 room `/room` · 04 diary `/diary` · 05 sees `/world.html` · 06 about `/about.html`.
Secondary pages (`/life.html`, `/tastes.html`, `/fibres.html`) are notes: they declare no `data-deck`.
The page declares itself with `<body data-deck="02" data-pulse>` (`data-pulse` = show the pulse strip; `/` omits it).

    <header class="ui-hdr" id="hdr">
      <a class="ui-lockup" href="/"><b>SUB-01</b><small>brain model</small></a>
      <nav class="ui-nav" aria-label="pages"><a href="/">live</a><a href="/brain">brain</a><a href="/room">room</a><a href="/diary">diary</a><a href="/world.html">sees</a><a href="/about.html">about</a></nav>
      <div class="ui-spacer"></div>
      <div class="ui-state">
        <span class="ui-chip live" id="ui-live"><i class="ui-dot"></i><span id="ui-live-t">live</span></span>
        <span class="ui-clock" id="ui-clock">--:-- Tokyo</span>
      </div>
    </header>
    … page …
    <script src="/deck.js" defer></script><script src="/pulse.js" defer></script>

`.ui-lockup`: two lines, like the title slide (SUB-01 bold 16px, "brain model" 11px mono tracked under it).
The ONE live chip lives in the header. No other LIVE chip anywhere (panels, viewports, HUDs).
Pages that had extra links (about on tastes, map on life) keep them after the six.

## web/deck.js (defer, every page)
- marks the current nav link `.on` (by pathname; `/` only for `/`);
- no slide counter (owner, 11-02): the deck position shows only as the `.on` nav link;
- ← → (and `[` `]`) go to the previous / next slide unless focus is in an input, textarea, select or
  contenteditable, or a modal dialog is open (`dialog[open]`, `#intro:not([hidden])`);
- cross-document view transitions: ui.css declares `@view-transition { navigation: auto; }` and a 320 ms crossfade on
  `::view-transition-old(root)` / `::view-transition-new(root)`; browsers without it just navigate; off under
  prefers-reduced-motion;
- tolerates missing elements (no errors on a page that lacks the header).
- `<body data-keys>`: the page owns ← → (a frame viewer, a night viewer); deck.js binds only `[` `]` there. `[` `]`
  also work with Alt/AltGr (an Italian keyboard needs them to type a bracket).

## web/pulse.js (defer, every page with `body[data-pulse]`)
Creates `<div id="ui-pulse" role="group" aria-label="live readouts">` fixed at the bottom: 28 px tall, full width,
black, top hairline. Inside: a canvas with the four readouts of the last 60 s scrolling right to left
(attention `--ui-attn`, alertness `--ui-arousal`, effort `--ui-load`, activity `--ui-neural`, 1 px
lines, 50 = baseline as a faint dashed line), and at the right a mono row `attention 61 · alertness 70 · effort 54 · activity 49` (11 px) plus
the stage chip when not AWAKE ("NREM · asleep", "REM · dreaming"). Formulas, from live.html: rel(g) = groups[g] /
EMA25s(groups[g]); R(x) = clamp(50 + 40·log2 x); Attention = R(mean(rel attention, salience, visual)); Arousal =
clamp(50 + 30·log2(NE)); Load = 0.7·R(mean(rel control, default)) + 0.3·clamp(ACh/2·100); Neural = R(mean_i act_i /
EMA25s(act_i)) from `aq`. One WebSocket `/ws?rate=5&q=1` per page, reconnect with backoff, nothing drawn while
hidden, 10 fps. It also writes `#ui-clock` ("20:51 Tokyo") and `#ui-live-t` ("live · 3 watching" / "offline").
ui.css gives `body[data-pulse] { padding-bottom: 28px }` so nothing hides under the strip.

Names and accessibility (11-02, audience fixes): the readouts are attention, alertness, effort, activity (formerly
attention, arousal, cognitive load, neural activity; the formulas are unchanged); the visible row is words above 720 px
("attention 61 · alertness 70 · effort 54 · activity 49") and AT · AL · EF · AC on phones, and every item carries a
visually hidden full name and value ("Attention 61"). The wrapper is `role="group" aria-label="live readouts"`, the canvas
`aria-hidden`; the only live region is the stage chip (`aria-live="polite"`), never the numbers. `window.SUB01Pulse.spike()`
(any page, guard it with `window.SUB01Pulse && SUB01Pulse.spike()`) sends a white 24 px pulse with a 2 px glow along the strip,
left edge to right edge in 900 ms (ease-out), then a 200 ms fade; under reduced motion the strip flashes for 300 ms instead.
pulse.js calls it itself on every `chat` message from the socket (also in feed mode, through `feed()`), so every open page
shows a stimulus sent from anywhere; calls less than 500 ms apart count as one (the sender's call and the echo). Tokens: `--ui-dim`
#9494a1 and `--ui-faint` #8a8a98 (both at least 4.5:1 on #141418); text never below 11 px (`.ui-honest` 12 px); the focus ring
is a 2 px white outline with a 1 px black ring inside it (also `.ui-input:focus-visible`).

## Classes (web/ui.css v2; everything v1 stays and keeps working)
- tokens v1 + `--ui-blue:#3f7bff; --ui-blue2:#8fb3ff; --ui-r3:16px;`
- `.ui-lockup`, `.ui-state`, `.ui-clock` (header; `.ui-counter` stays in ui.css, unused)
- `.ui-seg` segmented control: one bordered pill, `button` children, `.on` filled white with black text
- `.ui-btn.primary` white fill, black text; `.ui-btn` stays the hairline pill
- `.ui-caption` 11 px mono tracked uppercase dim (same as `.ui-label`, alias)
- `.ui-num` a big-number block: `.ui-caption` above, `.ui-big` (+ optional `.ui-word` next to it), `.ui-caption` below
- `.ui-rail` a vertical stack of `.ui-num` with hairlines between (HUD rails on 3D pages); `.ui-rail.right`
  pins to the right edge, `.ui-rail.left` to the left; on phones rails become a horizontal scroll row
- `.ui-hud` a full-bleed page's overlay layer (pointer-events none, children re-enable)
- `.ui-sheet` the contact-sheet grid: tiles edge to edge, 1 px seams (`gap:1px; background:var(--ui-line)`)
- `.ui-dock` a bottom dock for a full-bleed page: a panel pinned above the pulse, max-width 920 px, centred
- `.ui-title` the title-slide headline block: `h1` 800 + a second line 600, `p` mono sub
- focus-visible: 2 px white outline + 1 px black inner ring on every control

## Motion
Page crossfade 320 ms; panels enter with the `.ui-in` stagger; big numbers tween 300 ms; the pulse breathes
(opacity ±8 % with sync); nothing faster than 0.5 Hz except pops and tweens. All off under prefers-reduced-motion.

## Hard rules (unchanged)
A model, not a mind. The character, his room and his life are fiction. Never name the scanned person (credit on
/about.html only). No coin promotion beyond the address line, no trade tape. Keep the password gate and every API.
No new third-party scripts beyond the CDNs already used. Fonts: Geist and Geist Mono, self-hosted in web/fonts (SIL OFL; owner, 2 November, late: "improve the font"); nothing from a font CDN. No "AI" wording on any page.

## v3 · controls that answer (11-02, from the owner's five component references)
Rare UI, Kobra, EasyUI, Pin UI and Aceternity UI, translated into black and white; no library, no font, nothing new under
reduced motion except the end states. All of it is ui.css (the v3 block) and deck.js (`window.SUB01UI`); a page only adds
a class or a call.
- Every `.ui-btn`: a white light runs round the hairline while the pointer is on it (a conic gradient masked to the ring,
  `--ui-ang` animated); the press squeezes 3 %. `.ui-btn.primary`: a shine crosses the white fill once on hover, and the
  button leans up to 3 px toward the pointer (magnetic; `.btn-primary` too).
- `.ui-seg`: deck.js inserts `.ui-seg-thumb`, a white pill that slides to the one `.on` / `aria-pressed` button (a
  MutationObserver follows the choice). A control with several chosen buttons keeps the static fill.
- `.ui-nav`: deck.js inserts `.ui-nav-pill`; it rests under the current page and slides under the hovered or focused link.
- `.ui-panel`: a 260 px light at 7 % follows the pointer inside (`--mx`/`--my`), the hairline brightens.
- Tooltips: a `title` on a button, link, chip or summary shows as `.ui-tip` (11 px mono, hairline panel, 160 ms in) above
  the control; the title moves to `data-tip` on first hover and `aria-describedby` points at the tip while it shows.
- `SUB01UI.toast(text)`: a white pill above the pulse for 1.6 s (`role=status`). `SUB01UI.state(btn, "busy"|"done"|"fail", text)`:
  the send buttons read "sent ✓" (white) or "not sent" (red hairline) for 1.2 s. `SUB01UI.swap(el, fn)`: a changing
  headline comes in from a 6 px blur (brain and room `#story`, once per change). `.ui-shimmer`: a light passes along a
  loader caption (the room's boot line, the live page's "loading the wiring…").

## v4 · the look (2 November, late; the owner: "it still feels made with AI, the buttons are the same, improve the font")
The references read again (Kobra, Aceternity, EasyUI): Geist or Inter type, sentence-case labels, rounded rectangles, translucent
fills with a hairline and a top highlight, layered surfaces. The v4 block at the end of ui.css wins over v1–v3:
- Type: Geist everywhere (`--ui-sans`), Geist Mono (`--ui-mono`) only for numbers, times and the pulse row. Labels and captions
  (`.ui-label`, `.ui-caption`, the lock-up's small line) are 12 px medium sentence case with no tracking; the pages' own captions
  were converted the same way (no `text-transform:uppercase` left in web/). Headlines keep the tight negative tracking.
- Shapes: `--ui-r` 8 px (buttons, inputs, nav, chips 7 px), `--ui-r2` 12, `--ui-r3` 14 (panels, docks). No 999 px pills left in web/.
- Buttons: `.ui-btn` 13 px medium, fill `--ui-fill` (white 6 %), hairline `--ui-hair` (10 %), top highlight `--ui-top`, 32 px tall;
  hover fill 10 % and hairline 18 %; `.primary` a white-to-#e4e4e8 gradient with a white top line and a soft drop. `.ui-seg` a 10 px
  box with 7 px buttons and a thumb with a 1 px drop. `.ui-input` 13 px on #0b0b0e with an inset shadow.
- Surfaces: `.ui-panel` and `.ui-dock` a #121216→#0d0d10 gradient, an 8–10 % hairline, the top highlight.
- The v3 behaviours (the light round a pill, the sliding thumb and nav pill, the panel light, tooltips, toast) are unchanged.

## v5 · the owner's design skill (2 November, late): github.com/elayadesign/ai-design-skills + redesign-skill
Applied as the v5 block at the end of ui.css and a pass over every page (these values now win over v1–v4):
- Motion: `--ui-ease` is cubic-bezier(.22,1,.36,1); no transition under 200 ms (colour and opacity at 300 ms); no default `ease`.
- Surfaces: flat. The ground #000, panels, docks and the pulse strip #181818, inputs #000, tooltips #1F1F1F; no background
  gradients anywhere (the only gradient is the hero heading text, #fff → #9B9B9B, on `.ui-title h1`, `#hero-h`, `#story`, `h1.lead`).
- Radii on the Tailwind scale: 8 (buttons, nav, inputs), 12 (the header), 16 (panels, docks); nested shapes outer minus gap
  (the segmented control 8 with 4 px buttons and thumb; chips 6).
- Spacing from the scale: buttons 8 / 12, chips and seg buttons 4 / 8, nav links 4 / 8.
- Type on the Tailwind scale: nothing under 12 px (every 9–11.5 px caption became 12), 13 → 12, 15 → 14; buttons and nav 14 px;
  no weight above 700; headings `text-wrap:balance`, paragraphs `pretty`; no italics; no hyphens inside running copy
  (paper titles keep theirs).
- The header floats: 8 px off the top, sized to its content, centred, rgba(0,0,0,.6) over a 12 px blur, a 12 px radius, a hairline;
  on phones it spans the width.
- The skills are installed user-level in ~/.claude/skills (landing-page-design, redesign-existing-projects) for later sessions.
