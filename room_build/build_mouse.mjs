// node build_mouse.mjs <ambientCG Plastic016A 1K folder> ../web/room/mouse.glb
// A generic computer mouse on a cloth pad, modelled in code (original, CC0; no maker's shape, no logo): 11.8 cm long, 6.2 cm
// wide, 3.6 cm high, its hump in the back third, the two buttons sloping gently to the front with a seam between them, a
// small scroll wheel. Two nodes: "mouse" (origin: the middle of its base; its front, the buttons, towards -z) and
// "mousepad" (origin: the middle of its underside). PBR (desk_pbr.mjs): a soft-touch matte shell, a glossier wheel; the
// pad a plain rough cloth; a contact shadow under the mouse (its child "mouse_contact").
import { Document, NodeIO } from "@gltf-transform/core";
import { plasticMaps, contactBlob } from "./desk_pbr.mjs";

const L = 0.118, W = 0.062, H = 0.036, BASE = 0.004;
const BODY = [0.010, 0.010, 0.011], SEAM = [0.002, 0.002, 0.002], WHEEL = [0.035, 0.035, 0.038], PAD = [0.016, 0.017, 0.02];
const NR = 18, NT = 48;                                        // rings from the top's middle to the rim, steps around

const parts = [];
function part(name){ const p = {name, pos: [], col: [], uv: [], idx: []}; parts.push(p); return p; }
// uv: the shell maps into the matte half of the maps, the wheel into the polished half
const vtx = (p, x, y, z, c, uv = [0.5 * (x / W + 0.5), 0.5 + z / L]) => { p.pos.push(x, y, z); p.col.push(...c, 1); p.uv.push(...uv); return p.pos.length / 3 - 1; };

// the outline: a rounded rectangle-ish superellipse, a little narrower at the front
function outline(t){                                           // t in [0, 2pi): (x, z) on the rim
  const c = Math.cos(t), s = Math.sin(t), e = 2 / 2.6;
  let x = Math.sign(c) * Math.abs(c) ** e * W / 2, z = Math.sign(s) * Math.abs(s) ** e * L / 2;
  if (z < 0) x *= 1 - 0.12 * (-z / (L / 2));                   // (the front, -z, narrower)
  return [x, z];
}
// the height of the top at (x, z): the hump peaks a third from the back, the buttons slope to the front, rounded sideways
function top(x, z){
  const u = 0.5 + z / L;                                       // 0 at the front, 1 at the back
  const along = 0.62 + 0.38 * Math.exp(-(((u - 0.68) / 0.30) ** 2));
  return H * along * (1 - 0.22 * (x / (W / 2)) ** 2);
}
const m = part("mouse");
const ring = [];
for (let r = 0; r <= NR; r++) {
  const k = r / NR, row = [];
  for (let i = 0; i < NT; i++) {
    const [ox, oz] = outline(2 * Math.PI * i / NT), x = ox * k, z = oz * k;
    let y = BASE + (top(x, z) - BASE) * Math.sqrt(Math.max(0, 1 - k ** 5));
    const seam = Math.abs(x) < 0.0009 && z < 0.004 && k < 0.92;           // the split between the buttons (front half)
    if (seam) y -= 0.0007;
    row.push(vtx(m, x, y, z, seam ? SEAM : BODY));
  }
  ring.push(row);
}
for (let r = 0; r < NR; r++) for (let i = 0; i < NT; i++) {
  const a = ring[r][i], b = ring[r][(i + 1) % NT], c = ring[r + 1][(i + 1) % NT], d = ring[r + 1][i];
  m.idx.push(a, d, c, a, c, b);                                // (top faces up: counter-clockwise seen from above)
}
const rim = ring[NR], low = [];                                // the side skirt down to the desk, and the flat underside
for (let i = 0; i < NT; i++) { const [x, z] = outline(2 * Math.PI * i / NT); low.push(vtx(m, x * 0.97, 0, z * 0.97, BODY)); }
for (let i = 0; i < NT; i++) { const j = (i + 1) % NT; m.idx.push(rim[i], low[i], low[j], rim[i], low[j], rim[j]); }
const mid = vtx(m, 0, 0, 0, BODY); for (let i = 0; i < NT; i++) m.idx.push(mid, low[(i + 1) % NT], low[i]);
// the scroll wheel: a short cylinder across x, a third of the way from the front, standing 2 mm proud of the top
{ const zc = -L / 2 + 0.34 * L, R = 0.0058, hw = 0.0032, yc = top(0, zc) + 0.002 - R, n = 14, c0 = [], c1 = [];
  for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n, y = yc + R * Math.sin(a), z = zc + R * Math.cos(a);
    c0.push(vtx(m, -hw, y, z, WHEEL, [0.6, i / n])); c1.push(vtx(m, hw, y, z, WHEEL, [0.9, i / n])); }
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; m.idx.push(c0[i], c0[j], c1[j], c0[i], c1[j], c1[i]); }
  const e0 = vtx(m, -hw, yc, zc, WHEEL, [0.75, 0.5]), e1 = vtx(m, hw, yc, zc, WHEEL, [0.75, 0.5]);
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; m.idx.push(e0, c0[j], c0[i], e1, c1[i], c1[j]); } }

