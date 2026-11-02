# SUB-01 · live (`web/live.html`, served at `/`)

The brain-first dashboard of the "decoded" redesign: one self-contained page (inline CSS + JS, `/ui.css` tokens, no frameworks, no external scripts; two images, `web/hero_brain.webp` and `web/intro_brain_top.webp`). Layout per the reference: an intro deck on the first visit of a browser session (`#intro`, five slides, replayable from the header's "intro" link) · header (wordmark, nav, LIVE · n watching, Tokyo clock, stage chip, 01 / 03 hero counter) · rotating hero (three lines, 8 s, over a muted side view of the real fibres) · grid [LIVE brain | his screen + timeline | feed + RESPONSE brain] · a one-line footer (the honesty line and a link to `/brain`). The "his screen" viewport shows the 3D room (`/room?embed`) whenever his screen is off.

**Fold (desktop):** the grid is 100dvh minus the header and the hero (at least 560 px); the main row is `minmax(0,1fr)`
and the timeline row `clamp(220px,34vh,300px)`. The viewport fills its row (no 16:9 lock; captures letterbox with
`object-fit: contain`). The big numbers, captions, legend, event pills and the chat input are above the fold at 1440×900
and 1280×800. The hero is `clamp(110px,15vh,170px)` high. ≤1100px: two columns with the brains side by side underneath;
≤720px: one column (screen, timeline, LIVE, RESPONSE, feed).

**Hero:** three lines, rotating every 8 s (`HERO` in `live.html`), each with a sub-line: "A brain model, live." ("It runs on one person's real MRI wiring. Every number here is read from the model.") · "Send it a message." ("Your words enter the model. Attention, arousal and load respond.") · "A model, not a mind." ("The character and his room are fiction. Credits on /about.html."). The image is `web/hero_brain.webp` (1400×954, 77 KB): a muted blue side view made from the real fibre render, behind the headline inside the hero box, with a radial mask and opacity .55 (.3 on phones). It drifts with a 20 s ken-burns, and its opacity breathes ±8 % with the model's sync. Both stop under reduced motion, and the line rotation is off too (the counter stays 01 / 03).

**Motion:** a radial bloom under each brain breathes with the model's synchrony (CSS variables `--bl` and `--bs`, set at most 10 times a second); the attention trace has a glow; the playhead has a 0.5 Hz halo; a big number that moves 5 points or more flashes its brightness (at most once per 2 s); the grid fades in over 600 ms after the intro deck closes; panel borders lift on hover. All of it is off under `prefers-reduced-motion`. Measured under software GL: no measurable cost (20.5 → 20.9 fps). The room iframe is the open cost (see the gaps).

**Intro deck:** five slides on the first visit per browser session (`sessionStorage` key `sub01.intro`), counter 01 / 05: "A brain / decoded", "Real wiring.", "Simulated activity." (`web/intro_brain_top.webp`, a muted blue top view), "Four readouts." and "Send a stimulus." with the primary button. Keyboard, dots and click navigate; Esc skips.

## What it shows
- **His screen**: the official embed (YouTube/TikTok allowlist, 8 s fallback), else `/api/screen/<desk|phone>.jpg` every 3 s with a crossfade, else the 3D room (see Room below). The away card (place / stage / activity on an animated grid) is the loading placeholder until the room has drawn ("camera on him · loading"). The bottom strip shows only when there is a title or music: the card title · host (80 chars), a "model-chosen …" chip and the music line.
- **Room** (`web/room.html?embed`): a chromeless scene with a fading mono caption of what he does, a slow camera drift, 30 fps, DPR 1. The parent posts `{type:"sub01-embed", visible}`; `visible:false` stops its render loop. The room posts `{type:"sub01-embed-ready"}` once he is first drawn. The iframe is created once and shown or hidden by opacity; the parent posts `visible:false` when he is at a screen, when the tab is hidden, when the viewport is off screen and while the intro deck is open.
- **Timeline**: four traces, a segmented 1m / 5m / 15m control, a playhead with the clock, red diamonds and bands for dopamine bursts,
  white ticks for chat stimuli, violet ticks for replays, a hover tooltip, click a marker or one of the last-6 buttons to scrub.
- **Brains** (WebGL, top view of the brain.json cortex mesh plus 900 connectome edges as curved strokes, additive). The
  mesh is built in a Worker (Blob URL) and the panels shimmer until it is ready.
  - Colour (model readouts; rel = a region's level against its own baseline): blue at baseline, lighter blue above it,
    yellow from rel ≈ 1.35, red by 2.0. Most of the brain stays blue: a 25 s warm-up blends rel towards 1 after the first
    tick; the display is smoothed over 1.5 s; additive alphas scale with the drawn size. A burst compressor: when the 92nd
    percentile of rel is above 1.3, the part above baseline is compressed so only about 8 % of regions turn warm.
    Measured: 91–100 % of lit brain pixels are blue-dominant at 1440 and 390 px. The 2D fallback uses the same thresholds.
    The panels carry one caption each: "ATTENTION · LIVE" and, before the first event, "ATTENTION · WAITING". The long colour note under the LIVE brain is gone with the rest of the explanatory text.
  - Frame rate: 30 fps on desktop, 15 on phones.
  - The left panel is live. The right panel (RESPONSE) freezes at the last event (the peak attention within 3 s; the delta
    is against the 5 s before), and its border flashes when an event arrives. While frozen it is redrawn only when its
    snapshot changes or on resize.
  - Before the first event RESPONSE shows the live brain dimmed, the current Attention in dim grey, the head
    "RESPONSE · waiting" and the caption "ATTENTION · WAITING". Both brains draw once after the mesh loads, on resize and
    when they come into view, so a full-page capture is never empty.
- **Feed**: NOW (life.doing + place; the latest mind_read note, tagged "his notes"; the latest decision reason, tagged "why"), UP NEXT (plan + the next 2 steps, tagged "planned by the model"), CHAT (last 30 lines, his replies tagged "his reply", system lines for replays/sleep; each line reads "nick text · hh:mm", with the networks in its title attribute), and a stimulus form → `chat_ack` line ("sent", or "not sent: reason"). Chat rows are ordered by age on the next tick's clock, so the order holds across midnight.

## Readouts (page-side model readouts, never measurements)
    rel(g) = groups[g] / EMA25s(groups[g]);  R(x) = clamp(50 + 40*log2(x), 0, 100)   (50 = his own baseline)
    Attention       = R(mean(rel attention, rel salience, rel visual))
    Arousal         = clamp(50 + 30*log2(neuro.NE))   (1.0 = resting wake = 50; the old NE/2*100 sat at 100 for minutes)
    Cognitive load  = 0.7*R(mean(rel control, rel default)) + 0.3*clamp(neuro.ACh/2*100)
    Neural activity = R(mean_i act[i]/EMA25s(act[i]))
If `groups` is missing, the page uses the mean `act` of each network's regions instead.
Traces: 500 ms bins, 15-min ring. Big numbers: an EMA, then a 300 ms tween; the legend's Attention follows the same tween,
so both show one value.

## Data
`/ws?rate=5&q=1` (tick: sleep, sync, events, life(.screen), neuro, groups, aud.n, slow.label, aq; plus hello, chat,
chat_ack, chat_reply, dopamine, music, screen, decision, mind_read, plan, full) · `/brain.json` · `/api/mind`,
`/api/decisions`, `/api/music` on load (mind every 60 s) · `/api/screen/<dev>.jpg`.
Vertex → region: the nearest LH_/RH_ node within 30 mm using the nodes' **`p`** coordinates, because brain.json's
mesh is in `p` space. `q` is the space of cortex.bin, which index.html uses. With `q`, the occipital pole maps poorly.

## Preview
    BROWSE=0 python3 live_server.py --demo --port 8793 --data-dir /tmp/demo   # then http://localhost:8793/
`/live.html` now redirects to `/` (server routes). `--time-scale 60 --start 23:50` shows the asleep state.

## Honesty rules followed
Model, not mind: no feel, think or understand. "He" is a fictional character. Every readout is labelled "model
readouts — not measured from anyone". No text is labelled as AI-written (decision 14 in `docs/HANDOFF_DECODED.md`); the about page states that a language model writes the notes, plans and replies. No real person is named. No trade or coin content.
All server text is escaped. Images come only from the server itself, and embeds only from the official hosts.

**Copy rules (2026-11-02):** plain factual sentences; no fragment-for-punch headlines (the hero line "Stimuli in. Readouts out." is now "Send it a message."); no "day and night"; no "AI" on any page: the tags read "his reply", "his notes" and "why", the diary and world pages say images are "rendered from the brain model's state", and the room's page-reader lines say "the page is read for him".

## Not done / known gaps (handed over)
- **Real GPU.** Fps and brain colours were measured only under software GL (rAF 12.8 → 20.6 fps at 1440 px; the caps
  are 30 fps on desktop and 15 on phones). Check on a device.
- **Embed and screenshot viewport, and dopamine markers, on a live server.** The demo runs with `BROWSE=0` (no
  `life.screen`) and has no dopamine events. The room embed has been run in headless Chromium only.
- **Room iframe cost.** Under software GL the room iframe shares the main thread and drops the dashboard's rAF from 20.9 to 1.4 fps while it renders. On a real GPU it is capped at 30 fps and the cost is expected to be small, but that is NOT measured. Measure on the owner's Mac and on a phone; if it costs too much, pause the room while the brains draw, or lower its resolution in embed mode.
- **Headless room T-pose.** The room shows a T-pose in headless runs: the software GL animation state, not a page bug.
- **Owner decisions:** about.html's section "The coin" (left in place with the MINT code; now one contract-address line); whether the chat replies,
  which keep the casual voice from `mind.py`, should take the scientific register too.

## Design references
Reference lock from a design-reference search (2026-11-02). Primary direction: "midnight command center": compact layout,
tight-tracked headlines, mono metadata, hairline borders, no shadows. Outlined mono tags; big numbers with a caption above
and below. Rejected: light sections, violet and green accents, rounded 20px cards.
