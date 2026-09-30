// Travel + views (travel stream): where SUB-01 is inside the construct and what the camera sees.
//
// createTravel(camera, controls, data, {scene}?) -> {update(dt, life, env), setView('first'|'orbit'), view, position, state()}
//   life   tick.life snapshot (+ stage) or null. While walking it carries route (life.py place names, start..goal) and
//          progress (0..1 of the walked distance, timed by life.py WALK_SPEED).
//   env    main.js env: stage, groupRel (group -> activity relative to the mean), follow, night ...
//
// First person (default): the camera rides at eye height on data.pathBetween(start district, goal district) - the real
//   fibre road - at life.progress. The 20 Hz server ticks are turned into a smooth glide (ProgressTracker: the recent
//   progress rate is extrapolated between ticks, then a critically damped follower removes the remaining steps). The
//   first and last STANDOFF units of a road are not driven: they are the "stations" in front of a district, where
//   SUB-01 stands looking at its towers (arrival settles exactly there, idle starts from there). Idle: slow
//   look-around, every now and then looking at the most active group of districts; lying (bed / phone): looks up at
//   the sky; asleep: slow drift. Drag (mouse / touch) looks around a little and springs back.
// Orbit: OrbitControls over the whole city, SUB-01 marked by an orange beacon with a tiny "SUB-01" tag, slow
//   auto-rotate while nobody touches it. Switching views blends the camera pose (no snap).
// It is a model of brain activity, not a mind.
import * as THREE from "three";
import { pointAt } from "./data.js";

export const EYE = 4.5;              // camera height above the road / ground (city units)
export const STANDOFF = 56;          // distance in front of a district where SUB-01 stands
export const LOOK_AHEAD = 30;        // look this far ahead along the road while walking
const BLEND_S = 1.5;                 // view switch duration
export const TOWER_R = 15;           // the camera keeps this far (xz) from the centre of a district it passes
export const MAX_SPEED = 54;         // city units / s: hard cap of the first-person camera (walks run at ~25-35)
const OFFSET_S = 1.75;               // a walk that starts away from its road blends in over this time
const FOLLOW = 0.6;                  // orbit: how far towards SUB-01 the view target sits

// ---------------- pure helpers (unit-tested in tests/js/travel.test.mjs) ----------------
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const wrapAngle = a => { a = (a + Math.PI) % (2 * Math.PI); if (a < 0) a += 2 * Math.PI; return a - Math.PI; };
export const yawOf = (dx, dz) => Math.atan2(dx, -dz);                       // camera forward = (sin yaw, ., -cos yaw)
const smooth01 = x => { x = clamp(x, 0, 1); return x * x * x * (x * (x * 6 - 15) + 10); };

/** Critically damped follower (no overshoot for a still target, C1-continuous, frame-rate independent). */
export class Damped {
  constructor(n = 1) { this.x = new Float64Array(n); this.v = new Float64Array(n); this.n = n; }
  set(...vals) { for (let k = 0; k < this.n; k++) { this.x[k] = vals[k] ?? 0; this.v[k] = 0; } return this; }
  step(target, smoothTime, dt, angular = false) {
    if (!(dt > 0)) return this;
    const omega = 2 / Math.max(1e-3, smoothTime), x = omega * dt, e = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
    const multi = Array.isArray(target) || ArrayBuffer.isView(target);
    for (let k = 0; k < this.n; k++) {
      let goal = multi ? target[k] : target;
      if (angular) goal = this.x[k] + wrapAngle(goal - this.x[k]);
      const change = this.x[k] - goal, temp = (this.v[k] + omega * change) * dt;
      this.v[k] = (this.v[k] - omega * temp) * e;
      this.x[k] = goal + (change + temp) * e;
    }
    return this;
  }
}

/** The part of a road that is driven: the ends (STANDOFF units in front of each district) are the stations. */
export function trimRange(total, standoff = STANDOFF) {
  if (!(total > 0)) return [0, 1];
  const s = Math.min(standoff, total * 0.22);
  return [s / total, 1 - s / total];
}

