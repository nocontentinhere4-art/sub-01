// MakeHuman's CC0 system hair proxy short02 (fitted to the default head by fit_proxy.py), re-cut and re-coloured.
//   recolorHair(img) -> {color, data}: the proxy's photo-based strand texture taken to natural black-brown (#1b1512
//     base, the photo's own light and dark strands kept as luminance), the green-screen spill and the mark in the
//     texture's unused corner removed, alpha kept; data = the hair shader's map (R depth from the strands' darkness,
//     G a per-strand ID in short vertical streaks, B unused).
//   cutProxy(THREE, proxy, hair) -> the re-cut shell as a BufferGeometry with uv, normals, tangent (the growth
//     direction from hair.flowAt, for the Kajiya-Kay highlights) and a vertex-colour occlusion. The proxy is a
//     helmet-like shell, long over the ears; the re-cut pulls every vertex in toward the scalp (about 3 mm on the
//     tapered sides and back, at most ~1 cm on top) and walks everything below the tapered hairline up the scalp
//     onto it, so the texture's soft edge lands on the hairline and the forehead and ears are free. The fringe's
//     pieces and the top's texture come from hair_gen.js's cards laid over it.
import { BASE } from "./hair_tex.js";
import { inside } from "./hair_gen.js";
export const SHELL = t => 0.003 + t * 0.007;   // the re-cut shell's height over the scalp, taper (0) to top (1)
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function recolorHair(img){
  const cv = document.createElement("canvas"); cv.width = img.width; cv.height = img.height;
  const g = cv.getContext("2d"); g.drawImage(img, 0, 0);
  const W = cv.width, H = cv.height, d = g.getImageData(0, 0, W, H), p = d.data;
  let sum = 0, n = 0;
  for (let i = 0; i < p.length; i += 4) if (p[i + 3] > 128){ sum += 0.3 * p[i] + 0.45 * Math.min(p[i + 1], p[i]) + 0.25 * p[i + 2]; n++; }
  const mean = sum / Math.max(1, n);
  for (let i = 0; i < p.length; i += 4){
    const x = (i / 4) % W, y = Math.floor(i / 4 / W);
    if (x > W * 0.78 && y > H * 0.94){ p[i] = BASE[0]; p[i + 1] = BASE[1]; p[i + 2] = BASE[2]; p[i + 3] = 0; continue; }   // the corner mark: gone
    const l = (0.3 * p[i] + 0.45 * Math.min(p[i + 1], p[i]) + 0.25 * p[i + 2]) / mean;   // green spill ignored
    const k = Math.pow(Math.max(0, l), 1.3) * 1.6, lo = Math.min(1, k), hi = Math.min(16, Math.max(0, k - 1) * 12);   // the strands' own contrast:
    p[i] = Math.min(255, BASE[0] * lo + hi); p[i + 1] = Math.min(255, BASE[1] * lo + hi); p[i + 2] = Math.min(255, BASE[2] * lo + hi);   // lit strands go grey, not brown
  }
  g.putImageData(d, 0, 0);
  const dc = document.createElement("canvas"); dc.width = W; dc.height = H;
  const dg = dc.getContext("2d"), dd = dg.createImageData(W, H), q = dd.data;
  for (let i = 0; i < q.length; i += 4){
    const x = (i / 4) % W, y = Math.floor(i / 4 / W), l = (p[i] / BASE[0]);
    let h = Math.imul(x * 73856093 ^ (y >> 3) * 19349663, 0x9E3779B1) >>> 0; h = (h ^ h >>> 15) & 255;
    q[i] = Math.round(255 * Math.min(1, 0.25 + 0.3 * l)); q[i + 1] = h; q[i + 2] = 0; q[i + 3] = 255;
  }
  dg.putImageData(dd, 0, 0);
  return {color: cv, data: dc};
}

export function cutProxy(THREE, proxy, hair){
  const P = [], UV = [], IDX = [], key = new Map();
  for (const f of proxy.f){
    const ids = f.map(([vi, ti]) => {
      const k = vi + "/" + ti;
      if (!key.has(k)){ key.set(k, P.length / 3); P.push(...proxy.v[vi]); const t = proxy.uv[ti]; UV.push(t[0], 1 - t[1]); }
      return key.get(k);
    });
    for (let i = 1; i + 1 < ids.length; i++) IDX.push(ids[0], ids[i], ids[i + 1]);
  }
  // The re-cut, per vertex.
  const q = new THREE.Vector3(), up = new THREE.Vector3(), OCC = [];
  for (let i = 0; i < P.length / 3; i++){
    q.fromArray(P, i * 3);
    let s = hair.surfAt(q); if (!s) { OCC.push(1, 0); continue; }
    const off = Math.max(0, q.clone().sub(s.p).dot(s.n));
    for (let k = 0; k < 40 && inside(s.p) < 0.0015; k++){                // below the hairline: up the scalp onto it
      up.set(0, 1, 0).addScaledVector(s.n, -s.n.y).normalize();
      const nx = hair.surfAt(s.p.clone().addScaledVector(up, 0.002)); if (!nx) break; s = nx;
    }
    const t = hair.topness(s.p);
    const keep = Math.min(off, SHELL(t));
    s.p.addScaledVector(s.n, keep).toArray(P, i * 3);
    OCC.push(0.75 + 0.25 * t, smooth(0.0015, 0.011, inside(s.p)) * smooth(0.0, 0.004, keep + 0.002));
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(UV, 2));
  g.setIndex(IDX); g.computeVertexNormals();
  const TAN = [], COL = [], v = new THREE.Vector3();
  for (let i = 0; i < P.length / 3; i++){
    v.fromArray(P, i * 3); const d = hair.flowAt(v); TAN.push(d.x, d.y, d.z, 1);
    COL.push(OCC[2 * i], OCC[2 * i], OCC[2 * i], OCC[2 * i + 1]);   // alpha: feathered into the hairline
  }
  g.setAttribute("tangent", new THREE.Float32BufferAttribute(TAN, 4));
  g.setAttribute("color", new THREE.Float32BufferAttribute(COL, 4));
  return g;
}
