// A Mixamo-rigged character in the room: the character (room_build/kimodo/mixamo_glb.mjs: Mixamo's FBX as a GLB, its
// mixamorig:* skeleton of 65 bones with the fingers, the whole under one node scaled 0.01) and Mixamo clips played on it
// by bone name - the clips were recorded on this skeleton, so nothing is retargeted. Only the hips' travel is scaled,
// by the character's hip height over the clip skeleton's (a taller or shorter body covers the same steps in proportion).
//
// boy_mh.js and the page name the bones as the MakeHuman / v5 body did; the Mixamo bones get those names (NAMES), in the
// rig and in every clip's tracks alike, and the hips hang straight under the body so a Hips.position is in the body's
// frame (feet at y = 0, metres, facing +z: Mixamo's own frame), as char_v5.js does for v5.

const strip = n => n.replace(/^mixamorig\d*:?/, "");
// Mixamo -> the page's names (char_v5.js TO_MH's targets; the spine chain Hips > Spine02 > Spine01 > Spine > neck)
export const NAMES = {Hips: "Hips", Spine: "Spine02", Spine1: "Spine01", Spine2: "Spine", Neck: "neck", Head: "Head", HeadTop_End: "head_end"};
for (const [S, x] of [["Left", "L"], ["Right", "R"]]) {
  for (const b of ["Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase"]) NAMES[S + b] = S + b;
  NAMES[S + "Toe_End"] = `toe1-2.${x}`;
  ["Thumb", "Index", "Middle", "Ring", "Pinky"].forEach((f, i) => { for (let j = 1; j <= 4; j++) NAMES[`${S}Hand${f}${j}`] = `finger${i + 1}-${j}.${x}`; });
}
export const pageName = n => NAMES[strip(n)] || strip(n);
export const isMixamo = root => { let y = false; root.traverse(o => { if (o.isBone && /^mixamorig\d*:?Hips$/.test(o.name)) y = true; }); return y; };

// the hips' height over the lowest foot joint, at rest (metres, world)
function hipHeight(THREE, root) {
  root.updateMatrixWorld(true); let hips = null, low = Infinity; const v = new THREE.Vector3();
  root.traverse(o => { const n = NAMES[strip(o.name)] || o.name;
    if (n === "Hips") hips = o.getWorldPosition(new THREE.Vector3()).y;
    if (/^(Left|Right)(Foot|ToeBase)$/.test(n)) low = Math.min(low, o.getWorldPosition(v).y); });
  return hips == null || low === Infinity ? null : hips - low;
}

// the loaded character glTF (g.scene) made into the body boy_mh.js expects; returns the conversion for its clips
export function prep(THREE, g) {
  const sc = g.scene; sc.updateMatrixWorld(true);
  let hip = null; sc.traverse(o => { if (o.isBone && strip(o.name) === "Hips") hip = o; });
  if (!hip) throw new Error("char_mixamo: no mixamorig Hips");
  const par = hip.parent;
  // a Hips value in its parent's frame (the clips') -> in the body's: M = body^-1 * parent (world, at rest)
  const M = new THREE.Matrix4().copy(sc.matrixWorld).invert().multiply(par.matrixWorld);
  const mp = new THREE.Vector3(), mq = new THREE.Quaternion(), ms = new THREE.Vector3(); M.decompose(mp, mq, ms);
  const H = hipHeight(THREE, sc);
  sc.attach(hip);                                      // (world transform kept: the skin is unchanged)
  sc.traverse(o => { if (o.isBone) o.name = pageName(o.name); });
  const conv = {M, q: mq, hipH: H};
  g.animations = g.animations.map(c => fixClip(THREE, c, conv));
  return conv;
}

// a clip's skeleton (the clip's own glTF, g.scene) for its hip height; without it the clip is taken to be recorded on a
// skeleton of the character's height (Mixamo's clips for this character are)
export const clipHipHeight = (THREE, g) => g && g.scene ? hipHeight(THREE, g.scene) : null;

// a Mixamo clip for the prepared character: the tracks renamed as the bones are, the hips' translation carried into the
// body's frame and scaled by hip height (conv.hipH / srcHipH), the hips' rotation turned with it; nothing else changes
export function fixClip(THREE, clip, conv, srcHipH) {
  const k = srcHipH && conv.hipH ? conv.hipH / srcHipH : 1, M = conv.M, q = conv.q, v = new THREE.Vector3(), r = new THREE.Quaternion();
  const tracks = clip.tracks.map(t => {
    const dot = t.name.lastIndexOf("."), node = t.name.slice(0, dot), prop = t.name.slice(dot + 1), name = pageName(node) + "." + prop;
    if (pageName(node) !== "Hips" || (prop !== "position" && prop !== "quaternion")) { const c = t.clone(); c.name = name; return c; }
    const vals = t.values.slice();
    if (prop === "position") {
      // in the body's frame, then the travel about the first frame's hips scaled (its height above the floor too)
      for (let i = 0; i < vals.length; i += 3) { v.fromArray(vals, i).applyMatrix4(M); v.toArray(vals, i); }
      for (let i = 0; i < vals.length; i++) vals[i] *= k;
    } else for (let i = 0; i < vals.length; i += 4) { r.fromArray(vals, i); r.premultiply(q); r.toArray(vals, i); }
    return new t.constructor(name, t.times.slice(), vals);
  });
  return new THREE.AnimationClip(clip.name, clip.duration, tracks);
}
