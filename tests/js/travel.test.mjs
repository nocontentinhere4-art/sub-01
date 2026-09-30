// Unit tests for web/construct/travel.js: path sampling math, tick smoothing, walks along the real fibre roads.
// Run: node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { register } from "node:module";
import { readFileSync } from "node:fs";

register("./three-hooks.mjs", import.meta.url);
const THREE = await import("three");
const { buildBrainData } = await import("../../web/construct/data.js");
const T = await import("../../web/construct/travel.js");

const web = new URL("../../web/", import.meta.url);
const buf = f => { const b = readFileSync(new URL(f, web)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const raw = { brain: JSON.parse(readFileSync(new URL("brain.json", web), "utf8")), meta: JSON.parse(readFileSync(new URL("fibres.json", web), "utf8")),
  fibres: buf("fibres.bin"), ends: buf("fibres_ends.bin") };
const data = buildBrainData(raw, "low");

const fakeControls = () => ({ enabled: false, target: new THREE.Vector3(), update() {}, addEventListener() {}, touches: {}, domElement: { addEventListener() {}, style: {} } });
const line = (...pts) => { const p = pts.map(v => new THREE.Vector3(...v)); p.lengths = new Float32Array(p.length); for (let k = 1; k < p.length; k++) p.lengths[k] = p.lengths[k - 1] + p[k].distanceTo(p[k - 1]); p.total = p.lengths[p.length - 1]; return p; };

test("trimRange leaves a station at both ends and never collapses on short roads", () => {
  const [a, b] = T.trimRange(900);
  assert.ok(Math.abs(a * 900 - T.STANDOFF) < 1e-6 && Math.abs((1 - b) * 900 - T.STANDOFF) < 1e-6);
  const [c, d] = T.trimRange(60);                                    // short: at most 22% on each side
  assert.ok(c <= 0.22 + 1e-9 && d >= 0.78 - 1e-9 && d > c);
  assert.deepEqual(T.trimRange(0), [0, 1]);
});

test("walkSample: position at fraction f along a polyline, look-ahead in the direction of travel", () => {
  const path = line([0, 0, 0], [100, 0, 0], [100, 0, 100]);        // total 200
  const p = new THREE.Vector3(), ahead = new THREE.Vector3();
  T.walkSample(path, 0.25, [0, 1], 10, p, ahead);                   // 50 units along
  assert.ok(p.distanceTo(new THREE.Vector3(50, 0, 0)) < 1e-4);
  assert.ok(ahead.distanceTo(new THREE.Vector3(60, 0, 0)) < 1e-4);
  T.walkSample(path, 0.75, [0, 1], 10, p, ahead);                   // 150 -> 50 into the second leg
  assert.ok(p.distanceTo(new THREE.Vector3(100, 0, 50)) < 1e-4);
  T.walkSample(path, 0.75, [0, 1], 10, p, ahead, -1);               // walking back: ahead is behind on the polyline
  assert.ok(ahead.distanceTo(new THREE.Vector3(100, 0, 40)) < 1e-4);
  T.walkSample(path, 1, [0.1, 0.9], 10, p, ahead);                  // trimmed range: f = 1 is at 90 %
  assert.ok(p.distanceTo(new THREE.Vector3(100, 0, 80)) < 1e-4);
  T.walkSample(path, 0, [0.1, 0.9], 10, p, ahead);
  assert.ok(p.distanceTo(new THREE.Vector3(20, 0, 0)) < 1e-4);
});

test("wrapAngle / yawOf / Damped", () => {
  assert.ok(Math.abs(T.wrapAngle(3 * Math.PI) - Math.PI) < 1e-9 || Math.abs(T.wrapAngle(3 * Math.PI) + Math.PI) < 1e-9);
  assert.ok(Math.abs(T.wrapAngle(0.2 - 6.2) - (0.2 - 6.2 + 2 * Math.PI)) < 1e-9);
  assert.equal(T.yawOf(0, -1), 0);                                   // forward is -z
  assert.ok(Math.abs(T.yawOf(1, 0) - Math.PI / 2) < 1e-9);
  const d = new T.Damped(1).set(0);
  for (let i = 0; i < 600; i++) d.step(1, 0.3, 1 / 60);
  assert.ok(Math.abs(d.x[0] - 1) < 1e-3);
  let over = 0; const e = new T.Damped(1).set(0);
  for (let i = 0; i < 600; i++) { e.step(1, 0.3, 1 / 60); over = Math.max(over, e.x[0] - 1); }
  assert.ok(over < 1e-3, "critically damped: no overshoot for a still target");
  const a = new T.Damped(1).set(3.0);                                // angular: takes the short way over +-pi
  for (let i = 0; i < 300; i++) a.step(-3.0, 0.3, 1 / 60, true);
  assert.ok(Math.abs(T.wrapAngle(a.x[0] + 3.0)) < 1e-2);
});

test("ProgressTracker: 20 Hz quantised ticks become a smooth monotonic glide at the true speed", () => {
  const tr = new T.ProgressTracker(), speed = 1 / 40;                // a 40 s walk
  const out = []; let now = 0, next = 0, sent = 0;
  for (let f = 0; f < 60 * 30; f++) {
    now = f / 60;
    if (now >= next) { next += 0.05 + (((f * 7919) % 13) / 13 - 0.5) * 0.02; sent = Math.round(now * speed * 1000) / 1000; tr.push(sent, now); }   // jittered 20 Hz, 0.001 steps
    out.push(tr.update(1 / 60, now));
  }
  const v = out.map((x, i) => (i ? (x - out[i - 1]) * 60 : 0)).slice(120);   // speed per frame after warm-up
  const mean = v.reduce((s, x) => s + x, 0) / v.length;
  assert.ok(Math.abs(mean - speed) / speed < 0.03, `mean speed ${mean} vs ${speed}`);
  const sd = Math.sqrt(v.reduce((s, x) => s + (x - mean) ** 2, 0) / v.length);
  assert.ok(sd / speed < 0.12, `speed jitter ${sd / speed}`);
  assert.ok(v.every(x => x > 0), "never steps back");
  assert.ok(Math.abs(out[out.length - 1] - (29.98 * speed)) < 0.02, "lag stays small");
});

test("ProgressTracker: reset, clamping, stalled server", () => {
  const tr = new T.ProgressTracker();
  tr.reset(0.5, 10);
  assert.equal(tr.update(1 / 60, 10), 0.5);
  tr.push(0.99, 10.1); tr.push(1.2, 10.2);
  for (let i = 0; i < 300; i++) tr.update(1 / 60, 10.2 + i / 60);
  assert.ok(tr.value <= 1);
  tr.reset(0, 20);
  tr.push(0.1, 20.05); tr.push(0.12, 20.45);
  const p1 = tr.predict(25);                                          // no tick for 4.5 s: extrapolation is capped
  assert.ok(p1 <= 0.12 + tr.rate * 0.4 + 1e-9);
});

test("the real road home -> reward district: smooth, long enough, ends inside the stations", () => {
  const h = data.districtOf("home"), r = data.districtOf("reward");
  const path = data.pathBetween(h, r);
  assert.ok(path.total > 4 * T.STANDOFF);
  const [u0, u1] = T.trimRange(path.total);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), q = new THREE.Vector3();
  T.walkSample(path, 0, [u0, u1], T.LOOK_AHEAD, a, q);
  T.walkSample(path, 1, [u0, u1], T.LOOK_AHEAD, b, q);
  assert.ok(Math.abs(a.distanceTo(data.districts[h].pos) - T.STANDOFF) < 4, "start station is STANDOFF from home");
  assert.ok(Math.abs(b.distanceTo(data.districts[r].pos) - T.STANDOFF) < 4, "end station is STANDOFF from the reward district");
  let prev = a.clone(), maxStep = 0;
  for (let k = 1; k <= 2000; k++) { T.walkSample(path, k / 2000, [u0, u1], T.LOOK_AHEAD, q, new THREE.Vector3()); maxStep = Math.max(maxStep, q.distanceTo(prev)); prev.copy(q); }
  assert.ok(maxStep < path.total / 2000 * 1.5 + 1e-6, `constant-speed sampling (${maxStep})`);
});

function sim({ life, frames, env = {}, cam = new THREE.PerspectiveCamera(), ctl = fakeControls() }) {
  const tr = T.createTravel(cam, ctl, data, {});
  tr.setView("first");
  const pos = [], states = [];
  for (let f = 0; f < frames; f++) {
    const now = f / 60, L = life(now);
    tr.update(1 / 60, L, { stage: "AWAKE", groupRel: {}, follow: true, ...env });
    pos.push(cam.position.clone()); states.push(tr.state());
  }
  return { tr, cam, ctl, pos, states };
}

test("a walk to the reward district: camera follows the fibre road smoothly (no jitter at 20 Hz ticks)", () => {
  const dur = 40, route = ["bed", "door_in", "door_out", "street_home", "street_bakery", "bakery_door", "bakery_in", "counter"];
  let last = null, lastP = -1;
  const life = now => {
    const p = Math.min(1, Math.round(Math.max(0, now - 1) / dur * 1000) / 1000);
    if (Math.floor(now * 20) !== last) { last = Math.floor(now * 20); lastP = p; }           // a new snapshot object at 20 Hz
    return { walking: now - 1 < dur && now >= 1, route, progress: lastP, place: now - 1 < dur ? "bed" : "counter", activity: "buy_bread", _t: last };
  };
  let cache = null;
  const lifeObj = now => { const k = Math.floor(now * 20); if (!cache || cache._t !== k) cache = { ...life(now) }; return cache; };
  const { pos, states, tr } = sim({ life: lifeObj, frames: 60 * 45 });
  const h = data.districtOf("home"), r = data.districtOf("reward");
  const path = data.pathBetween(h, r), [u0, u1] = T.trimRange(path.total);
  const endStation = new THREE.Vector3(); THREE.Vector3.prototype.copy.call(endStation, data.pathBetween(h, r)[0]);
  T.walkSample(path, 1, [u0, u1], 1, endStation, new THREE.Vector3());
  assert.ok(states.some(s => s.mode === "walk"));
  // settles at the end station in front of the reward district (eye height above the road)
  const fin = pos[pos.length - 1];
  assert.ok(Math.hypot(fin.x - endStation.x, fin.z - endStation.z) < 3, `arrived ${fin.toArray()} vs ${endStation.toArray()}`);
  assert.equal(tr.state().district, r);
  // continuity: per-frame step is bounded by the walking speed, second difference (jitter) is tiny
  const speed = path.total / dur;
  let maxStep = 0, maxAcc = 0;
  for (let i = 2; i < pos.length; i++) {
    const s1 = pos[i].distanceTo(pos[i - 1]), s0 = pos[i - 1].distanceTo(pos[i - 2]);
    if (i > 60 * 3 && i < 60 * 40) { maxStep = Math.max(maxStep, s1); maxAcc = Math.max(maxAcc, Math.abs(s1 - s0)); }
  }
  assert.ok(maxStep < speed / 60 * 1.6, `step ${maxStep} vs ${speed / 60}`);
  assert.ok(maxAcc < speed / 60 * 0.25, `jitter ${maxAcc}`);
  // the camera never leaves the road by much
  let worst = 0;
  for (let i = 60 * 3; i < 60 * 40; i += 7) { let best = 1e9; for (let k = 0; k < path.length; k += 3) best = Math.min(best, Math.hypot(pos[i].x - path[k].x, pos[i].z - path[k].z)); worst = Math.max(worst, best); }
  assert.ok(worst < 6, `max distance from the road ${worst}`);
});

test("idle / lying / sleeping: stays in its district; no NaN; looks up when lying", () => {
  for (const [activity, place, pose, stage] of [["window", "window", "standing", "AWAKE"], ["phone", "bed", "lying_phone", "AWAKE"], ["sleep", "bed", "lying", "NREM"]]) {
    const { cam, pos, states } = sim({ life: () => ({ walking: false, route: [], progress: 0, place, activity, pose }), frames: 60 * 20, env: { stage } });
    for (const p of pos) for (const v of p.toArray()) assert.ok(Number.isFinite(v));
    const here = data.districts[data.placeDistrict(place)].pos;
    assert.ok(pos[pos.length - 1].distanceTo(here) < 80, `${activity} stays near its district`);
    const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion);
    if (activity !== "window") assert.ok(fwd.y > 0.5, `${activity} looks up at the sky (${fwd.y})`);
    assert.ok(states.every(s => s.district === data.districtOf("home") || data.districts[s.district].role === "home"));
  }
});

