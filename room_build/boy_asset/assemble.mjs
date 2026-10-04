// Stage 2 of the boy.glb rebuild:  node assemble.mjs [--install]
// Takes the ORIGINAL file (work/boy_raw.glb: nodes, 24-joint skin, inverse bind matrices, the embedded sit clip) and
// puts the rebuilt mesh (work/boy_mesh.glb, from build_mesh.py) into it, primitive by primitive, with its new
// materials and textures (out/tex_*.png from make_textures.py), plus the eye and eyelid nodes under the Head joint.
// Nothing of the rig is touched: the vertex positions are written back in the original's quantised vertex space
// (int16, normalised, which the original inverse bind matrices expect), joints are remapped by bone name.
// Writes out/boy.glb (meshopt + WebP); with --install copies it to ../../web/room/boy.glb.
import { NodeIO, Document, Accessor, Primitive } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression, EXTTextureWebP, KHRMaterialsSheen, KHRMaterialsClearcoat, KHRMaterialsIOR, KHRMaterialsSpecular, KHRMeshQuantization } from "@gltf-transform/extensions";
import { quantize, reorder, prune, dedup } from "@gltf-transform/functions";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";
import sharp from "sharp";
import fs from "fs"; import path from "path";
import { mat4, vec3, quat, vec4 } from "gl-matrix";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WORK = path.join(HERE, "work"), OUT = path.join(HERE, "out");
const SPEC = JSON.parse(fs.readFileSync(path.join(OUT, "spec.json"), "utf8"));   // eyes, lids, texture names (make_textures.py)
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const orig = await io.read(path.join(WORK, "boy_raw.glb"));
const built = await io.read(path.join(WORK, "boy_mesh.glb"));

const root = orig.getRoot(), skin = root.listSkins()[0], charNode = root.listNodes().find(n => n.getMesh());
const jointsOrig = skin.listJoints(), nameToJoint = new Map(jointsOrig.map((j, i) => [j.getName(), i]));
const skinB = built.getRoot().listSkins()[0], jointsB = skinB.listJoints().map(j => j.getName());
const remap = jointsB.map(n => { const i = nameToJoint.get(n); if (i == null) throw new Error("joint missing in the original: " + n); return i; });

// ---- the mapping from the Blender export's vertex space (metres, y up) to the original's (normalised int16):
// p_orig = IBM_orig(j)^-1 * IBM_built(j) * p_built, the same for every joint j (checked below)
const ibmO = skin.getInverseBindMatrices(), ibmB = skinB.getInverseBindMatrices();
const X = mat4.create();
{ const a = mat4.create(), b = mat4.create(); ibmO.getElement(nameToJoint.get("Hips"), a); ibmB.getElement(jointsB.indexOf("Hips"), b); mat4.invert(a, a); mat4.multiply(X, a, b); }
for (const [bi, oi] of remap.entries()) { const a = mat4.create(), b = mat4.create(), t = mat4.create(); ibmO.getElement(oi, a); ibmB.getElement(bi, b); mat4.invert(a, a); mat4.multiply(t, a, b);
  const err = Math.max(...t.map((v, k) => Math.abs(v - X[k]))); if (err > 2e-4) throw new Error(`joint ${jointsB[bi]}: vertex-space mapping differs by ${err}`); }
console.log("vertex space: scale %s, offset %s", (1 / X[0]).toFixed(3), [X[12], X[13], X[14]].map(v => v.toFixed(4)).join(","));

