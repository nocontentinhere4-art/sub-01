// The pure parts of web/room/mood.js, window_view.js's dayPhase and web/room/mood_arrange.js, run in node by tests/test_mood.py (no WebGL here: createMood
// is never called). The day's four weights (sum, range, named hours, continuity), the hour arithmetic (hourDelta, fmtHour),
// the lamps by the hour, the visitor's choices in storage (defaults on any error, round trip, unknown ids, the key), and the
// swatch groups and looks. Prints one JSON line; the raw values are returned so the Python side states the expectations.
import {STORE_KEY, GROUPS, LOOKS, LAMPS, hourDelta, fmtHour, lampsByHour, loadChoice, saveChoice} from "../../web/room/mood.js";
import {dayPhase, PHASES} from "../../web/room/window_view.js";
import {spotOK, loadArrange, saveArrange, TYPES, MAX_ITEMS, MAX_LAMPS, BOUNDS, KEEP_FREE, PATH_CLEAR, STAND_CLEAR, ARRANGE_KEY} from "../../web/room/mood_arrange.js";

const out = {};
const KEYS = ["morning", "noon", "evening", "night"];

// dayPhase over one day in 0.25 h steps, 0..24 inclusive
const steps = [];
for (let k = 0; k <= 96; k++) steps.push(k * 0.25);
const weightsOk = [];
let maxSum = 0, minW = Infinity, maxW = -Infinity;
for (const h of steps) {
  const w = dayPhase(h);
  const sum = KEYS.reduce((a, k) => a + w[k], 0);
  maxSum = Math.max(maxSum, Math.abs(sum - 1));
  for (const k of KEYS) { minW = Math.min(minW, w[k]); maxW = Math.max(maxW, w[k]); }
  weightsOk.push(KEYS.every(k => Number.isFinite(w[k]) && w[k] >= 0 && w[k] <= 1) && PHASES.includes(w.name));
}
let maxStep = 0, maxStepAt = null;
for (let i = 1; i < steps.length; i++) {
  const a = dayPhase(steps[i - 1]), b = dayPhase(steps[i]);
  for (const k of KEYS) {
    const d = Math.abs(b[k] - a[k]);
    if (d > maxStep) { maxStep = d; maxStepAt = steps[i]; }
  }
}
out.phase = {
  steps: steps.length,
  all_weights_ok: weightsOk.every(Boolean),
  min_weight: minW, max_weight: maxW,
  max_sum_error: maxSum,
  names: {h8: dayPhase(8).name, h12_5: dayPhase(12.5).name, h18: dayPhase(18).name, h1: dayPhase(1).name, h23: dayPhase(23).name},
  max_step_per_quarter_hour: maxStep,
  max_step_at_h: maxStepAt,
};

// hourDelta: the short way round the clock
out.hourDelta = {a: hourDelta(23, 1), b: hourDelta(1, 23), c: hourDelta(6, 18), d: hourDelta(10, 10)};

// fmtHour
out.fmtHour = {h0: fmtHour(0), h13_5: fmtHour(13.5), h24: fmtHour(24), hm1: fmtHour(-1)};

// lampsByHour
const lamp = {};
for (const h of [12, 19, 0.0, 3, 16]) lamp[String(h)] = lampsByHour(h);
const lampVals = Object.values(lamp);
out.lamps = {values: lamp, all_in_range: lampVals.every(v => Number.isFinite(v) && v >= 0 && v <= 1)};

// storage: fake objects passed explicitly (mood.js only reaches for localStorage when none is given)
const throwing = {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }};
const DEFAULTS = {floor: "oak", wall: "chalk", bed: "indigo", soft: "mustard", lamps: "auto", rays: true, open: true};
const bad = {getItem() { throw new Error("blocked"); }};
out.storage = {};
out.storage.a_getItem_throws = loadChoice(bad);
let setRet, setThrew = false;
try { setRet = saveChoice({...DEFAULTS}, throwing); } catch (e) { setThrew = true; }
out.storage.b_setItem_throws = {ret: setRet, threw: setThrew};

const mapStore = () => {
  const m = new Map();
  return {
    m,
    getItem: k => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
  };
};
const rt = mapStore();
const saved = {floor: "walnut", wall: "clay", bed: "rust", soft: "terra", lamps: "on", rays: false, open: false};
const savedRet = saveChoice(saved, rt);
out.storage.c_round_trip = {ret: savedRet, loaded: loadChoice(rt), expected: saved};
out.storage.c_keys = [...rt.m.keys()];

