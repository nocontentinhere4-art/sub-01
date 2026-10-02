// node boy_ref.mjs [../web/room/boy.glb] [out/boy_ref.json] : the old character's skeleton at rest, in world space (metres,
// glTF axes: +y up, he faces +z). build_boy.py poses the new body into this pose, and boy_post.mjs gives the new
// skeleton these same bone frames, so every clip made for the old rig plays on the new one unchanged.
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder } from "meshoptimizer";
import * as THREE from "three";
import { palmOf, handPoints } from "./palm.mjs";
const [,, IN = "../web/room/boy.glb", OUT = "out/boy_ref.json"] = process.argv;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder});
const doc = await io.read(IN), joints = doc.getRoot().listSkins()[0].listJoints();
// the axes the clips bend about (measured over all clips: rotation from rest, in the bone's own frame); positive = flex
const HINGE = {LeftForeArm: [-0.8, 0, 0.6], RightForeArm: [-0.8, 0, -0.6], LeftLeg: [1, 0, 0], RightLeg: [1, 0, 0]};
const bones = {};
for (const j of joints) {
  const m = new THREE.Matrix4().fromArray(j.getWorldMatrix()), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  m.decompose(p, q, s);
  const b = bones[j.getName()] = {parent: j.getParentNode() && joints.includes(j.getParentNode()) ? j.getParentNode().getName() : null,
    pos: p.toArray(), quat: q.toArray(), x: new THREE.Vector3(1, 0, 0).applyQuaternion(q).toArray(),
    y: new THREE.Vector3(0, 1, 0).applyQuaternion(q).toArray(), z: new THREE.Vector3(0, 0, 1).applyQuaternion(q).toArray()};
  if (HINGE[j.getName()]) b.hinge = new THREE.Vector3(...HINGE[j.getName()]).normalize().applyQuaternion(q).toArray();
}
// the palms (world): build_boy.py rolls the new hands onto them
const prim = doc.getRoot().listMeshes()[0].listPrimitives()[0], skin = doc.getRoot().listSkins()[0];
for (const side of ["Left", "Right"]) bones[side + "Hand"].palm = palmOf(handPoints(prim, skin, side)).applyQuaternion(new THREE.Quaternion(...bones[side + "Hand"].quat)).toArray();
fs.writeFileSync(OUT, JSON.stringify({source: IN, bones}, null, 1));
console.log(`${Object.keys(bones).length} bones -> ${OUT}`);
