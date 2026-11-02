# SUB-01 · live (`web/live.html`, served at `/`)

The brain-first dashboard of the "decoded" redesign: one self-contained page (inline CSS + JS, `/ui.css` tokens,
no frameworks, no external scripts). Layout per the reference: header (wordmark, nav, LIVE · n watching, Tokyo clock,
stage chip, 01/05 counter) · rotating hero (5 lines, 8 s) · grid [LIVE brain | his screen + timeline | feed + RESPONSE
brain] · honesty footer (with the slow-layer label and a link to `/brain`). ≤1100px: two columns with the brains side
by side underneath; ≤720px: one column (screen, timeline, LIVE, RESPONSE, feed).

## What it shows
- **His screen**: the official embed (YouTube/TikTok allowlist, 8 s fallback), else `/api/screen/<desk|phone>.jpg`
  every 3 s with a crossfade, else an "away" card (place / stage / activity on an animated grid). The bottom strip shows
  the card title · host (80 chars), a "model-chosen …" chip and the music line.
- **Timeline**: four traces (1m/5m/15m window), a playhead with the clock, red diamonds and bands for dopamine bursts,
  white ticks for chat stimuli, violet ticks for replays, a hover tooltip, click a marker or one of the last-6 buttons to scrub.
- **Brains** (WebGL, top view of the brain.json cortex mesh plus 900 connectome edges as curved strokes, additive):
  blue at baseline, then yellow at rel 1.3 and red at rel 1.8+. They breathe with `sync`. The mesh is built in a Worker
  (Blob URL) and the panels shimmer until it is ready.
  The left panel is live. The right panel freezes at the last event (the peak attention within 3 s; the delta is
  against the 5 s before), and its border flashes when an event arrives.
- **Feed**: NOW (life.doing + place; the latest mind_read note, tagged "notes written by an AI"; the latest decision
  reason, tagged "why his model clicked"), UP NEXT (plan + the next 2 steps, "voted by his brain model"), CHAT (last 30
  lines, his replies tagged "his reply · AI-written", system lines for replays/sleep), and a stimulus form → `chat_ack` line.

## Readouts (page-side model readouts, never measurements)
    rel(g) = groups[g] / EMA25s(groups[g]);  R(x) = clamp(50 + 40*log2(x), 0, 100)   (50 = his own baseline)
    Attention       = R(mean(rel attention, rel salience, rel visual))
    Arousal         = clamp(neuro.NE/2*100)
    Cognitive load  = 0.7*R(mean(rel control, rel default)) + 0.3*clamp(neuro.ACh/2*100)
    Neural activity = R(mean_i act[i]/EMA25s(act[i]))
If `groups` is missing, the page uses the mean `act` of each network's regions instead.
Traces: 500 ms bins, 15-min ring. Big numbers: an EMA, then a 300 ms tween.

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
readouts — not measured from anyone". AI-written text is tagged. No real person is named. No trade or coin content.
All server text is escaped. Images come only from the server itself, and embeds only from the official hosts.

## Not done / known gaps (handed over)
- Asleep state (`--time-scale 60 --start 23:50`) not yet tested in a browser; the captions and the away card have code
  paths but are unverified.
- Not checked in a browser: the embed and screenshot viewport (the demo has BROWSE=0, so no `life.screen`), dopamine
  markers (none in the demo), and the response panel after a real event at 390px. The 390px shot showed the RESPONSE
  brain empty before any event (probably the software-GL headless run; check on a device).
- Brain colours: at small sizes (phone) additive blending saturates to yellow/red. Tune `uAlpha`/`dens` in
  `BrainView.drawGL`, and maybe add a stronger temporal smoothing of rel.
- Perf: headless software GL ran rAF at 2–5 fps at 1440/390. Not measured on a real GPU. Consider capping the
  brains at 30 fps on desktop and skipping the RESPONSE redraw while it is frozen.
- RESPONSE shows "--" until the first event. The hero has no brain image (image 2 look is text-only).
- The hello chat order is sorted by "HH:MM" strings (wrong across midnight).
