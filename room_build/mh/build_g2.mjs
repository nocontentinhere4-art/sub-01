// node build_g2.mjs <MakeHuman data dir> <out.glb> — G2's body on the MakeHuman base (all assets CC0, makehumancommunity/
// makehuman, "explicitly released as CC0 in september 2020" in each file's header): a fictional young man, ~20 years
// old, slim, 1.75 m, with proportioned male hands and real-size eyeballs, on the DEFAULT skeleton (default.mhskel, 163
// bones, names kept) with default_weights.mhw; metres, feet at y = 0, bones world-aligned at rest (identity rotation) at
// their head joints, as build_mh.mjs. Then rename_mh.mjs gives the main bones the room page's names.
//
// The macro modifiers are evaluated as MakeHuman does (apps/humanmodifier.py, MacroModifier): gender 1 (male), age
// 20 years (MakeHuman's age value 0.1875 + (20 - 11) / (25 - 11) * 0.3125 = 0.388: a blend of the "child" (11 y) and
// "young" (25 y) targets), muscle 0.5 (average), weight 0.4 (slim: 20 % towards minweight), proportions 0.75 (towards
// the "ideal" proportions); ethnicity 1/3 each (a fictional mix, no real person). Height is set by uniform scaling to
// 1.75 m. Hands: the base mesh's fingers are thin and long; the hand targets thicken them and shorten them a little to
// a male hand (palm ~8.5 cm wide, middle finger ~8 cm), measured after the build.
import fs from "node:fs";
import { Document, NodeIO } from "@gltf-transform/core";
const [,, D, OUT] = process.argv;
const HEIGHT = 1.75, AGE_Y = 20, WEIGHT = 0.4, MUSCLE = 0.5, PROPS = 0.75;
const HAND = { "fingers-diameter-incr": +(process.env.FD ?? 0.55), "fingers-length-decr": +(process.env.FL ?? 1.0), "scale-incr": +(process.env.HS ?? 0.15) };

// ---- base mesh (all groups: the joints and the eye helpers are vertex groups too)
const V = [], F = [], groupOf = []; let grp = "";
for (const l of fs.readFileSync(`${D}/3dobjs/base.obj`, "utf8").split("\n")) {
  if (l.startsWith("v ")) V.push(l.split(/\s+/).slice(1, 4).map(Number));
  else if (l.startsWith("g ")) grp = l.slice(2).trim();
  else if (l.startsWith("f ") && grp === "body") F.push(l.split(/\s+/).slice(1).filter(Boolean).map(t => +t.split("/")[0] - 1));
}
const applied = [];
function target(rel, w) {
  if (w <= 1e-6) return;
  const f = `${D}/targets/${rel}`; if (!fs.existsSync(f)) throw new Error("missing target " + rel);
  for (const l of fs.readFileSync(f, "utf8").split("\n")) {
    if (!l || l[0] === "#") continue; const t = l.trim().split(/\s+/); if (t.length < 4) continue;
    const i = +t[0]; V[i][0] += w * +t[1]; V[i][1] += w * +t[2]; V[i][2] += w * +t[3];
  }
  applied.push([rel, +w.toFixed(4)]);
}
// ---- macro weights (MakeHuman's getWeights: piecewise-linear "min / average / max" blends)
const ageVal = 0.1875 + (AGE_Y - 11) / (25 - 11) * (0.5 - 0.1875);
const ages = ageVal < 0.1875 ? { baby: 1 - ageVal / 0.1875, child: ageVal / 0.1875 } : ageVal < 0.5 ? { child: (0.5 - ageVal) / (0.5 - 0.1875), young: (ageVal - 0.1875) / (0.5 - 0.1875) } : { young: (1 - ageVal) / 0.5, old: (ageVal - 0.5) / 0.5 };
const tri = v => v < 0.5 ? { min: 1 - v / 0.5, average: v / 0.5 } : { average: (1 - v) / 0.5, max: (v - 0.5) / 0.5 };
const muscles = Object.fromEntries(Object.entries(tri(MUSCLE)).map(([k, w]) => [k + "muscle", w]));
const weights = Object.fromEntries(Object.entries(tri(WEIGHT)).map(([k, w]) => [k + "weight", w]));
const gender = "male";
for (const [eth, ew] of [["african", 1 / 3], ["asian", 1 / 3], ["caucasian", 1 / 3]])
  for (const [age, aw] of Object.entries(ages)) target(`macrodetails/${eth}-${gender}-${age}.target`, ew * aw);