// ---- textures
const texCache = new Map();
async function texture(name, {quality = 85, lossless = false} = {}) {
  if (texCache.has(name)) return texCache.get(name);
  const file = path.join(OUT, `tex_${name}.png`); let img = sharp(file); const size = (SPEC.sizes || {})[name]; if (size) img = img.resize(size, size, {kernel: "lanczos3"});
  const buf = await img.webp({quality, lossless, effort: 6}).toBuffer();
  const t = orig.createTexture(name).setImage(buf).setMimeType("image/webp"); texCache.set(name, t); console.log("texture", name, (buf.length / 1024).toFixed(0), "KB"); return t;
}
const oldMat = root.listMaterials()[0];
const sheenExt = orig.createExtension(KHRMaterialsSheen), ccExt = orig.createExtension(KHRMaterialsClearcoat);
async function material(name, spec) {
  const m = orig.createMaterial("boy_" + name).setDoubleSided(!!spec.doubleSided).setMetallicFactor(0).setRoughnessFactor(spec.roughness ?? 1).setBaseColorFactor(spec.color || [1, 1, 1, 1]);
  if (spec.base) m.setBaseColorTexture(await texture(spec.base, {quality: spec.baseQ ?? 85}));
  if (spec.orm) m.setMetallicRoughnessTexture(await texture(spec.orm, {quality: 80})).setOcclusionTexture(await texture(spec.orm, {quality: 80}));
  if (spec.normal) { m.setNormalTexture(await texture(spec.normal, {quality: spec.normalQ ?? 88})); m.setNormalScale(spec.normalScale ?? 1); }
  if (spec.alphaMask) m.setAlphaMode("MASK").setAlphaCutoff(0.5);
  if (spec.blend) m.setAlphaMode("BLEND");
  if (spec.sheen) { const s = sheenExt.createSheen().setSheenColorFactor(spec.sheen).setSheenRoughnessFactor(spec.sheenRoughness ?? 0.6); m.setExtension("KHR_materials_sheen", s); }
  if (spec.clearcoat) { const c = ccExt.createClearcoat().setClearcoatFactor(spec.clearcoat).setClearcoatRoughnessFactor(spec.clearcoatRoughness ?? 0.05); m.setExtension("KHR_materials_clearcoat", c); }
  for (const t of [m.getBaseColorTextureInfo(), m.getNormalTextureInfo(), m.getMetallicRoughnessTextureInfo(), m.getOcclusionTextureInfo()]) if (t) t.setMagFilter(9729).setMinFilter(9987).setWrapS(10497).setWrapT(10497);
  return m;
}