// the pad: a cloth rectangle with rounded corners, 3 mm thick (its top and a thin edge)
const pad = part("mousepad"), PW = 0.20, PD = 0.19, PT = 0.003, RC = 0.012, pts = [];
for (const [cx, cz, a0] of [[PW / 2 - RC, PD / 2 - RC, 0], [-(PW / 2 - RC), PD / 2 - RC, Math.PI / 2], [-(PW / 2 - RC), -(PD / 2 - RC), Math.PI], [PW / 2 - RC, -(PD / 2 - RC), 1.5 * Math.PI]])
  for (let i = 0; i <= 6; i++) { const a = a0 + (Math.PI / 2) * i / 6; pts.push([cx + RC * Math.cos(a), cz + RC * Math.sin(a)]); }
const c = vtx(pad, 0, PT, 0, PAD), up = pts.map(([x, z]) => vtx(pad, x, PT, z, PAD)), dn = pts.map(([x, z]) => vtx(pad, x, 0, z, PAD));
for (let i = 0; i < pts.length; i++) { const j = (i + 1) % pts.length;
  pad.idx.push(c, up[j], up[i]); pad.idx.push(up[i], up[j], dn[j], up[i], dn[j], dn[i]); }

// (the mouse's triangles were laid clockwise seen from outside: turn them over) and smooth normals for both parts
for (let i = 0; i < m.idx.length; i += 3) [m.idx[i + 1], m.idx[i + 2]] = [m.idx[i + 2], m.idx[i + 1]];
for (const p of parts) {
  const n = new Float32Array(p.pos.length), P = p.pos;
  for (let i = 0; i < p.idx.length; i += 3) {
    const [a, b, c] = [p.idx[i] * 3, p.idx[i + 1] * 3, p.idx[i + 2] * 3];
    const u = [P[b] - P[a], P[b + 1] - P[a + 1], P[b + 2] - P[a + 2]], v = [P[c] - P[a], P[c + 1] - P[a + 1], P[c + 2] - P[a + 2]];
    const f = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    for (const k of [a, b, c]) { n[k] += f[0]; n[k + 1] += f[1]; n[k + 2] += f[2]; }
  }
  for (let i = 0; i < n.length; i += 3) { const l = Math.hypot(n[i], n[i + 1], n[i + 2]) || 1; n[i] /= l; n[i + 1] /= l; n[i + 2] /= l; }
  p.nor = n;
}
const [folder, out] = process.argv.slice(2);
const maps = await plasticMaps(folder), blob = await contactBlob();
const doc = new Document(), buf = doc.createBuffer(), scene = doc.createScene();
const acc = (type, arr) => doc.createAccessor().setType(type).setArray(arr).setBuffer(buf);
const tex = (name, img, mime) => doc.createTexture(name).setImage(img).setMimeType(mime);
const shell = doc.createMaterial("mouse").setBaseColorFactor([1, 1, 1, 1]).setRoughnessFactor(1).setMetallicFactor(1)
  .setMetallicRoughnessTexture(tex("plastic_mr", maps.mr, "image/webp")).setNormalTexture(tex("plastic_normal", maps.normal, "image/webp")).setNormalScale(0.5);
const cloth = doc.createMaterial("mousepad").setBaseColorFactor([1, 1, 1, 1]).setRoughnessFactor(0.95).setMetallicFactor(0);
let tris = 0;
const nodes = {};
for (const p of parts) {
  if (process.env.REF && p !== m) continue;              // (REF=1: the bare mouse, the clean reference picture for the Tripo attempt)
  const prim = doc.createPrimitive().setAttribute("POSITION", acc("VEC3", new Float32Array(p.pos))).setAttribute("NORMAL", acc("VEC3", p.nor))
    .setAttribute("TEXCOORD_0", acc("VEC2", new Float32Array(p.uv))).setAttribute("COLOR_0", acc("VEC4", new Float32Array(p.col)))
    .setIndices(acc("SCALAR", new Uint32Array(p.idx))).setMaterial(p === m ? shell : cloth);
  nodes[p.name] = doc.createNode(p.name).setMesh(doc.createMesh(p.name).addPrimitive(prim)); scene.addChild(nodes[p.name]); tris += p.idx.length / 3;
}
if (!process.env.REF) { const x0 = -W / 2 - 0.012, x1 = W / 2 + 0.012, z0 = -L / 2 - 0.012, z1 = L / 2 + 0.012, y = 0.0004;   // the mouse's contact shadow
  const smat = doc.createMaterial("mouse_contact").setBaseColorFactor([0, 0, 0, 0.6]).setAlphaMode("BLEND").setRoughnessFactor(1).setMetallicFactor(0)
    .setBaseColorTexture(tex("contact_blob", blob, "image/png"));
  const sp = doc.createPrimitive().setAttribute("POSITION", acc("VEC3", new Float32Array([x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z0])))
    .setAttribute("NORMAL", acc("VEC3", new Float32Array([0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0])))
    .setAttribute("TEXCOORD_0", acc("VEC2", new Float32Array([0, 1, 1, 1, 1, 0, 0, 0]))).setIndices(acc("SCALAR", new Uint32Array([0, 1, 2, 0, 2, 3]))).setMaterial(smat);
  nodes.mouse.addChild(doc.createNode("mouse_contact").setMesh(doc.createMesh("mouse_contact").addPrimitive(sp))); }
await new NodeIO().write(out, doc);
let hy = 0, hz = 0; for (let i = 0; i < m.pos.length; i += 3) if (m.pos[i + 1] > hy) { hy = m.pos[i + 1]; hz = m.pos[i + 2]; }
console.log(out, `${tris} triangles; mouse ${L} x ${W} x ${hy.toFixed(4)} m, hump top at z ${hz.toFixed(3)} (+z back)`);
