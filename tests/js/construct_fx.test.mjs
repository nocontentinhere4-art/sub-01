// Unit tests for the pure helpers of web/construct/fx.js (rain words, weather targets, glitch burst timing).
// Run: node --test tests/js/*.test.mjs   (the "three" import resolves to web/vendor/three via three-hooks.mjs)
import test from "node:test";
import assert from "node:assert/strict";
import { register } from "node:module";

register("./three-hooks.mjs", import.meta.url);
const { splitWords, marketTargets, createBurster, wrapText, BURST_GAP, MAX_WORDS, MAX_GLYPHS, createFx } = await import("../../web/construct/fx.js");

test("exports the contract surface", () => { assert.equal(typeof createFx, "function"); });

test("splitWords keeps the message's own words, drops what the atlas cannot draw, caps count and length", () => {
  assert.deepEqual(splitWords("vai a comprare il pane"), ["vai", "a", "comprare", "il", "pane"]);
  assert.deepEqual(splitWords("  perché   no?  "), ["perché", "no?"]);
  assert.deepEqual(splitWords("<b>x</b> 日本語 ok"), ["<b>x</b>", "ok"]);          // atlas glyphs only; never HTML (drawn to a canvas)
  assert.deepEqual(splitWords(""), []); assert.deepEqual(splitWords(null), []);
  const many = splitWords(Array.from({ length: 100 }, (_, i) => "w" + i).join(" "));
  assert.ok(many.length <= MAX_WORDS);
  assert.ok(many.reduce((n, w) => n + w.length, 0) <= MAX_GLYPHS);
  assert.equal(splitWords("a".repeat(80))[0].length, 16);
});

test("marketTargets: pump warms, dump glitches, choppy jitters, calm nothing; reduced motion softens", () => {
  assert.deepEqual(marketTargets("pumping"), { pump: 1, glitch: 0, jitter: 0 });
  assert.deepEqual(marketTargets("dumping"), { pump: 0, glitch: 1, jitter: 0 });
  assert.deepEqual(marketTargets("choppy").jitter, 1);
  assert.deepEqual(marketTargets("calm"), { pump: 0, glitch: 0, jitter: 0 });
  assert.deepEqual(marketTargets(undefined), { pump: 0, glitch: 0, jitter: 0 });
  assert.ok(marketTargets("dumping", true).glitch < 0.5);
  assert.equal(marketTargets("choppy", true).jitter, 0);
});

test("glitch bursts stay below 3 Hz and short, and stop when the level drops", () => {
  let seed = 1; const rng = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const b = createBurster(rng);
  const starts = []; let on = false, onFor = 0, maxOn = 0;
  for (let t = 0; t < 60; t += 1 / 60) {
    const s = b.tick(t, 1);
    assert.ok(s >= 0 && s <= 1);
    if (s > 0 && !on) { starts.push(t); on = true; onFor = 0; }
    if (s > 0) { onFor += 1 / 60; maxOn = Math.max(maxOn, onFor); }
    if (s === 0) on = false;
  }
  assert.ok(starts.length > 20, "bursts happen");
  for (let i = 1; i < starts.length; i++) assert.ok(starts[i] - starts[i - 1] >= BURST_GAP[0] - 1 / 60, "gap " + (starts[i] - starts[i - 1]));
  assert.ok(starts.length / 60 < 3, "less than 3 bursts per second");
  assert.ok(maxOn < 0.25, "bursts are short: " + maxOn);
  let calm = 0; for (let t = 60; t < 70; t += 1 / 60) calm += b.tick(t, 0);
  assert.equal(calm, 0);
});

test("wrapText wraps the inner line at word boundaries and ends a cut line with an ellipsis, never mid-word", () => {
  const fits = n => s => s.length <= n;
  assert.deepEqual(wrapText("giusto, un pezzo di pane", fits(40), 1), ["giusto, un pezzo di pane"]);
  assert.deepEqual(wrapText("giusto, un pezzo di pane", fits(12), 2), ["giusto, un", "pezzo di…"]);
  assert.deepEqual(wrapText("giusto, un pezzo di pane e poi a casa", fits(16), 2), ["giusto, un pezzo", "di pane e poi a…"]);
  assert.deepEqual(wrapText("  spaced   out  ", fits(20), 2), ["spaced out"]);
  assert.deepEqual(wrapText("", fits(20), 2), []); assert.deepEqual(wrapText(null, fits(20), 2), []);
  assert.deepEqual(wrapText("abcdefghijklmnop", fits(6), 1), ["abcdef"]);               // an overlong word is cut, not squeezed
  const two = wrapText("uno due tre quattro cinque sei sette otto nove dieci undici", fits(14), 2);
  assert.equal(two.length, 2);
  assert.ok(two[1].endsWith("…") && two.every(l => l.length <= 14));
  assert.ok(!/\S…$/.test(two[1]) || two[1].replace("…", "").split(" ").every(w => "uno due tre quattro cinque sei sette otto nove dieci undici".split(" ").includes(w)), "cut only between words");
});
