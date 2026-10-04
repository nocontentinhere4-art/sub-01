// Short, slightly messy black hair as layered cards grown on the MakeHuman default head (head.json from
// extract_head.py, metres, the base mesh's own frame: face toward +z, crown at y = 0.849).
//   buildHair(THREE, head) -> {cards, scalp, stats}
// cards: alpha-textured strips (uv.x picks an atlas column of hair_tex.js, uv.y runs root -> tip), with vertex colours
//        as baked occlusion (inner layers and roots darker). Normals are the scalp's, so the cards shade as one volume.
// scalp: a thin shell 0.6 mm off the skin where the hair grows, dark, its vertex alpha fading out across the hairline.
import { ATLAS_COLS } from "./hair_tex.js";

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// Where the hair grows: the hairline's height (m) against the azimuth round the head (degrees, 0 = the face's middle,
// 90 = over the ear, 180 = the nape). A sideburn in front of the ear, a curve over it, the nape low at the back.
const HAIRLINE = [[0, 0.806], [22, 0.804], [38, 0.797], [50, 0.785], [60, 0.762], [68, 0.736], [76, 0.726],
                  [84, 0.752], [96, 0.770], [110, 0.764], [122, 0.722], [140, 0.690], [180, 0.672]];
export const CENTER = [0, 0.772, 0.052];          // the skull's middle, the rays are cast toward it

function hairlineY(azDeg){
  const a = Math.min(180, Math.abs(azDeg));
  for (let i = 1; i < HAIRLINE.length; i++) if (a <= HAIRLINE[i][0]){
    const [a0, y0] = HAIRLINE[i - 1], [a1, y1] = HAIRLINE[i]; return lerp(y0, y1, smooth(0, 1, (a - a0) / (a1 - a0)) * 0.5 + (a - a0) / (a1 - a0) * 0.5);
  }
  return HAIRLINE[HAIRLINE.length - 1][1];
}
const azimuth = p => Math.atan2(p.x - CENTER[0], p.z - CENTER[2]) * 180 / Math.PI;
export const inside = p => p.y - hairlineY(azimuth(p));          // > 0: on the scalp, metres above the hairline

