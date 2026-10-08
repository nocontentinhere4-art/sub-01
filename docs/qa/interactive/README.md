# Viewers in the room: the vote on what he does next, live viewers, reactions (preview/interactive)

Status: **first working version in progress** (G24). Branch `preview/interactive`; `main` untouched, no PR.

## What was built

### 1. Vote on what he does next
- **Rounds**: one every `VOTE_ROUND_S` seconds, default **3600 (60 min)**; configurable with `--vote-round SECONDS`
  or the env `SUB01_VOTE_ROUND_S`. A round opens as soon as the last one closes.
- **Options (3)**: drawn from the activities his activity model (`life.py`, `Life.scores`) allows **both now and at the
  round's end** (score > 0 at both), so nothing impossible is offered: no park at 3 am (the park is day-only, 08–20 in
  Tokyo), no chess after 23:30, no park at 19:30 for a round ending at 20:30. Never offered: food, sleep, the door
  (needs) and the chart (nothing financial). Votable set: read at the computer, watch a video at the desk, play a game of
  chess, listen to music on the bed, walk to the park, look out of the window, scroll the phone in bed.
  Fewer than 2 possible: no round; it retries a minute later.
- **Result**: the most-voted option becomes a **strong nudge** in his activity model when the round ends:
  `Life.viewer_nudge`, a bonus of `VOTE_BONUS = 1.2` on that activity's score (the day plan's tilt is 0.35, a meal need
  1.6), held for one simulated hour or until carried out. It is carried out like a chat wish: what he is doing at home
  ends early when the nudged activity now beats it. Needs still come first (a hungry boy eats first). His caption then
  reads "…; viewers voted for it".
- **Asleep**: the result waits (`Votes.pending`) and is applied when he is awake **and** the activity is possible then
  (up to 2 simulated days, then dropped). The card says "viewers voted “…” · waiting until he is awake".
- **Tie rule**: options are listed in the order his own model ranks them when the round opens; a tie goes to the tied
  option listed first (what the model already leaned toward). No votes: no nudge.
- **One vote per viewer per round**: an **HttpOnly cookie** `sub01v` (random id, `SameSite=Lax`, `Secure` behind
  HTTPS; set on `/` and `/brain`) **and** a **salted hash of IP + user agent**. Both are HMAC-SHA256 hashed with a salt
  that lives only in memory; a vote is checked against those hashes re-hashed with a **per-round salt**. Nothing raw is
  kept, nothing is written to disk, and a round's hashes are dropped when it closes. Either hash already seen = voted.
  (Known trade-off: two people on the same network with the same browser build share the IP + UA hash.)
- **Panel** ("What next? · viewers vote", top of the room's side column; first card under the room on phones): the 3
  options with live counts and bars, time left, your vote marked, the last round's result. Wording is neutral:
  "viewers voted “walk to the park”", never what he wants or feels.
- `GET /api/vote`: the running round (options, counts, seconds left), the last result, a result waiting for him to wake.

### 2. Live viewers + reactions
- **Viewer count**: open websockets (`len(Live.sockets)`), anonymous, in every tick as `aud.n`; shown as "N watching"
  next to the reactions.
- **Reactions**: a fixed set of 6 — 👋 ❤️ 😂 😮 👏 ✨ — no free text; a bar of buttons above the chat (on phones in
  the fixed bottom dock, always reachable).
- **Rate limit**: per viewer token bucket, **1 every 3 s, burst 5** (keyed by the viewer's hash, never the address);
  over the limit the page gets `react_ack {ok: false, reason: "slow down"}` and dims the buttons for 3 s.
- **Aggregation**: accepted reactions are summed server-side and broadcast **in the existing tick** (`rx`: a count per
  emoji since the last tick); feeds at a lower rate (`?rate=5`) sum the skipped ticks' counts, like trades. They float up
  over the room for everyone (CSS, at most 40 on screen).
- **Spike glance**: **≥ 10 reactions within 10 s** → the server sends `{type: "glance"}`, **at most once every 2 min**.
  The page turns his head toward the camera once (`web/room/glance.js`: neck 40 % + head 60 %, capped at 55° turn /
  27° nod, 0.35 s in, 1.3 s hold, 0.6 s out), drawn after the clips; the desk-states layer gets the same message through
  its existing event hook (`deskEv` → `room/desk_states.js` `reactionFor`: `glance` → the calm `attend` loop).

### Wire format (websocket `/ws`)
| direction | message |
|---|---|
| server → page | `hello.audience = {reactions, viewers, vote, react_every, react_burst}` |
| server → page | tick: `aud = {n, v: [round id, counts, seconds left]}`, `rx = [counts]` (only when > 0) |
| server → page | `vote` (a round opens), `vote_result` (it closed), `vote_applied` (the nudge is on), `glance` |
| page → server | `{type: "vote", k}` → `vote_ack {ok, reason, mine}`; `{type: "react", k}` (ack only on refusal) |

## Hard rules, checked
- No claim that he understands, is conscious or alive; the vote card says what happens to the result, in model terms.
- No financial or buy language; the chart is not votable.
- No new LLM/API spend: counting and hashing only.
- No PII stored: hashes only, salts in memory, a round's hashes dropped at its end; the IP + UA never leave the
  connection's handler; nothing written to disk.
- Mobile 390 px: checked (screenshots below and the phone segment of the video).

## Files
- `audience.py` — rounds, options, tie rule, pending-while-asleep, fingerprints, token bucket, reactions, spike.
- `life.py` — `viewer_nudge`, `apply_vote`, `nudge`, the bonus in `scores`, carried out via `wish_now`.
- `live_server.py` — `audience_tick` (in the 50 ms brain tick), `handle_vote`, `handle_react`, the hello, the cookie
  middleware, `/api/vote`, `--vote-round`, `Feed` sums `rx` over skipped ticks.
- `web/room.html` — the vote card, the reactions bar + viewer count, floating reactions, the glance.
- `web/room/glance.js`, `web/room/desk_states.js` (the `glance` event).
- `tests/test_interactive.py` — 15 tests.
- `tools/interactive_demo.py` — records `demo.mp4`.

## Tests
_(filled in below as runs complete)_

## Demo video
_(in progress)_
