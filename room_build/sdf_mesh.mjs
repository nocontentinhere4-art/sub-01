// Shared helpers for props modelled in code (build_desk_tech.mjs's, for build_chair.mjs): parts (positions, colours, uvs,
// indices), lofts and lathes with faces turned the way they should look, signed distance fields meshed by surface nets
// and simplified with meshoptimizer, normals from the field's gradient.
import { MeshoptSimplifier } from "meshoptimizer";
await MeshoptSimplifier.ready;
// ---------- a part: positions, colours, uvs, normals (optional, else smooth from faces), indices
function part(name){ return {name, pos: [], col: [], uv: [], nor: null, idx: []}; }
const add = (p, q, c, uv) => { p.pos.push(...q); p.col.push(...c, 1); p.uv.push(...uv); return p.pos.length / 3 - 1; };
function smoothNormals(p){
  const n = new Float32Array(p.pos.length), P = p.pos;
  for (let i = 0; i < p.idx.length; i += 3) {
    const [a, b, c] = [p.idx[i] * 3, p.idx[i + 1] * 3, p.idx[i + 2] * 3];
    const u = [P[b] - P[a], P[b + 1] - P[a + 1], P[b + 2] - P[a + 2]], v = [P[c] - P[a], P[c + 1] - P[a + 1], P[c + 2] - P[a + 2]];
    const f = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    for (const k of [a, b, c]) { n[k] += f[0]; n[k + 1] += f[1]; n[k + 2] += f[2]; }
  }
  for (let i = 0; i < n.length; i += 3) { const l = Math.hypot(n[i], n[i + 1], n[i + 2]) || 1; n[i] /= l; n[i + 1] /= l; n[i + 2] /= l; }
  return n;
}
function merge(into, p){                                       // append part p to part `into`
  const base = into.pos.length / 3;
  into.pos.push(...p.pos); into.col.push(...p.col); into.uv.push(...p.uv);
  into.nor.push(...(p.nor || smoothNormals(p))); into.idx.push(...p.idx.map(i => i + base));
}
// a closed ring of points -> a band to the next ring; rings are arrays of [x, y, z]. Faces wound so their normal looks
// along `out(centre)` (a function of the face's centre)
function bands(p, rings, c, uvu, out, capStart = false, capEnd = false){
  const ids = rings.map(r => r.map(q => add(p, q, c, [uvu, 0.5])));
  const tri = (a, b, d) => p.idx.push(a, b, d);
  for (let k = 0; k + 1 < ids.length; k++) { const A = ids[k], B = ids[k + 1], n = A.length;
    for (let i = 0; i < n; i++) { const j = (i + 1) % n; tri(A[i], B[i], B[j]); tri(A[i], B[j], A[j]); } }
  for (const [on, ring] of [[capStart, ids[0]], [capEnd, ids[ids.length - 1]]]) if (on) {
    const r = ring.map(i => p.pos.slice(3 * i, 3 * i + 3)), m = [0, 1, 2].map(a => r.reduce((s, q) => s + q[a], 0) / r.length);
    const ci = add(p, m, c, [uvu, 0.5]); const cr = ring.map(i => add(p, p.pos.slice(3 * i, 3 * i + 3), c, [uvu, 0.5]));
    for (let i = 0; i < cr.length; i++) p.idx.push(ci, cr[i], cr[(i + 1) % cr.length]);
  }
  orient(p, out);
}
// turn every triangle of p (from index `from`) so its face normal looks along out(centre)
function orient(p, out, from = 0){ orientRange(p, from, p.idx.length, out); }
function orientRange(p, from, to, out){
  const P = i => [p.pos[3 * i], p.pos[3 * i + 1], p.pos[3 * i + 2]];
  for (let t = from; t < to; t += 3) {
    const [a, b, c] = [P(p.idx[t]), P(p.idx[t + 1]), P(p.idx[t + 2])];
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const f = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const w = out([(a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3]);
    if (f[0] * w[0] + f[1] * w[1] + f[2] * w[2] < 0) [p.idx[t + 1], p.idx[t + 2]] = [p.idx[t + 2], p.idx[t + 1]];
  }
}
// a lathe about the vertical through (cx, cz): profile [[r, y], ...] from the axis outwards; rmod(angle, k) scales radii
function lathe(name, prof, cx, y0, cz, c, uvu, n = 32, rmod = null){
  const p = part(name);
  const rings = prof.map(([r, y], k) => Array.from({length: n}, (_, i) => { const a = 2 * Math.PI * i / n, rr = r * (rmod ? rmod(a, k) : 1);
    return [cx + rr * Math.cos(a), y0 + y, cz + rr * Math.sin(a)]; }));
  const ids = rings.map(r => r.map(q => add(p, q, c, [uvu, 0.5])));
  for (let k = 0; k + 1 < ids.length; k++) for (let i = 0; i < n; i++) { const j = (i + 1) % n;
    p.idx.push(ids[k][i], ids[k + 1][i], ids[k + 1][j], ids[k][i], ids[k + 1][j], ids[k][j]); }
  // each band faces along the profile's outward normal (-dy, dr): up on caps that run outwards, out on walls going down
  for (let k = 0; k + 1 < prof.length; k++) { const nr = -(prof[k + 1][1] - prof[k][1]), ny = prof[k + 1][0] - prof[k][0];
    const t0 = k * n * 6; orientRange(p, t0, t0 + n * 6, q => { const dx = q[0] - cx, dz = q[2] - cz, l = Math.hypot(dx, dz) || 1; return [nr * dx / l, ny, nr * dz / l]; }); }
  return p;
}

// ---------- signed distance fields and surface nets
const len3 = (x, y, z) => Math.hypot(x, y, z);
const sdRoundBox = (x, y, z, hx, hy, hz, r) => { const qx = Math.abs(x) - hx + r, qy = Math.abs(y) - hy + r, qz = Math.abs(z) - hz + r;
  return len3(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qy, qz), 0) - r; };
