// The construct's data layer (core stream): SUB-01's own brain data turned into a city.
//
//   loadBrainData(quality, {fetch, base}) -> Promise<data>     fetches brain.json + fibres.json + fibres.bin +
//       fibres_ends.bin once (cached) and builds the city for that quality (cached per quality name).
//   buildBrainData(raw, quality) -> data                          pure builder (used by the node tests)
//       raw = {brain: brain.json object, meta: fibres.json object, fibres: ArrayBuffer, ends: ArrayBuffer}
//
// data = {
//   nodes          brain.json nodes (same order as tick.act)
//   districts      [{i, name, label, group, pos: Vector3 (city space, y = ground height), role, cluster}]
//                  role: "home" | "reward" | "park" | "fear" | "salience" | null   (cluster: index inside the home cluster)
//   roles          {home: [i...], reward: [...], park: [...], fear: [...], salience: [...]}  (first = the main district)
//   districtOf(role) -> i            main district of a role ("home", "reward"/"bakery"/"food", "park", "fear")
//   placeDistrict(place) -> i|null   life.py place -> district (street_* -> null: on the road between districts)
//   roads          {positions: Float32Array (segments*2 vertices*3), pairs: Int16Array (per vertex: region a, region b),
//                   t: Float32Array (per vertex, 0..1 along its fibre), fibres, segments}
//                  subsampled real fibres (low ~2.5k, medium ~10k, high ~25k), every point through mapPoint()
//   graph          {n, edges: [{a, b, count, len, rep}], adj: [[{j, e}]]}  region graph from ALL labelled fibre ends
//                  (count = fibres in the bundle, len = median fibre length in mm, rep = representative fibre index)
//   pathBetween(i, j) -> [Vector3...] with .lengths (Float32Array cumulative, city units), .total, .hops ([regions])
//                  shortest path over the region graph (strong bundles preferred), each hop following its
//                  representative fibre (oriented start -> end), passing through every district on the way, smoothed
//   pointAt(path, u, out) -> out      point at fraction u (0..1) of the walked length of a path
//   mapPoint(x, y, z, out) -> out     brain mm (fibres / node q space) -> city space
//   radius, scale, quality
// }
//
// Mapping (deterministic, keeps the real topology recognisable): the axial plane (left-right, back-front) is the ground
// (x = right, -z = front of the brain), expanded radially: inferior cortex is pushed outwards, deep nuclei stay inside.
// Districts are then relaxed apart (fixed iterations, fixed order) so none overlap; the same displacement is carried
// to every fibre point through a smooth 3D field, so roads still start and end in their districts. Height (y) is the
// superior-inferior axis compressed to a low terrain. It is a model of brain activity, not a mind.
import * as THREE from "three";

export const SCALE = 4.2;                  // city units per (expanded) mm
export const MIN_GAP = 7.5;                // mm between district centres after relaxation
export const TERRAIN = 14;                 // city units of height from the lowest to the highest cortex
export const EXPAND = 1.0;                 // radial expansion of inferior cortex
export const FIBRES = { low: 2500, medium: 10000, high: 25000 };
export const STEP = { low: 2, medium: 2, high: 2 };   // keep every STEP-th fibre point (+ the last one)

// every life.py place (PLACES) -> role; home places are spread over the home cluster
export const PLACE_ROLE = {
  bed: ["home", 0], door_in: ["home", 0], door_out: ["home", 0],
  window: ["home", 1], desk: ["home", 2], table: ["home", 3],
  street_home: null, street_bakery: null, street_park: null,
  bakery_door: ["reward", 0], bakery_in: ["reward", 0], counter: ["reward", 0],
  park_gate: ["park", 0], bench: ["park", 0],
};
const ROLE_ALIAS = { bakery: "reward", food: "reward", memory: "park", amygdala: "fear" };

const RAW = new Map();                      // base url -> Promise<raw>
const BUILT = new Map();                    // base url + quality -> Promise<data>

