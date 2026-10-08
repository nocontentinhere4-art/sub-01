# Launch QA: what visitors see (G23)

**Runs:**
- origin/main `b0eff95`;
- `preview/launch` `061eb67` (G14).

**Setup:** `live_server.py --demo` locally (`BROWSE=0 MIND=0 CLIPS=0 SUB01_SPIKING_LIVE=0`). Headless Chromium (software GL), with the default mixamo character, at desktop 1366×820 and mobile 390×844.

**Pages:** `/` (room), `/brain`, `/diary`, `/about.html`, `/life.html`, `/tastes.html`, `/world.html`, `/fibres.html`.

**What each page got:**
- a 25 s settle;
- a JS console and page-error log;
- a failed-request log;
- a horizontal-overflow check;
- a scan of the visible text for alive/conscious claims and financial or buy language.

**The room, on preview/launch:** also run with the clock at daytime (`--start 15:00`), with five frames 20 s apart on each viewport, asleep and at the desk.

**Scope:** problems only, ranked worst first. Nothing on main or `preview/launch` was changed. Screenshots are alongside.

## 1. HIGH — The brain page shows buy/sell trades with dollar amounts (main and launch)
- **What a visitor sees:** bottom left of `/brain` (`launch_desktop_brain.jpg`), in green and red: "buy $1.89 → reward, visual / sell $403 → salience, fear / buy $21 …". On mobile the same lines are in the page text.
- **Code:**
  - rendered at `web/index.html:943` (`#ticker`, styles at `web/index.html:40-45`);
  - fed by `m.trades` from `live_server.py`: `demo_trades()` at `live_server.py:494` in demo, and the on-chain feed `rpc_trades()` at `live_server.py:451` whenever `--mint`/`MINT` is set (`live_server.py:1971`, "our token, set at launch").
- **Production:** the ticker shows real trades the moment MINT is set.
- **The rule:** "any financial or buy language". If the coin stays, the ticker still prints "buy $…" in large type on the science page.

## 2. HIGH — NaN geometry in the room at the desk (launch; not reproduced on main in the same window)
- **What happened:** on `preview/launch`, desktop, the room logged `THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values` **four times**. It was logged in the run where he went from asleep to reading at the computer.
- **Effect:** a geometry with NaN positions renders nothing and breaks raycasts/culling for that mesh. Which mesh it is was not identified; `web/room.html` and `web/room/boy_mh.js` are the files that changed on launch (+57 / +152 lines vs main).
- **Main comparison:** the same check on main stayed asleep for its whole window (it never reached the desk), so main is **not cleared**, only not observed.
- **The frames:** they look right. He sits at the desk, the right hand on the mouse, nothing through the desk (`launch_room_desktop_reading.jpg`).

## 3. MEDIUM — Mobile room: old-rig animation tracks bound to the mixamo character (launch only)
- **What happened:** on `preview/launch`, 390 px, the room logs `THREE.PropertyBinding: No target node found for track: headfront.position / .quaternion / .scale`.
- **Why it matters:** `headfront` exists only in the old rig's clips (`web/room/boy*.glb`, `boy_m_*.glb`). So on mobile one of those clips is mixed onto char_mixamo, with a risk of a wrong pose on the bones the clips do share.
- **Main:** does not log it. The launch diff adds a mobile path (`narrow()`, from phone-camera, in `web/room.html`; `bones.headfront` used at `web/room.html:924, 1340, 1902`).
- **The frames:** the 5 mobile frames looked like the right pose (reading).

## 4. MEDIUM — Internal config messages are shown to visitors (main and launch)
- **The text:** `/brain` and `/life.html` show "YouTube API key not set", "no music playing · Spotify keys not set: playing from the curated list", and "the browser is turned off (BROWSE=0)" (`launch_mobile_life.jpg`).
- **Code:** `web/index.html:869`, `web/life.html:278`, `live_server.py:1097`, `live_server.py:1805`.
- In demo all three show. In production they show whenever a key is missing or the browser service is down. They read as broken.

## 5. MEDIUM — An empty black box in the room's "Now playing" card (main and launch)
- **What happens:** with no track embedded, the Spotify `<iframe id="mu-embed">` (`web/room.html:227`) stays visible as a black rectangle under the track name (`launch_room_desktop_reading.jpg`, top right).
- **Why:** its `src` is only set when there is an embed (`web/room.html:2068`), and the iframe is not hidden otherwise.

## 6. MEDIUM — Financial wording on the about page (main and launch)
- **Section "7 The coin"** (`web/about.html:258-262`): "The site shows a coin's public trades only as stimuli … Nothing on this site is financial advice. There are no promises, no price talk and no calls to buy."
- **Elsewhere on the page:**
  - "Reacts to the coin's trades" (`web/about.html:160`);
  - the browsing note "It may look at crypto and stock pages … never connects a wallet or clicks buy, sell or swap" (`web/about.html:149`).
- These are disclaimers, but they are financial language and they name a coin. Owner's call, given the rule.
- **Alive/conscious:** no claim anywhere. The about page says the opposite ("It is not alive and it is not conscious"), and no page uses "he feels/thinks/wants".

## 7. LOW — Mobile room: header and status unreadable over the poster (launch)
- At 390 px the nav (`room brain diary sees`, `web/room.html:205`) and "is reading Tokyo." sit on top of the bright city poster, white on bright (`launch_room_mobile_reading.jpg`).
- `#top` at `web/room.html:179` has no backing.

## 8. LOW — Mobile brain: the status line is drawn over the 3D brain (main and launch)
- At 390 px the line "stimulus gain … · sleep debt …" under the headline sits on the brain render and can't be read (`launch_mobile_brain.jpg`, `main_mobile_brain.jpg`).

## 9. LOW — Light streaks on the hoodie's back at the desk (launch)
- In the desk view, thin light streaks run across the back of the hoodie (`launch_room_desktop_reading.jpg`, centre left). They may be what 56d9a67 (monitor glow) addressed for the hood, still visible on the back.

## 10. LOW — No favicon: a 404 on every page (main and launch)
- The console shows "Failed to load resource: 404" on every load. That's `/favicon.ico` (curl: 404); no page declares an icon.

## Checked, no problem found
- **Overflow:** no horizontal page overflow on any page at 390 px. The wide elements reported are Leaflet's own map canvas (clipped by its container) and the `/brain` cards row, which is a deliberate horizontal scroller (`#cards`, `web/index.html:145`).
- **Errors:** no JS page errors (uncaught exceptions) on any page, and no 404 other than the favicon.
- **Pose:** no T-pose in any room frame (asleep in bed; reading at the desk), desktop or mobile.
- **Empty panels:** none, apart from the demo's no-data states ("No night written yet", "Nothing yet"). Those are expected with an empty data dir.

**Not covered:** chess, eating, the phone camera modes and the bed transitions were not reached in these windows. The demo clock in a 9-minute window only showed asleep → reading.
