# ui-simple visual QA: 107961b @ 107961b

Demo server (`--demo --time-scale 60 --start 10:00`), headless Chromium; viewports 1280x800, 390x844, 360x780, 430x932; states: as loaded, then each tab clicked. Sheet: `qa_sheet.jpg`. Raw: `qa.json`.

## 1. A tab could not be found or clicked
- 1280x800 Chat: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"chat\"]").first - locator resolved to <button role="tab" type="button" data-tab="chat" aria-selected="false">…</button> - attempting click action - waiting for element to be visible, enabled and stable - element is not stable - retrying click action - waiting for element to be visible, enabled and stable
- 390x844 Vote: TAB NOT FOUND
- 390x844 Chat: TAB NOT FOUND
- 390x844 Teach: TAB NOT FOUND
- 390x844 More: TAB NOT FOUND
- 360x780 Vote: TAB NOT FOUND
- 360x780 Chat: TAB NOT FOUND
- 360x780 Teach: TAB NOT FOUND
- 360x780 More: TAB NOT FOUND
- 430x932 Vote: TAB NOT FOUND
- 430x932 Chat: TAB NOT FOUND
- 430x932 Teach: TAB NOT FOUND
- 430x932 More: TAB NOT FOUND

## 2. Tap targets under 44 px on touch viewports
- #todaybtn "today ▾": 54×32
- a "brain": 44×29, 50×29
- a "diary": 44×29, 50×29
- a "sees": 37×29, 43×29
- a.on "room": 37×29, 43×29
- button "✨": 34×44, 40×44
- button "❤️": 34×44, 40×44
- button "👋": 34×44, 40×44
- button "👏": 34×44, 40×44
- button "😂": 34×44, 40×44
- button "😮": 34×44, 40×44

