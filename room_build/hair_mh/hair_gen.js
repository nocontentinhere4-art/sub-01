// A short textured fringe cut as layered hair cards grown on the MakeHuman default head (head.json from
// extract_head.py, metres, the base mesh's own frame: face toward +z, crown at y = 0.849). The cut: about 5 cm on
// top with choppy texture, a fringe brought forward in small separate pieces that stops just above the brows with the
// forehead showing between them, and the sides and back tapered short (1-2 cm, tight to the head, shortest at the
// hairline so the temples and nape show scalp shadow); nothing over the ears.
//   buildHair(THREE, head) -> {cards, scalp, scalpStrokes, stats}
// cards: alpha-textured strips, narrow (0.5-1.5 cm), grown from the crown's whorl along the growth direction, layered
//        from opaque cards hugging the scalp through more transparent mid layers to a few flyaways. uv.x picks an atlas
//        column of hair_tex.js, uv.y runs root -> tip; tangent = the strand direction (for the Kajiya-Kay highlights);
//        vertex colours = baked occlusion (inner layers and roots darker) times a slight per-card brown-black tint.
//        Normals are the scalp's, so the cards shade as one volume.
// scalp: the painted base layer, a shell 0.6 mm off the skin where hair grows, with an equirectangular uv round the
//        skull (paintScalp() draws its strokes along the growth direction) and vertex alpha feathering across the
//        hairline.
import { ATLAS_COLS } from "./hair_tex.js";

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// Where the hair grows: the hairline's height (m) against the azimuth round the head (degrees, 0 = the face's middle,
// 90 = over the ear, 180 = the nape). A sideburn in front of the ear, a curve over it, the nape low at the back.
const HAIRLINE = [[0, 0.806], [22, 0.804], [38, 0.796], [50, 0.779], [60, 0.752], [68, 0.734], [76, 0.728],
                  [84, 0.738], [96, 0.749], [110, 0.744], [122, 0.714], [140, 0.688], [180, 0.672]];   // down to the ear's rim
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

  // The ears stay clear: no roots on them.
  const ear = p => Math.abs(p.x) > 0.066 && p.y > 0.695 && p.y < 0.750 && p.z > -0.004 && p.z < 0.056;

  // Root candidates: an even spread of directions, kept where hair grows.
  const cand = [], N = 12000, ga = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++){
    const y = 1 - 2 * (i + 0.5) / N, r = Math.sqrt(1 - y * y), th = ga * i;
    const s = surf(new V(Math.cos(th) * r, y, Math.sin(th) * r));
    if (!s || ear(s.p)) continue;
    const ins = inside(s.p); if (ins > 0.0005) cand.push({...s, ins, az: azimuth(s.p)});
  }

  // How far up the head a point is in the cut: 0 in the tapered sides and back, 1 on top (the "weight line" sits a
  // little above the temples and runs back round the head, lower behind).
  const topness = (p, az) => smooth(lerp(0.792, 0.808, smooth(60, 150, Math.abs(az))), lerp(0.806, 0.826, smooth(60, 150, Math.abs(az))), p.y);

  // The growth direction: away from the crown's whorl (a little behind the top), forward over the top into the fringe
  // with a slight sweep to his right (-x), straight down the tapered sides and back.
  const whorl = surf(new V(0.0, 0.85, -0.02).sub(C)).p;
  function flow(p, n, card){
    const az = azimuth(p), top = topness(p, az), front = 1 - smooth(25, 60, Math.abs(az));
    const away = p.clone().sub(whorl); away.addScaledVector(n, -away.dot(n));
    const dw = away.length(); away.normalize();
    if (dw < 0.012) away.lerp(new V(0, -0.3, -1).addScaledVector(n, -n.z), 1 - dw / 0.012).normalize();   // round the whorl
    away.addScaledVector(new V().crossVectors(n, away), 1.4 * (1 - smooth(0.0, 0.07, dw))).normalize();     // the whorl's spiral
    const d = away.multiplyScalar(0.25 + 0.75 * top);
    d.y -= (1 - top) * 1.2;                                                           // the taper combs down
    d.x -= 0.25 * front * smooth(0.79, 0.81, p.y);                                    // the fringe's sweep
    d.addScaledVector(n, -d.dot(n));
    if (card) d.applyAxisAngle(n, card.turn);
    return d.normalize();
  }
  // Hair length at a root: about 5 cm on top, the fringe long enough to reach just above the brows (~0.758),
  // tapering from ~2 cm at the weight line to under 1 cm at the hairline on the sides and nape.
  function lengthAt(p, az){
    const a = Math.abs(az), top = topness(p, az), ins = inside(p);
    const taper = lerp(0.006, 0.019, smooth(0.0, 0.05, ins));
    let L = lerp(taper, a > 120 ? 0.042 : 0.05, top);
    if (a < 40 && p.y > 0.79) L = Math.max(L, (p.y - 0.768) * 1.15);                  // the fringe: tips ~1 cm above the brows
    return L;
  }

  // Layers, from the scalp out: base (opaque, hugging the scalp), mid (more transparent, some lift on top), the
  // fringe's separate pieces, flyaways (a few single hairs breaking the silhouette on top), and the short taper.
  const LAYERS = [
    {name: "base",  gap: 0.0100, width: [0.010, 0.014], off: 0.0010, vol: 0.0,    turn: 0.10, cols: [0, 1], ao: 0.62, lift: 0.0005, lenK: 0.9, top: true},
    {name: "mid",   gap: 0.0095, width: [0.008, 0.012], off: 0.0028, vol: 0.0045, turn: 0.18, cols: [1, 2, 3], ao: 0.85, lift: 0.0030, lenK: 1.0, top: true},
    {name: "piece", gap: 0.0110, width: [0.006, 0.009], off: 0.0045, vol: 0.0065, turn: 0.22, cols: [2, 3], ao: 0.78, lift: 0.0025, lenK: 1.0, top: true},
    {name: "fringe", gap: 0.0050, width: [0.010, 0.014], off: 0.0035, vol: 0.002, turn: 0.12, cols: [0, 1], ao: 0.75, lift: 0.0015, lenK: 0.75, fringe: true},
    {name: "fly",   gap: 0.0450, width: [0.004, 0.006], off: 0.0055, vol: 0.005,  turn: 0.5, cols: [6, 7], ao: 1.0, lift: 0.005, lenK: 0.85, top: true},
    {name: "taper", gap: 0.0045, width: [0.005, 0.008], off: 0.0007, vol: 0.0,    turn: 0.12, cols: [6, 7], ao: 1.0, lift: 0.0003, lenK: 1.0, side: true, thin: 0.7},
  ];
  const P = [], UV = [], COL = [], NRM = [], TAN = [], IDX = [];
  let cards = 0;
  for (const L of LAYERS){
    if (opt.layers && !opt.layers.includes(L.name)) continue;
    const pool = cand.filter(c => {
      const t = topness(c.p, c.az);
      if (L.fringe) return Math.abs(c.az) < 40 && c.p.y > 0.792 && c.p.y < 0.83;
      if (L.side) return t < 0.85;
      return t > 0.05;
    }).sort(() => R() - 0.5), roots = [];
    for (const c of pool) if (roots.every(r => r.p.distanceToSquared(c.p) > L.gap * L.gap)) roots.push(c);
    for (const r of roots){
      const card = {turn: (R() - 0.5) * 2 * L.turn}, top = topness(r.p, r.az);
      const vol = L.vol * top * (0.5 + 0.8 * R()) * smooth(0.006, 0.02, r.p.distanceTo(whorl));
      const len = Math.max(0.004, lengthAt(r.p, r.az) * L.lenK * (0.75 + R() * 0.5));   // choppy: lengths vary
      const w = Math.min(lerp(L.width[0], L.width[1], R()), len * (L.thin || 0.45));
      const col = L.cols[Math.floor(R() * L.cols.length)], flip = R() < 0.5;
      const u0 = (col + (flip ? 1 : 0)) / ATLAS_COLS, u1 = (col + (flip ? 0 : 1)) / ATLAS_COLS;
      const tw = (R() - 0.5) * (L.name === "piece" ? 0.6 : 0.2);                      // the card's tilt about its strand
      const SEG = len < 0.012 ? 1 : len < 0.025 ? 2 : len < 0.045 ? 3 : 4;
      let cur = r, rows = [];
      for (let k = 0; k <= SEG; k++){
        const t = k / SEG, offset = L.off + vol + t * L.lift * (0.4 + R()) * (L.side ? 1 : 0.4 + top) + (opt.over ? opt.over(topness(cur.p, azimuth(cur.p))) : 0);
        const dir = flow(cur.p, cur.n, card);
        rows.push({base: cur.p.clone().addScaledVector(cur.n, offset), n: cur.n.clone(), dir, offset, t});
        if (k < SEG){
          card.turn += (R() - 0.5) * 0.12;
          const nx = surf(cur.p.clone().addScaledVector(dir, len / SEG).sub(C));
          if (!nx) break;
          cur = nx;
        }
      }
      if (rows.length < SEG + 1) continue;
      const v0 = P.length / 3, hue = R() < 0.3 ? 0.4 + R() * 0.6 : (R() - 0.5) * 0.25;   // a few browner cards
      const tint = [1 + 0.2 * hue, 1 + 0.1 * hue, 1 - 0.02 * hue], bright = 0.5 + R() * 0.15;     // matched to the shell under them
      for (const row of rows){
        const side = new V().crossVectors(row.n, row.dir).normalize();
        const hw = w * 0.5 * (1 - 0.3 * row.t);
        for (const s of [-1, 1]){
          const q = surf(row.base.clone().addScaledVector(side, s * hw).sub(C));       // wrap the strip round the skull
          const p = q ? q.p.addScaledVector(q.n, row.offset + s * tw * hw) : row.base.clone().addScaledVector(side, s * hw);
          P.push(p.x, p.y, p.z); NRM.push(row.n.x, row.n.y, row.n.z); TAN.push(row.dir.x, row.dir.y, row.dir.z, 1);
          UV.push(s < 0 ? u0 : u1, row.t * 0.995);
          const occ = L.ao * lerp(0.6, 1.0, smooth(0, 0.7, row.t));
          COL.push(occ * tint[0] * bright, occ * tint[1] * bright, occ * tint[2] * bright);
        }
      }
      for (let k = 0; k < SEG; k++){ const a = v0 + k * 2; IDX.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
      cards++;
    }
  }
  const cardsGeo = new THREE.BufferGeometry();
  cardsGeo.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  cardsGeo.setAttribute("normal", new THREE.Float32BufferAttribute(NRM, 3));
  cardsGeo.setAttribute("tangent", new THREE.Float32BufferAttribute(TAN, 4));
  cardsGeo.setAttribute("uv", new THREE.Float32BufferAttribute(UV, 2));
  cardsGeo.setAttribute("color", new THREE.Float32BufferAttribute(COL, 3));
  cardsGeo.setIndex(IDX);

  // The painted base: the head's triangles near and inside the hair, 0.6 mm out, unindexed so the equirectangular
  // uv can be mended where a triangle crosses the seam at the back. Alpha feathers over ~1.4 cm across the hairline
  // and stays lower on the taper, so skin shows through as scalp shadow.
  const sp = [], sn = [], sc = [], suv = [], hv = new V(), hn = new V();
  const uvOf = v => { tv.copy(v).sub(C); return [0.5 + Math.atan2(tv.x, tv.z) / (2 * Math.PI), 0.5 - Math.atan2(tv.y, Math.hypot(tv.x, tv.z)) / Math.PI]; };
  for (let f = 0; f < head.i.length; f += 3){
    const ids = [head.i[f], head.i[f + 1], head.i[f + 2]], al = [], uvs = [];
    for (const i of ids){
      hv.fromBufferAttribute(pos, i);
      al.push(ear(hv) ? 0 : smooth(-0.004, 0.014, inside(hv)) * lerp(0.42, 0.9, topness(hv, azimuth(hv))));   // light on the taper
      uvs.push(uvOf(hv));
    }
    if (Math.max(...al) <= 0) continue;
    if (Math.max(...uvs.map(u => u[0])) - Math.min(...uvs.map(u => u[0])) > 0.5) uvs.forEach(u => { if (u[0] < 0.5) u[0] += 1; });
    ids.forEach((i, k) => {
      hv.fromBufferAttribute(pos, i); hn.fromBufferAttribute(nrm, i);
      sp.push(hv.x + hn.x * 0.0006, hv.y + hn.y * 0.0006, hv.z + hn.z * 0.0006); sn.push(hn.x, hn.y, hn.z);
      sc.push(1, 1, 1, al[k] * (0.92 + 0.08 * R())); suv.push(uvs[k][0], uvs[k][1]);
    });
  }
  const scalp = new THREE.BufferGeometry();
  scalp.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
  scalp.setAttribute("normal", new THREE.Float32BufferAttribute(sn, 3));
  scalp.setAttribute("color", new THREE.Float32BufferAttribute(sc, 4));
  scalp.setAttribute("uv", new THREE.Float32BufferAttribute(suv, 2));

  // Strokes for the painted base: at every root candidate, a short dash along the growth direction, in the map's uv.
  const scalpStrokes = [];
  for (const c of cand){
    const d = flow(c.p, c.n, null), a = uvOf(c.p), b = uvOf(c.p.clone().addScaledVector(d, 0.003));
    let du = b[0] - a[0]; if (du > 0.5) du -= 1; if (du < -0.5) du += 1;
    const len = Math.min(1, lengthAt(c.p, c.az) / 0.012);
    for (let k = 0; k < 6; k++) scalpStrokes.push({u: a[0] + (R() - 0.5) * 0.004, v: a[1] + (R() - 0.5) * 0.004, du, dv: b[1] - a[1], len: 1.5 + 2 * len});
  }
  // The growth direction (unit vector along the scalp) under any point near the head, for other hair meshes.
  const flowAt = q => { const s = surf(q.clone().sub(C)); return s ? flow(s.p, s.n, null) : new V(0, -1, 0); };
  return {cards: cardsGeo, scalp, scalpStrokes, flowAt, surfAt: q => surf(q.clone().sub(C)), topness: q => topness(q, azimuth(q)),
          lengthAt: q => lengthAt(q, azimuth(q)), ear, whorl, flow, stats: {cards, cardTris: IDX.length / 3, scalpTris: sp.length / 9, roots: cand.length}};
}