/** Closest point of the polyline to p (xz plane): its position along the road as a fraction 0..1 of the total length. */
export function nearestU(path, p) {
  const total = Math.max(1e-6, path.total);
  let best = Infinity, bu = 0;
  for (let k = 0; k + 1 < path.length; k++) {
    const a = path[k], b = path[k + 1], sx = b.x - a.x, sz = b.z - a.z, l2 = sx * sx + sz * sz;
    const s = l2 > 1e-9 ? clamp(((p.x - a.x) * sx + (p.z - a.z) * sz) / l2, 0, 1) : 0;
    const d = Math.hypot(a.x + sx * s - p.x, a.z + sz * s - p.z);
    if (d < best) { best = d; bu = (path.lengths[k] + (path.lengths[k + 1] - path.lengths[k]) * s) / total; }
  }
  return bu;
}

/**
 * Detour around the district towers a road runs through (the roads hop through district centres, where a tower stands):
 * near every passed centre the road is moved sideways (along its own normal, in a smooth bump) until it clears the
 * centre by `R` (xz). Which side is fixed in the world (independent of the direction of travel), so a road and its
 * reverse agree. -> {at(u, out)} adds the offset at u.
 */
export function lateralField(path, centres, R = TOWER_R, spacing = 2) {
  const total = Math.max(1e-6, path.total), n = Math.max(2, Math.ceil(total / spacing)), H = 3 * R;
  const dx = new Float32Array(n + 1), dz = new Float32Array(n + 1), nx = new Float32Array(n + 1), nz = new Float32Array(n + 1);
  const p = new THREE.Vector3(), q = new THREE.Vector3(), eps = Math.min(0.02, 4 / total);
  for (let i = 0; i <= n; i++) {                                         // left normal of the road at every sample
    pointAt(path, Math.max(0, i / n - eps), p); pointAt(path, Math.min(1, i / n + eps), q);
    const l = Math.hypot(q.x - p.x, q.z - p.z) || 1;
    nx[i] = -(q.z - p.z) / l; nz[i] = (q.x - p.x) / l;
  }
  const first = path[0], last = path[path.length - 1];
  for (const c of centres) {
    if ((first && Math.hypot(first.x - c.x, first.z - c.z) < 1) || (last && Math.hypot(last.x - c.x, last.z - c.z) < 1)) continue;   // the stations' own districts
    let best = Infinity, bk = -1, bs = 0;
    for (let k = 0; k + 1 < path.length; k++) {
      const a = path[k], b = path[k + 1], sx = b.x - a.x, sz = b.z - a.z, l2 = sx * sx + sz * sz;
      const s = l2 > 1e-9 ? clamp(((c.x - a.x) * sx + (c.z - a.z) * sz) / l2, 0, 1) : 0;
      const d = Math.hypot(a.x + sx * s - c.x, a.z + sz * s - c.z);
      if (d < best) { best = d; bk = k; bs = s; }
    }
    if (bk < 0 || best >= R) continue;
    const a = path[bk], b = path[bk + 1], sl = Math.hypot(b.x - a.x, b.z - a.z) || 1;
    const uc = (path.lengths[bk] + (path.lengths[bk + 1] - path.lengths[bk]) * bs) / total;
    const lx = -(b.z - a.z) / sl, lz = (b.x - a.x) / sl;                // left normal at the closest approach
    const lat = (a.x + (b.x - a.x) * bs - c.x) * lx + (a.z + (b.z - a.z) * bs - c.z) * lz;
    let side = Math.sign(lat);
    if (Math.abs(lat) < 0.5) side = (lx > 0 || (lx === 0 && lz > 0)) ? 1 : -1;   // on the centre: fixed world side (+x / +z)
    const shift = side * (R - Math.abs(lat)), hu = H / total;
    for (let i = Math.max(0, Math.floor((uc - hu) * n)); i <= Math.min(n, Math.ceil((uc + hu) * n)); i++) {
      const x = Math.abs(i / n - uc) / hu;
      if (x >= 1) continue;
      const w = 0.5 * (1 + Math.cos(Math.PI * x)) * shift;
      dx[i] += nx[i] * w; dz[i] += nz[i] * w;
    }
  }
  const rad = Math.max(1, Math.round(R * 0.35 / spacing)), tmpA = new Float32Array(n + 1);   // round off kinks of the road
  for (const arr of [dx, dz]) for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i <= n; i++) { let sum = 0, cnt = 0; for (let k = Math.max(0, i - rad); k <= Math.min(n, i + rad); k++) { sum += arr[k]; cnt++; } tmpA[i] = sum / cnt; }
    arr.set(tmpA);
  }
  return {
    at(u, out) {
      const f = clamp(u, 0, 1) * n, i = Math.min(n - 1, Math.floor(f)), w = f - i;
      out.x += dx[i] + (dx[i + 1] - dx[i]) * w; out.z += dz[i] + (dz[i + 1] - dz[i]) * w;
      return out;
    },
  };
}

