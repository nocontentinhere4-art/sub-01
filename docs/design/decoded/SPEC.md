# SUB-01 "decoded" redesign — shared spec for all agents (coordinator: read fully before working)

Repo: /home/user/sub-01 (branch claude/compassionate-fermat-piv6wx, already checked out). Do NOT commit or push; the
coordinator does. Do not touch files owned by another agent (ownership below). Python deps are installed
(python3 -m pytest, live_server.py run). Demo server: `BROWSE=0 python3 live_server.py --demo --port <port> --data-dir <tmp>`
(pages at /, /brain, /room, /diary; ws at /ws). Chromium + Playwright for Python are available (`from playwright.sync_api import sync_playwright`;
`chromium.launch()` works with no options). Scratchpad for temporary files: /tmp/claude-0/-home-user/c5bf9a3b-2374-5276-a21c-1b03742ab284/scratchpad/

## Goal (from the owner)
Make the site brand new: new UI, brain FIRST on the site, with animations and a new voice, in the style of the
reference screenshots (a "cognitive API" dashboard, black ground, bold white Helvetica headlines, thin lines, small
uppercase mono captions, red for LIVE, teal for PROJECTED):
- centre: a video viewport of what is being watched with a LIVE badge and viewer count; under it a multi-trace
  timeline (Attention · Arousal · Cognitive load · Neural activity, each with a % and a colour) over time with
  diamond markers at events and a playhead;
- left and right: a brain seen from above (blue fibrous glow, warm hotspots) with a caption "RESPONSE AT 3:55" /
  "ATTENTION · LIVE", a big number score, and a delta like "10 ↑ +34" with a line explaining which networks
  ("Recruiting Visual · Ventral Attention · Dorsal Attention. Projected from the mechanism, not measured");
- right column: a feed ("NOW PLAYING" description, "UP NEXT", then chat lines "nick: text");
- a label "SYNTHETICALLY GENERATED — CLICK IT" style tag on anything synthetic; buttons for timestamps (0:00 1:04 2:04 3:17).

## Hard rules (project): see docs/HANDOFF.md "Hard rules" and "Science status"
- Honest: it is a MODEL, not a mind. Never say it feels, thinks, understands, is alive or conscious. "He" is shorthand
  for a fictional character. All readouts are "model readouts, not measurements of anyone". No text is labelled as AI-written (owner, 2026-11-02; this supersedes the earlier rule, see `docs/HANDOFF_DECODED.md` decision 14).
- Never name or hint at the real scanned person; the data credit lives on /about.html only.
- No coin promotion, no financial advice, no trade tape. No secrets. No third-party fonts/scripts beyond the CDNs
  already used (cdnjs three.js r128 is fine). No external tracking.
- Keep the password gate and existing APIs. Keep every existing page working.

## Decisions (made by the coordinator; do not re-litigate)
1. Routes: `/` → NEW `web/live.html` (the brain-first dashboard). `/room` → `web/room.html` (the 3D room; was `/`).
   `/brain` → `web/index.html` unchanged (the deep 3D brain). `/diary`, `/world.html`, `/tastes.html`,
   `/about.html`, `/life.html` unchanged. Old links: `/live` → `/`, `/room/` → `/room`, `/home`,`/index` → `/`.
2. Nav order on every page: **live** (`/`) · **brain** (`/brain`) · **room** (`/room`) · **diary** (`/diary`) ·
   **sees** (`/world.html`). The city was removed on 2026-11-02 (`docs/HANDOFF_DECODED.md`, decision 7): no nav link, and no page links to it.
   Pages that also link about/map keep those links after the common ones.
3. Design system: `web/ui.css` (already written; read it). Use its tokens/classes. Black #000 ground. Headlines in
   --ui-sans weight 700/800 tight tracking; captions/data in --ui-mono 10–12px uppercase tracked. Red = live,
   teal = projected/estimated. Respect prefers-reduced-motion.
4. Voice (copy): plain factual sentences, short lines, honest sub-lines in mono, in a scientific register. The front page
   describes the method, the data and the readouts ("A brain model, live." / "Send it a message." / "A model, not a mind.").
   The fictional framing stays. No fragment-for-punch headlines and no "AI" labels on any page (owner, 2026-11-02).
   His chat replies keep the casual voice from `mind.py` (lowercase, light slang) and are tagged "his reply". Whether
   they take the scientific register too is the owner's decision.