const sdEllipsoid = (x, y, z, a, b, c) => { const k0 = len3(x / a, y / b, z / c), k1 = len3(x / (a * a), y / (b * b), z / (c * c)); return k0 * (k0 - 1) / k1; };
function sdRoundCone(p, a, b, r1, r2){                      // a capsule whose radius goes from r1 at a to r2 at b
  const ba = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], pa = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
  const l2 = ba[0] ** 2 + ba[1] ** 2 + ba[2] ** 2, t = Math.max(0, Math.min(1, (pa[0] * ba[0] + pa[1] * ba[1] + pa[2] * ba[2]) / l2));
  return len3(pa[0] - ba[0] * t, pa[1] - ba[1] * t, pa[2] - ba[2] * t) - (r1 + (r2 - r1) * t);
}
const smin = (a, b, k) => { const h = Math.max(k - Math.abs(a - b), 0) / k; return Math.min(a, b) - h * h * k * 0.25; };
const smax = (a, b, k) => -smin(-a, -b, k);
// surface nets over [lo, hi] at `step`: a vertex per cell the surface crosses (the mean of its edge crossings), a quad per
// crossed grid edge; normals from the field's gradient
function surfaceNets(name, f, lo, hi, step, c, uvOf){
  const nx = Math.ceil((hi[0] - lo[0]) / step) + 1, ny = Math.ceil((hi[1] - lo[1]) / step) + 1, nz = Math.ceil((hi[2] - lo[2]) / step) + 1;
  const F = new Float32Array(nx * ny * nz), at = (i, j, k) => (k * ny + j) * nx + i;
  for (let k = 0; k < nz; k++) for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++)
    F[at(i, j, k)] = f(lo[0] + i * step, lo[1] + j * step, lo[2] + k * step);
  const p = part(name), cellV = new Int32Array(nx * ny * nz).fill(-1);
  const E = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
  for (let k = 0; k + 1 < nz; k++) for (let j = 0; j + 1 < ny; j++) for (let i = 0; i + 1 < nx; i++) {
    const v = [], cs = [];
    for (let m = 0; m < 8; m++) { const di = m & 1, dj = (m >> 1) & 1, dk = (m >> 2) & 1; v.push(F[at(i + di, j + dj, k + dk)]); cs.push([di, dj, dk]); }
    if (v.every(x => x > 0) || v.every(x => x <= 0)) continue;
    let sx = 0, sy = 0, sz = 0, n = 0;
    for (const [a, b] of E) if ((v[a] > 0) !== (v[b] > 0)) { const t = v[a] / (v[a] - v[b]);
      sx += cs[a][0] + t * (cs[b][0] - cs[a][0]); sy += cs[a][1] + t * (cs[b][1] - cs[a][1]); sz += cs[a][2] + t * (cs[b][2] - cs[a][2]); n++; }
    const q = [lo[0] + (i + sx / n) * step, lo[1] + (j + sy / n) * step, lo[2] + (k + sz / n) * step];
    cellV[at(i, j, k)] = add(p, q, c, uvOf(q));
  }
  for (let k = 1; k + 1 < nz; k++) for (let j = 1; j + 1 < ny; j++) for (let i = 1; i + 1 < nx; i++) {
    const s0 = F[at(i, j, k)] > 0;
    for (const [di, dj, dk, A, B] of [[1, 0, 0, [0, 1, 0], [0, 0, 1]], [0, 1, 0, [0, 0, 1], [1, 0, 0]], [0, 0, 1, [1, 0, 0], [0, 1, 0]]]) {
      if (i + di >= nx || j + dj >= ny || k + dk >= nz) continue;
      if (s0 === (F[at(i + di, j + dj, k + dk)] > 0)) continue;
      const c0 = at(i, j, k), c1 = at(i - A[0], j - A[1], k - A[2]), c2 = at(i - A[0] - B[0], j - A[1] - B[1], k - A[2] - B[2]), c3 = at(i - B[0], j - B[1], k - B[2]);
      const q = [cellV[c0], cellV[c1], cellV[c2], cellV[c3]];
      if (q.some(x => x < 0)) continue;
      if (s0) p.idx.push(q[0], q[1], q[2], q[0], q[2], q[3]); else p.idx.push(q[0], q[2], q[1], q[0], q[3], q[2]);
    }
  }
  return p;
}
function gradNormals(p, f){
  const e = 1e-4, n = [];
  for (let i = 0; i < p.pos.length; i += 3) { const [x, y, z] = p.pos.slice(i, i + 3);
    const g = [f(x + e, y, z) - f(x - e, y, z), f(x, y + e, z) - f(x, y - e, z), f(x, y, z + e) - f(x, y, z - e)], l = Math.hypot(...g) || 1;
    n.push(g[0] / l, g[1] / l, g[2] / l); }
  return n;
}
function simplify(p, f, ratio, err){                       // fewer triangles (meshoptimizer), then compact and SDF normals
  const idx = new Uint32Array(p.idx), pos = new Float32Array(p.pos);
  const [out] = MeshoptSimplifier.simplify(idx, pos, 3, Math.floor(idx.length * ratio / 3) * 3, err);
  orientFix(p, out, f);
  const map = new Map(), q = part(p.name);
  for (const i of out) if (!map.has(i)) { map.set(i, q.pos.length / 3); q.pos.push(...p.pos.slice(3 * i, 3 * i + 3)); q.col.push(...p.col.slice(4 * i, 4 * i + 4)); q.uv.push(...p.uv.slice(2 * i, 2 * i + 2)); }
  q.idx = [...out].map(i => map.get(i)); q.nor = gradNormals(q, f); return q;
}
function orientFix(p, idx, f){                              // (the triangles' winding against the field's gradient)
  for (let t = 0; t < idx.length; t += 3) {
    const P = i => p.pos.slice(3 * i, 3 * i + 3), a = P(idx[t]), b = P(idx[t + 1]), c = P(idx[t + 2]);
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const fn = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const m = [0, 1, 2].map(k => (a[k] + b[k] + c[k]) / 3), e = 1e-4;
    const g = [f(m[0] + e, m[1], m[2]) - f(m[0] - e, m[1], m[2]), f(m[0], m[1] + e, m[2]) - f(m[0], m[1] - e, m[2]), f(m[0], m[1], m[2] + e) - f(m[0], m[1], m[2] - e)];
    if (fn[0] * g[0] + fn[1] * g[1] + fn[2] * g[2] < 0) { const s = idx[t + 1]; idx[t + 1] = idx[t + 2]; idx[t + 2] = s; }
  }
}

export { part, add, smoothNormals, merge, bands, orient, orientRange, lathe, len3, sdRoundBox, sdEllipsoid, sdRoundCone, smin, smax, surfaceNets, gradNormals, simplify, orientFix };
