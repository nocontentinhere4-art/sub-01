# ui-simple visual QA: e3e846e @ e3e846e

Demo server (`--demo --time-scale 60 --start 10:00`), headless Chromium; viewports 1280x800, 390x844, 360x780, 430x932; states: as loaded, then each tab clicked. Sheet: `qa_sheet.jpg`. Raw: `qa.json`.

## 1. A tab could not be found or clicked
- 1280x800 Vote: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"vote\"]").first - locator resolved to <button role="tab" class="on" type="button" data-tab="vote" aria-selected="true">…</button> - attempting click action - waiting for element to be visible, enabled and stable
- 1280x800 Chat: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"chat\"]").first - locator resolved to <button role="tab" type="button" data-tab="chat" aria-selected="false">…</button> - attempting click action - waiting for element to be visible, enabled and stable
- 1280x800 More: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"more\"]").first - locator resolved to <button role="tab" type="button" data-tab="more" aria-selected="false">More</button> - attempting click action - waiting for element to be visible, enabled and stable
- 390x844 Teach: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"teach\"]").first - locator resolved to <button role="tab" type="button" data-tab="teach" aria-selected="false">Teach</button> - attempting click action - waiting for element to be visible, enabled and stable
- 390x844 More: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"more\"]").first - locator resolved to <button role="tab" type="button" data-tab="more" aria-selected="false">More</button> - attempting click action - waiting for element to be visible, enabled and stable
- 360x780 Chat: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"chat\"]").first - locator resolved to <button role="tab" type="button" data-tab="chat" aria-selected="false">…</button> - attempting click action - waiting for element to be visible, enabled and stable
- 360x780 Teach: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"teach\"]").first - locator resolved to <button role="tab" type="button" data-tab="teach" aria-selected="false">Teach</button> - attempting click action - waiting for element to be visible, enabled and stable
- 430x932 Chat: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"chat\"]").first - locator resolved to <button role="tab" type="button" data-tab="chat" aria-selected="false">…</button> - attempting click action - waiting for element to be visible, enabled and stable
- 430x932 Teach: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"teach\"]").first - locator resolved to <button role="tab" type="button" data-tab="teach" aria-selected="false">Teach</button> - attempting click action - waiting for element to be visible, enabled and stable
- 430x932 More: click failed: Locator.click: Timeout 15000ms exceeded. Call log: - waiting for locator("[role=tab][data-tab=\"more\"]").first - locator resolved to <button role="tab" type="button" data-tab="more" aria-selected="false">More</button> - attempting click action - waiting for element to be visible, enabled and stable

## 2. Tap targets under 44 px on touch viewports
- #todaybtn "today ▾": 72×32
- a "brain": 50×37
- a "diary": 50×37
- a "sees": 43×37
- a.on "room": 43×37
- button "✨": 34×44, 40×44
- button "❤️": 34×44, 40×44
- button "👋": 34×44, 40×44
- button "👏": 34×44, 40×44
- button "😂": 34×44, 40×44
- button "😮": 34×44, 40×44

## 3. Console errors
- THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values. BufferGeometry