export function buildHair(THREE, head, opt = {}){
  const R = rng(opt.seed ?? 11), V = THREE.Vector3;
  const hg = new THREE.BufferGeometry();
  hg.setAttribute("position", new THREE.Float32BufferAttribute(head.v, 3)); hg.setIndex(head.i); hg.computeVertexNormals();
  const C = new V(...CENTER), ray = new THREE.Ray(), tri = new THREE.Triangle(), bc = new V();
  const nA = new V(), nB = new V(), nC = new V(), nrm = hg.attributes.normal, pos = hg.attributes.position;

  // Triangles binned by their direction from the centre (azimuth x elevation), so a ray toward the centre only
  // tests the few that can lie across it.
  const GA = 96, GE = 48, bins = Array.from({length: GA * GE}, () => []), tv = new V();
  const dirOf = v => { tv.copy(v).sub(C); return [Math.atan2(tv.x, tv.z), Math.atan2(tv.y, Math.hypot(tv.x, tv.z))]; };
  const binA = a => Math.floor((a + Math.PI) / (2 * Math.PI) * GA), binE = e => Math.max(0, Math.min(GE - 1, Math.floor((e + Math.PI / 2) / Math.PI * GE)));
  for (let f = 0; f < head.i.length; f += 3){
    const ds = [0, 1, 2].map(k => dirOf(nA.fromBufferAttribute(pos, head.i[f + k])));
    let as = ds.map(d => d[0]); if (Math.max(...as) - Math.min(...as) > Math.PI) as = as.map(a => a < 0 ? a + 2 * Math.PI : a);
    const es = ds.map(d => d[1]), e0 = binE(Math.min(...es)) - 1, e1 = binE(Math.max(...es)) + 1;
    const a0 = binA(Math.min(...as)) - 1, a1 = binA(Math.max(...as)) + 1, polar = Math.max(...es.map(Math.abs)) > 1.3;
    for (let e = Math.max(0, e0); e <= Math.min(GE - 1, e1); e++)
      for (let a = polar ? 0 : a0; a <= (polar ? GA - 1 : a1); a++) bins[e * GA + ((a % GA) + GA) % GA].push(f);
  }
  const hitP = new V(), best = new V();
  function cast(d){
    const [az, el] = dirOf(tv.copy(C).add(d)), list = bins[binE(el) * GA + ((binA(az) % GA) + GA) % GA];
    ray.set(C.clone().addScaledVector(d, 0.4), d.clone().negate());
    let bd = Infinity, bf = -1;
    for (const f of list){
      nA.fromBufferAttribute(pos, head.i[f]); nB.fromBufferAttribute(pos, head.i[f + 1]); nC.fromBufferAttribute(pos, head.i[f + 2]);
      if (ray.intersectTriangle(nA, nB, nC, false, hitP)){ const t = hitP.distanceTo(ray.origin); if (t < bd){ bd = t; bf = f; best.copy(hitP); } }
    }
    return bf < 0 ? null : {point: best.clone(), face: {a: head.i[bf], b: head.i[bf + 1], c: head.i[bf + 2]}};
  }

  // The outer skin along a direction from the centre, with the smooth normal there.
  function surf(dir){
    const d = dir.clone().normalize();
    const hit = cast(d);
    if (!hit) return null;
    const {a, b, c} = hit.face;
    tri.setFromAttributeAndIndices(pos, a, b, c); tri.getBarycoord(hit.point, bc);
    nA.fromBufferAttribute(nrm, a); nB.fromBufferAttribute(nrm, b); nC.fromBufferAttribute(nrm, c);
    const n = new V().addScaledVector(nA, bc.x).addScaledVector(nB, bc.y).addScaledVector(nC, bc.z).normalize();
    if (n.dot(d) < 0) n.negate();
    return {p: hit.point.clone(), n};
  }

  // The ears stay clear: no roots on them, and hair ending over them stays short.
  const ear = p => Math.abs(p.x) > 0.064 && p.y > 0.695 && p.y < 0.758 && p.z > -0.006 && p.z < 0.058;

  // Root candidates: an even spread of directions, kept where hair grows.
  const cand = [], N = 9000, ga = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++){
    const y = 1 - 2 * (i + 0.5) / N, r = Math.sqrt(1 - y * y), th = ga * i;
    const s = surf(new V(Math.cos(th) * r, y, Math.sin(th) * r));
    if (!s || ear(s.p)) continue;
    const ins = inside(s.p); if (ins > 0.0005) cand.push({...s, ins, az: azimuth(s.p)});
  }

  // The combing: away from the crown's whorl, gravity taking over down the sides and back; the top's front comes
  // forward into a fringe that falls over the forehead, swept a little to his right (-x).
  const whorl = surf(new V(0.0, 0.85, -0.02).sub(C)).p;
  function flow(p, n, card){
    const top = smooth(0.792, 0.838, p.y), az = Math.abs(azimuth(p)), front = 1 - smooth(25, 60, az);
    const away = p.clone().sub(whorl); away.addScaledVector(n, -away.dot(n));
    const d = away.normalize().multiplyScalar(top * (0.6 + 0.4 * front) + 0.15);
    d.y -= (1 - top) * 1.0 + front * (1 - top) * 0.6;                               // gravity below the crown
    if (az > 55 && az < 130) d.z -= 0.35 * (1 - top);                                 // the sides go a little back
    d.x -= 0.28 * front * smooth(0.77, 0.80, p.y);                                    // the fringe's sweep
    d.addScaledVector(n, -d.dot(n));
    d.applyAxisAngle(n, card.turn);
    return d.normalize();
  }
  function lengthAt(p, az){
    const a = Math.abs(az), top = smooth(0.786, 0.826, p.y);
    let L = lerp(lerp(0.026, 0.017, smooth(115, 165, a)), 0.060, top);
    if (a < 42 && p.y > 0.79) L = lerp(0.060, 0.074, smooth(0.79, 0.81, p.y));       // the fringe
    return L;
  }

  // Layers: cover (wide, dense, on the skin), mid, outer (narrow, messy, lifted tips), an extra fringe so the forehead
  // never shows through in a hole, and hairline wisps.
  const LAYERS = [
    {name: "cover", gap: 0.0125, width: [0.022, 0.028], off: 0.0012, vol: 0.0,  turn: 0.12, cols: [0, 1, 2], ao: 0.62, lift: 0.0005, lenK: 0.95},
    {name: "mid",   gap: 0.0125, width: [0.016, 0.022], off: 0.0030, vol: 0.004, turn: 0.2, cols: [0, 2, 3, 4], ao: 0.8,  lift: 0.002, lenK: 1.0},
    {name: "outer", gap: 0.0135, width: [0.010, 0.016], off: 0.0050, vol: 0.0065, turn: 0.28, cols: [3, 4, 5], ao: 0.95, lift: 0.0028, lenK: 1.08},
    {name: "fringe", gap: 0.0062, width: [0.014, 0.020], off: 0.0042, vol: 0.003, turn: 0.2, cols: [0, 2, 3, 4], ao: 0.92, lift: 0.002, lenK: 1.06, fringe: true},
    {name: "wisp",  gap: 0.0075, width: [0.007, 0.011], off: 0.0009, vol: 0.0,  turn: 0.25, cols: [6, 7], ao: 0.85, lift: 0.0015, lenK: 0.45, edge: 0.012},
  ];
  const P = [], UV = [], COL = [], NRM = [], IDX = [];
  let cards = 0;
  for (const L of LAYERS){
    const pool = cand.filter(c => (L.edge ? c.ins < L.edge : true) && (L.fringe ? Math.abs(c.az) < 40 && c.p.y > 0.792 && c.p.y < 0.832 : true)).sort(() => R() - 0.5), roots = [];
    for (const c of pool){                                                           // closer where the hair is short
      const gap = L.gap * lerp(0.72, 1, smooth(0.74, 0.8, c.p.y));
      if (roots.every(r => r.p.distanceToSquared(c.p) > gap * gap)) roots.push(c);
    }
    for (const r of roots){
      const card = {turn: (R() - 0.5) * 2 * L.turn};
      const vol = L.vol * smooth(0.74, 0.83, r.p.y) * (0.6 + 0.6 * R());              // more volume on top
      const len = lengthAt(r.p, r.az) * L.lenK * (0.82 + R() * 0.36);
      const w = Math.min(lerp(L.width[0], L.width[1], R()) * (0.75 + 0.25 * smooth(0.74, 0.8, r.p.y)), len * 0.42);   // short hair, narrow cards
      const cols = len < 0.032 && !L.edge ? [3, 4, 5, 6] : L.cols;                     // short sides and nape: finer, see-through
      const col = cols[Math.floor(R() * cols.length)], flip = R() < 0.5;
      const u0 = (col + (flip ? 1 : 0)) / ATLAS_COLS, u1 = (col + (flip ? 0 : 1)) / ATLAS_COLS;
      const tw = (R() - 0.5) * (L.name === "outer" ? 0.6 : 0.2);                      // the card's tilt about its strand
      // Grow the guide along the scalp, then hang the strip on it (short cards need fewer segments).
      const SEG = len < 0.032 ? 3 : 4;
      let cur = r, rows = [];
      for (let k = 0; k <= SEG; k++){
        const t = k / SEG, offset = L.off + vol + t * L.lift * (0.4 + R());
        const dir = flow(cur.p, cur.n, card);
        const base = cur.p.clone().addScaledVector(cur.n, offset);
        rows.push({base, n: cur.n.clone(), dir, offset, t});
        if (k < SEG){
          card.turn += (R() - 0.5) * 0.15;
          const nx = surf(cur.p.clone().addScaledVector(dir, len / SEG).sub(C));
          if (!nx) break;
          cur = nx;
        }
      }
      if (rows.length < SEG + 1) continue;
      const v0 = P.length / 3;
      for (const row of rows){
        const side = new V().crossVectors(row.n, row.dir).normalize();
        const hw = w * 0.5 * (1 - 0.35 * row.t);
        for (const s of [-1, 1]){
          const q = surf(row.base.clone().addScaledVector(side, s * hw).sub(C));       // wrap the strip round the skull
          const p = q ? q.p.addScaledVector(q.n, row.offset + s * tw * hw) : row.base.clone().addScaledVector(side, s * hw);
          P.push(p.x, p.y, p.z); NRM.push(row.n.x, row.n.y, row.n.z);
          UV.push(s < 0 ? u0 : u1, row.t * 0.995);
          const occ = L.ao * lerp(0.62, 1.0, smooth(0, 0.7, row.t));
          COL.push(occ, occ, occ);
        }
      }
      for (let k = 0; k < SEG; k++){ const a = v0 + k * 2; IDX.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
      cards++;
    }
  }
  const cardsGeo = new THREE.BufferGeometry();
  cardsGeo.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  cardsGeo.setAttribute("normal", new THREE.Float32BufferAttribute(NRM, 3));
  cardsGeo.setAttribute("uv", new THREE.Float32BufferAttribute(UV, 2));
  cardsGeo.setAttribute("color", new THREE.Float32BufferAttribute(COL, 3));
  cardsGeo.setIndex(IDX);

  // The scalp tint: the head's own triangles near and inside the hair, pushed 0.6 mm out, alpha feathering out over
  // ~1.4 cm across the hairline so the skin darkens gradually into the hair, with a little noise so it isn't a line.
  const sp = [], sn = [], sc = [], si = [], map = new Map(), hv = new V(), hn = new V();
  for (let f = 0; f < head.i.length; f += 3){
    const ids = [head.i[f], head.i[f + 1], head.i[f + 2]];
    const al = ids.map(i => { hv.fromBufferAttribute(pos, i); return ear(hv) ? 0 : smooth(-0.006, 0.008, inside(hv)); });
    if (Math.max(...al) <= 0) continue;
    for (const i of ids){
      if (!map.has(i)){
        hv.fromBufferAttribute(pos, i); hn.fromBufferAttribute(nrm, i);
        const a = ear(hv) ? 0 : smooth(-0.006, 0.008, inside(hv)) * (0.86 + 0.1 * R());
        map.set(i, sp.length / 3);
        sp.push(hv.x + hn.x * 0.0006, hv.y + hn.y * 0.0006, hv.z + hn.z * 0.0006); sn.push(hn.x, hn.y, hn.z);
        sc.push(0.020, 0.016, 0.014, a);
      }
      si.push(map.get(i));
    }
  }
  const scalp = new THREE.BufferGeometry();
  scalp.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
  scalp.setAttribute("normal", new THREE.Float32BufferAttribute(sn, 3));
  scalp.setAttribute("color", new THREE.Float32BufferAttribute(sc, 4));
  scalp.setIndex(si);
  return {cards: cardsGeo, scalp, stats: {cards, cardTris: IDX.length / 3, scalpTris: si.length / 3, roots: cand.length}};
}