## Live data contract (WebSocket `/ws?rate=5&q=1`, JSON messages; see live_server.py Feed.brain_view)
After the server agent's change the q=1 tick is:
  {"type":"tick","sync":0.1,"events":[...],"sleep":{"stage":"AWAKE|NREM|REM","burst":0,"clock":"18:35","tz":"Tokyo","gain":1,"debt":0,"tired":0,"woken_tonight":0},
   "baseline":null,"slow":{"label":"..."},"neuro":{"DA":1.25,"5HT":1.0,"NE":2.0,"ACh":1.0},
   "groups":{"visual":..,"somatomotor":..,"attention":..,"salience":..,"limbic":..,"control":..,"default":..,"reward":..,"fear":..,"memory":..,"relay":..},
   "life":{"doing":"sitting on the park bench","walking":false,"activity":"research","place":"desk","phone":null,
           "screen":{"device":"desk","title":"...","host":"...","url":"...","kind":"page|video|search|shorts","id":123,"restarting":false,
                     "embed":{"src":"https://www.youtube.com/embed/..","label":"YouTube (official embed)"},"video":{...}} },
   "aud":{"n":12,"v":{...vote counts...}},     (n = viewers connected)
   "aq":"<base64, one byte per region, 214 regions>"}
  Decode aq: a = ACT_LO*(ACT_HI/ACT_LO)**(byte/255), ACT_LO=0.01, ACT_HI=10 (see web/index.html `unq`, line ~851).
  `life.screen` is absent when he is not at a screen (asleep, out, demo without BROWSE). `groups` are mean |z| per
  network this tick (absolute level; divide by a running ~25 s EMA baseline per network to get "vs own baseline").
Other messages (all already exist):
  hello {chat:[{t,text,networks,nick?}], replies:[{t,text,to,replying_to,tag,source}], rules, world, music, audience:{viewers,reactions,...}}
  chat {t,text,networks:[..],asleep,gain,nick?}        chat_ack {ok,reason?,queued,will_reply}     chat_reply {t,text,to,replying_to,tag,source}
  dopamine {size,rpe,novelty,interest,expect,n,kind,habituation,why,label,da}   (a reward burst: a marker on the timeline)
  screen {device,title,host,url,kind,id,restarting,embed?,video?,decision?{options,reason,eyes,outcome,watch_min}}
  decision {device,t,page,reason,options:[...],...}     mind_read {t,summary,topics,host,tag:"notes written by an AI"}
  plan {day,text:"Today he wants to: ...",steps:[{activity,label,done}],reason,source,vote,why}
  reading {title,url,...}  music {playing,id,title,artist,art,embed,embed_height,why,reason,options}  nights {last,tonight}
  vote {..options..}  vote_result  eye {...}  full {why,retry}  taught  teach_ack  spiking (ignore on the new page)
  tick.events[]: {type:"replay",t,text,networks,received,source} | {type:"sleep"...,t,text}
Chat send: ws.send(JSON.stringify({type:"chat", text, nick?})) → chat_ack. Max 200 chars; no links/addresses/tickers.
Screenshots: GET /api/screen/desk.jpg or /api/screen/phone.jpg (404 when nothing showable; poll ≤ every 3 s; add a
cache-buster). Other reads: /api/screens, /api/mind, /api/music, /api/diary, /api/config.
Brain geometry (static, already served): web/brain.json {nodes:[{name,group,p:[x,y,z],q:[x,y,z],lab}]×214,
  edges, mesh:{left:{v:[flat xyz]×10242, f:[flat tri idx]}, right:{...}}, groups:[11 names]}. Vertex→region: nearest
  node `q` among cortical nodes (names starting LH_/RH_), as web/index.html does at line ~650 (within 30 mm).
  Axial (top) view: x = left-right, y = back-front, z = up: project (x, y), front (+y) at the top of the panel.

Room embed (`web/room.html?embed`, the viewport when his screen is off): parent → iframe `postMessage({type:"sub01-embed", visible:boolean}, location.origin)`. `visible:false` stops its render loop; `visible:true` starts it again and lets him catch up 8 s. Iframe → parent `{type:"sub01-embed-ready"}` once he is first drawn. `live.html` posts `visible:false` when he is at a screen, when the tab is hidden, when the viewport is off screen and while the intro deck is open. The embed is chromeless: scene only, a fading mono caption of what he does, 30 fps, DPR 1.

## Readouts (page-side; all are model readouts, label them so)
 rel(g) = groups[g] / EMA25s(groups[g]); R(x) = clamp(50 + 40*log2(x), 0, 100)  (50 = his own baseline)
 Attention      = R(mean(rel attention, rel salience, rel visual))
 Arousal        = clamp(50 + 30*log2(neuro.NE))                  (noradrenaline on a log scale, 1.0 = resting wake = 50; NE/2*100 sat at 100 for minutes: NE runs 1.8-2.6 while he listens to music)
 Cognitive load = R(mean(rel control, rel default)) blended 70/30 with clamp(neuro.ACh/2*100)
 Neural activity= R(mean over regions of act[i]/EMA25s(act[i]))  (or from groups if act is costly)
 Big score on the LIVE brain panel = Attention. The RESPONSE panel freezes at the last event (dopamine burst, chat
 stimulus, replay): score = Attention at the peak within 3 s after the event, delta vs the 5 s before; caption
 "RESPONSE AT hh:mm" + "Recruiting <top 3 networks by rel>". Asleep: the panel says so (stage, "replay" events).
