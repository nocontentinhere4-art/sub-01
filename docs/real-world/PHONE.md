# Phone overlay (`web/world/phone.js`)

In the construct there is no 3D phone prop. When `life.phone` is set (lying in bed, scrolling) the HUD shows SUB-01's
simulated phone as a small overlay (`#phone-overlay`, bottom-left; tap = enlarge, x = close, esc / backdrop = shrink;
it hides itself when the phone is not in use or while asleep). It is a stage prop of a simulation; nothing on it claims
the model is alive or a person. `phone_util.js` holds the pure helpers (feed validation, candles, canvas drawers).

## Apps (`life.phone`)
| app | content |
|---|---|
| `chart` | net order flow of the pool (its "coin") from the live trade stream: candles of cumulative signed volume (trades carry no price) + buy/sell volume bars |
| `chat` | the most recent accepted chat lines (drawn on a canvas, never as HTML; nicknames shown) |
| `tiktok` | only curated videos from `web/phone_feed.json`, through the official embed; see below |

`?phoneapp=chart|chat|tiktok` (or `phone.setApp(app)`) forces the app shown (the overlay itself still needs
`state.visible`, which main.js takes from `life.phone`; use the demo flag `--life-activity phone` for screenshots).

## `web/phone_feed.json`
```json
[
  {"url": "https://www.tiktok.com/@username/video/7234567890123456789", "note": "short neutral caption (<= 140 chars)"}
]
```
- Array of objects; `url` is required and must match `https://www.tiktok.com/@<user>/video/<digits>` exactly
  (no query string, no short links). `note` is optional plain text shown on the card.
- Entries that do not validate, or duplicate a video id, are ignored; the browser console prints why (`[phone] phone_feed.json: ...`).
  `tests/test_phone_feed.py` checks the committed file, `tests/js/phone_util.test.mjs` the validator.
- Empty list (the default) -> the tiktok app shows a "No curated videos yet" card and nothing is ever requested from tiktok.com.
- Curate by hand: only add videos that are fine to show next to the honesty line (no money/trading calls, no real faces
  of the scanned person, nothing about the scanned person).
- Playback is the official player only: `<iframe src="https://www.tiktok.com/embed/v2/<id>">` (sandboxed), created after the
  viewer enlarges the phone (no third-party request before that). Videos are never downloaded or re-hosted. A "next"
  button steps through the list; every new tiktok session starts at the next entry.

## API
```js
const phone = createPhone();                 // {overlayEl, update(state), setApp(app), pushTrades(trades), feed, drawOrderFlow}
$("phone-overlay").appendChild(phone.overlayEl);
phone.update({app, visible, asleep, pool, flow, chat, clock});   // every frame, redraws at 2 Hz
```
`state.flow` is the cumulative signed flow main.js keeps; for true time-bucketed candles also call
`phone.pushTrades(m.trades)` in the `tick` handler (optional). `drawOrderFlow(ctx, w, h, {pool, candles})` is pure 2D-canvas
code and can be reused for any other chart.
