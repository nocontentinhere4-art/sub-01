# SUB-01 design system v2: "one deck" (2026-11-02, coordinator)

Every page is one slide of the same deck. Same chrome, same tokens, same motion, same voice. Black ground, bold
white Helvetica headlines with tight tracking, small uppercase mono captions. Red = live, teal = projected,
blue = the brain at baseline. No orange anywhere. No shadows; hairline borders. A model, not a mind; the character
is fiction; no "AI" wording; plain sentences, no punch fragments. Readouts are "not measured from anyone".
References (Refero): Active Theory and cthdrl (void canvas, peripheral HUD, mono notation), Gt-planar (outlined
mono tags, hairlines), Julia Krantz (contact sheet with 1 px seams), Luma Genie (full-bleed 3D with a quiet HUD),
Dovetail (compact command-center density), plus the owner's "Humans Decoded" screenshots in ref/.

## Deck order and the header (identical markup on every page)
01 live `/` · 02 brain `/brain` · 03 room `/room` · 04 diary `/diary` · 05 sees `/world.html` · 06 about `/about.html`.
Secondary pages (`/life.html`, `/tastes.html`, `/fibres.html`) are notes: their counter reads `—`.
The page declares itself with `<body data-deck="02" data-pulse>` (`data-pulse` = show the pulse strip; `/` omits it).

    <header class="ui-hdr" id="hdr">
      <a class="ui-lockup" href="/"><b>SUB-01</b><small>brain model</small></a>
      <nav class="ui-nav" aria-label="pages"><a href="/">live</a><a href="/brain">brain</a><a href="/room">room</a><a href="/diary">diary</a><a href="/world.html">sees</a><a href="/about.html">about</a></nav>
      <div class="ui-spacer"></div>
      <div class="ui-state">
        <span class="ui-chip live" id="ui-live"><i class="ui-dot"></i><span id="ui-live-t">live</span></span>
        <span class="ui-clock" id="ui-clock">--:-- Tokyo</span>
        <span class="ui-counter" id="ui-counter">02 / 06</span>
      </div>
    </header>
    … page …
    <script src="/deck.js" defer></script><script src="/pulse.js" defer></script>

`.ui-lockup`: two lines, like the title slide (SUB-01 bold 16px, "brain model" 11px mono tracked under it).
The ONE live chip lives in the header. No other LIVE chip anywhere (panels, viewports, HUDs).
Pages that had extra links (about on tastes, map on life) keep them after the six.

## web/deck.js (defer, every page)
- marks the current nav link `.on` (by pathname; `/` only for `/`);
- fills `#ui-counter` from `body[data-deck]` ("02 / 06"; "—" when absent);
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
is a 2 px white outline with a 1 px black ring inside it (also `.ui-input:focus-visible`). The deck counter's aria-label reads
"page 2 of 6 · ← → or [ ] change page" and carries `aria-keyshortcuts`.

## Classes (web/ui.css v2; everything v1 stays and keeps working)
- tokens v1 + `--ui-blue:#3f7bff; --ui-blue2:#8fb3ff; --ui-r3:16px;`
- `.ui-lockup`, `.ui-state`, `.ui-clock`, `.ui-counter` (header)
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
No new third-party scripts or fonts beyond the CDNs already used. No "AI" wording on any page.
