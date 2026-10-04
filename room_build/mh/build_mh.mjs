// node build_mh.mjs <out.glb> — the MakeHuman base body (CC0) as a skinned GLB with the default skeleton (163 bones,
// fingers included). Crude: body group only, bones world-aligned (identity rest rotation) at their head joints, metres.
import fs from "node:fs";
import { Document, NodeIO } from "@gltf-transform/core";
const D = "/tmp/claude-0/-home-user-sub-01/a1581955-cea1-5ea6-8301-a7608fa8d399/scratchpad/mh/mhsrc/makehuman/data";
const OUT = process.argv[2];
const S = 0.1;                                                    // decimetres -> metres
const V = [], F = []; let grp = "";
for (const l of fs.readFileSync(`${D}/3dobjs/base.obj`, "utf8").split("\n")) {
  if (l.startsWith("v ")) V.push(l.split(/\s+/).slice(1, 4).map(Number));
  else if (l.startsWith("g ")) grp = l.slice(2).trim();
  else if (l.startsWith("f ") && grp === "body") F.push(l.split(/\s+/).slice(1).filter(Boolean).map(t => +t.split("/")[0] - 1));
}
{ // feet on the floor (y = 0): the base mesh is centred on the origin
  const bodyV = new Set(F.flat()); let ymin = 1e9; for (const i of bodyV) ymin = Math.min(ymin, V[i][1]); for (const v of V) v[1] -= ymin; }
const sk = JSON.parse(fs.readFileSync(`${D}/rigs/default.mhskel`, "utf8"));
const W = JSON.parse(fs.readFileSync(`${D}/rigs/default_weights.mhw`, "utf8")).weights;
const jp = n => { const ix = sk.joints[n]; const p = [0, 0, 0]; for (const i of ix) for (let k = 0; k < 3; k++) p[k] += V[i][k]; return p.map(x => x / ix.length * S); };
const names = Object.keys(sk.bones);
// parents before children
const order = []; const seen = new Set();
const visit = n => { if (seen.has(n)) return; const p = sk.bones[n].parent; if (p) visit(p); seen.add(n); order.push(n); };
names.forEach(visit);
const head = Object.fromEntries(order.map(n => [n, jp(sk.bones[n].head)]));
const tail = Object.fromEntries(order.map(n => [n, jp(sk.bones[n].tail)]));
// compact the body's vertices
const used = [...new Set(F.flat())].sort((a, b) => a - b), remap = new Map(used.map((v, i) => [v, i]));
const pos = new Float32Array(used.length * 3); used.forEach((v, i) => pos.set(V[v].map(x => x * S), i * 3));
const idx = []; for (const f of F) { const q = f.map(v => remap.get(v)); idx.push(q[0], q[1], q[2]); if (q.length === 4) idx.push(q[0], q[2], q[3]); }
// skin: top 4 weights per vertex
const per = used.map(() => []);
order.forEach((n, bi) => { for (const [v, w] of (W[n] || [])) { const i = remap.get(v); if (i !== undefined) per[i].push([bi, w]); } });
const J = new Uint16Array(used.length * 4), Wt = new Float32Array(used.length * 4);
per.forEach((l, i) => { l.sort((a, b) => b[1] - a[1]); const t = l.slice(0, 4); const s = t.reduce((a, b) => a + b[1], 0) || 1;
  if (!t.length) t.push([0, 1]); t.forEach(([b, w], k) => { J[i * 4 + k] = b; Wt[i * 4 + k] = l.length ? w / s : 1; }); });
// normals
const nrm = new Float32Array(pos.length);
for (let i = 0; i < idx.length; i += 3) { const [a, b, c] = [idx[i], idx[i + 1], idx[i + 2]];
  const e1 = [0, 1, 2].map(k => pos[b * 3 + k] - pos[a * 3 + k]), e2 = [0, 1, 2].map(k => pos[c * 3 + k] - pos[a * 3 + k]);
  const n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
  for (const v of [a, b, c]) for (let k = 0; k < 3; k++) nrm[v * 3 + k] += n[k]; }
for (let i = 0; i < nrm.length; i += 3) { const l = Math.hypot(nrm[i], nrm[i + 1], nrm[i + 2]) || 1; nrm[i] /= l; nrm[i + 1] /= l; nrm[i + 2] /= l; }
const doc = new Document(), buf = doc.createBuffer();
const acc = (a, t) => doc.createAccessor().setArray(a).setType(t).setBuffer(buf);
const prim = doc.createPrimitive().setAttribute("POSITION", acc(pos, "VEC3")).setAttribute("NORMAL", acc(nrm, "VEC3"))
  .setAttribute("JOINTS_0", acc(J, "VEC4")).setAttribute("WEIGHTS_0", acc(Wt, "VEC4")).setIndices(acc(new Uint32Array(idx), "SCALAR"))
  .setMaterial(doc.createMaterial("skin").setBaseColorFactor([0.8, 0.62, 0.52, 1]).setRoughnessFactor(0.6));
const nodes = {};
for (const n of order) { const p = sk.bones[n].parent, h = head[n], ph = p ? head[p] : [0, 0, 0];
  nodes[n] = doc.createNode(n).setTranslation([h[0] - ph[0], h[1] - ph[1], h[2] - ph[2]]); if (p) nodes[p].addChild(nodes[n]); }
const ibm = new Float32Array(order.length * 16);
order.forEach((n, i) => { const h = head[n]; ibm.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -h[0], -h[1], -h[2], 1], i * 16); });
const skin = doc.createSkin().setSkeleton(nodes.root).setInverseBindMatrices(acc(ibm, "MAT4")); order.forEach(n => skin.addJoint(nodes[n]));
const mesh = doc.createMesh("body").addPrimitive(prim);
const scene = doc.createScene().addChild(doc.createNode("body").setMesh(mesh).setSkin(skin)).addChild(nodes.root);
doc.getRoot().setDefaultScene(scene);
await new NodeIO().write(OUT, doc);
fs.writeFileSync(OUT.replace(/\.glb$/, "_rest.json"), JSON.stringify({ order, head, tail, parent: Object.fromEntries(order.map(n => [n, sk.bones[n].parent])) }));
const ys = used.map(v => V[v][1] * S);
console.log("bones", order.length, "verts", used.length, "tris", idx.length / 3, "height", (Math.max(...ys) - Math.min(...ys)).toFixed(3), "m", (fs.statSync(OUT).size / 1e6).toFixed(2), "MB");