for (const [age, aw] of Object.entries(ages)) for (const [mu, mw] of Object.entries(muscles)) for (const [we, ww] of Object.entries(weights)) {
  target(`macrodetails/universal-${gender}-${age}-${mu}-${we}.target`, aw * mw * ww);
  if (age !== "baby") target(`macrodetails/proportions/${gender}-${age}-${mu}-${we}-idealproportions.target`, aw * mw * ww * Math.max(0, (PROPS - 0.5) / 0.5));
}
for (const s of ["l", "r"]) for (const [k, w] of Object.entries(HAND)) target(`armslegs/${s}-hand-${k}.target`, w);
// ---- metres, uniform scale to the height, feet at y = 0
const body = [...new Set(F.flat())];
let y0 = Infinity, y1 = -Infinity; for (const i of body) { y0 = Math.min(y0, V[i][1]); y1 = Math.max(y1, V[i][1]); }
const S = HEIGHT / (y1 - y0);
for (const v of V) { v[0] *= S; v[1] = (v[1] - y0) * S; v[2] *= S; }

// ---- skeleton and weights (as build_mh.mjs)
const sk = JSON.parse(fs.readFileSync(`${D}/rigs/default.mhskel`, "utf8"));
const W = JSON.parse(fs.readFileSync(`${D}/rigs/default_weights.mhw`, "utf8")).weights;
const jp = n => { const ix = sk.joints[n]; const p = [0, 0, 0]; for (const i of ix) for (let k = 0; k < 3; k++) p[k] += V[i][k]; return p.map(x => x / ix.length); };
const names = Object.keys(sk.bones), order = [], seen = new Set();
const visit = n => { if (seen.has(n)) return; const p = sk.bones[n].parent; if (p) visit(p); seen.add(n); order.push(n); };
names.forEach(visit);
const head = Object.fromEntries(order.map(n => [n, jp(sk.bones[n].head)]));
const tail = Object.fromEntries(order.map(n => [n, jp(sk.bones[n].tail)]));
const used = [...body].sort((a, b) => a - b), remap = new Map(used.map((v, i) => [v, i]));
const P = [], N = [], Jt = [], Wt = [], I = [];
used.forEach(v => P.push(...V[v]));
for (const f of F) { const q = f.map(v => remap.get(v)); I.push(q[0], q[1], q[2]); if (q.length === 4) I.push(q[0], q[2], q[3]); }
const per = used.map(() => []);
order.forEach((n, bi) => { for (const [v, w] of (W[n] || [])) { const i = remap.get(v); if (i !== undefined) per[i].push([bi, w]); } });
per.forEach(l => { l.sort((a, b) => b[1] - a[1]); const t = l.slice(0, 4); const s = t.reduce((a, b) => a + b[1], 0) || 1; if (!t.length) t.push([0, 1]);
  for (let k = 0; k < 4; k++) { Jt.push(t[k] ? t[k][0] : 0); Wt.push(t[k] ? (l.length ? t[k][1] / s : 1) : 0); } });

// ---- the eyes: MakeHuman's high-poly eyeballs (CC0), fitted to the eye helpers with the .mhclo (three base vertices,
// barycentric weights, and an offset scaled by the base's own measures), each skinned to its eye bone
const eyeDir = `${D}/eyes/high-poly`, mhclo = fs.readFileSync(`${eyeDir}/high-poly.mhclo`, "utf8").split("\n");
const scl = {}; let inV = false; const refs = [];
for (const l of mhclo) { const t = l.trim().split(/\s+/);
  if (/^[xyz]_scale$/.test(t[0])) { const k = "xyz".indexOf(t[0][0]); scl[t[0][0]] = Math.abs(V[+t[1]][k] - V[+t[2]][k]) / +t[3]; }
  else if (t[0] === "verts") inV = true; else if (inV && t.length === 9) refs.push(t.map(Number)); else if (inV && t.length === 1 && t[0] !== "") refs.push([+t[0], +t[0], +t[0], 1, 0, 0, 0, 0, 0]); }