// ---- the body primitives, in the built file's (= material slot) order: skin first, which room.html's handVertices relies
// on; the slides last, with the invisible full-body proxy appended to it (room.html's bedInit / slidesInit / debug helpers
// take the LAST skinned mesh as his whole body: they need every bone's vertices there, and slidesInit must find exactly
// the slide triangles, dark texels on the feet; the proxy's texels are white with alpha 0 in the cloth atlas, MASK)
const mesh = charNode.getMesh(); for (const p of mesh.listPrimitives()) { p.dispose(); }
const buf = root.listBuffers()[0];
const tmp = vec4.create();
function convert(pb, uvOverride) {
  const pos = pb.getAttribute("POSITION"), nrm = pb.getAttribute("NORMAL"), uv = pb.getAttribute("TEXCOORD_0"), jt = pb.getAttribute("JOINTS_0"), wt = pb.getAttribute("WEIGHTS_0"), idx = pb.getIndices();
  const n = pos.getCount(), P = new Int16Array(n * 3), N = new Float32Array(n * 3), J = new Uint8Array(n * 4), Wt = new Float32Array(n * 4), UV = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    pos.getElement(i, tmp); tmp[3] = 1; vec4.transformMat4(tmp, tmp, X);
    for (let k = 0; k < 3; k++) { let v = Math.round(tmp[k] * 32767); if (Math.abs(v) > 33000) throw new Error("vertex out of the quantised range: " + tmp); P[i * 3 + k] = Math.max(-32767, Math.min(32767, v)); }   // (the decimated proxy may overshoot the body's box by a fraction of a mm)
    nrm.getElement(i, tmp); for (let k = 0; k < 3; k++) N[i * 3 + k] = tmp[k];
    jt.getElement(i, tmp); for (let k = 0; k < 4; k++) J[i * 4 + k] = remap[tmp[k]];
    wt.getElement(i, tmp); let s = tmp[0] + tmp[1] + tmp[2] + tmp[3]; for (let k = 0; k < 4; k++) Wt[i * 4 + k] = s > 0 ? tmp[k] / s : (k === 0 ? 1 : 0);
    if (uvOverride) { UV[i * 2] = uvOverride[0]; UV[i * 2 + 1] = uvOverride[1]; } else { uv.getElement(i, tmp); UV[i * 2] = tmp[0]; UV[i * 2 + 1] = tmp[1]; }
  }
  return {n, P, N, J, Wt, UV, I: new Uint32Array(idx.getArray())};
}
function concat(a, b) {
  const cat = (x, y) => { const o = new x.constructor(x.length + y.length); o.set(x); o.set(y, x.length); return o; };
  const I = new Uint32Array(a.I.length + b.I.length); I.set(a.I); for (let i = 0; i < b.I.length; i++) I[a.I.length + i] = b.I[i] + a.n;
  return {n: a.n + b.n, P: cat(a.P, b.P), N: cat(a.N, b.N), J: cat(a.J, b.J), Wt: cat(a.Wt, b.Wt), UV: cat(a.UV, b.UV), I};
}
const acc = (arr, type, normalized = false) => orig.createAccessor().setType(type).setArray(arr).setNormalized(normalized).setBuffer(buf);
const nodeMesh = name => built.getRoot().listNodes().find(n => n.getName() === name && n.getMesh())?.getMesh();   // Blender names the mesh data "char1.001"; the nodes keep their names
const bodyMesh = nodeMesh("char1"), proxyMesh = nodeMesh("proxy");
if (!proxyMesh) throw new Error("work/boy_mesh.glb has no proxy mesh (build_mesh.py exports one)");
const PROXY_UV = [0.5, 0.5];                                       // (never drawn: its triangles are degenerate)
for (const pb of bodyMesh.listPrimitives()) {
  const name = pb.getMaterial().getName().replace(/^boy_/, "");
  let d = convert(pb);
  if (name === "slides") { let px = null; for (const pp of proxyMesh.listPrimitives()) { const c = convert(pp, PROXY_UV); px = px ? concat(px, c) : c; }
    // the proxy's triangles are made degenerate (a, a, a): zero area, so the rasteriser never draws them at any distance or
    // mip level (an alpha-masked texel leaked through the mips as white/black slivers at the wrist and the slide strap);
    // room.html's bedInit / slidesInit only read the vertices (positions, skin indices, uvs) and the triangle list
    for (let i = 0; i < px.I.length; i += 3) { px.I[i + 1] = px.I[i]; px.I[i + 2] = px.I[i]; }
    d = concat(d, px); console.log("proxy appended to the slides:", px.n, "vertices", px.I.length / 3, "degenerate triangles"); }
  const prim = orig.createPrimitive().setMode(Primitive.Mode.TRIANGLES)
    .setAttribute("POSITION", acc(d.P, Accessor.Type.VEC3, true))
    .setAttribute("NORMAL", acc(d.N, Accessor.Type.VEC3))
    .setAttribute("TEXCOORD_0", acc(d.UV, Accessor.Type.VEC2))
    .setAttribute("JOINTS_0", acc(d.J, Accessor.Type.VEC4))
    .setAttribute("WEIGHTS_0", acc(d.Wt, Accessor.Type.VEC4))
    .setIndices(acc(d.I, Accessor.Type.SCALAR))
    .setMaterial(await material(name, SPEC.materials[name]));
  mesh.addPrimitive(prim);
  console.log("primitive", name, d.n, "vertices", d.I.length / 3, "triangles");
}
oldMat.dispose();

// ---- eyes and eyelids: plain mesh nodes under the Head joint (they move with the head; G3 rotates them)
// Head's global rest transform (cm, y up) from the node hierarchy; the eye nodes get the inverse of Head's global
// rotation so that their own axes are the world axes at rest (x right, y up, z forward): yaw = rotation.y, pitch = rotation.x.
function globalMatrix(node) { const m = mat4.create(); let n = node; const chain = []; while (n) { chain.unshift(n); n = n.getParentNode(); }
  for (const c of chain) { const l = mat4.create(); mat4.fromRotationTranslationScale(l, c.getRotation(), c.getTranslation(), c.getScale()); mat4.multiply(m, m, l); } return m; }
