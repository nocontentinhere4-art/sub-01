// node build_headphones.mjs <raw Tripo GLB> ../web/room/headphones_worn.glb
// The pair he wears (#75): one Tripo text-to-model (P1-20260311, PBR) of generic over-ear headphones in the open, worn
// shape, cut at the band into three meshes the page fits to his head (web/room/boy_mh.js, headphones()):
//  - hp_cupL / hp_cupR: each cup (its shell, its cushion and the band's hinge pin), rigid. In its own frame the
//    cushion's face, the part that meets the ear, is at the origin, the cup's axis on x (the right cup outward to +x,
//    the left to -x), y up. Its extras.pin: the hinge pin in that frame.
//  - hp_band: the band, in the model's frame (the pins' midpoint at the origin, y up). Its extras: the two pins, the
//    centre O and the band's inner outline about O (inner: [angle from straight up, radius], the right half; the model is
//    symmetric), which the page maps onto the outline of his hair.
// The cut: the raw mesh is six connected pieces (welded by position): the band with the LEFT cup's shell fused to it, the
// right shell, two cushions and two hinge pins. Each triangle of the fused piece goes to the left cup when its mirror
// image lies nearer to the right shell than to the band's right end; nothing is cut by hand. Scale: the cup 9.5 cm tall
// (S); the rest follows the model. One material: base colour, metal/roughness and normals at 512 px, WebP; meshopt.
// The raw file is not committed; its task id is in ../web/room/CREDITS.md.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression } from "@gltf-transform/extensions";
import { prune, dedup, quantize, reorder, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";

const [src, dst] = process.argv.slice(2);
const S = 0.19;                                            // model units -> metres (the cup, 0.5 tall in the model: 9.5 cm)
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const doc = await io.read(src), root = doc.getRoot();
const node = root.listNodes().find(n => n.getMesh()), prim = node.getMesh().listPrimitives()[0], W = node.getWorldMatrix();
const A = {}; for (const k of prim.listSemantics()) A[k] = prim.getAttribute(k);
const idx = Array.from(prim.getIndices().getArray()), nv = A.POSITION.getCount(), nt = idx.length / 3;
// the model's frame -> ours: its cups lie along its z: x = z, y = y, z = -x (the band's front to +z)
const tr = (v, w) => { const x = W[0]*v[0]+W[4]*v[1]+W[8]*v[2]+w*W[12], y = W[1]*v[0]+W[5]*v[1]+W[9]*v[2]+w*W[13], z = W[2]*v[0]+W[6]*v[1]+W[10]*v[2]+w*W[14]; return [z, y, -x]; };
const P = [], N = [];
for (let i = 0; i < nv; i++) { P.push(tr(A.POSITION.getElement(i, []), 1)); if (A.NORMAL) { const n = tr(A.NORMAL.getElement(i, []), 0), l = Math.hypot(...n) || 1; N.push(n.map(c => c / l)); } }
// connected pieces, welded by position
const key = p => p.map(c => Math.round(c * 1e5)).join(","), weld = new Map(), wid = P.map(p => { const k = key(p); if (!weld.has(k)) weld.set(k, weld.size); return weld.get(k); });
const par = [...Array(weld.size).keys()], find = a => { while (par[a] !== a) a = par[a] = par[par[a]]; return a; };
for (let t = 0; t < nt; t++) for (let k = 0; k < 3; k++) { const a = find(wid[idx[3*t+k]]), b = find(wid[idx[3*t+(k+1)%3]]); if (a !== b) par[a] = b; }
const comp = P.map((_, i) => find(wid[i])), pieces = new Map();
P.forEach((p, i) => { const c = comp[i]; if (!pieces.has(c)) pieces.set(c, []); pieces.get(c).push(i); });
const cen = ids => [0, 1, 2].map(k => ids.reduce((s, i) => s + P[i][k], 0) / ids.length);
const list = [...pieces.entries()].map(([c, ids]) => ({c, ids, n: ids.length, cx: cen(ids)})).sort((a, b) => b.n - a.n);
const band0 = list[0], loose = list.slice(1);
if (loose.length !== 5) throw new Error(`expected six pieces, got ${list.length}`);
const shellR = loose.filter(p => p.cx[0] > 0).sort((a, b) => b.n - a.n)[0];
const near = (q, ids) => { let d = 1e9; for (const i of ids) d = Math.min(d, (P[i][0]-q[0])**2 + (P[i][1]-q[1])**2 + (P[i][2]-q[2])**2); return d; };
const bandR = band0.ids.filter(i => P[i][0] > 0.15);
const part = new Array(nt);                                // 0 band, 1 left cup, 2 right cup
for (let t = 0; t < nt; t++) {
  const v = [0, 1, 2].map(k => idx[3*t+k]), c = [0, 1, 2].map(k => (P[v[0]][k] + P[v[1]][k] + P[v[2]][k]) / 3);
  if (comp[v[0]] !== band0.c) { part[t] = c[0] > 0 ? 2 : 1; continue; }
  if (c[0] > -0.15) { part[t] = 0; continue; }
  const m = [-c[0], c[1], c[2]]; part[t] = near(m, shellR.ids) < near(m, bandR) ? 1 : 0;
}
// each cup: its cushion (the loose piece nearest the middle on its side), its axis by PCA (the ring's normal), its face
const pins = {}, cups = {};
for (const [side, sx] of [[1, -1], [2, 1]]) {
  const mine = loose.filter(p => Math.sign(p.cx[0]) === sx), cush = mine.sort((a, b) => Math.abs(a.cx[0]) - Math.abs(b.cx[0]))[0];
  const pin = loose.filter(p => Math.sign(p.cx[0]) === sx).sort((a, b) => a.n - b.n)[0];
  const c = cush.cx, C = [[0,0,0],[0,0,0],[0,0,0]];
  for (const i of cush.ids) for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) C[a][b] += (P[i][a]-c[a]) * (P[i][b]-c[b]);
  let ax = [1, 0, 0];                                      // smallest eigenvector: inverse power iteration
  const inv = m => { const [a,b,cc] = m, det = a[0]*(b[1]*cc[2]-b[2]*cc[1]) - a[1]*(b[0]*cc[2]-b[2]*cc[0]) + a[2]*(b[0]*cc[1]-b[1]*cc[0]);
    return [[b[1]*cc[2]-b[2]*cc[1], a[2]*cc[1]-a[1]*cc[2], a[1]*b[2]-a[2]*b[1]], [b[2]*cc[0]-b[0]*cc[2], a[0]*cc[2]-a[2]*cc[0], a[2]*b[0]-a[0]*b[2]], [b[0]*cc[1]-b[1]*cc[0], a[1]*cc[0]-a[0]*cc[1], a[0]*b[1]-a[1]*b[0]]].map(r => r.map(x => x / det)); };
  const Ci = inv(C); for (let k = 0; k < 50; k++) { const n = [0, 1, 2].map(r => Ci[r][0]*ax[0] + Ci[r][1]*ax[1] + Ci[r][2]*ax[2]), l = Math.hypot(...n); ax = n.map(x => x / l); }
  if (ax[0] * sx > 0) ax = ax.map(x => -x);                // pointing in, toward the head
  const f = Math.max(...cush.ids.map(i => (P[i][0]-c[0])*ax[0] + (P[i][1]-c[1])*ax[1] + (P[i][2]-c[2])*ax[2]));
  const face = c.map((x, k) => x + f * ax[k]);
  // the turn taking ax onto (-sx, 0, 0) (the cup's axis level, its face to the head): Rodrigues
  const to = [-sx, 0, 0], k = [ax[1]*to[2]-ax[2]*to[1], ax[2]*to[0]-ax[0]*to[2], ax[0]*to[1]-ax[1]*to[0]], sn = Math.hypot(...k), cs = ax[0]*to[0]+ax[1]*to[1]+ax[2]*to[2];
  const kk = sn ? k.map(x => x / sn) : [0, 0, 1];
  const rot = v => { const d = kk[0]*v[0]+kk[1]*v[1]+kk[2]*v[2], x = [kk[1]*v[2]-kk[2]*v[1], kk[2]*v[0]-kk[0]*v[2], kk[0]*v[1]-kk[1]*v[0]];
    return [0, 1, 2].map(j => v[j]*cs + x[j]*sn + kk[j]*d*(1-cs)); };
  cups[side] = {pos: p => rot(p.map((x, j) => x - face[j])).map(x => x * S), nrm: rot, tilt: +(Math.atan2(sn, cs) * 180 / Math.PI).toFixed(1)};
  pins[side] = {model: pin.cx, cup: cups[side].pos(pin.cx)};
}
// the band: the pins' midpoint at the origin, metres; O on its axis at the pins' height. Its inner outline about O: the
// nearest band surface to O at each angle, from straight up (0) to the pin's angle
const mid = [0, (pins[1].model[1] + pins[2].model[1]) / 2, 0];
const bandPos = p => [(p[0] - mid[0]) * S, (p[1] - mid[1]) * S, (p[2] - mid[2]) * S];
// (the band's triangles cut by the plane z = 0, then the nearest crossing along each ray from O)
const segs = [];
for (let t = 0; t < nt; t++) if (!part[t]) { const v = [0, 1, 2].map(k => bandPos(P[idx[3*t+k]])), q = [];
  for (let k = 0; k < 3; k++) { const a = v[k], b = v[(k+1)%3]; if ((a[2] < 0) !== (b[2] < 0)) { const u = a[2] / (a[2] - b[2]); q.push([a[0] + (b[0]-a[0])*u, a[1] + (b[1]-a[1])*u]); } }
  if (q.length === 2) segs.push(q); }
