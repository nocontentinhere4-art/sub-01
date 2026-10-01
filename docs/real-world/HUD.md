# HUD (`web/world/hud.js`, `hud_util.js`, `minibrain.js`, `phone.js`)

All user-written text is shown with `textContent`; the honesty line (`#honesty`, static in `web/life.html`) is never hidden
and is restored by `createHud` if something removed it. Palette: deep blue-black, orange `#ff6a00`, warm whites, small cyan /
violet accents for data (no green code rain, no "Matrix" naming).

`createHud({send, onView, view})` -> `{hello, tick, chat, chatAck, eye, nights, mind, speech, update, setView}`.
When `onView` is given the HUD builds the view switch (`#view`: first person / overview) and the quality switch (`#quality`);
`main.js` calls `hud.setView(v)` when the view changes (keyboard `v`, URL).

| area | source | notes |
|---|---|---|
| status (`#doing`, `#meta`) | `tick.life`, `tick.sleep` | Rome clock, stage, sleep debt, woken count, what it is doing |
| inner speech (`#speech`) | `speech` | tag `rule` or `generated` (`kind: llm`), what it answers (`cid` -> the chat line) or the topic, the action it requested with its ok / reason; fades after 14 s |
| global workspace panel | `mind` | candidates as bars (colour per kind, label, salience), winner highlighted, self-model (doing / feeling / wanting + the last 4 broadcasts), caption "an architecture inspired by theories of consciousness (Global Workspace) . a model of brain activity, not a mind" |
| chat | `chat`, `chat_ack`, `hello.chat` | optional nickname (localStorage `sub01.nick`, same rules as `chat.check_nick`, server stays authoritative), nick, "back again" marker (`returning`), topic chips (client copy of the topic table), networks hit, number of districts, "won the workspace" mark when `mind.winner == chat.cid` |
| rules panel | `hello.rules`, `hello.region_rules` | the transparent table; the rows a message matched light up for 4 s |
| needs & today | `tick.life` | hunger / boredom / sleepiness, bread, today's log |

Panels are collapsible (state in localStorage); on phones (< 900 px) needs and rules start collapsed.

`minibrain.js`: the real tractography (`fibres.bin`, every 40th / 15th / 8th fibre for low / medium / high, one LineSegments)
with the activity shader of `/brain`, plus the 214 regions as glow points. `flash(regions, color)` lights regions (indices or group
names), `pulse(fromEl)` sends a dot from the chat box to it. It reads the construct's raw data promise
(`createMiniBrain(el, {quality, raw: loadBrainRaw()})`, `web/construct/data.js`), so `brain.json` and the 17 MB `fibres.bin` are
downloaded once per page (the browser cache did not dedupe them: startup was 36 MB, now 19 MB); its fibre geometry is still built
only after the construct is ready (`window.__sub01.ready`). Without `raw` it fetches the files itself. Redraws at 30 fps (20 on low),
skipped while hidden. `/brain` (`web/index.html`) flashes the regions of every `chat` message too.

Tests: `node --test tests/js/hud_util.test.mjs tests/js/phone_util.test.mjs`, `pytest tests/test_phone_feed.py`.