/** Position on the road (and a point `look` units ahead in the direction of travel) at walk fraction f (0..1). */
export function walkSample(path, f, range, look, outPos, outAhead, dir = 1, field = null) {
  const [u0, u1] = range, total = Math.max(1e-6, path.total);
  const u = u0 + (u1 - u0) * clamp(f, 0, 1), ua = clamp(u + dir * look / total, 0, 1);
  pointAt(path, u, outPos);
  pointAt(path, ua, outAhead);
  if (field) { field.at(u, outPos); field.at(ua, outAhead); }
  return outPos;
}

/** Walk fraction of the road for the server progress p: progress from `p0` (the switch) to 1 runs f0 -> f1. */
export const walkFraction = (p, p0, f0, f1) => f0 + (f1 - f0) * clamp((p - p0) / Math.max(1e-6, 1 - p0), 0, 1);

/**
 * Server progress arrives at 20 Hz, quantised to 0.001: turn it into a smooth value. The rate is the slope over the
 * last ~2 s of samples; between ticks the last value is extrapolated with it (for at most 0.4 s), and a critically
 * damped follower smooths what remains.
 */
export class ProgressTracker {
  constructor(window = 2, smoothTime = 0.22) { this.window = window; this.smoothTime = smoothTime; this.sm = new Damped(1); this.reset(0, 0); }
  reset(p = 0, now = 0) { this.samples = [[now, p]]; this.lastP = p; this.lastT = now; this.rate = 0; this.sm.set(p); this.value = p; }
  push(p, now) {
    if (!Number.isFinite(p)) return;
    this.samples.push([now, p]);
    while (this.samples.length > 2 && now - this.samples[0][0] > this.window) this.samples.shift();
    this.lastP = p; this.lastT = now;
    const a = this.samples[0], b = this.samples[this.samples.length - 1];
    if (b[0] - a[0] > 0.3) this.rate = Math.max(0, (b[1] - a[1]) / (b[0] - a[0]));
  }
  predict(now) { return clamp(this.lastP + this.rate * clamp(now - this.lastT, 0, 0.4), 0, 1); }
  update(dt, now) { this.sm.step(this.predict(now), this.smoothTime, dt); this.value = clamp(this.sm.x[0], 0, 1); return this.value; }
}

/** life.py street_* waypoints are on the road in front of a place: they belong to that place's district role. */
export const STREET_ROLE = { street_home: "home", street_bakery: "reward", street_park: "park" };