const EV = [], EF = [], EN = [];
for (const l of fs.readFileSync(`${eyeDir}/high-poly.obj`, "utf8").split("\n")) {
  if (l.startsWith("f ")) EF.push(l.split(/\s+/).slice(1).filter(Boolean).map(t => +t.split("/")[0] - 1)); }
for (const r of refs) { const [a, b, c, wa, wb, wc, ox, oy, oz] = r;
  EV.push([0, 1, 2].map(k => wa * V[a][k] + wb * V[b][k] + wc * V[c][k] + [ox * scl.x, oy * scl.y, oz * scl.z][k])); }
const eyeL = jp(sk.bones["eye.L"].head)[0];
// real-size eyeballs: MakeHuman's eye proxy is ~3.3 cm across at this height; a real eyeball is ~2.4 cm. Each eye is
// scaled about its front pole (the cornea stays under the lids, the ball shrinks back into the socket)
const EYE_D = 0.024;
for (const sgn of [1, -1]) {
  const ids = EV.map((p, i) => i).filter(i => Math.sign(EV[i][0]) === sgn); if (!ids.length) continue;
  const lo = [0, 1, 2].map(k => Math.min(...ids.map(i => EV[i][k]))), hi = [0, 1, 2].map(k => Math.max(...ids.map(i => EV[i][k])));
  const s_ = EYE_D / ((hi[0] - lo[0] + hi[1] - lo[1]) / 2), pole = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2]];
  for (const i of ids) for (let k = 0; k < 3; k++) EV[i][k] = pole[k] + (EV[i][k] - pole[k]) * s_;
}
// the eyes' colour (vertex colour): sclera, a dark brown iris 11.5 mm across with a darker limbal ring, a 4 mm pupil,
// measured across the front pole of each ball (the cornea's axis is +z, forward)
const eyeCol = EV.map(() => [0.9, 0.88, 0.86]);
for (const sgn of [1, -1]) {
  const ids = EV.map((p, i) => i).filter(i => Math.sign(EV[i][0]) === sgn); if (!ids.length) continue;
  const zf = Math.max(...ids.map(i => EV[i][2])), cx = ids.reduce((t, i) => t + EV[i][0], 0) / ids.length, cy = ids.reduce((t, i) => t + EV[i][1], 0) / ids.length;
  for (const i of ids) { const r = Math.hypot(EV[i][0] - cx, EV[i][1] - cy); if (EV[i][2] < zf - 0.006) continue;
    if (r < 0.002) eyeCol[i] = [0.02, 0.015, 0.012]; else if (r < 0.0052) eyeCol[i] = [0.24, 0.13, 0.07]; else if (r < 0.00575) eyeCol[i] = [0.08, 0.05, 0.03]; }
}
const base = used.length;
EV.forEach(p => { P.push(...p); const bone = order.indexOf(Math.sign(p[0]) === Math.sign(eyeL) ? "eye.L" : "eye.R"); Jt.push(bone, 0, 0, 0); Wt.push(1, 0, 0, 0); });
for (const f of EF) { const q = f.map(v => v + base); I.push(q[0], q[1], q[2]); if (q.length === 4) I.push(q[0], q[2], q[3]); }

// ---- normals
const pos = new Float32Array(P), nrm = new Float32Array(P.length);
for (let i = 0; i < I.length; i += 3) { const [a, b, c] = [I[i], I[i + 1], I[i + 2]];
  const e1 = [0, 1, 2].map(k => pos[b * 3 + k] - pos[a * 3 + k]), e2 = [0, 1, 2].map(k => pos[c * 3 + k] - pos[a * 3 + k]);
  const n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
  for (const v of [a, b, c]) for (let k = 0; k < 3; k++) nrm[v * 3 + k] += n[k]; }
for (let i = 0; i < nrm.length; i += 3) { const l = Math.hypot(nrm[i], nrm[i + 1], nrm[i + 2]) || 1; nrm[i] /= l; nrm[i + 1] /= l; nrm[i + 2] /= l; }

