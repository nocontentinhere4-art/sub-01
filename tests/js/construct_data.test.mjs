// Unit tests for web/construct/data.js (the construct's city built from the brain data).
// Run: node --test tests/js/*.test.mjs   (the "three" import resolves to web/vendor/three via three-hooks.mjs)
import test from "node:test";
import assert from "node:assert/strict";
import { register } from "node:module";
import { readFileSync } from "node:fs";

register("./three-hooks.mjs", import.meta.url);
const { buildBrainData, loadBrainData, pointAt, PLACE_ROLE, FIBRES } = await import("../../web/construct/data.js");

const web = new URL("../../web/", import.meta.url);
const buf = f => { const b = readFileSync(new URL(f, web)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const raw = { brain: JSON.parse(readFileSync(new URL("brain.json", web), "utf8")), meta: JSON.parse(readFileSync(new URL("fibres.json", web), "utf8")),
  fibres: buf("fibres.bin"), ends: buf("fibres_ends.bin") };
// every place in life.py PLACES
const lifeSrc = readFileSync(new URL("../life.py", web), "utf8");
const placesBlock = /PLACES = \{([\s\S]*?)\n\}/.exec(lifeSrc)[1];
const LIFE_PLACES = [...placesBlock.matchAll(/"(\w+)":/g)].map(m => m[1]);

const t0 = Date.now();
const low = buildBrainData(raw, "low");
const buildMs = Date.now() - t0;

test("life.py places were parsed", () => { assert.ok(LIFE_PLACES.length >= 14, LIFE_PLACES.join(",")); });

test("one district per brain region, no NaN, deterministic", () => {
  assert.equal(low.districts.length, raw.brain.nodes.length);
  for (const d of low.districts) for (const v of [d.pos.x, d.pos.y, d.pos.z]) assert.ok(Number.isFinite(v), d.name);
  const again = buildBrainData(raw, "medium");
  low.districts.forEach((d, i) => assert.ok(d.pos.distanceTo(again.districts[i].pos) < 1e-9, d.name));
  assert.ok(buildMs < 5000, `build took ${buildMs} ms`);
});

test("districts do not overlap and keep the real layout", () => {
  let minD = Infinity;
  const D = low.districts;
  for (let i = 0; i < D.length; i++) for (let j = i + 1; j < D.length; j++)
    minD = Math.min(minD, Math.hypot(D[i].pos.x - D[j].pos.x, D[i].pos.z - D[j].pos.z));
  assert.ok(minD > 0.8 * 7.5 * low.scale, `min spacing ${minD}`);
  const n = raw.brain.nodes;
  // left hemisphere on the -x side, frontal regions in front (-z) of occipital ones
  const L = D.filter(d => n[d.i].name.startsWith("LH_")), R = D.filter(d => n[d.i].name.startsWith("RH_"));
  assert.ok(L.filter(d => d.pos.x < 0).length / L.length > 0.9);
  assert.ok(R.filter(d => d.pos.x > 0).length / R.length > 0.9);
  const vis = D.filter(d => d.group === "visual"), pfc = D.filter(d => /PFC/.test(d.name));
  const mz = a => a.reduce((s, d) => s + d.pos.z, 0) / a.length;
  assert.ok(mz(pfc) < mz(vis));
  // deep nuclei stay inside the city
  const deep = D.filter(d => /Thalamus|Caudate|Putamen|Accumbens/.test(d.name));
  for (const d of deep) assert.ok(Math.hypot(d.pos.x, d.pos.z) < 0.6 * low.radius, d.name);
});

test("roads: real fibres subsampled per quality, finite, labelled", () => {
  const r = low.roads;
  assert.ok(r.fibres > 0 && r.fibres <= FIBRES.low);
  assert.equal(r.positions.length, r.segments * 6);
  assert.equal(r.pairs.length, r.segments * 4);
  for (let k = 0; k < r.positions.length; k++) assert.ok(Number.isFinite(r.positions[k]));
  for (let k = 0; k < r.pairs.length; k++) assert.ok(r.pairs[k] >= 0 && r.pairs[k] < low.districts.length);
  assert.ok(low.graph.edges.length > 1000);
});

test("roles and places", () => {
  const n = raw.brain.nodes;
  assert.equal(n[low.districtOf("home")].group, "default");
  assert.match(n[low.districtOf("reward")].name, /Accumbens|Caudate|Putamen/);
  assert.equal(low.districtOf("bakery"), low.districtOf("reward"));
  assert.match(n[low.districtOf("park")].name, /Hippocampus/);
  assert.match(n[low.districtOf("fear")].name, /Amygdala/);
  for (const p of LIFE_PLACES) {
    assert.ok(p in PLACE_ROLE, `PLACE_ROLE misses ${p}`);
    const d = low.placeDistrict(p);
    if (p.startsWith("street")) assert.equal(d, null, p);
    else assert.ok(Number.isInteger(d) && d >= 0, p);
  }
  for (const p of ["bed", "window", "table", "desk", "door_in", "door_out"]) assert.equal(low.districts[low.placeDistrict(p)].role, "home", p);
  for (const p of ["bakery_door", "bakery_in", "counter"]) assert.equal(low.placeDistrict(p), low.districtOf("reward"), p);
  for (const p of ["park_gate", "bench"]) assert.equal(low.placeDistrict(p), low.districtOf("park"), p);
  assert.equal(low.placeDistrict(undefined), null);
});

test("pathBetween home -> reward follows fibres continuously", () => {
  const a = low.districtOf("home"), b = low.districtOf("reward");
  const path = low.pathBetween(a, b);
  assert.ok(path.length > 10);
  assert.ok(path[0].distanceTo(low.districts[a].pos) < 1e-6);
  assert.ok(path.at(-1).distanceTo(low.districts[b].pos) < 1e-6);
  assert.equal(path.hops[0], a); assert.equal(path.hops.at(-1), b);
  let maxStep = 0;
  for (let k = 1; k < path.length; k++) {
    for (const v of [path[k].x, path[k].y, path[k].z]) assert.ok(Number.isFinite(v));
    maxStep = Math.max(maxStep, path[k].distanceTo(path[k - 1]));
    assert.ok(path.lengths[k] >= path.lengths[k - 1]);
  }
  assert.ok(maxStep < 6, `max step ${maxStep}`);
  assert.ok(path.total >= path[0].distanceTo(path.at(-1)));
  const mid = pointAt(path, 0.5);
  assert.ok(Number.isFinite(mid.x));
  assert.ok(pointAt(path, 0).distanceTo(path[0]) < 1e-6 && pointAt(path, 1).distanceTo(path.at(-1)) < 1e-6);
  // hops are real bundles
  for (let h = 0; h + 1 < path.hops.length; h++) assert.ok(low.graph.adj[path.hops[h]].some(x => x.j === path.hops[h + 1]));
  assert.equal(low.pathBetween(a, b), path, "cached");
  // every place-to-place walk of life.py resolves
  for (const g of ["park", "fear"]) assert.ok(low.pathBetween(a, low.districtOf(g)).length > 2);
  assert.equal(low.pathBetween(a, a).total, 0);
});

test("loadBrainData caches the fetch", async () => {
  let calls = 0;
  const fetch = async f => { calls++; const name = f.replace(/^.*\//, "");
    const body = name.endsWith(".json") ? JSON.parse(readFileSync(new URL(name, web), "utf8")) : buf(name);
    return { ok: true, json: async () => body, arrayBuffer: async () => body }; };
  const a = await loadBrainData({ name: "low" }, { fetch, base: "/t/" });
  const b = await loadBrainData("low", { fetch, base: "/t/" });
  await loadBrainData("medium", { fetch, base: "/t/" });
  assert.equal(a, b);
  assert.equal(calls, 4);
});