// ---------------- the module ----------------
export function createTravel(camera, controls, data, { scene } = {}) {
  const D = data.districts;
  const homeD = data.districtOf("home") ?? 0, rewardD = data.districtOf("reward") ?? homeD;
  const groupIdx = {};
  D.forEach(d => (groupIdx[d.group] ||= []).push(d.i));

  // A place is its district's MAIN district: every room of the home (bed, window, desk, table ...) is one place for
  // travel, as are the bakery places and the park places. Only walks between different roles ride a road.
  const districtFor = place => {
    let d = data.placeDistrict(place);
    if (d == null) { const role = STREET_ROLE[place]; d = role ? data.districtOf(role) : null; }
    if (d == null) return null;
    const r = D[d].role;
    return r && data.roles[r] && data.roles[r].length ? data.roles[r][0] : d;
  };

  // ---- tower detours, per road (cached) ----
  const centres = D.map(d => d.pos), fields = new Map();
  const fieldOf = path => { let f = fields.get(path); if (!f) fields.set(path, f = lateralField(path, centres)); return f; };

  // ---- stations: where SUB-01 stands in front of a district (the ends of the roads) ----
  const stations = new Map();
  function stationOf(i) {
    let s = stations.get(i);
    if (s) return s;
    s = new THREE.Vector3();
    const [from, to] = i === homeD ? [homeD, rewardD] : [i, homeD];
    const path = from !== to ? data.pathBetween(from, to) : null;
    if (path && path.total > STANDOFF * 2) { const u = trimRange(path.total)[0]; pointAt(path, u, s); fieldOf(path).at(u, s); }
    else {
      const p = D[i].pos, len = Math.hypot(p.x, p.z), out = len > 30;
      s.set(p.x + (out ? p.x / len : 0) * STANDOFF, p.y, p.z + (out ? p.z / len : 1) * STANDOFF);
    }
    stations.set(i, s);
    return s;
  }

  // ---- first-person state (always computed, also while the overview is shown, so switching back is seamless) ----
  const pos = new Damped(3), yaw = new Damped(1), pitch = new Damped(1);
  const tracker = new ProgressTracker();
  const here = new THREE.Vector3();                 // SUB-01 on the ground
  const tp = new Float64Array(3), prevPos = new Float64Array(3), offV = new THREE.Vector3();
  const tPos = new THREE.Vector3(), ahead = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();
  const fromPos = new THREE.Vector3(), fpPos = new THREE.Vector3(), fpQ = new THREE.Quaternion();
  const rig = new THREE.PerspectiveCamera();
  let t = 0, view = "first", walk = null, prevWalk = null, lastLife = null, lastProg = -1, lastDistrict = homeD;
  let walkW = 0, bobPhase = 0, lastWalking = false, mode = "idle", walkKey = null, lastWalkT = -1e9;
  let focus = -1, focusUntil = 0, focusNext = 6, seed = 12345;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  let userYaw = 0, userPitch = 0, dragging = false, dragAt = -1e9, dragId = null, lx = 0, ly = 0, lastTouch = -1e9;

  function setPose(outQ, p, target, roll = 0) {
    rig.position.copy(p); rig.up.set(0, 1, 0); rig.lookAt(target);
    if (roll) rig.rotateZ(roll);
    outQ.copy(rig.quaternion);
  }

  // A walk starts (or the route changes while walking: life.py re-plans mid-walk and its progress on the new route does
  // not start at 0). Fresh walk: progress p runs the road from the start station. Mid-walk switch: the camera keeps
  // the place it is at - the same road (turn-back) continues from the current fraction, a new road is entered at its
  // point nearest to the camera, and progress p0..1 of the new route maps to that point .. the goal station.
  function startWalk(route, pInit) {
    const a = districtFor(route[0]), b = districtFor(route[route.length - 1]);
    walkKey = route[0] + ">" + route[route.length - 1];
    const old = walk;
    walk = null;
    if (a == null || b == null || a === b) { if (b != null) lastDistrict = b; return; }   // inside one place: stay put
    const mid = !!prevWalk && t - lastWalkT < 1.5;
    let path, pa = a, pb = b, f0 = 0, p0 = 0;
    const range0 = () => trimRange(path.total);
    if (mid && ((prevWalk.pa === a && prevWalk.pb === b) || (prevWalk.pa === b && prevWalk.pb === a))) {
      path = prevWalk.path; pa = prevWalk.pa; pb = prevWalk.pb;           // turning back: the same road, the other way
      f0 = old ? old.f : prevWalk.f; p0 = pInit;
    } else {
      path = data.pathBetween(a, b);
      if (mid) {
        fromPos.set(pos.x[0], 0, pos.x[2]);
        const [u0, u1] = range0();
        f0 = clamp((nearestU(path, fromPos) - u0) / Math.max(1e-6, u1 - u0), 0, 1); p0 = pInit;
      }
    }
    const f1 = b === pb ? 1 : 0;
    walk = { a, b, pa, pb, path, range: range0(), f0, f1, p0, f: walkFraction(pInit, p0, f0, f1), field: fieldOf(path), t0: t, off: offV.clone() };
    tracker.reset(clamp(pInit, 0, 1), t);
    lastProg = -1;
    fromPos.set(pos.x[0], pos.x[1] - EYE, pos.x[2]);                     // the camera may be away from the road: blend in
    walkSample(path, walk.f, walk.range, 1, tmp, tmp2, f1 >= f0 ? 1 : -1, walk.field);
    walk.off.subVectors(fromPos, tmp); walk.off.y = 0;
    if (!mid) { const len = walk.off.length(); if (len < 0.5) walk.off.set(0, 0, 0); }
  }

  function update(dt, life, env) {
    dt = clamp(dt || 0, 0, 0.1);
    t += dt;
    const sleeping = (env?.stage && env.stage !== "AWAKE") || life?.activity === "sleep" || (life?.stage && life.stage !== "AWAKE");

    // ---- which mode: walking a road / standing in a district ----
    const routeOk = !!(life && life.walking && Array.isArray(life.route) && life.route.length >= 2);
    if (routeOk) {
      const key = life.route[0] + ">" + life.route[life.route.length - 1];
      if (!lastWalking || walkKey !== key) startWalk(life.route, +life.progress || 0);
      if (walk) {
        const p = +life.progress || 0;
        if (life !== lastLife || p !== lastProg) { tracker.push(p, t); lastProg = p; }
        walk.f = walkFraction(tracker.update(dt, t), walk.p0, walk.f0, walk.f1);
      }
    } else if (walk) {                                                    // arrived (or the walk was cancelled)
      lastDistrict = walk.b;
      walk = null;
    }
    lastLife = life;
    const walking = routeOk && !!walk;
    if (walking) { prevWalk = walk; lastWalkT = t; }
    lastWalking = routeOk;
    walkW += ((walking ? 1 : 0) - walkW) * (1 - Math.exp(-dt * 3));

    // ---- target pose ----
    let yawT, pitchT, sPos = 0.6, sYaw = 0.45, sPitch = 0.6;
    if (walking) {
      mode = "walk";
      walkSample(walk.path, walk.f, walk.range, LOOK_AHEAD, tPos, ahead, walk.f1 >= walk.f0 ? 1 : -1, walk.field);
      tPos.addScaledVector(walk.off, 1 - smooth01((t - walk.t0) / OFFSET_S));   // a walk that starts off the road blends in
      here.copy(tPos);
      tPos.y += EYE;
      tmp.subVectors(ahead, tPos);
      const h = Math.hypot(tmp.x, tmp.z);
      yawT = h > 1e-2 ? yawOf(tmp.x, tmp.z) : yaw.x[0];
      pitchT = clamp(Math.atan2(ahead.y + 8 - tPos.y, Math.max(1, h)), -0.2, 0.3);
      sPos = 0.14; sYaw = 0.5; sPitch = 0.4;
    } else {
      const place = life?.place, pd = place ? districtFor(place) : null;
      if (pd != null) lastDistrict = pd;
      const di = lastDistrict, S = stationOf(di), P = D[di].pos;
      here.copy(S);
      tPos.copy(S); tPos.y += EYE;
      tmp.set(P.x - S.x, 0, P.z - S.z);
      const toward = tmp.lengthSq() > 1e-4 ? yawOf(tmp.x, tmp.z) : yaw.x[0];
      const dist = Math.max(8, Math.hypot(tmp.x, tmp.z));
      const lying = life?.activity === "sleep" || life?.activity === "phone" || /lying/.test(life?.pose || "");
      if (sleeping) {                                                      // slow drift high over the home district, the city stays in frame
        mode = "sleep";
        const th = t * 0.03;
        tPos.x += Math.cos(th) * 10; tPos.z += Math.sin(th) * 10; tPos.y += 14 + 3 * Math.sin(t * 0.05);
        yawT = toward + 0.5 * Math.sin(t * 0.04); pitchT = -0.06 + 0.04 * Math.sin(t * 0.09);
        sPos = 1.4; sYaw = 1.6; sPitch = 1.6;
      } else if (lying) {                                                  // in bed with the phone: raised gaze, towers and roads still in view
        mode = "lying";
        yawT = toward + 0.35 * Math.sin(t * 0.07); pitchT = 0.3 + 0.04 * Math.sin(t * 0.13);
        sPos = 0.8; sYaw = 1.2; sPitch = 1.2;
      } else {
        mode = "idle";
        yawT = toward + 0.3 * Math.sin(t * 0.13) + 0.12 * Math.sin(t * 0.051 + 1.3);
        pitchT = clamp(Math.atan2(P.y + 18 - tPos.y, dist), -0.1, 0.5) + 0.05 * Math.sin(t * 0.17);
        if (t >= focusNext) {                                              // now and then look at the most active group
          focusNext = t + 8 + rnd() * 8;
          let best = null, bv = 1.12;
          const rel = env?.groupRel;
          if (rel) for (const g in rel) if (groupIdx[g] && rel[g] > bv) { bv = rel[g]; best = g; }
          if (best) {
            let bi = -1, bd = 650;
            for (const i of groupIdx[best]) {
              const d = Math.hypot(D[i].pos.x - S.x, D[i].pos.z - S.z);
              if (i !== di && d > 30 && d < bd) { bd = d; bi = i; }
            }
            if (bi >= 0) { focus = bi; focusUntil = t + 5; }
          }
        }
        if (focus >= 0 && t < focusUntil) {
          const F = D[focus].pos;
          yawT = yawOf(F.x - S.x, F.z - S.z);
          pitchT = clamp(Math.atan2(F.y + 22 - tPos.y, Math.hypot(F.x - S.x, F.z - S.z)), -0.1, 0.5);
        } else focus = -1;
        sPos = 0.7; sYaw = 0.9; sPitch = 0.9;
      }
    }

    // ---- drag-to-look (springs back) ----
    if (!dragging && t - dragAt > 2.5) { const k = Math.exp(-dt * 0.9); userYaw *= k; userPitch *= k; }
    yawT += userYaw; pitchT = clamp(pitchT + userPitch, -0.6, 1.3);

    prevPos.set(pos.x);
    tp[0] = tPos.x; tp[1] = tPos.y; tp[2] = tPos.z;
    pos.step(tp, sPos, dt);
    {                                                                      // the camera never outruns MAX_SPEED (re-plans, station changes)
      const dx = pos.x[0] - prevPos[0], dy = pos.x[1] - prevPos[1], dz = pos.x[2] - prevPos[2], d = Math.hypot(dx, dy, dz), lim = MAX_SPEED * dt;
      if (d > lim && dt > 0) { const k = lim / d; for (let c = 0; c < 3; c++) { pos.x[c] = prevPos[c] + (pos.x[c] - prevPos[c]) * k; pos.v[c] *= k; } }
    }
    yaw.step(yawT, sYaw, dt, true);
    pitch.step(pitchT, sPitch, dt);

    // ---- head bob / sway while walking (added on top of the smoothed pose) ----
    bobPhase += dt * 2 * Math.PI * 1.7 * walkW;
    const bob = Math.sin(bobPhase) * 0.13 * walkW + Math.sin(t * 0.7) * 0.04;
    const sway = Math.sin(bobPhase * 0.5) * 0.09 * walkW;
    let roll = Math.sin(bobPhase * 0.5) * 0.007 * walkW;
    if (env?.stage === "REM") roll += 0.03 * Math.sin(t * 0.55);
    const ya = yaw.x[0], pa = clamp(pitch.x[0] + Math.sin(bobPhase) * 0.004 * walkW, -1.3, 1.3), cp = Math.cos(pa);
    fpPos.set(pos.x[0] + Math.cos(ya) * sway, pos.x[1] + bob, pos.x[2] + Math.sin(ya) * sway);
    tmp.set(fpPos.x + Math.sin(ya) * cp * 10, fpPos.y + Math.sin(pa) * 10, fpPos.z - Math.cos(ya) * cp * 10);
    setPose(fpQ, fpPos, tmp, roll);

    if (beacon) updateBeacon(dt);

    // ---- views ----
    if (blend) {
      blend.t += dt / BLEND_S;
      const w = smooth01(blend.t), toFirst = view === "first";
      camera.position.lerpVectors(blend.pos, toFirst ? fpPos : orbitGoal.pos, w);
      camera.quaternion.slerpQuaternions(blend.q, toFirst ? fpQ : orbitGoal.q, w);
      if (blend.t >= 1) { blend = null; if (!toFirst) enterOrbit(); }
      return;
    }
    if (view === "orbit") {
      const follow = !!env?.follow;
      controls.enablePan = !follow;
      if (follow) {                                                        // the target drifts towards where SUB-01 is
        tmp.set(here.x * FOLLOW, 0, here.z * FOLLOW);
        tmp2.copy(tmp).sub(controls.target).multiplyScalar(1 - Math.exp(-dt * 0.5));
        controls.target.add(tmp2); camera.position.add(tmp2);
      }
      controls.autoRotate = !dragging && t - lastTouch > 6;
      return;
    }
    camera.position.copy(fpPos);
    camera.quaternion.copy(fpQ);
  }

  // ---- views ----
  const orbitGoal = { pos: new THREE.Vector3(), target: new THREE.Vector3(), q: new THREE.Quaternion() };
  let blend = null, ready = false;
  function computeOrbitGoal() {
    const R = data.radius;
    orbitGoal.target.set(here.x * FOLLOW, 0, here.z * FOLLOW);
    orbitGoal.pos.set(here.x * FOLLOW + R * 0.12, R * 1.0, here.z * FOLLOW + R * 1.1);
    setPose(orbitGoal.q, orbitGoal.pos, orbitGoal.target);
  }
  function enterOrbit() {
    controls.target.copy(orbitGoal.target);
    camera.position.copy(orbitGoal.pos); camera.quaternion.copy(orbitGoal.q);
    controls.enabled = true; controls.update();
  }
  function setView(v, instant = false) {
    const next = v === "orbit" ? "orbit" : "first";
    if (next === view && ready) return;
    const first = !ready;
    ready = true;
    view = next; api.view = view;
    controls.enabled = false; controls.autoRotate = false;
    dragging = false; dragId = null;
    if (view === "orbit") computeOrbitGoal();
    if (first || instant) {
      blend = null;
      if (view === "orbit") enterOrbit(); else { camera.position.copy(fpPos); camera.quaternion.copy(fpQ); }
      return;
    }
    blend = { t: 0, pos: camera.position.clone(), q: camera.quaternion.clone() };   // smooth transition, no snap
  }

  // ---- drag-to-look in first person (mouse or touch; the orbit controls stay off) ----
  const el = controls.domElement;
  if (el && el.addEventListener) {
    el.addEventListener("pointerdown", e => {
      lastTouch = t;
      if (view !== "first" || blend || dragging) return;
      dragging = true; dragId = e.pointerId; lx = e.clientX; ly = e.clientY;
      try { el.setPointerCapture?.(e.pointerId); } catch { /* synthetic pointer: no capture */ }
    });
    el.addEventListener("pointermove", e => {
      if (!dragging || e.pointerId !== dragId) return;
      userYaw = clamp(userYaw - (e.clientX - lx) * 0.004, -1.3, 1.3);
      userPitch = clamp(userPitch - (e.clientY - ly) * 0.003, -0.5, 0.5);
      lx = e.clientX; ly = e.clientY; dragAt = t;
    });
    const end = e => { if (dragging && e.pointerId === dragId) { dragging = false; dragAt = t; try { el.releasePointerCapture?.(e.pointerId); } catch { /* already released */ } } };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("lostpointercapture", end);
    if (typeof window !== "undefined" && window.addEventListener) {        // released over the side panel / outside the window
      window.addEventListener("pointerup", end);
      window.addEventListener("pointercancel", end);
      window.addEventListener("blur", () => { if (dragging) { dragging = false; dragAt = t; } });
    }
  }
  controls.addEventListener?.("start", () => { lastTouch = t; });
  controls.addEventListener?.("end", () => { lastTouch = t; });
  controls.autoRotateSpeed = 0.35;
  controls.enableDamping = true;
  if (THREE.TOUCH && controls.touches) controls.touches.TWO = THREE.TOUCH.DOLLY_ROTATE;   // phones: pinch zoom + rotate

  // ---- beacon: SUB-01's marker in the overview ----
  let beacon = null, ring = null, tag = null, core = null;
  function makeTag() {
    if (typeof document === "undefined") return null;
    const cv = document.createElement("canvas"), x = cv.getContext("2d"), fs = 34;
    x.font = `${fs}px ui-monospace, Menlo, monospace`;
    cv.width = Math.ceil(x.measureText("SUB-01").width) + 26; cv.height = fs + 18;
    x.font = `${fs}px ui-monospace, Menlo, monospace`;
    x.fillStyle = "rgba(5,6,12,0.75)"; x.fillRect(0, 0, cv.width, cv.height);
    x.strokeStyle = "#ff6a00"; x.lineWidth = 2; x.strokeRect(1, 1, cv.width - 2, cv.height - 2);
    x.fillStyle = "#ffe6cc"; x.textBaseline = "middle"; x.fillText("SUB-01", 13, cv.height / 2 + 2);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false, toneMapped: false, sizeAttenuation: false, fog: false }));
    const h = 0.03; sp.scale.set(h * cv.width / cv.height, h, 1); sp.renderOrder = 12;
    return sp;
  }
  if (scene) {
    beacon = new THREE.Group(); beacon.name = "sub01-beacon"; beacon.visible = false;
    const beamGeo = new THREE.CylinderGeometry(0.9, 1.6, 1, 10, 1, true).translate(0, 0.5, 0);
    const col = new Float32Array(beamGeo.attributes.position.count * 3);
    for (let v = 0; v < beamGeo.attributes.position.count; v++) col.fill(beamGeo.attributes.position.getY(v) > 0.5 ? 0.0 : 1.0, v * 3, v * 3 + 3);
    beamGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const beam = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({ color: 0xff8a2a, vertexColors: true, transparent: true, opacity: 0.8,
      blending: THREE.AdditiveBlending, depthWrite: false, fog: false, side: THREE.DoubleSide }));
    beam.scale.y = 26;
    core = new THREE.Mesh(new THREE.OctahedronGeometry(1.4, 0), new THREE.MeshBasicMaterial({ color: 0xffd9a0, fog: false, toneMapped: false }));
    core.position.y = 1.6;
    ring = new THREE.Mesh(new THREE.RingGeometry(1.6, 2, 40).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0xff6a00, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, side: THREE.DoubleSide }));
    ring.position.y = 0.5;
    beacon.add(beam, core, ring);
    tag = makeTag();
    if (tag) scene.add(tag);                                   // not in the group: the tag keeps its screen size
    scene.add(beacon);
  }
  function updateBeacon(dt) {
    const show = view === "orbit" || !!blend;
    beacon.visible = show;
    if (tag) tag.visible = show;
    if (!show) return;
    beacon.position.copy(here);
    const sc = clamp(camera.position.distanceTo(here) / 160, 1, 14);             // stays visible from far away
    beacon.scale.setScalar(sc);
    if (tag) tag.position.set(here.x, here.y + 26 * sc + 6, here.z);
    core.rotation.y += dt * 1.5;
    const ph = (t * 0.8) % 1;
    ring.scale.setScalar(1 + ph * 5); ring.material.opacity = 0.8 * (1 - ph);
  }

  const api = { update, setView, view, position: here,
    state: () => ({ mode, walking: !!walk, progress: +tracker.value.toFixed(3), district: lastDistrict, view, blend: !!blend, f: walk ? +walk.f.toFixed(3) : null }) };
  // initial pose: standing in front of the home district
  {
    const S = stationOf(homeD);
    here.copy(S); tPos.copy(S); tPos.y += EYE;
    pos.set(tPos.x, tPos.y, tPos.z);
    tmp.set(D[homeD].pos.x - S.x, 0, D[homeD].pos.z - S.z);
    yaw.set(yawOf(tmp.x, tmp.z)); pitch.set(0.15);
    fpPos.copy(tPos); fromPos.copy(S);
    tmp.set(fpPos.x + Math.sin(yaw.x[0]) * 10, fpPos.y + 1.5, fpPos.z - Math.cos(yaw.x[0]) * 10);
    setPose(fpQ, fpPos, tmp);
    camera.position.copy(fpPos); camera.quaternion.copy(fpQ);
  }
  controls.enabled = false;
  return api;
}