const pinR = bandPos(pins[2].model), phEnd = Math.atan2(pinR[0], pinR[1]), inner = [];
for (let i = 0; i <= 24; i++) { const ph = phEnd * i / 24, d = [Math.sin(ph), Math.cos(ph)]; let r = 1e9;
  for (const [a, b] of segs) { const e = [b[0]-a[0], b[1]-a[1]], den = d[0]*e[1] - d[1]*e[0]; if (Math.abs(den) < 1e-12) continue;
    const t = (a[0]*e[1] - a[1]*e[0]) / den, u = (a[0]*d[1] - a[1]*d[0]) / den; if (t > 0 && u >= 0 && u <= 1) r = Math.min(r, t); }
  inner.push([+ph.toFixed(4), +r.toFixed(5)]); }

// write: three primitives off the one material
const mat = prim.getMaterial(), buf = root.listBuffers()[0], scene = root.listScenes()[0];
for (const n of root.listNodes()) n.dispose();
const out = [["hp_band", 0], ["hp_cupL", 1], ["hp_cupR", 2]];
for (const [name, p] of out) {
  const used = new Map(), I = [], pos = [], nrm = [], uv = [];
  for (let t = 0; t < nt; t++) if (part[t] === p) for (let k = 0; k < 3; k++) { const i = idx[3*t+k]; if (!used.has(i)) { used.set(i, used.size);
    const q = p ? cups[p].pos(P[i]) : bandPos(P[i]); pos.push(...q); if (N.length) nrm.push(...(p ? cups[p].nrm(N[i]) : N[i]));
    if (A.TEXCOORD_0) uv.push(...A.TEXCOORD_0.getElement(i, [])); } I.push(used.get(i)); }
  const pr = doc.createPrimitive().setMaterial(mat)
    .setIndices(doc.createAccessor().setType("SCALAR").setArray(new Uint32Array(I)).setBuffer(buf))
    .setAttribute("POSITION", doc.createAccessor().setType("VEC3").setArray(new Float32Array(pos)).setBuffer(buf));
  if (nrm.length) pr.setAttribute("NORMAL", doc.createAccessor().setType("VEC3").setArray(new Float32Array(nrm)).setBuffer(buf));
  if (uv.length) pr.setAttribute("TEXCOORD_0", doc.createAccessor().setType("VEC2").setArray(new Float32Array(uv)).setBuffer(buf));
  const nd = doc.createNode(name).setMesh(doc.createMesh(name).addPrimitive(pr));
  nd.setExtras(p ? {pin: pins[p].cup.map(x => +x.toFixed(5)), tilt_deg: cups[p].tilt}
                 : {pinL: bandPos(pins[1].model).map(x => +x.toFixed(5)), pinR: pinR.map(x => +x.toFixed(5)), inner});
  scene.addChild(nd);
  console.log(name, I.length / 3, "triangles", JSON.stringify(nd.getExtras()));
}
prim.dispose();
await doc.transform(prune(), dedup(),
  textureCompress({encoder: sharp, targetFormat: "webp", resize: [512, 512]}),
  reorder({encoder: MeshoptEncoder}), quantize());
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method: EXTMeshoptCompression.EncoderMethod.QUANTIZE});
await io.write(dst, doc);