export function loadBrainData(quality, { fetch: fetchFn = globalThis.fetch, base = "/" } = {}) {
  const q = qname(quality);
  const key = base + "|" + q;
  if (BUILT.has(key)) return BUILT.get(key);
  if (!RAW.has(base)) {
    const get = (f, kind) => fetchFn(base + f).then(r => {
      if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
      return kind === "json" ? r.json() : r.arrayBuffer();
    });
    RAW.set(base, Promise.all([get("brain.json", "json"), get("fibres.json", "json"), get("fibres.bin"), get("fibres_ends.bin")])
      .then(([brain, meta, fibres, ends]) => ({ brain, meta, fibres, ends })));
    RAW.get(base).catch(() => RAW.delete(base));
  }
  const p = RAW.get(base).then(raw => buildBrainData(raw, q));
  BUILT.set(key, p);
  p.catch(() => BUILT.delete(key));
  return p;
}

function qname(quality) {
  const n = typeof quality === "string" ? quality : quality?.name;
  return n in FIBRES ? n : "medium";
}

export function buildBrainData(raw, quality) {
  const q = qname(quality);
  const nodes = raw.brain.nodes, N = nodes.length;
  const meta = raw.meta, K = meta.pts;
  const P = new Float32Array(raw.fibres), E = new Int16Array(raw.ends);
  const nF = Math.min(meta.n, Math.floor(P.length / (K * 3)), Math.floor(E.length / 2));
  const lab2node = new Int16Array(1024).fill(-1);
  nodes.forEach((n, i) => { if (n.lab >= 0 && n.lab < 1024) lab2node[n.lab] = i; });
  const endNode = v => (v > 0 && v < 1024 ? lab2node[v] : -1);

  // ---------------- the base mapping (brain mm -> expanded planar mm) ----------------
  const cortex = nodes.map((n, i) => i).filter(i => !isDeep(nodes[i]));
  const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
  for (const i of cortex) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], nodes[i].q[k]); hi[k] = Math.max(hi[k], nodes[i].q[k]); }
  const c = lo.map((v, k) => (v + hi[k]) / 2), half = lo.map((v, k) => Math.max(1, (hi[k] - v) / 2));
  const zlo = lo[2], zspan = Math.max(1, hi[2] - lo[2]);
  const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v);
  function base(x, y, z, out) {                              // out[0] = east (mm), out[1] = north (mm)
    const dx = x - c[0], dy = y - c[1], dz = z - c[2];
    const rho = Math.min(1, Math.hypot(dx / half[0], dy / half[1], dz / half[2]));
    const e = 1 + EXPAND * (1 - clamp01((z - zlo) / zspan)) * rho;
    out[0] = dx * e; out[1] = dy * e;
    return out;
  }
  const heightOf = z => TERRAIN * clamp01((z - zlo) / zspan);

  // ---------------- districts: base positions, relaxed apart (deterministic) ----------------
  const b0 = new Float64Array(N * 2), cur = new Float64Array(N * 2), tmp2 = [0, 0];
  nodes.forEach((n, i) => { base(n.q[0], n.q[1], n.q[2], tmp2); b0[2 * i] = cur[2 * i] = tmp2[0]; b0[2 * i + 1] = cur[2 * i + 1] = tmp2[1]; });
  for (let it = 0; it < 220; it++) {
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
      let dx = cur[2 * j] - cur[2 * i], dy = cur[2 * j + 1] - cur[2 * i + 1], d = Math.hypot(dx, dy);
      if (d >= MIN_GAP) continue;
      if (d < 1e-6) { const a = (i * 7 + j * 13) % 360 * Math.PI / 180; dx = Math.cos(a); dy = Math.sin(a); d = 1e-6; }
      else { dx /= d; dy /= d; }
      const push = (MIN_GAP - d) * 0.5;
      cur[2 * i] -= dx * push; cur[2 * i + 1] -= dy * push; cur[2 * j] += dx * push; cur[2 * j + 1] += dy * push;
    }
    if (it < 180) for (let k = 0; k < N * 2; k++) cur[k] += (b0[k] - cur[k]) * 0.03;   // stay close to the real place
  }

  // ---------------- displacement field (3D grid over the fibre volume) ----------------
  const G = 6, SIG2 = 2 * 9 * 9;                              // 6 mm cells, gaussian sigma 9 mm
  const glo = [-80, -100, -80], gn = [Math.ceil(160 / G) + 1, Math.ceil(220 / G) + 1, Math.ceil(160 / G) + 1];
  const field = new Float32Array(gn[0] * gn[1] * gn[2] * 2);
  for (let iz = 0, o = 0; iz < gn[2]; iz++) for (let iy = 0; iy < gn[1]; iy++) for (let ix = 0; ix < gn[0]; ix++, o++) {
    const x = glo[0] + ix * G, y = glo[1] + iy * G, z = glo[2] + iz * G;
    let w0 = 0.02, sx = 0, sy = 0;                            // a small weight for "no displacement" far from districts
    for (let i = 0; i < N; i++) {
      const qq = nodes[i].q, d2 = (x - qq[0]) ** 2 + (y - qq[1]) ** 2 + (z - qq[2]) ** 2;
      if (d2 > 900) continue;
      const w = Math.exp(-d2 / SIG2);
      w0 += w; sx += w * (cur[2 * i] - b0[2 * i]); sy += w * (cur[2 * i + 1] - b0[2 * i + 1]);
    }
    field[o * 2] = sx / w0; field[o * 2 + 1] = sy / w0;
  }
  function disp(x, y, z, out) {                               // trilinear
    const fx = clampF((x - glo[0]) / G, gn[0]), fy = clampF((y - glo[1]) / G, gn[1]), fz = clampF((z - glo[2]) / G, gn[2]);
    const ix = Math.floor(fx), iy = Math.floor(fy), iz = Math.floor(fz), tx = fx - ix, ty = fy - iy, tz = fz - iz;
    out[0] = out[1] = 0;
    for (let k = 0; k < 8; k++) {
      const ax = k & 1, ay = (k >> 1) & 1, az = (k >> 2) & 1;
      const w = (ax ? tx : 1 - tx) * (ay ? ty : 1 - ty) * (az ? tz : 1 - tz);
      if (!w) continue;
      const o = ((iz + az) * gn[1] + (iy + ay)) * gn[0] + (ix + ax);
      out[0] += w * field[o * 2]; out[1] += w * field[o * 2 + 1];
    }
    return out;
  }
  const t2a = [0, 0], t2b = [0, 0];
  function mapInto(x, y, z, arr, o) {                         // write city xyz into arr[o..o+2]
    base(x, y, z, t2a); disp(x, y, z, t2b);
    arr[o] = (t2a[0] + t2b[0]) * SCALE;
    arr[o + 1] = heightOf(z);
    arr[o + 2] = -(t2a[1] + t2b[1]) * SCALE;
  }
  const t3 = [0, 0, 0];
  function mapPoint(x, y, z, out = new THREE.Vector3()) { mapInto(x, y, z, t3, 0); return out.set(t3[0], t3[1], t3[2]); }

  // ---------------- districts ----------------
  let radius = 0;
  const districts = nodes.map((n, i) => {
    const pos = new THREE.Vector3(cur[2 * i] * SCALE, heightOf(n.q[2]), -cur[2 * i + 1] * SCALE);
    radius = Math.max(radius, Math.hypot(pos.x, pos.z));
    return { i, name: n.name, label: labelOf(n), group: n.group, pos, role: null, cluster: -1 };
  });

  // ---------------- region graph from ALL labelled fibre ends ----------------
  const flen = new Float32Array(nF);
  const bundles = new Map();
  for (let s = 0; s < nF; s++) {
    const a = endNode(E[2 * s]), b = endNode(E[2 * s + 1]);
    if (a < 0 || b < 0 || a === b) continue;
    let L = 0;
    for (let k = 0, o = s * K * 3; k < K - 1; k++, o += 3) L += Math.hypot(P[o + 3] - P[o], P[o + 4] - P[o + 1], P[o + 5] - P[o + 2]);
    flen[s] = L;
    const key = a < b ? a * N + b : b * N + a;
    let list = bundles.get(key);
    if (!list) bundles.set(key, (list = []));
    list.push(s);
  }
  const edges = [], adj = Array.from({ length: N }, () => []);
  for (const key of [...bundles.keys()].sort((x, y) => x - y)) {
    const list = bundles.get(key).slice().sort((x, y) => flen[x] - flen[y] || x - y);
    const rep = list[list.length >> 1];
    const e = { a: Math.floor(key / N), b: key % N, count: list.length, len: flen[rep], rep };
    const ei = edges.push(e) - 1;
    adj[e.a].push({ j: e.b, e: ei }); adj[e.b].push({ j: e.a, e: ei });
  }
  const graph = { n: N, edges, adj };

  // ---------------- roles ----------------
  const byGroup = g => nodes.map((n, i) => i).filter(i => nodes[i].group === g);
  const centroidNearest = (list, pts = list) => {
    const m = [0, 0, 0];
    for (const i of pts) for (let k = 0; k < 3; k++) m[k] += nodes[i].q[k] / pts.length;
    return nearestTo(list, m);
  };
  const nearestTo = (list, m) => list.reduce((best, i) => (dist3(nodes[i].q, m) < dist3(nodes[best].q, m) ? i : best), list[0]);
  const direct = (i, j) => adj[i].some(x => x.j === j);

  const defaults = byGroup("default");
  const home = centroidNearest(defaults);
  const homeCluster = [home, ...defaults.filter(i => i !== home && direct(home, i))
    .sort((x, y) => districts[x].pos.distanceTo(districts[home].pos) - districts[y].pos.distanceTo(districts[home].pos) || x - y)
    .slice(0, 3)];
  const rewardAll = nodes.map((n, i) => i).filter(i => /Accumbens|Caudate|Putamen/.test(nodes[i].name));
  const accumbens = rewardAll.filter(i => /Accumbens/.test(nodes[i].name));
  const reward = [centroidNearest(accumbens.length ? accumbens : rewardAll, rewardAll)];
  for (const i of rewardAll) if (i !== reward[0]) reward.push(i);
  const hippo = nodes.map((n, i) => i).filter(i => /Hippocampus/.test(nodes[i].name));
  const parkPool = hippo.length ? hippo : byGroup("memory").concat(byGroup("limbic"));
  const park = [parkPool.reduce((b, i) => (districts[i].pos.distanceTo(districts[home].pos) < districts[b].pos.distanceTo(districts[home].pos) ? i : b), parkPool[0])];
  for (const i of parkPool.concat(byGroup("memory"))) if (!park.includes(i)) park.push(i);
  const amyg = nodes.map((n, i) => i).filter(i => /Amygdala/.test(nodes[i].name));
  const fearPool = amyg.length ? amyg : byGroup("fear");
  const fear = [centroidNearest(fearPool)];
  for (const i of fearPool.concat(byGroup("fear"))) if (!fear.includes(i)) fear.push(i);
  const salience = byGroup("salience");
  const roles = { home: homeCluster, reward, park, fear, salience };
  for (const i of salience) districts[i].role = "salience";
  for (const i of fear) districts[i].role = "fear";
  for (const i of park) districts[i].role = "park";
  for (const i of reward) districts[i].role = "reward";
  homeCluster.forEach((i, k) => { districts[i].role = "home"; districts[i].cluster = k; });

  function districtOf(role) {
    const r = ROLE_ALIAS[role] || role;
    return roles[r] && roles[r].length ? roles[r][0] : null;
  }
  function placeDistrict(place) {
    if (typeof place !== "string" || !place) return null;
    let spec = PLACE_ROLE[place];
    if (spec === undefined) {                                  // a place life.py may add later: guess from its name
      if (/^street/.test(place)) spec = null;
      else if (/bakery|counter|shop|food/.test(place)) spec = ["reward", 0];
      else if (/park|bench|garden/.test(place)) spec = ["park", 0];
      else spec = ["home", 0];
    }
    if (!spec) return null;
    const list = roles[spec[0]];
    return list[Math.min(spec[1], list.length - 1)];
  }

  // ---------------- roads: subsampled fibres in city space ----------------
  const want = FIBRES[q], step = STEP[q];
  const labelled = [];
  for (let s = 0; s < nF; s++) if (flen[s] > 0) labelled.push(s);
  const pick = [];
  if (labelled.length <= want) pick.push(...labelled);
  else for (let k = 0; k < want; k++) pick.push(labelled[Math.floor(k * labelled.length / want)]);
  const idx = [];
  for (let k = 0; k < K; k += step) idx.push(k);
  if (idx[idx.length - 1] !== K - 1) idx.push(K - 1);
  const segPer = idx.length - 1, segs = pick.length * segPer;
  const positions = new Float32Array(segs * 6), pairs = new Int16Array(segs * 4), tpos = new Float32Array(segs * 2);
  const pt = new Float32Array(idx.length * 3);
  let o = 0;
  for (const s of pick) {
    const a = endNode(E[2 * s]), b = endNode(E[2 * s + 1]);
    idx.forEach((k, m) => { const p = (s * K + k) * 3; mapInto(P[p], P[p + 1], P[p + 2], pt, m * 3); });
    for (let m = 0; m < segPer; m++, o++) {
      for (let j = 0; j < 3; j++) { positions[o * 6 + j] = pt[m * 3 + j]; positions[o * 6 + 3 + j] = pt[(m + 1) * 3 + j]; }
      pairs[o * 4] = pairs[o * 4 + 2] = a; pairs[o * 4 + 1] = pairs[o * 4 + 3] = b;
      tpos[o * 2] = idx[m] / (K - 1); tpos[o * 2 + 1] = idx[m + 1] / (K - 1);
    }
  }
  const roads = { positions, pairs, t: tpos, fibres: pick.length, segments: segs };

  // ---------------- paths along real fibres ----------------
  const fibreCache = new Map();
  function fibreCity(s) {                                       // representative fibre polyline in city space
    let pts = fibreCache.get(s);
    if (!pts) {
      pts = [];
      for (let k = 0; k < K; k++) { const p = (s * K + k) * 3; pts.push(mapPoint(P[p], P[p + 1], P[p + 2])); }
      fibreCache.set(s, pts);
    }
    return pts;
  }
  function route(i, j, minCount) {                              // Dijkstra over the region graph
    const dist = new Float64Array(N).fill(Infinity), prev = new Int32Array(N).fill(-1), done = new Uint8Array(N);
    dist[i] = 0;
    for (;;) {
      let u = -1, best = Infinity;
      for (let k = 0; k < N; k++) if (!done[k] && dist[k] < best) { best = dist[k]; u = k; }
      if (u < 0 || u === j) break;
      done[u] = 1;
      for (const { j: v, e } of adj[u]) {
        const ed = edges[e];
        if (ed.count < minCount) continue;
        const w = ed.len * (1 + 3 / Math.sqrt(ed.count));      // strong bundles are cheaper
        if (dist[u] + w < dist[v]) { dist[v] = dist[u] + w; prev[v] = u; }
      }
    }
    if (!isFinite(dist[j])) return null;
    const hops = [j];
    while (hops[hops.length - 1] !== i) hops.push(prev[hops[hops.length - 1]]);
    return hops.reverse();
  }
  const pathCache = new Map();
  function pathBetween(i, j) {
    if (!(i >= 0 && i < N && j >= 0 && j < N)) return finishPath([], []);
    const key = i * N + j;
    if (pathCache.has(key)) return pathCache.get(key);
    let out;
    if (i === j) out = finishPath([districts[i].pos.clone(), districts[i].pos.clone()], [i]);
    else {
      const hops = route(i, j, 3) || route(i, j, 1) || [i, j];
      const pts = [districts[i].pos.clone()];
      for (let h = 0; h + 1 < hops.length; h++) {
        const u = hops[h], v = hops[h + 1];
        const eIdx = adj[u].find(x => x.j === v);
        if (eIdx) {
          const ed = edges[eIdx.e], line = fibreCity(ed.rep);
          const forward = endNode(E[2 * ed.rep]) === u;            // orient the fibre start -> end
          const seq = forward ? line : line.slice().reverse();
          for (let k = 1; k < seq.length - 1; k++) pts.push(seq[k].clone());
        }
        pts.push(districts[v].pos.clone());
      }
      out = finishPath(smooth(pts), hops);
    }
    pathCache.set(key, out);
    return out;
  }

  return {
    nodes, districts, roles, districtOf, placeDistrict, roads, graph, pathBetween, pointAt, mapPoint,
    radius, scale: SCALE, quality: q, lab2node,
  };
}

