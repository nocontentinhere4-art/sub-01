// node rename_mh.mjs <in.glb> <out.glb> — MakeHuman bone names -> the room page's rig names (Hips, Spine02, LeftHand, ...)
// so room.html / boy_motion.js keep working; adds head_end above Head. Fingers and twist bones keep their MakeHuman names.
import { NodeIO } from "@gltf-transform/core";
const [,, IN, OUT] = process.argv;
const R = { root: "Hips", spine05: "Spine02", spine03: "Spine01", spine01: "Spine", neck01: "neck", head: "Head" };
for (const [s, m] of [["L", "Left"], ["R", "Right"]]) Object.assign(R, { [`clavicle.${s}`]: `${m}Shoulder`, [`upperarm01.${s}`]: `${m}Arm`,
  [`lowerarm01.${s}`]: `${m}ForeArm`, [`wrist.${s}`]: `${m}Hand`, [`upperleg01.${s}`]: `${m}UpLeg`, [`lowerleg01.${s}`]: `${m}Leg`,
  [`foot.${s}`]: `${m}Foot`, [`toe1-1.${s}`]: `${m}ToeBase` });
const io = new NodeIO(), doc = await io.read(IN); let n = 0;
for (const node of doc.getRoot().listNodes()) { const k = node.getName(); if (R[k]) { node.setName(R[k]); n++; } }
const head = doc.getRoot().listNodes().find(x => x.getName() === "Head");
if (!head.listChildren().some(c => c.getName() === "head_end")) head.addChild(doc.createNode("head_end").setTranslation([0, 0.2, 0]));
await io.write(OUT, doc); console.log("renamed", n, "->", OUT);
