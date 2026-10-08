// node build_glb.mjs <char_mixamo.glb> <out.glb> <hand: Right|Left|none> <tex px> <clip.json>...
// Bakes retargeted clips (retarget.py JSON) onto the character as named animations, with a generic
// phone (unbranded dark slab, lighter screen face) parented to the chosen hand at the Sims prop slot.
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { prune, dedup, meshopt, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";
const [,, IN, OUT, HAND, TEX, ...CLIPS] = process.argv;
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const doc = await io.read(IN);
const root = doc.getRoot(), buf = root.listBuffers()[0];
const node = n => root.listNodes().find(x => x.getName() === n);
const acc = (arr, type) => doc.createAccessor().setType(type).setArray(new Float32Array(arr)).setBuffer(buf);

// phone: 7.2 x 15.0 x 0.8 cm, long axis / screen normal in the slot frame (see README: slot axes)
const PH = {w: 0.072, h: 0.150, t: 0.008};
function box(name, sx, sy, sz, color, ox = 0, oy = 0, oz = 0) {
  const x = sx / 2, y = sy / 2, z = sz / 2, P = [], N = [], I = [];
  const faces = [[[1,0,0],[0,1,0],[0,0,1]],[[-1,0,0],[0,0,1],[0,1,0]],[[0,1,0],[0,0,1],[1,0,0]],[[0,-1,0],[1,0,0],[0,0,1]],[[0,0,1],[1,0,0],[0,1,0]],[[0,0,-1],[0,1,0],[1,0,0]]];
  for (const [n, u, v] of faces) {
    const b = P.length / 3;
    for (const [a, c] of [[-1,-1],[1,-1],[1,1],[-1,1]]) {
      P.push(ox + (n[0] + a*u[0] + c*v[0]) * x, oy + (n[1] + a*u[1] + c*v[1]) * y, oz + (n[2] + a*u[2] + c*v[2]) * z); N.push(...n);
    }
    I.push(b, b+1, b+2, b, b+2, b+3);
  }
  const mat = doc.createMaterial(name).setBaseColorFactor(color).setRoughnessFactor(0.5).setMetallicFactor(0);
  const prim = doc.createPrimitive().setAttribute("POSITION", acc(P, "VEC3")).setAttribute("NORMAL", acc(N, "VEC3"))
    .setIndices(doc.createAccessor().setType("SCALAR").setArray(new Uint16Array(I)).setBuffer(buf)).setMaterial(mat);
  return doc.createMesh(name).addPrimitive(prim);
}
const clips = CLIPS.map(f => JSON.parse(fs.readFileSync(f, "utf8")));
const hands = HAND === "both" ? ["Right", "Left"] : HAND === "none" ? [] : HAND === "auto" ? [...new Set(clips.map(c => c.hand))] : [HAND];
for (const side of hands) {
  const pr = (clips.find(c => c.hand === side) || clips[0]).props[side];
  const hand = node("mixamorig:" + side + "Hand");
  // slot frame -> phone: screen normal = slot +X... set by PHONE_AXES below
  const n = doc.createNode("phone_" + side).setTranslation(pr.pos.map(v => v / 0.01)).setRotation(pr.quat).setScale([100, 100, 100]);
  const ax = JSON.parse(process.env.PHONE_AXES || '{"len":"y","thick":"x"}');
  const dim = {x: 0, y: 0, z: 0}; dim[ax.len] = PH.h; dim[ax.thick] = PH.t;
  const wide = ["x", "y", "z"].find(k => k !== ax.len && k !== ax.thick); dim[wide] = PH.w;
  const off = JSON.parse(process.env.PHONE_OFF || '[0,0,0]');
  const body = doc.createNode("phone_body").setMesh(box("phone_body", dim.x, dim.y, dim.z, [0.06, 0.06, 0.07, 1], ...off));
  // screen: a thin lighter plate on the face given by PHONE_SCREEN (+x/-x/...)
  const sc = process.env.PHONE_SCREEN || "+x", sgn = sc[0] === "-" ? -1 : 1, k = sc[1];
  const sd = {x: dim.x * 0.9, y: dim.y * 0.92, z: dim.z * 0.9}; sd[k] = 0.001;
  const so = [...off]; so["xyz".indexOf(k)] += sgn * (dim[k] / 2 + 0.0006);
  const screen = doc.createNode("phone_screen").setMesh(box("phone_screen", sd.x, sd.y, sd.z, process.env.PHONE_DEBUG ? (side === "Right" ? [0.95, 0.2, 0.2, 1] : [0.2, 0.4, 0.95, 1]) : [0.55, 0.75, 0.95, 1], ...so));
  n.addChild(body).addChild(screen); hand.addChild(n);
}
// animations
for (const c of clips) {
  const anim = doc.createAnimation(c.set);
  const times = Array.from({length: c.frames}, (_, i) => i / c.fps);
  const tIn = acc(times, "SCALAR");
  const add = (target, path, arr, type) => {
    const s = doc.createAnimationSampler().setInput(tIn).setOutput(acc(arr.flat(), type)).setInterpolation("LINEAR");
    anim.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(target).setTargetPath(path).setSampler(s));
  };
  for (const [name, q] of Object.entries(c.rot)) add(node(name), "rotation", q, "VEC4");
  add(node("mixamorig:Hips"), "translation", c.hips, "VEC3");
  if (clips.length > 1) for (const side of hands) {          // one phone per hand: this clip's grip, hidden if unused
    const ph = node("phone_" + side), pr = c.props[side], on = c.hand === side, two = [0, times[times.length - 1]];
    const add2 = (path, v, type) => { const s = doc.createAnimationSampler().setInput(acc(two, "SCALAR")).setOutput(acc([...v, ...v], type)).setInterpolation("STEP");
      anim.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(ph).setTargetPath(path).setSampler(s)); };
    add2("translation", pr.pos.map(v => v / 0.01), "VEC3"); add2("rotation", pr.quat, "VEC4"); add2("scale", on ? [100, 100, 100] : [0, 0, 0], "VEC3");
  }
}
// small: textures down to TEX px webp, meshopt geometry
await doc.transform(dedup(), prune({keepLeaves: true}),
  textureCompress({encoder: sharp, targetFormat: "webp", resize: [+TEX, +TEX], quality: 80}),
  meshopt({encoder: MeshoptEncoder, level: "medium"}));
await io.write(OUT, doc);
console.log(OUT, (fs.statSync(OUT).size / 1e6).toFixed(2), "MB", clips.map(c => c.set).join(","));