// ---------------- helpers ----------------
function isDeep(n) { return /Thalamus|Caudate|Putamen|Pallidum|Hippocampus|Amygdala|Accumbens/.test(n.name) || n.lab > 200; }
function dist3(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
function clampF(f, n) { return f < 0 ? 0 : f > n - 1.0001 ? n - 1.0001 : f; }
function labelOf(n) {
  const m = /^(LH|RH)_(\w+?)_(.+)$/.exec(n.name);
  if (m) return `${m[1] === "LH" ? "left" : "right"} ${n.group} · ${m[3].replace(/_/g, " ")}`;
  return n.name.toLowerCase();
}

/** Drop near-duplicates, then a centripetal Catmull-Rom resampled every ~2 city units. */
function smooth(pts) {
  const clean = [pts[0]];
  for (let k = 1; k < pts.length; k++) if (pts[k].distanceTo(clean[clean.length - 1]) > 0.5) clean.push(pts[k]);
  if (clean.length < 2) return [pts[0].clone(), pts[pts.length - 1].clone()];
  const curve = new THREE.CatmullRomCurve3(clean, false, "centripetal");
  const n = Math.max(2, Math.min(4000, Math.ceil(curve.getLength() / 2)));
  const out = curve.getSpacedPoints(n);
  out[0].copy(pts[0]); out[out.length - 1].copy(pts[pts.length - 1]);   // start / end exactly at the districts
  return out;
}

function finishPath(points, hops) {
  const lengths = new Float32Array(points.length);
  for (let k = 1; k < points.length; k++) lengths[k] = lengths[k - 1] + points[k].distanceTo(points[k - 1]);
  points.lengths = lengths;
  points.total = points.length ? lengths[points.length - 1] : 0;
  points.hops = hops;
  return points;
}

/** Point at fraction u (0..1) of a path's length (binary search on the cumulative lengths). */
export function pointAt(path, u, out = new THREE.Vector3()) {
  const n = path.length;
  if (!n) return out.set(0, 0, 0);
  if (n === 1 || !(path.total > 0)) return out.copy(path[0]);
  const d = Math.max(0, Math.min(1, u)) * path.total, L = path.lengths;
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (L[mid] <= d) lo = mid; else hi = mid; }
  const seg = L[hi] - L[lo];
  return out.copy(path[lo]).lerp(path[hi], seg > 0 ? (d - L[lo]) / seg : 0);
}
