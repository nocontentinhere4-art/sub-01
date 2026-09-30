// node --test tests/js/phone_util.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { validateFeed, embedSrc, candlesFromFlow, TradeAggregator, drawOrderFlow, drawChatApp, drawCard, wrapText } from "../../web/world/phone_util.js";

test("validateFeed accepts only canonical tiktok video urls", () => {
  const ok = "https://www.tiktok.com/@some.user_1/video/7234567890123456789";
  const { items, errors } = validateFeed([
    { url: ok, note: "  a note\nwith newline " },
    { url: ok }, // duplicate
    { url: "http://www.tiktok.com/@u/video/12345678" },
    { url: "https://vm.tiktok.com/abc/" },
    { url: "https://www.tiktok.com/@u/video/12345678?x=1" },
    { url: "https://evil.com/https://www.tiktok.com/@u/video/12345678" },
    { url: "javascript:alert(1)" }, null, "x", {},
  ]);
  assert.equal(items.length, 1);
  assert.equal(items[0].id, "7234567890123456789");
  assert.equal(items[0].note, "a note with newline");
  assert.equal(errors.length, 9);
  assert.equal(validateFeed({}).items.length, 0);
  assert.equal(embedSrc(items[0].id), "https://www.tiktok.com/embed/v2/7234567890123456789");
});

test("candlesFromFlow groups points and keeps ohlc consistent", () => {
  const flow = [0, 1, 3, 2, 2, 5, 4];
  const c = candlesFromFlow(flow, 3);
  assert.equal(c.length, 2);
  for (const k of c) { assert.ok(k.h >= Math.max(k.o, k.c)); assert.ok(k.l <= Math.min(k.o, k.c)); assert.ok(k.b <= k.v + 1e-9); }
  assert.equal(c[c.length - 1].c, 4);
  assert.deepEqual(candlesFromFlow([1]), []);
  assert.deepEqual(candlesFromFlow(null), []);
});

test("TradeAggregator buckets by time and signs by kind", () => {
  const a = new TradeAggregator(4, 3);
  a.push([{ kind: "buy", usd: 100 }, { kind: "sell", usd: 30 }], 0);
  a.push([{ kind: "sell", usd: 50 }, { kind: "buy", usd: -5 }, { kind: "buy", usd: NaN }], 5);
  const l = a.list();
  assert.equal(l.length, 2);
  assert.equal(l[0].c, 70); assert.equal(l[0].h, 100); assert.equal(l[0].v, 130); assert.equal(l[0].b, 100);
  assert.equal(l[1].o, 70); assert.equal(l[1].c, 20);
  for (let i = 0; i < 10; i++) a.push([{ kind: "buy", usd: 1 }], 10 + 4 * i);
  assert.ok(a.list().length <= 4);
});

// minimal recording 2d context: every call must be accepted and text measured deterministically
function mockCtx() {
  const calls = [];
  return new Proxy({ calls, measureText: t => ({ width: String(t).length * 8 }) }, {
    get(t, k) { if (k in t) return t[k]; return (...a) => { calls.push(k); }; },
    set(t, k, v) { t[k] = v; return true; },
  });
}

test("drawers run on several canvas sizes, with and without data", () => {
  const candles = candlesFromFlow(Array.from({ length: 60 }, (_, i) => Math.sin(i / 4) * 5 + i * 0.1), 3);
  for (const [w, h] of [[512, 300], [360, 620], [540, 930]]) {
    const c = mockCtx(); drawOrderFlow(c, w, h, { pool: "TEST/SOL", candles }); assert.ok(c.calls.length > 30);
    const e = mockCtx(); drawOrderFlow(e, w, h, {}); assert.ok(e.calls.includes("fillText"));
    const k = mockCtx(); drawChatApp(k, w, h, [{ t: "12:00", text: "hello there ".repeat(30), nick: "ann" }, { t: "12:01", text: "x" }]); assert.ok(k.calls.includes("fillText"));
    drawChatApp(mockCtx(), w, h, []); drawCard(mockCtx(), w, h, "tiktok", ["No curated videos yet"], "foot");
  }
});

test("wrapText limits lines and splits huge words", () => {
  const c = mockCtx();
  const l = wrapText(c, "a ".repeat(200), 80, 3); assert.equal(l.length, 3);
  const w = wrapText(c, "x".repeat(100), 80); assert.ok(w.length >= 2 && w.every(s => s.length <= 10));
});