// ---- GLB: two primitives (skin, eyes) on one skinned mesh
const doc = new Document(), buf = doc.createBuffer();
const acc = (a, t) => doc.createAccessor().setArray(a).setType(t).setBuffer(buf);
const J16 = new Uint16Array(Jt), W32 = new Float32Array(Wt);
const SKIN = [0.78, 0.6, 0.5], col = new Float32Array((pos.length / 3) * 3);
for (let i = 0; i < pos.length / 3; i++) col.set(i < base ? SKIN : eyeCol[i - base], i * 3);
const bodyTris = new Uint32Array(I.slice(0, I.length - EF.reduce((s, f) => s + (f.length === 4 ? 6 : 3), 0)));
const eyeTris = new Uint32Array(I.slice(bodyTris.length));
const mk = (ix, mat) => doc.createPrimitive().setAttribute("POSITION", acc(pos, "VEC3")).setAttribute("NORMAL", acc(nrm, "VEC3"))
  .setAttribute("COLOR_0", acc(col, "VEC3")).setAttribute("JOINTS_0", acc(J16, "VEC4")).setAttribute("WEIGHTS_0", acc(W32, "VEC4")).setIndices(acc(ix, "SCALAR")).setMaterial(mat);
const mesh = doc.createMesh("body")
  .addPrimitive(mk(bodyTris, doc.createMaterial("skin").setBaseColorFactor([1, 1, 1, 1]).setRoughnessFactor(0.55)))
  .addPrimitive(mk(eyeTris, doc.createMaterial("eyes").setBaseColorFactor([1, 1, 1, 1]).setRoughnessFactor(0.15)));
const nodes = {};
for (const n of order) { const p = sk.bones[n].parent, h = head[n], ph = p ? head[p] : [0, 0, 0];
  nodes[n] = doc.createNode(n).setTranslation([h[0] - ph[0], h[1] - ph[1], h[2] - ph[2]]); if (p) nodes[p].addChild(nodes[n]); }
const ibm = new Float32Array(order.length * 16);
order.forEach((n, i) => { const h = head[n]; ibm.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -h[0], -h[1], -h[2], 1], i * 16); });
const skin = doc.createSkin().setSkeleton(nodes.root).setInverseBindMatrices(acc(ibm, "MAT4")); order.forEach(n => skin.addJoint(nodes[n]));
const scene = doc.createScene().addChild(doc.createNode("body").setMesh(mesh).setSkin(skin)).addChild(nodes.root);
doc.getRoot().setDefaultScene(scene);
await new NodeIO().write(OUT, doc);

// ---- report: proportions to check against real anthropometry
const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const jn = n => jp(n);
const eyeVL = EV.filter(p => Math.sign(p[0]) === Math.sign(eyeL)); let er = 0; const ec = [0, 1, 2].map(k => eyeVL.reduce((s, p) => s + p[k], 0) / eyeVL.length);
for (const p of eyeVL) er = Math.max(er, d(p, ec));
const rep_extra = {};
const rep = {
  bones: order.length, verts: pos.length / 3, tris: I.length / 3, height_m: HEIGHT, scale_from_base: +S.toFixed(4),
  shoulder_width_m: +d(head["upperarm01.L"], head["upperarm01.R"]).toFixed(3),
  hand_length_m: +d(head["wrist.L"], tail["finger3-3.L"]).toFixed(3),
  palm_width_m: +d(head["finger2-1.L"], head["finger5-1.L"]).toFixed(3),
  middle_finger_m: +(d(head["finger3-1.L"], head["finger3-2.L"]) + d(head["finger3-2.L"], head["finger3-3.L"]) + d(head["finger3-3.L"], tail["finger3-3.L"])).toFixed(3),
  eyeball_diameter_m: +(2 * er).toFixed(4), glb_MB: +(fs.statSync(OUT).size / 1e6).toFixed(2), targets: applied,
};
const exL = [0, 1, 2].map(k => [Math.min(...eyeVL.map(p => p[k])), Math.max(...eyeVL.map(p => p[k]))]); rep_extra.eyeL_extent = exL.map(([a, b]) => +(b - a).toFixed(4)); rep_extra.eyeL_centre = ec.map(x => +x.toFixed(3)); rep_extra.headJ = head["head"].map(x => +x.toFixed(3));
fs.writeFileSync(OUT.replace(/\.glb$/, "_report.json"), JSON.stringify(rep, null, 1));
fs.writeFileSync(OUT.replace(/\.glb$/, "_rest.json"), JSON.stringify({ order, head, tail, parent: Object.fromEntries(order.map(n => [n, sk.bones[n].parent])) }));
console.log(JSON.stringify({ ...rep, ...rep_extra, targets: applied.length }));
