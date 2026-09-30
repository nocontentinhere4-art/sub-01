// node --test tests/js/hud_util.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { topicsOf, checkNick, workspaceRows, kindColor, speechTag, metaLine, fold, tokens, WORKSPACE_CAPTION, HONESTY } from "../../web/world/hud_util.js";

const RULES = [
  { topic: "food / bread", networks: ["reward", "limbic"], words: ["bread", "pane", "mangi*", "hungry"] },
  { topic: "greetings / people", networks: ["default", "language"], words: ["hello", "ciao"] },
  { topic: "questions", networks: ["attention", "control"], words: ["who", "what", "come", "cosa"] },
];

test("topicsOf mirrors the server rule table (keywords, prefixes, accents, questions)", () => {
  assert.deepEqual(topicsOf("vai a comprare il PANE", RULES).map(t => t.topic), ["food / bread"]);
  assert.deepEqual(topicsOf("Mangio una mela", RULES).map(t => t.topic), ["food / bread"]);       // mangi* prefix
  assert.deepEqual(topicsOf("Cosa fai? ciao", RULES).map(t => t.topic), ["greetings / people", "questions"]);
  assert.deepEqual(topicsOf("is it sunny?", RULES).map(t => t.topic), ["questions"]);             // "?" anywhere
  assert.deepEqual(topicsOf("the bread is what I want", RULES).map(t => t.topic), ["food / bread"]); // "what" not first word
  assert.deepEqual(topicsOf("nothing relevant", RULES), []);
  assert.deepEqual(topicsOf("hello", null), []);
  assert.equal(fold("Perché città"), "perche citta");
  assert.deepEqual(tokens("don't stop, me-now"), ["don't", "stop", "me", "now"]);
});

test("checkNick: optional, <= 20 chars, latin letters/digits/space/_-, cannot imitate SUB-01", () => {
  assert.deepEqual(checkNick(""), { ok: true, nick: "", reason: null });
  assert.deepEqual(checkNick(null), { ok: true, nick: "", reason: null });
  assert.equal(checkNick("  anna   maria ").nick, "anna maria");
  assert.ok(checkNick("Zoë_9-x").ok);
  assert.ok(!checkNick("a".repeat(21)).ok);
  assert.ok(!checkNick("<b>hi</b>").ok);
  assert.ok(!checkNick("名前").ok);
  assert.ok(!checkNick("Sub-01").ok);
  assert.ok(!checkNick("SUB 01").ok);
  assert.ok(!checkNick("SUB-O1").ok);
  assert.ok(!checkNick("admin").ok);
  assert.ok(checkNick("subway").ok);
});

test("workspaceRows sorts, caps, scales and marks the winner", () => {
  const mind = { winner: "b", candidates: [
    { id: "a", kind: "need", label: "hungry", salience: 0.5 }, { id: "b", kind: "chat", label: "msg", salience: 2 },
    { id: "c", kind: "market", label: "chart", salience: 1, gated: true }, null, { kind: "x" } ] };
  const r = workspaceRows(mind, 2);
  assert.deepEqual(r.map(x => x.id), ["b", "c"]);
  assert.equal(r[0].width, 1); assert.equal(r[1].width, 0.5);
  assert.ok(r[0].winner && !r[1].winner && r[1].gated);
  assert.deepEqual(workspaceRows(null), []);
  assert.deepEqual(workspaceRows({}), []);
});

test("small formatters and the approved wording", () => {
  assert.equal(kindColor("chat"), "#ff6a00"); assert.equal(kindColor("zzz"), "#9a9aae");
  assert.equal(speechTag("llm"), "generated"); assert.equal(speechTag("rule"), "rule"); assert.equal(speechTag(undefined), "rule");
  assert.equal(metaLine({ clock: "03:10", stage: "REM", debt: 1.234, woken: 2 }), "03:10 Rome · REM · sleep debt 1.2 h · woken 2x tonight");
  assert.match(WORKSPACE_CAPTION, /architecture inspired by theories of consciousness \(Global Workspace\)/);
  assert.match(WORKSPACE_CAPTION, /a model of brain activity, not a mind/);
  assert.match(HONESTY, /It is not a mind and it is not the person\.$/);
  // never claim it is conscious / alive
  for (const s of [WORKSPACE_CAPTION, HONESTY]) assert.ok(!/\b(is|are) (conscious|alive|sentient)\b/i.test(s));
});