const garbage = mapStore(); garbage.m.set(STORE_KEY, "{not json");
out.storage.d_garbage = loadChoice(garbage);

const unknown = mapStore(); unknown.m.set(STORE_KEY, JSON.stringify({floor: "marble", lamps: "disco"}));
out.storage.e_unknown = loadChoice(unknown);

out.storage.f_key = {STORE_KEY, used: [...rt.m.keys()].every(k => k === STORE_KEY) && rt.m.size === 1};
out.storage.defaults = DEFAULTS;

// GROUPS: five variants each, unique ids, the first as built, every other one with a colour for each material, #rrggbb
const HEX = /^#[0-9a-fA-F]{6}$/;
const gp = {};
for (const [g, def] of Object.entries(GROUPS)) {
  const problems = [];
  const ids = def.variants.map(v => v.id);
  if (def.variants.length !== 5) problems.push(`${g}: ${def.variants.length} variants`);
  if (new Set(ids).size !== ids.length) problems.push(`${g}: duplicate ids`);
  if (!def.mats || def.mats.length === 0) problems.push(`${g}: no mats`);
  def.variants.forEach((v, i) => {
    if (i === 0 && v.c !== undefined) problems.push(`${g}: first variant ${v.id} has c`);
    if (i > 0) {
      if (!v.c || typeof v.c !== "object") problems.push(`${g}: ${v.id} has no c`);
      else for (const m of def.mats) {
        if (!(m in v.c)) problems.push(`${g}: ${v.id} has no c.${m}`);
      }
      for (const [m, col] of Object.entries(v.c || {})) if (!HEX.test(col)) problems.push(`${g}: ${v.id} c.${m}=${col}`);
    }
    const sw = Array.isArray(v.sw) ? v.sw : [v.sw];
    for (const col of sw) if (!HEX.test(col)) problems.push(`${g}: ${v.id} sw=${col}`);
  });
  gp[g] = {count: def.variants.length, ids, problems};
}
out.groups = gp;

// LOOKS: every set refers to existing variant ids
const lp = [];
for (const look of LOOKS) {
  for (const [g, id] of Object.entries(look.set)) {
    if (!GROUPS[g]) { lp.push(`${look.id}: no group ${g}`); continue; }
    if (!GROUPS[g].variants.some(v => v.id === id)) lp.push(`${look.id}: ${g}.${id} missing`);
  }
}
out.looks = {count: LOOKS.length, problems: lp};
out.lamp_options = LAMPS;

// ---- the arrange layer (web/room/mood_arrange.js): pure functions only ----
// The room's routes, furniture and places, copied from web/room.html (NODES, LINKS, BLOCK are compared with the file's text
// by tests/test_mood.py; ANCHOR as it is there, with F = 0.16 and Math.PI). Only positions matter for the stands.
// The arrange layer's checks: spotOK never accepts a spot that breaks a rule (rechecked here from the geometry), skipBlock
// leaves out exactly one box, loadArrange / saveArrange survive bad storage and keep to MAX_ITEMS and finite numbers.
const F = 0.16;
const NODES = {bs:[-0.36, -0.18], ds:[-0.62, -0.35], w:[0.15, -0.12], c:[0.45, -0.35], m:[0.35, 0.05], d:[1.22, -0.92], f:[0.40, 0.75],
  sl:[-1.10, 0.03], g:[-0.62, 0.03], bn:[-0.17, -0.66]};
const LINKS = [["bs","ds"], ["bs","w"], ["ds","w"], ["w","m"], ["w","c"], ["m","c"], ["c","d"], ["m","d"], ["w","f"], ["m","f"], ["bs","g"], ["g","sl"], ["w","g"], ["bs","bn"], ["ds","bn"], ["c","bn"]];
const BLOCK = [[-1.90, 0.05, 0.25, 1.50], [-1.86, -0.36, -1.45, -0.80], [-1.42, -0.84, -0.88, -0.30], [-0.12, 0.32, -1.45, -1.17],
  [0.45, 0.93, -1.45, -0.97], [-1.90, -1.42, -0.60, -0.12]];
