# ui-simple visual QA: 5ac6cd9 @ 5ac6cd9

Demo server (`--demo --time-scale 60 --start 10:00`), headless Chromium; viewports 1280x800, 390x844, 360x780, 430x932; states: as loaded, then each tab clicked. Sheet: `qa_sheet.jpg`. Raw: `qa.json`.

Notes from G23 (read first):
- **Vote "TAB NOT FOUND" is a false negative of the script.** The tab's accessible name includes its counter ("Vote <n> left"), so an exact-name match missed it. Tabs are now found by `[role=tab][data-tab=…]`; the next run covers Vote.
- **Teach on 430×932: the click timed out (15 s).** Something intercepts the tap; the next run logs what.
- **Ranking:** the two uncaught page errors come first. `reading 'reset'` is also on main (852249a); `reading 'length'` is new on this branch.
- **The NaN-geometry console error** is the same one seen on preview/launch (docs/qa/launch/QA.md #2).

## 1. Page errors (uncaught JS)
- Cannot read properties of undefined (reading 'length')
- Cannot read properties of undefined (reading 'reset')

## 2. A tab could not be found or clicked
- 1280x800 Vote: TAB NOT FOUND
- 390x844 Vote: TAB NOT FOUND
- 360x780 Vote: TAB NOT FOUND
- 430x932 Vote: TAB NOT FOUND
- 430x932 Teach: click failed: Locator.click: Timeout 15000ms exceeded.
Call log:
  - waiting for get_by_role("tab", name="Teach", exact=True).first
    - locator resolved to <b

## 3. Tap targets under 44 px on touch viewports
- #tc-nick: 131×33, 143×33
- #tc-text: 328×33, 358×33
- #todaybtn "today ▾": 72×32
- a "brain": 50×37
- a "diary": 50×37
- a "sees": 43×37
- a.on "room": 43×37
- button "teach": 62×33
- button "✨": 36×44, 40×44
- button "❤️": 36×44, 40×44
- button "👋": 36×44, 40×44
- button "👏": 36×44, 40×44
- button "😂": 36×44, 40×44
- button "😮": 36×44, 40×44

## 4. Console errors
- THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values. BufferGeometry

