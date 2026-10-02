// the palm of a hand, measured on its skin: the hand's vertices in the hand bone's frame (y along the fingers). Over the
// fingers (past the thumb) the knuckle line is the widest direction across the hand and the palm's normal the thinnest;
// the normal's sign is the side the fingertips curl to. Returns the unit normal in the bone's frame.
import * as THREE from "three";
export function palmOf(pts) {
  const ymax = Math.max(...pts.map(p => p.y)), band = pts.filter(p => p.y > 0.62 * ymax && p.y < 0.8 * ymax);
  const c = band.reduce((a, p) => a.add(p), new THREE.Vector3()).divideScalar(band.length);
  let xx = 0, xz = 0, zz = 0; for (const p of band) { const dx = p.x - c.x, dz = p.z - c.z; xx += dx * dx; xz += dx * dz; zz += dz * dz; }
  const a = 0.5 * Math.atan2(2 * xz, xx - zz), minor = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
  const tips = pts.filter(p => p.y > 0.93 * ymax), ct = tips.reduce((s, p) => s.add(p), new THREE.Vector3()).divideScalar(tips.length);
  return minor.multiplyScalar(Math.sign(ct.sub(c).dot(minor)) || 1);
}
// the vertices skinned (> 90 %) to a hand and its fingers, in the hand bone's frame (the inverse bind matrix)
export function handPoints(prim, skin, side) {
  const names = skin.listJoints().map(j => j.getName()), ids = new Set(names.map((n, i) => n.startsWith(side + "Hand") ? i : -1).filter(i => i >= 0));
  const inv = new THREE.Matrix4().fromArray(skin.getInverseBindMatrices().getElement(names.indexOf(side + "Hand"), []));
  const P = prim.getAttribute("POSITION"), J = prim.getAttribute("JOINTS_0"), W = prim.getAttribute("WEIGHTS_0"), out = [], j = [], w = [], p = [];
  for (let i = 0; i < P.getCount(); i++) { J.getElement(i, j); W.getElement(i, w); let s = 0; for (let k = 0; k < 4; k++) if (ids.has(j[k])) s += w[k];
    if (s > 0.9) out.push(new THREE.Vector3(...P.getElement(i, p)).applyMatrix4(inv)); }
  return out;
}