const ANCHOR = {
  desk:    {seat:[-1.12, 0.87, -0.56], r:-2.85, stand:[-0.68, -0.55]},
  bedlie:  {p:[-0.93, -0.095, 0.89], r:Math.PI / 2},
  bedside: {seat:[-0.40, 1.06, 0.36], r:Math.PI, stand:[-0.36, -0.18]},
  door:    {p:[1.22, F, -0.92], r:2.2},
  window:  {p:[0.18, F, -0.15], r:-Math.PI / 2},
  middle:  {p:[0.35, F, 0.05], r:0.6},
  sill:    {p:[-1.56, F, -0.02], r:-Math.PI / 2},
  doorway: {p:[1.76, F, -0.98], r:-3.05},
  deskside:{p:[-0.30, F, -0.40], r:Math.PI},
  bin:     {p:[-0.24, F, -0.98], r:-2.23},
};
const nav = {BLOCK, NODES, LINKS, stands: Object.values(ANCHOR).map(a => a.stand || (a.p && [a.p[0], a.p[2]])).filter(Boolean)};
const arr = {stands: nav.stands.length};

// the scan grid: every 0.05 m over BOUNDS, both ends in
const xs = [], zs = [];
for (let i = 0; BOUNDS.x0 + i * 0.05 <= BOUNDS.x1 + 1e-9; i++) xs.push(BOUNDS.x0 + i * 0.05);
for (let i = 0; BOUNDS.z0 + i * 0.05 <= BOUNDS.z1 + 1e-9; i++) zs.push(BOUNDS.z0 + i * 0.05);
arr.grid = [xs.length, zs.length];

// independent geometry (not spotOK's): distance from a point to a segment, to a box, to a point
function segDist(px, pz, a, b){
  const vx = b[0] - a[0], vz = b[1] - a[1], L2 = vx * vx + vz * vz;
  const t = L2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - a[0]) * vx + (pz - a[1]) * vz) / L2));
  return Math.hypot(a[0] + t * vx - px, a[1] + t * vz - pz);
}
function boxDist(px, pz, [x0, x1, z0, z1]){
  return Math.hypot(Math.max(x0 - px, 0, px - x1), Math.max(z0 - pz, 0, pz - z1));
}
// every rule a spot of radius r must keep, listed by name when broken (skipBlock: the BLOCK index left out, as spotOK's)
function breaches(x, z, r, skipBlock = -1){
  const out = [];
  if (x - r < BOUNDS.x0 || x + r > BOUNDS.x1 || z - r < BOUNDS.z0 || z + r > BOUNDS.z1) out.push("bounds");
  BLOCK.forEach((b, j) => { if (j !== skipBlock && boxDist(x, z, b) < r) out.push("block" + j); });
  KEEP_FREE.forEach((b, j) => { if (boxDist(x, z, b) < r) out.push("keep" + j); });
  for (const [p, q] of LINKS) if (segDist(x, z, NODES[p], NODES[q]) < r + PATH_CLEAR) out.push("path " + p + q);
  for (const k of Object.keys(NODES)) if (Math.hypot(x - NODES[k][0], z - NODES[k][1]) < r + PATH_CLEAR) out.push("node " + k);
  nav.stands.forEach((s, j) => { if (Math.hypot(x - s[0], z - s[1]) < r + STAND_CLEAR) out.push("stand" + j); });
  return out;
}

// 1. no spot spotOK accepts breaks a rule (every TYPES radius, every grid point), and how many spots are accepted per type
arr.scan = {};
arr.flagged = 0;                                            // sanity: the independent check does flag spots (every grid point, lamp radius)
for (const x of xs) for (const z of zs) if (breaches(x, z, TYPES.lamp.r).length) arr.flagged++;
for (const [type, T] of Object.entries(TYPES)) {
  let accepted = 0, breached = 0, first = null;
  for (const x of xs) for (const z of zs) {
    if (!spotOK(x, z, T.r, nav)) continue;
    accepted++;
    const br = breaches(x, z, T.r);
    if (br.length) { breached++; if (!first) first = {x, z, br}; }
  }
  arr.scan[type] = {r: T.r, accepted, breached, first};
}

