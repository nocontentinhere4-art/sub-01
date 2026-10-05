// node build_char_tripo.mjs <dir> [out.glb] : the Tripo character for the web (preview/char-tripo).
//
// Input, in <dir>, from tripo_char.py: char_idle.glb and char_walk.glb, Tripo's retargets of the rig (char_rig.glb),
// the same skinned mesh and 41-bone skeleton in each, one clip each. Output: one GLB with the mesh, the skeleton and both
// clips, "idle" and "walk".
// - The walk is made in place: Tripo's walk carries the Hip forward 1.33 units over the clip although the task asked for
//   animate_in_place; the straight-line drift from the first key to the last is taken off the Hip's forward axis, so the
//   loop stays on the spot and the stride, sway and bob are kept.
// - Scaled to 1.75 m tall (from the bind-pose mesh top; Tripo outputs him about 0.98 units tall) on the Armature node, so
//   the clips scale with him.
// - MATTE=0.8 (optional): flat roughness instead of the metal/roughness map, see below.
// - Textures to WebP (base colour 4096 px for the face, normal and metal/roughness 2048 px), geometry meshopt-compressed.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression } from "@gltf-transform/extensions";
import { prune, dedup, meshopt, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder } from "meshoptimizer";
import sharp from "sharp";
import path from "node:path";

const [,, DIR, OUT = path.join(DIR, "char_tripo.glb")] = process.argv;
const BASE = Number(process.env.BASE_PX || 4096);         // base colour size; normal and metal/roughness at half
const HEIGHT = 1.75;
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ "meshopt.encoder": MeshoptEncoder });
const doc = await io.read(path.join(DIR, "char_idle.glb"));
const walk = await io.read(path.join(DIR, "char_walk.glb"));
const root = doc.getRoot();
const nodes = Object.fromEntries(root.listNodes().map(n => [n.getName(), n]));

// copy the walk clip onto this document's nodes, by bone name
const wa = walk.getRoot().listAnimations()[0];
const anim = doc.createAnimation("walk");
const buf = root.listBuffers()[0];
for (const ch of wa.listChannels()) {
  const s = ch.getSampler(), name = ch.getTargetNode().getName(), p = ch.getTargetPath();
  const inp = doc.createAccessor().setType("SCALAR").setArray(s.getInput().getArray().slice()).setBuffer(buf);
  const out = s.getOutput().getArray().slice();
  if (name === "Hip" && p === "translation") {            // in place: remove the linear drift on the axis that moves most
    const n = out.length / 3;
    const span = [0, 1, 2].map(k => out[(n - 1) * 3 + k] - out[k]);
    const k = span.map(Math.abs).indexOf(Math.max(...span.map(Math.abs)));
    for (let i = 0; i < n; i++) out[i * 3 + k] -= span[k] * i / (n - 1);
    console.log(`walk: Hip drift ${span[k].toFixed(3)} removed on axis ${"xyz"[k]}`);
  }
  const outA = doc.createAccessor().setType(s.getOutput().getType()).setArray(out).setBuffer(buf);
  const smp = doc.createAnimationSampler().setInput(inp).setOutput(outA).setInterpolation(s.getInterpolation());
  anim.addSampler(smp).addChannel(doc.createAnimationChannel().setTargetNode(nodes[name]).setTargetPath(p).setSampler(smp));
}

// 1.75 m tall: scale the scene's top node (the Armature)
const top = root.listScenes()[0].listChildren();
let ymax = 0;
for (const m of root.listMeshes()) for (const pr of m.listPrimitives()) ymax = Math.max(ymax, pr.getAttribute("POSITION").getMax([])[1]);
for (const n of top) n.setScale(n.getScale().map(v => v * HEIGHT / ymax));
console.log(`bind-pose mesh top ${ymax.toFixed(3)} (Tripo units); scaled x${(HEIGHT / ymax).toFixed(3)}`);

// MATTE=<r>: drop Tripo's metal/roughness map (it makes the fleece and cotton read as satin) and use one flat roughness
// and metalness 0 instead: a material setting, the colours are untouched.
if (process.env.MATTE) for (const m of root.listMaterials()) {
  m.setMetallicRoughnessTexture(null).setRoughnessFactor(Number(process.env.MATTE)).setMetallicFactor(0);
  console.log(`material ${m.getName()}: roughness ${process.env.MATTE}, metalness 0, metal/roughness map removed`);
}
const tex = root.listTextures();
await doc.transform(
  dedup(), prune(),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 88, slots: /baseColor/, resize: [BASE, BASE] }),
  textureCompress({ encoder: sharp, targetFormat: "webp", quality: 90, slots: /normal|metallicRoughness/, resize: [BASE / 2, BASE / 2] }),
  meshopt({ encoder: MeshoptEncoder, level: "medium" }),
);
await io.write(OUT, doc);
console.log(OUT, tex.length, "textures");