test("view switch blends the camera (no snap) and back; orbit enables the controls", () => {
  const cam = new THREE.PerspectiveCamera(), ctl = fakeControls();
  const tr = T.createTravel(cam, ctl, data, {});
  tr.setView("first");
  const life = { walking: false, route: [], progress: 0, place: "bed", activity: "window" };
  const env = { stage: "AWAKE", groupRel: {}, follow: true };
  for (let i = 0; i < 60; i++) tr.update(1 / 60, life, env);
  const fp = cam.position.clone();
  assert.equal(ctl.enabled, false);
  tr.setView("orbit");
  assert.equal(tr.view, "orbit");
  tr.update(1 / 60, life, env);
  assert.ok(cam.position.distanceTo(fp) < 5, "first frame of the transition hardly moves");
  let maxStep = 0, prev = cam.position.clone();
  for (let i = 0; i < 60 * 3; i++) { tr.update(1 / 60, life, env); maxStep = Math.max(maxStep, cam.position.distanceTo(prev)); prev.copy(cam.position); }
  assert.ok(maxStep < data.radius * 0.08, `no snap (${maxStep})`);
  assert.equal(ctl.enabled, true);
  assert.ok(cam.position.y > data.radius * 0.8, "overview is high above the city");
  tr.setView("first");
  assert.equal(ctl.enabled, false);
  for (let i = 0; i < 60 * 3; i++) tr.update(1 / 60, life, env);
  assert.ok(cam.position.distanceTo(tr.position) < 10 + T.EYE + 8, "back at SUB-01");
});
