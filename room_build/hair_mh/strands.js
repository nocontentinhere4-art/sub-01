// Real strands for a medium-length layered curtain cut on a ~20-year-old: ~45k individual hairs grown on the scalp.
//   growStrands(THREE, hair, opt) -> {lines, stats}
// The cut: top 9-12 cm from a part near the centre (a little to his left, +x); the two halves of the fringe fall to
// the brows and the outer eye corners and sweep out toward the temples and cheekbones, a few loose strands across the
// forehead; sides 6-8 cm over the upper half of the ears and behind them; nape 8-10 cm to the collar with soft,
// flicked-out ends. Natural loose waves, piece-y clumps of 20-40 hairs that twist and split, volume at the crown and
// lifted roots by the part. Dry and soft: fuller clumps, loose waves, little frizz.
// lines: a LineSegments-ready BufferGeometry, one polyline per hair (its points contiguous, segments i -> i+1),
//   position, normal (the scalp normal under the hair's root, for the lighting's wrap and self-shadow) and color =
//   (t along the hair 0..1, a per-hair random shared in part by its clump, the self-shadow 0..1, the distance to the
//   tip in cm capped at 1). Hairs are shuffled, so the first half of the index range is a uniform half-density LOD.
// How: clump guides ~5 mm apart are grown along a combing field (away from the part, forward and out at the front,
// down over the sides and back), hugging the head at a height that grows with the length (longer hair lies over
// shorter) and hanging free under gravity once they leave the skull; a slow wave rides along each guide. Each guide
// carries ~30 hairs rooted round it, twisted round it along their length, most pulled back into it toward the tips,
// a few splitting away. The fringe guides are cut evenly at the brows and outer eye corners.
import { inside } from "./hair_gen.js";

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

export const PART_X = 0.006;                                     // the part, a little to his left of the centre
const C0 = [0, 0.772, 0.052];
const az = p => Math.atan2(p.x - C0[0], p.z - C0[2]) * 180 / Math.PI;