const headJoint = jointsOrig[nameToJoint.get("Head")];
const G = globalMatrix(headJoint), Ginv = mat4.invert(mat4.create(), G);
const gq = mat4.getRotation(quat.create(), G); const gs = mat4.getScaling(vec3.create(), G);
const invRot = quat.invert(quat.create(), quat.normalize(gq, gq));
function sphere(nameSuffix, radius, segsU, segsV, capAngle, matr, uvFn) {
  // lat/long sphere (or a cap: polar angle 0..capAngle around +z, the forward axis), positions in cm
  const P = [], N = [], UV = [], I = [];
  for (let v = 0; v <= segsV; v++) { const th = capAngle * v / segsV; for (let u = 0; u <= segsU; u++) { const ph = 2 * Math.PI * u / segsU;
    const x = Math.sin(th) * Math.cos(ph), y = Math.sin(th) * Math.sin(ph), z = Math.cos(th);
    P.push(x * radius, y * radius, z * radius); N.push(x, y, z); const t = uvFn(th, ph, u / segsU, v / segsV); UV.push(t[0], t[1]); } }
  for (let v = 0; v < segsV; v++) for (let u = 0; u < segsU; u++) { const a = v * (segsU + 1) + u, b = a + segsU + 1; I.push(a, b, a + 1, a + 1, b, b + 1); }
  return orig.createPrimitive().setAttribute("POSITION", acc(new Float32Array(P), Accessor.Type.VEC3)).setAttribute("NORMAL", acc(new Float32Array(N), Accessor.Type.VEC3))
    .setAttribute("TEXCOORD_0", acc(new Float32Array(UV), Accessor.Type.VEC2)).setIndices(acc(new Uint16Array(I), Accessor.Type.SCALAR)).setMaterial(matr);
}
const eyeMat = await material("eye", SPEC.materials.eye), corneaMat = await material("cornea", SPEC.materials.cornea), lidMat = await material("lid", SPEC.materials.lid);
const E = SPEC.eyes;                                                       // {left:{center:[cm], forward:[...]}, right:..., radius}
for (const side of ["Left", "Right"]) {
  const e = E[side.toLowerCase()];
  // eye node: at the eyeball centre, axes = world axes; the mesh faces +z (forward)
  const local = vec3.transformMat4(vec3.create(), e.center, Ginv);
  const node = orig.createNode(side + "Eye").setTranslation(local).setRotation(invRot).setScale([1 / gs[0], 1 / gs[1], 1 / gs[2]]);
  // the eyeball's own forward: the face's forward at the eye, as a rotation of +z inside the node
  const f = vec3.normalize(vec3.create(), e.forward); const q = quat.rotationTo(quat.create(), [0, 0, 1], f);
  const ballNode = orig.createNode(side + "Eyeball").setRotation(q); node.addChild(ballNode);
  const ball = orig.createMesh(side + "Eyeball");
  // iris/pupil: the texture's centre maps to the front pole; uv radius ~ polar angle / (pi/2) * 0.5 over the front hemisphere
  ball.addPrimitive(sphere("ball", E.radius, 32, 20, Math.PI, eyeMat, (th, ph) => { const r = Math.min(0.5, 0.5 * th / (Math.PI * 0.55)); return [0.5 + r * Math.cos(ph), 0.5 + r * Math.sin(ph)]; }));
  ball.addPrimitive(sphere("cornea", E.radius * 1.015, 24, 8, 0.42, corneaMat, (th, ph) => [0.5, 0.5]));   // a glossy bulge over the iris
  ballNode.setMesh(ball);
  // eyelid: a cap of a slightly larger sphere, rotated up into the head when open; G3 rotates it down to blink
  const lidNode = orig.createNode(side + "Eyelid").setTranslation(local).setRotation(invRot).setScale([1 / gs[0], 1 / gs[1], 1 / gs[2]]);
  const lidPivot = orig.createNode(side + "EyelidCap").setRotation(quat.multiply(quat.create(), q, quat.setAxisAngle(quat.create(), [1, 0, 0], -SPEC.lid.openAngle)));
  lidNode.addChild(lidPivot);
  const lid = orig.createMesh(side + "Eyelid"); lid.addPrimitive(sphere("lid", E.radius * 1.08, 24, 8, SPEC.lid.capAngle, lidMat, (th, ph) => [0.5 + 0.45 * th / SPEC.lid.capAngle * Math.cos(ph), 0.5 + 0.45 * th / SPEC.lid.capAngle * Math.sin(ph)]));
  lidPivot.setMesh(lid);
  // ---- the eye's finish (the owner's "rifinito"): on the opening's ellipse from make_textures.py (A across, towards the
  // nose; B up; a, b half-lengths; centre relative to the eyeball centre), all in the Eye node's frame (metres, world axes):
  //   the lid rim: a band from the skin's edge back towards the eyeball (the eyelid's thickness, moist);
  //   the lashes: alpha cards rooted on the upper and lower margins, fanning forward and out;
  //   the caruncle: the small pink body in the inner corner.
  const O = e.opening, LS = SPEC.lashes || {};
  const F = f, A = vec3.normalize(vec3.create(), O.A), B = vec3.normalize(vec3.create(), O.B), C0 = O.center;
  // the hole's radius towards angle t in the (A, B) plane: the measured outline (48 bins from -pi) when there is one, else the ellipse
  const radiusAt = t => { if (!O.outline) { const c = Math.cos(t), s = Math.sin(t); return 1 / Math.sqrt((c * c) / (O.a * O.a) + (s * s) / (O.b * O.b)); }
    const NB = O.outline.length; let u = ((t - (O.outline0 ?? -Math.PI)) / (2 * Math.PI)) * NB; u = ((u % NB) + NB) % NB; const i0 = Math.floor(u), f_ = u - i0; return O.outline[i0 % NB] * (1 - f_) + O.outline[(i0 + 1) % NB] * f_; };
  const onEllipse = (t, da = 0, db = 0, dz = 0) => { const r = radiusAt(t) + (da + db) / 2, p = vec3.clone(C0); vec3.scaleAndAdd(p, p, A, r * Math.cos(t)); vec3.scaleAndAdd(p, p, B, r * Math.sin(t)); vec3.scaleAndAdd(p, p, F, dz); return p; };
  function quads(name, P, N, UV, I, matr) {
    return orig.createPrimitive().setAttribute("POSITION", acc(new Float32Array(P), Accessor.Type.VEC3)).setAttribute("NORMAL", acc(new Float32Array(N), Accessor.Type.VEC3))
      .setAttribute("TEXCOORD_0", acc(new Float32Array(UV), Accessor.Type.VEC2)).setIndices(acc(new Uint16Array(I), Accessor.Type.SCALAR)).setMaterial(matr);
  }
  const finish = orig.createMesh(side + "EyeFinish"); const finishNode = orig.createNode(side + "EyeFinish"); finishNode.setMesh(finish); node.addChild(finishNode);
  { // rim
    const SEG = 48, depth = LS.rimDepth ?? 0.002, P = [], N = [], UV = [], I = [];
    for (let k = 0; k <= SEG; k++) { const t = 2 * Math.PI * k / SEG;
      const po = onEllipse(t, -0.0005, -0.0005, -0.0006), pi = onEllipse(t, -0.0011, -0.0011, -depth);   // from inside the skin's edge, back towards the ball: a dark line of lid thickness, never in front of the skin
      const nrm = vec3.create(); vec3.sub(nrm, C0, po); vec3.normalize(nrm, nrm);          // facing the opening's centre (the inside of the lid)
      P.push(...po, ...pi); N.push(...nrm, ...nrm); UV.push(k / SEG, 0, k / SEG, 1); }
    for (let k = 0; k < SEG; k++) { const a0 = 2 * k; I.push(a0, a0 + 1, a0 + 2, a0 + 2, a0 + 1, a0 + 3); }
    finish.addPrimitive(quads("rim", P, N, UV, I, await material("rim", SPEC.materials.rim)));
  }
  { // caruncle: a small sphere in the inner corner, a little behind the skin
    const r = LS.caruncle ?? 0.0008, c = onEllipse(0, -0.0012, 0, -0.0022);                   // t = 0 is the +A end: the inner corner
    const prim = sphere("caruncle", r, 12, 8, Math.PI, await material("caruncle", SPEC.materials.caruncle), () => [0.5, 0.5]);
    const pos = prim.getAttribute("POSITION"), arr = pos.getArray().slice(); for (let i = 0; i < arr.length; i += 3) { arr[i] += c[0]; arr[i + 1] += c[1]; arr[i + 2] += c[2]; } pos.setArray(arr);
    finish.addPrimitive(prim);
  }
  { // lashes
    const lashMat = await material("lash", SPEC.materials.lash); const P = [], N = [], UV = [], I = [];
    const out = vec3.scale(vec3.create(), A, -1);                                          // outwards (away from the nose)
    for (const [which, lower] of [["upper", false], ["lower", true]]) {
      const cfg = LS[which] || {n: lower ? 8 : 14, length: lower ? 0.0035 : 0.0065, width: lower ? 0.0022 : 0.0028};
      for (let k = 0; k < cfg.n; k++) {
        const s = (k + 0.5) / cfg.n, t = lower ? Math.PI + 0.25 + s * (Math.PI - 0.5) : 0.2 + s * (Math.PI - 0.4);   // along the margin, away from the inner corner
        const root = onEllipse(t, -0.0002, -0.0002, 0.0002);
        const tg = vec3.sub(vec3.create(), onEllipse(t + 0.02), onEllipse(t - 0.02)); vec3.normalize(tg, tg);        // the margin's tangent
        const dir = vec3.create(); vec3.scale(dir, F, 0.8); vec3.scaleAndAdd(dir, dir, B, lower ? -0.55 : 0.5); vec3.scaleAndAdd(dir, dir, out, 0.25 * s); vec3.normalize(dir, dir);
        const len = cfg.length * (0.75 + 0.5 * Math.sin(Math.PI * s)), half = vec3.scale(vec3.create(), tg, cfg.width / 2);
        const b0 = vec3.sub(vec3.create(), root, half), b1 = vec3.add(vec3.create(), root, half);
        const t0 = vec3.scaleAndAdd(vec3.create(), b0, dir, len), t1 = vec3.scaleAndAdd(vec3.create(), b1, dir, len);
        const nrm = vec3.cross(vec3.create(), tg, dir); vec3.normalize(nrm, nrm);
        const base = P.length / 3; P.push(...b0, ...b1, ...t0, ...t1); for (let q = 0; q < 4; q++) N.push(...nrm);
        UV.push(0, 1, 1, 1, 0, 0, 1, 0); I.push(base, base + 1, base + 2, base + 2, base + 1, base + 3);
      }
    }
    finish.addPrimitive(quads("lashes", P, N, UV, I, lashMat));
  }
  headJoint.addChild(node); headJoint.addChild(lidNode);
}

// ---- finish: quantise the new attributes (positions are already in the original's int16 space), meshopt, write
await orig.transform(
  dedup(),
  prune(),
  quantize({pattern: /^(NORMAL|TEXCOORD_0|WEIGHTS_0|JOINTS_0)$/, quantizeNormal: 8, quantizeTexcoord: 16, quantizeWeight: 8}),
  reorder({encoder: MeshoptEncoder}),
);
orig.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method: EXTMeshoptCompression.EncoderMethod.QUANTIZE});
orig.createExtension(EXTTextureWebP).setRequired(true);
fs.mkdirSync(OUT, {recursive: true});
await io.write(path.join(OUT, "boy.glb"), orig);
const size = fs.statSync(path.join(OUT, "boy.glb")).size;
console.log("out/boy.glb", (size / 1024).toFixed(0), "KB");
if (size > 3 * 1024 * 1024) throw new Error("over the 3 MB budget");
if (process.argv.includes("--install")) { fs.copyFileSync(path.join(OUT, "boy.glb"), path.join(HERE, "..", "..", "web", "room", "boy.glb")); console.log("installed to web/room/boy.glb"); }
