// Real strands for the short textured-fringe cut: ~50k individual hairs grown on the scalp, the way game grooms do
// short hair. Uses hair_gen.js's head helpers (the scalp surface, the hairline, the growth direction from the crown's
// whorl, the cut's lengths by region).
//   growStrands(THREE, hair, opt) -> {lines, stats}
// lines: a LineSegments-ready BufferGeometry, one polyline per hair (its points contiguous, segments i -> i+1),
//   position, normal (the scalp normal under the hair, for the lighting's wrap and self-shadow) and color = (t along
//   the hair 0..1, a per-hair random, the self-shadow 0..1, 1). Hairs are shuffled, so the first half of the index
//   range is a uniform half-density LOD.
// How: clump guides ~4 mm apart grow along the growth direction at a height over the scalp that rises with length
// on top (the stack of a real cut); each guide carries ~25 hairs rooted in a disc round it that leave it at the
// root and are pulled back toward it along their length (soft clumps that stay mostly separate), each with its own
// length (choppy ends), a little curl and frizz; ~2 % flyaways on top.
import { inside } from "./hair_gen.js";

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function growStrands(THREE, hair, opt = {}){
  const V = THREE.Vector3, R = rng(opt.seed ?? 21), N = opt.count ?? 50000, GAP = opt.gap ?? 0.0042;
  const C = new V(0, 0.772, 0.052);

  // Clump guide roots: an even, jittered spread over where hair grows.
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

  // Guides: polylines along the growth direction, re-projected onto the scalp at a rising height.
  const guides = roots.map(r => {
    const top = hair.topness(r.p), L = hair.lengthAt(r.p) * (0.85 + 0.3 * R());
    const P = L < 0.012 ? 4 : L < 0.03 ? 5 : 7, vol = top * (0.006 + 0.010 * R()), card = {turn: (R() - 0.5) * 0.3};
    const pts = [], nrm = [], offs = []; let cur = r;
    for (let k = 0; k < P; k++){
      const t = k / (P - 1), off = 0.0004 + vol * Math.sin(Math.min(1, t * 1.25) * Math.PI / 2) + (1 - top) * 0.0010 * t;   // stands up, then lies over
      pts.push(cur.p.clone().addScaledVector(cur.n, off)); nrm.push(cur.n.clone()); offs.push(off);
      if (k < P - 1){
        card.turn += (R() - 0.5) * 0.1;
        const d = hair.flow(cur.p, cur.n, card);
        const nx = hair.surfAt(cur.p.clone().addScaledVector(d, L / (P - 1)));
        if (!nx) break; cur = nx;
      }
    }
    return pts.length === P ? {pts, nrm, offs, top, L, P} : null;
  }).filter(Boolean);

  // Hairs round each guide.
  const per = N / guides.length, hairs = [];
  const at = (g, t) => { const f = Math.min(g.P - 1.0001, t * (g.P - 1)), i = Math.floor(f), u = f - i;
    return [g.pts[i].clone().lerp(g.pts[i + 1], u), g.nrm[i].clone().lerp(g.nrm[i + 1], u).normalize(), g.offs[i] + (g.offs[i + 1] - g.offs[i]) * u]; };
  for (const g of guides){
    const n0 = g.nrm[0], t1 = new V().crossVectors(n0, new V(0.3, 1, 0.2)).normalize(), t2 = new V().crossVectors(n0, t1);
    const count = Math.round(per * (0.7 + 0.6 * R()));
    for (let h = 0; h < count; h++){
      const a = R() * Math.PI * 2, rr = Math.sqrt(R()) * GAP * 0.8;
      const D = t1.clone().multiplyScalar(Math.cos(a) * rr).addScaledVector(t2, Math.sin(a) * rr);
      const root = g.pts[0].clone().add(D); if (inside(root) < 0.0003) continue;
      const front = Math.abs(Math.atan2(g.pts[0].x, g.pts[0].z - 0.052)) < 0.7 && g.pts[0].y > 0.785;   // the fringe: firmer pieces
      const fly = g.top > 0.5 && R() < 0.02, lf = fly ? 0.9 + 0.3 * R() : 0.72 + 0.33 * R(), clump = front ? 0.7 + 0.25 * R() : 0.45 + 0.4 * R();
      const lift = (R() - 0.3) * 0.0016 * g.top, ph = R() * 6.28, curl = (0.0002 + 0.0005 * R()) * (0.4 + g.top), rnd = R();
      const pts = [], col = [], nrm = [];
      for (let k = 0; k < g.P; k++){
        const t = k / (g.P - 1), [p, n, off] = at(g, t * lf);
        const pull = clump * Math.pow(smooth(0, 1, t), 0.9);
        p.addScaledVector(D, 1 - pull).addScaledVector(n, lift * t);
        p.addScaledVector(t1, Math.sin(ph + t * 7) * curl * t).addScaledVector(t2, Math.cos(ph * 1.7 + t * 5) * curl * t);
        p.add(new V(R() - 0.5, R() - 0.5, R() - 0.5).multiplyScalar(0.0003 * t));          // frizz
        if (fly) p.addScaledVector(n, 0.005 * Math.pow(t, 1.6)).addScaledVector(t1, (ph - 3) * 0.0012 * t * t);
        const shade = Math.min(1, 0.35 + 0.65 * smooth(0.0004, 0.0004 + 0.008 * g.top + 0.0012, off + lift * t)) ;
        pts.push(p); nrm.push(n); col.push(t, rnd, Math.max(shade, g.top < 0.3 ? 0.55 : 0), 1);
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