export function growStrands(THREE, hair, opt = {}){
  const V = THREE.Vector3, R = rng(opt.seed ?? 31), N = opt.count ?? 45000, GAP = opt.gap ?? 0.006;
  const C = new V(...C0), DOWN = new V(0, -1, 0);

  // Lengths by region (metres): top 9-12 cm, the fringe from the front hairline to about the brows, sides 6-8 cm,
  // the nape 8-10 cm.
  function lengthAt(p){
    const a = Math.abs(az(p)), top = smooth(0.79, 0.835, p.y), front = 1 - smooth(25, 55, a), back = smooth(120, 165, a);
    let L = lerp(lerp(0.07, 0.095, back), lerp(0.10, 0.12, smooth(0.0, 0.06, -(p.z - 0.10))), top);  // sides 6-8 cm over the upper ear / nape -> top
    if (front > 0 && p.y > 0.785) L = Math.max(L, 0.11);                              // the fringe: long enough, cut at the brows below
    return L;
  }
  // The combing field at a point on (or near) the head, as a direction in its tangent plane.
  function comb(p, n){
    const side = Math.sign(p.x - PART_X) || 1, a = Math.abs(az(p)), top = smooth(0.78, 0.83, p.y);
    const front = 1 - smooth(20, 70, a), back = smooth(110, 160, a);
    const fronthalf = smooth(0.025, 0.075, p.z);                                    // the part only runs over the front half of the head (none at the crown)
    const nearPart = 1 - smooth(0.004, 0.03, Math.abs(p.x - PART_X));
    const d = new V(side * (0.45 + 0.5 * top) * fronthalf * (1 - 0.75 * front) * (1 - 0.8 * nearPart * front), 0, 0);   // away from the part; by the part at the front, straight forward
    d.z += 1.2 * front * top - 0.8 * back * top;                                    // forward over the forehead at the front, back behind
    d.y -= 0.35 + 0.9 * (1 - top);                                                  // gravity, stronger off the top
    if (p.y < 0.80 && front > 0.3){                                                 // the curtains: down over the forehead, then out and back toward the temples near the brows
      const k = smooth(0.795, 0.76, p.y); d.x += side * (0.15 + 1.6 * k); d.z -= 0.4 * k; d.y -= 0.55 - 0.3 * k; }   // a narrow V at the part, then the curtains turn out
    if (a > 70 && a < 130 && p.y < 0.79) d.z -= 0.45;                               // over and behind the ears
    d.addScaledVector(n, -d.dot(n));
    return d.normalize();
  }

  // Clump guide roots, an even jittered spread where hair grows.
  const roots = [], M = 40000, ga = Math.PI * (3 - Math.sqrt(5)), grid = new Map(), key = p => `${Math.floor(p.x / GAP)},${Math.floor(p.y / GAP)},${Math.floor(p.z / GAP)}`;
  for (let i = 0; i < M; i++){
    const y = 1 - 2 * (i + R()) / M, r = Math.sqrt(Math.max(0, 1 - y * y)), th = ga * i + R() * 0.3;
    const s = hair.surfAt(C.clone().add(new V(Math.cos(th) * r, y, Math.sin(th) * r)));
    if (!s || hair.ear(s.p) || inside(s.p) < 0.0008) continue;
    const [gx, gy, gz] = key(s.p).split(",").map(Number); let near = false;
    for (let a = -1; a <= 1 && !near; a++) for (let b = -1; b <= 1 && !near; b++) for (let c = -1; c <= 1 && !near; c++)
      for (const q of grid.get(`${gx + a},${gy + b},${gz + c}`) || []) if (q.p.distanceToSquared(s.p) < GAP * GAP){ near = true; break; }
    if (near) continue;
    roots.push(s); const k = key(s.p); (grid.get(k) || grid.set(k, []).get(k)).push(s);
  }

  // Guides: march along the combing field; while the head is under the hair, sit on it at a height that grows with the
  // distance travelled (and a lift at the roots by the part and the crown); past the head, hang under gravity.
  const guides = [];
  for (const r of roots){
    const L = lengthAt(r.p) * (0.88 + 0.24 * R()), P = Math.max(5, Math.min(11, Math.round(L / 0.0115) + 1)), step = L / (P - 1);
    const nearPart = (1 - smooth(0.004, 0.025, Math.abs(r.p.x - PART_X))) * smooth(0.05, 0.09, r.p.z), top = smooth(0.79, 0.835, r.p.y);   // the part's lift only at the front (no notch at the crown)
    const crown = smooth(0.825, 0.845, r.p.y) * (1 - smooth(0.03, 0.08, r.p.z));    // the crown, behind the part
    const lift = (0.007 + 0.014 * nearPart * top + 0.014 * top + 0.008 * crown) * (0.75 + 0.5 * R());   // lifted roots across the top, more by the part, raised crown
    const wave = {A: 0.002 + 0.003 * R(), lam: 0.05 + 0.03 * R(), ph: R() * 6.28};   // soft, loose waves
    const pts = [], nrm = []; let p = r.p.clone(), n = r.n.clone(), dir = comb(p, n), free = false, arc = 0;
    for (let k = 0; k < P; k++){
      const off = Math.min(0.028, 0.0006 + lift * Math.sin(Math.min(1, arc / 0.025) * Math.PI / 2) + 0.09 * arc);  // longer hair stacks over shorter (capped)
      const side = new V().crossVectors(n, dir).normalize();
      const w = wave.A * smooth(0, 0.03, arc) * Math.sin(arc / wave.lam * 6.28 + wave.ph);
      pts.push(p.clone().addScaledVector(n, free ? 0 : off).addScaledVector(side, w)); nrm.push(r.n);
      if (k === P - 1) break;
      if (!free){
        const s = hair.surfAt(p.clone().addScaledVector(dir, step));
        if (s && s.p.distanceTo(p) < step * 2.2 && s.n.y > -0.75 && inside(s.p) > -0.06){ dir = comb(s.p, s.n); p = s.p; n = s.n; }
        else { free = true; p = p.clone().addScaledVector(n, off); }
      }
      if (free){ dir.lerp(DOWN, 0.35).normalize(); p = p.clone().addScaledVector(dir, step); }
      arc += step;
    }
    const a = Math.abs(az(r.p)), front = a < 50 && r.p.y > 0.785;
    let Lg = L, gp = pts;
    if (front){                                                                     // the fringe ends evenly at the brows / outer eye corners
      const target = 0.753 - 0.022 * smooth(5, 50, a) + (R() - 0.5) * 0.008, cut = [gp[0]];   // a curved front edge: brows at the middle, cheekbone at the temple
      for (let k = 1; k < gp.length; k++){
        if (gp[k].y > target){ cut.push(gp[k]); continue; }
        const u = (gp[k - 1].y - target) / Math.max(1e-6, gp[k - 1].y - gp[k].y); cut.push(gp[k - 1].clone().lerp(gp[k], u)); break;
      }
      let total = 0; const acc = [0]; for (let k = 1; k < cut.length; k++){ total += cut[k].distanceTo(cut[k - 1]); acc.push(total); }
      gp = []; for (let k = 0; k < P; k++){ const d = total * k / (P - 1); let j = 1; while (j < acc.length - 1 && acc[j] < d) j++;
        const u = (d - acc[j - 1]) / Math.max(1e-6, acc[j] - acc[j - 1]); gp.push(cut[j - 1].clone().lerp(cut[Math.min(j, cut.length - 1)], Math.min(1, u))); }
      Lg = total;
    }
    guides.push({pts: gp, nrm, L: Lg, P, top, flick: a > 70 && r.p.y < 0.80 ? 1 : 0, front});
  }

  // Hairs round each guide.
  const per = N / guides.length, hairs = [];
  for (const g of guides){
    const n0 = g.nrm[0], t1 = new V().crossVectors(n0, new V(0.3, 1, 0.2)).normalize(), t2 = new V().crossVectors(n0, t1);
    const count = Math.round(per * (0.8 + 0.4 * R())), clumpRnd = R(), twist = (R() - 0.5) * 30;
    for (let h = 0; h < count; h++){
      const a0 = R() * Math.PI * 2, rr = Math.sqrt(R()) * GAP * 0.85;
      const root = g.pts[0].clone().addScaledVector(t1, Math.cos(a0) * rr).addScaledVector(t2, Math.sin(a0) * rr), ins = inside(root);
      if (ins < 0.0003 || R() > 0.12 + 0.88 * smooth(0.0, 0.007, ins)) continue;          // a soft, thinning hairline
      const split = R() < (g.top < 0.4 ? 0.02 : 0.05), stray = g.front && R() < 0.004;                             // a few pieces split away; rare strays over the forehead
      const sideLock = g.top < 0.4;                                                       // sides and nape: fuller locks, no stick spikes
      const clump = split ? 0.3 + 0.3 * R() : sideLock ? 0.3 + 0.25 * R() : 0.55 + 0.3 * R();
      const lf = g.front ? 0.95 + 0.05 * R() : sideLock ? 0.93 + 0.07 * R() : 0.85 + 0.15 * R(), rnd = 0.6 * clumpRnd + 0.4 * R();
      const ph = R() * 6.28, frizz = 0.0002 + 0.00025 * R(), edge = rr / (GAP * 0.85), cshade = 1 - 0.3 * edge * edge;
      const pts = [], col = [], nrm = [];
      for (let k = 0; k < g.P; k++){
        const t = k / (g.P - 1), f = Math.min(g.P - 1.0001, t * lf * (g.P - 1)), i = Math.floor(f), u = f - i;
        const p = g.pts[i].clone().lerp(g.pts[i + 1], u);
        const ang = a0 + twist * t * g.L, keep = rr * (1 - clump * smooth(0.0, 0.8, t));       // twist round the guide, pulled in
        p.addScaledVector(t1, Math.cos(ang) * keep).addScaledVector(t2, Math.sin(ang) * keep);
        p.add(new V(Math.sin(ph + t * 9), Math.cos(ph * 1.3 + t * 7), Math.sin(ph * 0.7 + t * 11)).multiplyScalar(frizz * t));
        if (g.flick) p.addScaledVector(g.nrm[0], 0.008 * smooth(0.75, 1.0, t));            // flicked-out ends
        if (stray) p.add(new V((ph - 3) * 0.002 * t, -0.002 * t, 0.002 * t));
        const shade = Math.min(1, (0.45 + 0.55 * smooth(0.0, 0.5, t)) * (0.85 + 0.15 * g.top) * cshade * (0.7 + 0.55 * clumpRnd));   // locks read: per-clump light and dark
        const tip = Math.min(1, (1 - t) * g.L * lf / 0.01);
        pts.push(p); nrm.push(g.nrm[0]); col.push(t, rnd, shade, tip);
      }
      hairs.push({pts, nrm, col});
    }
  }
  for (let i = hairs.length - 1; i > 0; i--){ const j = Math.floor(R() * (i + 1)); [hairs[i], hairs[j]] = [hairs[j], hairs[i]]; }

  const pos = [], nor = [], colr = [], idx = [];
  for (const h of hairs){
    const b = pos.length / 3;
    h.pts.forEach((p, k) => { pos.push(p.x, p.y, p.z); nor.push(h.nrm[k].x, h.nrm[k].y, h.nrm[k].z); colr.push(...h.col.slice(k * 4, k * 4 + 4)); if (k) idx.push(b + k - 1, b + k); });
  }
  const lines = new THREE.BufferGeometry();
  lines.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  lines.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  lines.setAttribute("color", new THREE.Float32BufferAttribute(colr, 4));
  lines.setIndex(idx);
  return {lines, stats: {hairs: hairs.length, guides: guides.length, points: pos.length / 3, segments: idx.length / 2}};
}