// 2. skipBlock: for each BLOCK index k (and -1), what spotOK accepts with that box left out
arr.skip = {};
for (let k = -1; k < BLOCK.length; k++) {
  let accepted = 0, breachedWithout = 0, notMonotone = 0, newlyAccepted = 0, newlyOutsideBox = 0, newlyOtherRule = 0;
  for (const T of Object.values(TYPES)) for (const x of xs) for (const z of zs) {
    const acc = spotOK(x, z, T.r, nav, [], k);
    const accAll = spotOK(x, z, T.r, nav, [], -1);
    if (acc) { accepted++; if (breaches(x, z, T.r, k).length) breachedWithout++; }
    if (accAll && !acc) notMonotone++;
    if (acc && !accAll && k >= 0) {
      newlyAccepted++;
      const b = BLOCK[k], pad = T.r + 0.03;               // the box grown by the spot's radius and spotOK's 3 cm margin
      if (!(x > b[0] - pad && x < b[1] + pad && z > b[2] - pad && z < b[3] + pad)) newlyOutsideBox++;
      // the only rule that stopped it was BLOCK k: nothing else breaks at this spot
      if (breaches(x, z, T.r, k).length) newlyOtherRule++;
    }
  }
  arr.skip[k] = {accepted, breachedWithout, notMonotone, newlyAccepted, newlyOutsideBox, newlyOtherRule};
}

// 3. NaN coordinates, and an `others` overlap
arr.nan = [spotOK(NaN, 0, 0.2, nav), spotOK(0, NaN, 0.2, nav), spotOK(Infinity, 0, 0.2, nav), spotOK(0, -Infinity, 0.2, nav)];
let w = null;
for (const x of xs) { for (const z of zs) if (spotOK(x, z, 0.2, nav)) { w = [x, z]; break; } if (w) break; }
arr.others = {
  witness: w,
  free: w ? spotOK(w[0], w[1], 0.2, nav) : false,
  near: w ? spotOK(w[0], w[1], 0.2, nav, [[w[0] + 0.3, w[1], 0.2]]) : null,   // 0.3 m away, radii 0.2 + 0.2: overlaps
  far: w ? spotOK(w[0], w[1], 0.2, nav, [[w[0] + 0.6, w[1], 0.2]]) : null,   // 0.6 m away: clear
};

// 4. loadArrange / saveArrange
const throwingGet = {getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }};
const throwingSet = {getItem: () => null, setItem() { throw new Error("full"); }};
const storeWith = raw => { const s = mapStore(); s.m.set(ARRANGE_KEY, raw); return s; };
arr.load = {};
arr.load.throwing_get = loadArrange(throwingGet);
arr.load.garbage = loadArrange(storeWith("{not json"));
arr.load.null_json = loadArrange(storeWith("null"));
arr.load.no_storage = loadArrange(mapStore());
arr.load.unknown_types = loadArrange(storeWith(JSON.stringify({items: [["sofa", 1, 1, 0], ["lamp", 0.5, 0.5, 0], ["bogus", 0, 0, 0]]})));
arr.load.truncated = loadArrange(storeWith(JSON.stringify({items: Array.from({length: 15}, (_, i) => ["plant", i * 0.1, 0, 0])})));
arr.load.non_finite = loadArrange(storeWith('{"plant":[1e999,0,0],"items":[["plant","1",0,0],["plant",null,0,0],["plant",1e999,0,0],["books",0.2,0.3,0]]}'));
arr.load.plant_bad = loadArrange(storeWith('{"plant":[0.1,0.2,"x"],"items":[]}'));
arr.load.plant_extra = loadArrange(storeWith('{"plant":[0.1,0.2,0.3,9],"items":[]}'));
const ROUND = {plant: [-1.66, -0.36, 0.5], items: [["lamp", 0.5, 0.5, 1.57], ["books", -1, 0.2, 0], ["pouf", 0.25, -0.75, 3.14]]};
const arrRt = mapStore();
arr.round = {ret: saveArrange(ROUND, arrRt), loaded: loadArrange(arrRt), keys: [...arrRt.m.keys()], expected: ROUND};
arr.save_throws = (() => { try { return saveArrange(ROUND, throwingSet); } catch (e) { return "threw"; } })();
arr.key = ARRANGE_KEY;
arr.limits = {MAX_ITEMS, MAX_LAMPS};

out.arrange = arr;
console.log(JSON.stringify(out));
