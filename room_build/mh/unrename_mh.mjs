// node unrename_mh.mjs <in.glb> <out.glb> — the inverse of rename_mh.mjs: room rig names (Hips, LeftHand, ...) back to
// MakeHuman's, so a body delivered with room names (boy_g2.glb) can be the retarget's target; head_end stays
import { NodeIO } from "@gltf-transform/core";
const [,, IN, OUT] = process.argv;
const R = { root: "Hips", spine05: "Spine02", spine03: "Spine01", spine01: "Spine", neck01: "neck", head: "Head" };
for (const [s, m] of [["L", "Left"], ["R", "Right"]]) Object.assign(R, { [`clavicle.${s}`]: `${m}Shoulder`, [`upperarm01.${s}`]: `${m}Arm`,
  [`lowerarm01.${s}`]: `${m}ForeArm`, [`wrist.${s}`]: `${m}Hand`, [`upperleg01.${s}`]: `${m}UpLeg`, [`lowerleg01.${s}`]: `${m}Leg`,
  [`foot.${s}`]: `${m}Foot`, [`toe1-1.${s}`]: `${m}ToeBase` });
const inv = Object.fromEntries(Object.entries(R).map(([a, b]) => [b, a]));
const io = new NodeIO(), doc = await io.read(IN); let n = 0;
for (const node of doc.getRoot().listNodes()) { const k = node.getName(); if (inv[k]) { node.setName(inv[k]); n++; } }
await io.write(OUT, doc); console.log("unrenamed", n, "->", OUT);
