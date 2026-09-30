// CHARACTER stream: SUB-01's stylised figure and the baker NPC.
//
//   createCharacter(scene, assets) -> {update(dt, life), object, setAnchors(anchors), setPhoneTexture(tex),
//                                      phoneMount, phoneScreen, rig}
//   createBaker(scene, assets, anchors) -> {update(dt, life), object, setAnchors(anchors), rig}
//
// The figure is a stylised adult without a face (smooth head): it is not modelled on anyone and it is never the real
// person whose scans drive the brain model. It is a rendering of a simulation, not a person.
//
// Two rigs behind one controller:
//   1. PRIMARY: a rigged CC0 character (Quaternius) when manifest.character.url is set (the file lives in
//      web/assets/character/ on branch assets/cc0). Loaded with GLTFLoader through assets.gltf(), cloned with
//      SkeletonUtils.clone (several actors can share one file), animation clips mapped per slot by
//      manifest.character.clips (slot -> clip name) or, for unmapped slots, by name heuristics. Extra animation
//      libraries (manifest.character.animations: [url]) are retargeted by bone name. Sit / lie heights and the lying
//      direction are calibrated automatically from the clips. If idle / walk / sit / lie cannot be resolved the file is
//      rejected and the procedural rig below stays. URL override for tests: ?charGlb=/assets/character/x.glb
//   2. FALLBACK (always built first, instantly): a procedural mannequin, one SkinnedMesh with a humanoid skeleton
//      (Hips Spine Chest Neck Head, UpperArm ForeArm Hand Thumb, UpLeg LowLeg Foot) and procedural keyframed clips
//      (idle walk sit sit_desk lie lie_phone eat stand look_window, baker: serve), played with an AnimationMixer.
//
// Clip slots (life -> slot): walking -> walk; lying (or any asleep stage, once at the bed) -> lie; lying_phone ->
// lie_phone; sitting -> sit (eat when activity == "eat"); sitting_desk -> sit_desk; standing -> idle / stand (buying
// bread) / look_window (activity "window"); baker: serve when life.npc.baker.pose == "serving" else idle.
//
// World anchors (all optional; Vector3, Object3D or {x, z, y?, seatY?, topY?, heading?, rotationY?} each):
//   anchors.bed     centre of the bed; y | topY = top of the mattress (default spring plane 0.49 + 0.15);
//                   heading | rotationY turns the bed (at 0 the head end is at -z)
//   anchors.table / anchors.desk / anchors.bench   where the pelvis sits (x, z), seatY | y = seat height,
//                   heading | rotationY = direction the sitter faces (radians, 0 = +z, PI = -z)
//   anchors.window  (optional) point to face; anchors.counter / anchors.baker  baker's standing spot (+ heading)
//   Anchors may also be given under anchors.places. Missing anchors fall back to life.x / life.z and defaults.
//   Call character.setAnchors(world.anchors) once the world exists (createCharacter does not receive them); it also
//   looks at assets.anchors, scene.userData.anchors and the "world" group's userData.anchors by itself.
import * as THREE from "three";

const TAU = Math.PI * 2, D = Math.PI / 180;
const WALK_SPEED = 1.3;                 // m/s the walk clip was authored for (life.WALK_SPEED)
const HEIGHT = 1.78;                    // mannequin height in metres
const tmpV = new THREE.Vector3(), tmpV2 = new THREE.Vector3(), tmpV3 = new THREE.Vector3(), tmpM = new THREE.Matrix4();
const lerp = (a, b, k) => a + (b - a) * k;
const wrapAngle = a => Math.atan2(Math.sin(a), Math.cos(a));
const damp = (dt, rate) => 1 - Math.exp(-dt * rate);

// ============================================================================================================
// 1. Procedural mannequin
// ============================================================================================================
// [name, parent, local rest position]. All rest rotations are identity, so a clip rotation is a rotation about a world
// axis of the rest pose. Character faces +z, its left side is +x. Arms hang down in the rest pose.
const BONES = [
  ["Hips", null, [0, 0.95, 0]], ["Spine", "Hips", [0, 0.08, 0]], ["Chest", "Spine", [0, 0.22, 0]],
  ["Neck", "Chest", [0, 0.2, 0]], ["Head", "Neck", [0, 0.07, 0]],
  ["UpperArm_L", "Chest", [0.22, 0.17, 0]], ["ForeArm_L", "UpperArm_L", [0, -0.29, 0]],
  ["Hand_L", "ForeArm_L", [0, -0.26, 0]], ["Thumb_L", "Hand_L", [0, -0.05, 0.03]],
  ["UpperArm_R", "Chest", [-0.22, 0.17, 0]], ["ForeArm_R", "UpperArm_R", [0, -0.29, 0]],
  ["Hand_R", "ForeArm_R", [0, -0.26, 0]], ["Thumb_R", "Hand_R", [0, -0.05, 0.03]],
  ["UpLeg_L", "Hips", [0.095, -0.03, 0]], ["LowLeg_L", "UpLeg_L", [0, -0.42, 0]], ["Foot_L", "LowLeg_L", [0, -0.42, 0]],
  ["UpLeg_R", "Hips", [-0.095, -0.03, 0]], ["LowLeg_R", "UpLeg_R", [0, -0.42, 0]], ["Foot_R", "LowLeg_R", [0, -0.42, 0]],
];
const BONE_NAMES = BONES.map(b => b[0]);
const REST_HIPS = [0, 0.95, 0];

const STYLES = {
  sub01: { skin: 0xc9b9a8, shirt: 0xd9d6cf, pants: 0x39465b, shoes: 0x24262c, apron: null, cap: false, scale: [1, 1, 1] },
  baker: { skin: 0xb98d6f, shirt: 0x5d7489, pants: 0x4a4a4e, shoes: 0x2b2522, apron: 0xf7f3e8, cap: true, scale: [1.07, 0.97, 1.1] },
};

function buildGeometry(style) {
  const idx = Object.fromEntries(BONE_NAMES.map((n, i) => [n, i]));
  const P = [], C = [], I = [], SI = [], SW = [];
  const col = new THREE.Color();
  function vert(x, y, z, color, w) {
    P.push(x, y, z); col.set(color); C.push(col.r, col.g, col.b);
    const ws = w.slice(0, 4); let s = 0; for (const a of ws) s += a[1];
    for (let k = 0; k < 4; k++) { const a = ws[k]; SI.push(a ? idx[a[0]] : 0); SW.push(a ? a[1] / s : 0); }
    return P.length / 3 - 1;
  }
  // rings: [{c:[x,y,z], ru, rv, col, colFn?(cos, sin), w:[[bone, weight]]}], axis "y" (rings horizontal) or "z".
  function tube(rings, axis = "y", radial = 14) {
    const base = P.length / 3;
    for (const r of rings) {
      for (let j = 0; j < radial; j++) {
        const a = TAU * j / radial, cs = Math.cos(a), sn = Math.sin(a);
        const c = r.colFn ? r.colFn(cs, sn) : r.col;
        if (axis === "y") vert(r.c[0] + r.ru * cs, r.c[1], r.c[2] + r.rv * sn, c, r.w);
        else vert(r.c[0] + r.rv * sn, r.c[1] + r.ru * cs, r.c[2], c, r.w);
      }
    }
    const at = (i, j) => base + i * radial + (j % radial);
    for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < radial; j++) {
      const a = at(i, j), b = at(i, j + 1), c = at(i + 1, j), d = at(i + 1, j + 1);
      I.push(a, c, b, b, c, d);
    }
    for (const [ri, top] of [[0, false], [rings.length - 1, true]]) {
      const r = rings[ri], cv = vert(r.c[0], r.c[1], r.c[2], r.colFn ? r.colFn(0, 0) : r.col, r.w);
      for (let j = 0; j < radial; j++) { const a = at(ri, j), b = at(ri, j + 1); if (top) I.push(cv, b, a); else I.push(cv, a, b); }
    }
  }
  function ellipsoid(c, ru, rv, rz, color, w, axis = "y", n = 9) {
    // rz = radius along the axis, (ru, rv) = cross-section radii
    const rings = [];
    for (let i = 0; i <= n; i++) {
      const phi = Math.PI * (0.06 + 0.88 * i / n), s = Math.sin(phi), k = Math.cos(phi);
      rings.push({ c: axis === "y" ? [c[0], c[1] - rz * k, c[2]] : [c[0], c[1], c[2] + rz * k], ru: ru * s, rv: rv * s, col: color, w });
    }
    tube(rings, axis, 12);
  }
  const { skin, shirt, pants, shoes, apron } = style;
  const front = (cs, sn) => sn > 0.25;
  // torso; the baker's apron is painted on the front half (vertex colour)
  const bibFn = colour => (apron ? (cs, sn) => (front(cs, sn) ? apron : colour) : undefined);
  const tw = (y, ru, rv, colour, w, bib) => ({ c: [0, y, 0], ru, rv, col: colour, w, colFn: bib ? bibFn(colour) : undefined });
  tube([
    tw(0.86, 0.125, 0.095, pants, [["Hips", 1]]), tw(0.895, 0.165, 0.105, pants, [["Hips", 1]]),
    tw(0.9, 0.17, 0.11, shirt, [["Hips", 1]]), tw(1.0, 0.165, 0.105, shirt, [["Hips", 0.5], ["Spine", 0.5]], true),
    tw(1.1, 0.15, 0.1, shirt, [["Spine", 1]], true), tw(1.22, 0.168, 0.11, shirt, [["Spine", 0.5], ["Chest", 0.5]], true),
    tw(1.32, 0.19, 0.115, shirt, [["Chest", 1]], true), tw(1.4, 0.2, 0.1, shirt, [["Chest", 1]]),
    tw(1.44, 0.13, 0.075, shirt, [["Chest", 1]]), tw(1.465, 0.05, 0.05, shirt, [["Chest", 1]]),
  ]);
  tube([ // neck
    { c: [0, 1.4, 0.005], ru: 0.07, rv: 0.07, col: skin, w: [["Chest", 1]] },
    { c: [0, 1.45, 0.008], ru: 0.06, rv: 0.06, col: skin, w: [["Neck", 1]] },
    { c: [0, 1.52, 0.012], ru: 0.055, rv: 0.055, col: skin, w: [["Neck", 0.5], ["Head", 0.5]] },
    { c: [0, 1.56, 0.012], ru: 0.055, rv: 0.055, col: skin, w: [["Head", 1]] },
  ]);
  ellipsoid([0, 1.65, 0.012], 0.088, 0.102, 0.116, skin, [["Head", 1]]);      // smooth egg head: no face
  for (const [s, L] of [[1, "L"], [-1, "R"]]) {
    const lw = (y, r, colour, w, bib) => ({ c: [0.095 * s, y, 0], ru: r, rv: r * 1.02, col: colour, w, colFn: bib ? bibFn(colour) : undefined });
    const U = `UpLeg_${L}`, Lo = `LowLeg_${L}`;
    tube([
      lw(0.95, 0.09, pants, [[U, 1]]), lw(0.93, 0.105, pants, [[U, 1]]), lw(0.85, 0.1, pants, [[U, 1]], true),
      lw(0.7, 0.088, pants, [[U, 1]]), lw(0.56, 0.073, pants, [[U, 0.75], [Lo, 0.25]]), lw(0.5, 0.066, pants, [[U, 0.5], [Lo, 0.5]]),
      lw(0.44, 0.06, pants, [[U, 0.25], [Lo, 0.75]]), lw(0.3, 0.055, pants, [[Lo, 1]]), lw(0.14, 0.046, pants, [[Lo, 1]]), lw(0.1, 0.042, pants, [[Lo, 1]]),
    ]);
    ellipsoid([0.095 * s, 0.05, 0.05], 0.05, 0.055, 0.135, shoes, [[`Foot_${L}`, 1]], "z", 8);
    const aw = (y, r, colour, w) => ({ c: [0.22 * s, y, 0], ru: r, rv: r, col: colour, w });
    const A = `UpperArm_${L}`, F = `ForeArm_${L}`;
    tube([
      aw(1.47, 0.03, shirt, [[A, 1]]), aw(1.44, 0.056, shirt, [[A, 1]]), aw(1.34, 0.053, shirt, [[A, 1]]), aw(1.27, 0.05, shirt, [[A, 1]]),
      aw(1.265, 0.046, skin, [[A, 1]]), aw(1.17, 0.042, skin, [[A, 0.9], [F, 0.1]]), aw(1.13, 0.04, skin, [[A, 0.5], [F, 0.5]]),
      aw(1.09, 0.038, skin, [[A, 0.1], [F, 0.9]]), aw(0.98, 0.036, skin, [[F, 1]]), aw(0.89, 0.028, skin, [[F, 1]]),
    ]);
    ellipsoid([0.22 * s, 0.795, 0.004], 0.03, 0.042, 0.088, skin, [[`Hand_${L}`, 1]]);
    ellipsoid([0.22 * s, 0.775, 0.045], 0.014, 0.014, 0.05, skin, [[`Thumb_${L}`, 1]]);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(C, 3));
  g.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(SI, 4));
  g.setAttribute("skinWeight", new THREE.Float32BufferAttribute(SW, 4));
  g.setIndex(I);
  g.computeVertexNormals();
  return g;
}

// --------------------------------------------------------------------------------------------------------------
// procedural clips. A pose function maps the loop phase ph in [0,1) to {Bone: [rx, ry, rz] degrees (Euler XYZ),
// pos: [x, y, z] (Hips position)}. Bones left out stay at rest. Rotation about x: negative swings a hanging limb
// FORWARD (+z), positive bends a knee / moves a foot's toes down; positive spine / head x leans forward; about z:
// positive moves the left (+x) limb outward, negative the right one.
// --------------------------------------------------------------------------------------------------------------
const S = x => Math.sin(TAU * x), Co = x => Math.cos(TAU * x);
const relu = x => Math.max(0, x);

function walkPose(ph) {
  const a = TAU * ph, p = { pos: [0, 0.913 + 0.037 * Math.cos(2 * a), 0] };
  p.Hips = [1.5 * Math.cos(2 * a) + 2, 5 * Math.sin(a), 2 * Math.sin(a)];
  p.Spine = [2, -3.5 * Math.sin(a), -1.2 * Math.sin(a)]; p.Chest = [1.5, -4 * Math.sin(a), 0];
  p.Neck = [-1, 3 * Math.sin(a), 0]; p.Head = [-2, 4 * Math.sin(a), 0];
  for (const [L, ph0, s] of [["L", 0, 1], ["R", Math.PI, -1]]) {
    const b = a + ph0, th = -24 * Math.sin(b), kn = 6 + 46 * Math.pow(relu(Math.cos(b)), 1.5);
    const foot = -(th + kn) - 10 * Math.pow(relu(Math.sin(b)), 2) + 18 * Math.pow(relu(-Math.sin(b)), 2);
    p["UpLeg_" + L] = [th, 0, 1.5 * s]; p["LowLeg_" + L] = [kn, 0, 0]; p["Foot_" + L] = [foot, 0, 0];
    const arm = 20 * Math.sin(b), elbow = -(16 + 14 * relu(-Math.sin(b)));
    p["UpperArm_" + L] = [arm, 0, 5 * s]; p["ForeArm_" + L] = [elbow, 0, 0]; p["Hand_" + L] = [0, 0, 0];
  }
  return p;
}
function standBase(ph, o = {}) {
  const br = S(ph), sway = S(ph), look = o.look ?? 5 * S(ph);
  const p = { pos: [0.004 * sway, REST_HIPS[1] - 0.004 * (0.5 - 0.5 * Co(ph * 2)), 0] };
  p.Hips = [0, 2 * sway, 1.4 * sway]; p.Spine = [0.6 * br, 0, -0.8 * sway]; p.Chest = [1.3 * br, 0, 0];
  p.Neck = [1, look, 0]; p.Head = [2 * S(ph * 2), look * 0.8, 0];
  p.UpLeg_L = [0, 2, 2]; p.UpLeg_R = [0, -2, -1]; p.LowLeg_L = [2, 0, 0]; p.LowLeg_R = [1, 0, 0];
  p.Foot_L = [-2, 4, 0]; p.Foot_R = [-1, -4, 0];
  p.UpperArm_L = [-3, 0, 6]; p.UpperArm_R = [-3, 0, -6]; p.ForeArm_L = [-12, 0, 0]; p.ForeArm_R = [-12, 0, 0];
  p.Thumb_L = [12, 0, 0]; p.Thumb_R = [12, 0, 0];
  return p;
}
const seatedLegs = p => {
  for (const [L, s] of [["L", 1], ["R", -1]]) { p["UpLeg_" + L] = [-82, 0, 5 * s]; p["LowLeg_" + L] = [84, 0, 0]; p["Foot_" + L] = [-2, 4 * s, 0]; }
};
const POSES = {
  idle: ph => standBase(ph),
  walk: walkPose,
  stand(ph) {      // standing at a counter, hands in front, small nods: buying bread
    const p = standBase(ph, { look: 3 * S(ph) }), br = S(ph);
    p.UpperArm_L = [-18, 0, 4]; p.ForeArm_L = [-52 - 3 * br, 0, 0]; p.Hand_L = [0, 0, 6];
    p.UpperArm_R = [-16, 0, -4]; p.ForeArm_R = [-46 - 3 * br, 0, 0];
    p.Head[0] = 4 + 3 * S(ph * 2); return p;
  },
  look_window(ph) {  // stands, weight on one leg, one hand to the chin, head drifts slowly up and across
    const p = standBase(ph, { look: 14 * S(ph) }), br = S(ph);
    p.Hips = [0, 4, 3 + br]; p.UpLeg_L = [0, 0, 3]; p.UpLeg_R = [-4, 0, -4]; p.LowLeg_R = [6, 0, 0];
    p.UpperArm_R = [-42, 0, -6]; p.ForeArm_R = [-112 - 2 * br, 0, 0]; p.Hand_R = [-12, 0, 0];
    p.UpperArm_L = [-28, 0, -12]; p.ForeArm_L = [-92, 0, 0]; p.Hand_L = [0, 0, 8];
    p.Neck = [-3 - 2 * S(ph * 2), 14 * S(ph), 0]; p.Head = [-4 - 3 * S(ph * 2), 6 * S(ph), 2]; return p;
  },
  sit(ph) {        // on a bench / chair, hands resting on the thighs, slow look around
    const br = S(ph), p = { pos: [0, 0.135, -0.03] };
    p.Hips = [0, 0, 0]; p.Spine = [2 + 0.5 * br, 0, 0]; p.Chest = [3 + 1.2 * br, 0, 0];
    p.Neck = [2, 12 * S(ph), 0]; p.Head = [3 + 2 * S(ph * 2), 10 * S(ph), 0];
    seatedLegs(p);
    for (const [L, s] of [["L", 1], ["R", -1]]) { p["UpperArm_" + L] = [-8, 0, 7 * s]; p["ForeArm_" + L] = [-62, 0, 0]; p["Thumb_" + L] = [14, 0, 0]; }
    return p;
  },
  sit_desk(ph) {   // leaning to the desk, typing, eyes drift across the screen
    const p = { pos: [0, 0.135, -0.03] };
    p.Hips = [0, 0, 0]; p.Spine = [7, 0, 0]; p.Chest = [6, 0, 0]; p.Neck = [9, 6 * S(ph), 0]; p.Head = [7 + 1.5 * S(ph * 3), 8 * S(ph * 2), 0];
    seatedLegs(p);
    for (const [L, s, o] of [["L", 1, 0], ["R", -1, 0.5]]) {
      const t = relu(S(ph * 18 + o));
      p["UpperArm_" + L] = [-30, 0, 5 * s]; p["ForeArm_" + L] = [-46 - 3 * t, 0, 0]; p["Hand_" + L] = [-6 + 5 * t, 0, 0]; p["Thumb_" + L] = [18 + 10 * t, 0, 0];
    }
    return p;
  },
  eat(ph) {        // sitting at the low table, a piece of bread to the mouth and back
    const cyc = ph * 2 % 1;      // two bites per loop
    const up = Math.sin(Math.PI * Math.min(1, Math.max(0, (cyc - 0.05) / 0.55))) ** 0.8; // 0 at rest, 1 at the mouth
    const hold = cyc > 0.33 && cyc < 0.55 ? 1 : 0, chew = hold * 2 * Math.abs(S(ph * 12));
    const p = { pos: [0, 0.135, -0.03] };
    p.Hips = [0, 0, 0]; p.Spine = [8 - 3 * up, 0, 0]; p.Chest = [9 - 3 * up, 0, 0]; p.Neck = [6 - 2 * up + chew, 0, 0]; p.Head = [8 - 3 * up + chew, 0, 0];
    seatedLegs(p);
    p.UpperArm_R = [lerp(-14, -38, up), 0, -7]; p.ForeArm_R = [lerp(-64, -128, up), 0, 0]; p.Hand_R = [lerp(0, -18, up), 0, 0];
    p.UpperArm_L = [-16, 0, 4]; p.ForeArm_L = [-70, 0, 0];
    return p;
  },
  lie(ph) {        // on the back in bed, slow breathing
    const br = S(ph), p = { pos: [0, 0.112, 0.08] };
    p.Hips = [-90, 0, 0]; p.Spine = [0.6 * br, 0, 0]; p.Chest = [1.6 * br, 0, 0]; p.Neck = [4, 3 * S(ph), 0]; p.Head = [6, 0, -4];
    for (const [L, s] of [["L", 1], ["R", -1]]) {
      p["UpLeg_" + L] = [-3, 4 * s, 4 * s]; p["LowLeg_" + L] = [4, 0, 0]; p["Foot_" + L] = [16, 8 * s, 0];
      p["UpperArm_" + L] = [-4, 0, 9 * s]; p["ForeArm_" + L] = [-12, 0, 0]; p["Thumb_" + L] = [14, 0, 0];
    }
    p.UpperArm_L = [-10, 0, 6]; p.ForeArm_L = [-38, 0, 0]; p.Hand_L = [-5, 0, 0];   // a hand on the belly
    return p;
  },
  lie_phone(ph) {  // propped up on pillows, one knee up, phone held above the face, thumb scrolling
    const br = S(ph), flick = relu(S(ph * 9)), p = { pos: [0, 0.112, 0.2] };
    p.Hips = [-90, 0, 0]; p.Spine = [14, 0, 0]; p.Chest = [18 + br, 0, 0]; p.Neck = [14, 0, 0]; p.Head = [14 + 1.5 * S(ph * 2), 0, 0];
    p.UpLeg_L = [-52, 0, 8]; p.LowLeg_L = [66, 0, 0]; p.Foot_L = [-10, 0, 0];
    p.UpLeg_R = [-4, 0, -6]; p.LowLeg_R = [6, 0, 0]; p.Foot_R = [16, -8, 0];
    p.UpperArm_R = [-18, 0, -16]; p.ForeArm_R = [-100, 0, 0]; p.Hand_R = [-24 + 1.5 * S(ph * 4), 0, 0]; p.Thumb_R = [-8 + 30 * flick, 0, 0];
    p.UpperArm_L = [-14, 0, 10]; p.ForeArm_L = [-26, 0, 0];
    return p;
  },
  serve(ph) {      // baker behind the counter: reaches forward with a paper bag, nods, pulls back
    const t = ph * 3 % 1, out = Math.sin(Math.PI * Math.min(1, Math.max(0, (t - 0.1) / 0.8))) ** 0.7;
    const p = standBase(ph, { look: 4 * S(ph * 3) });
    p.Spine = [4 + 3 * out, 0, 0]; p.Chest = [3 + 3 * out, 0, 0]; p.Head = [3 + 7 * out, 2 * S(ph * 3), 0]; p.Neck = [2 + 4 * out, 0, 0];
    p.UpperArm_R = [lerp(-28, -70, out), 0, -6]; p.ForeArm_R = [lerp(-56, -22, out), 0, 0];
    p.UpperArm_L = [lerp(-28, -62, out), 0, 6]; p.ForeArm_L = [lerp(-56, -30, out), 0, 0];
    return p;
  },
  baker_idle(ph) { // behind the counter, hands resting on it, looks toward the door now and then
    const p = standBase(ph, { look: 11 * S(ph) }), br = S(ph);
    p.UpperArm_L = [-26, 0, 6]; p.ForeArm_L = [-48 - 2 * br, 0, 0]; p.UpperArm_R = [-26, 0, -6]; p.ForeArm_R = [-48 - 2 * br, 0, 0];
    p.Spine = [5 + 0.6 * br, 0, 0]; p.Chest = [3 + 1.2 * br, 0, 0]; p.Head = [4 + 2 * S(ph * 2), 8 * S(ph), 0];
    return p;
  },
};
const CLIP_SPEC = {   // name -> [duration seconds, samples]
  idle: [4.5, 24], walk: [1.2, 24], stand: [4, 24], look_window: [8, 32], sit: [6, 24], sit_desk: [6, 36],
  eat: [7, 42], lie: [5.5, 24], lie_phone: [6, 36], serve: [3.6, 36], baker_idle: [5, 24],
};

let clipCache = null;
function proceduralClips() {
  if (clipCache) return clipCache;
  const e = new THREE.Euler(), q = new THREE.Quaternion();
  clipCache = {};
  for (const [name, [dur, n]] of Object.entries(CLIP_SPEC)) {
    const times = [], rot = {}, pos = [];
    BONE_NAMES.forEach(b => { rot[b] = []; });
    for (let i = 0; i <= n; i++) {
      const p = POSES[name](i / n);
      times.push(dur * i / n);
      for (const b of BONE_NAMES) {
        const r = p[b] || [0, 0, 0];
        q.setFromEuler(e.set(r[0] * D, r[1] * D, r[2] * D, "XYZ"));
        rot[b].push(q.x, q.y, q.z, q.w);
      }
      pos.push(...(p.pos || REST_HIPS));
    }
    const tracks = BONE_NAMES.map(b => new THREE.QuaternionKeyframeTrack(`${b}.quaternion`, times, rot[b]));
    tracks.push(new THREE.VectorKeyframeTrack("Hips.position", times, pos));
    clipCache[name] = new THREE.AnimationClip(name, dur, tracks);
  }
  return clipCache;
}

// props
function breadProp() {      // small loaf / roll
  const m = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 8), new THREE.MeshStandardMaterial({ color: 0xc98b43, roughness: 0.9 }));
  m.scale.set(1.5, 0.75, 0.9); m.castShadow = true; return m;
}
function bagProp() {        // paper bag with a baguette poking out
  const g = new THREE.Group();
  const bag = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.2, 0.08), new THREE.MeshStandardMaterial({ color: 0xc9a173, roughness: 0.95 }));
  const loaf = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.26, 8), new THREE.MeshStandardMaterial({ color: 0xc58a3e, roughness: 0.9 }));
  loaf.position.set(0.02, 0.17, 0); loaf.rotation.z = -0.25; bag.castShadow = loaf.castShadow = true;
  g.add(bag, loaf); return g;
}
function labelTexture(text, bg, fg, w = 256, h = 64, font = "bold 36px Menlo, Consolas, monospace") {
  const c = document.createElement("canvas"); c.width = w; c.height = h; const x = c.getContext("2d");
  x.fillStyle = bg; if (x.roundRect) { x.beginPath(); x.roundRect(0, 0, w, h, 14); x.fill(); } else x.fillRect(0, 0, w, h);
  x.fillStyle = fg; x.font = font; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(text, w / 2, h / 2 + 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

function buildMannequin(styleName) {
  const style = STYLES[styleName];
  const root = new THREE.Group(); root.name = styleName + "-rig";
  const bones = {}; const list = [];
  for (const [name, parent, pos] of BONES) {
    const b = new THREE.Bone(); b.name = name; b.position.set(...pos); bones[name] = b; list.push(b);
    (parent ? bones[parent] : root).add(b);
  }
  root.updateMatrixWorld(true);
  const skeleton = new THREE.Skeleton(list);
  const mesh = new THREE.SkinnedMesh(buildGeometry(style), new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.82, metalness: 0 }));
  mesh.name = styleName + "-body"; mesh.frustumCulled = false; mesh.castShadow = true; mesh.receiveShadow = true;
  root.add(mesh); mesh.bind(skeleton);
  root.scale.set(...style.scale);
  const clips = proceduralClips();
  const mixer = new THREE.AnimationMixer(root);
  const actions = {};
  for (const [slot, clip] of Object.entries(clips)) actions[slot] = mixer.clipAction(clip);
  if (style.cap) {
    const cap = new THREE.Group();
    const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 });
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.098, 0.1, 0.07, 14), m); band.position.y = 0.2;
    const puff = new THREE.Mesh(new THREE.SphereGeometry(0.115, 14, 10), m); puff.scale.set(1, 0.85, 1); puff.position.y = 0.3;
    band.castShadow = puff.castShadow = true; cap.add(band, puff); bones.Head.add(cap);
  }
  if (styleName === "sub01") {   // little SUB-01 badge on the chest (readable up close; the floating tag is the main one)
    const badge = new THREE.Mesh(new THREE.PlaneGeometry(0.1, 0.028), new THREE.MeshBasicMaterial({ map: labelTexture("SUB-01", "#ff6a00", "#0a0a0a", 256, 72, "bold 44px Menlo, Consolas, monospace") }));
    badge.position.set(0.075, 0.06, 0.118); badge.rotation.x = -0.06; badge.name = "chest-badge"; bones.Chest.add(badge);
  }
  const handR = bones.Hand_R, handL = bones.Hand_L;
  const bread = breadProp(); bread.position.set(0, -0.11, 0.045); bread.rotation.set(0, 0, Math.PI / 2 + 0.3); bread.visible = false; handR.add(bread);
  const bag = bagProp(); bag.position.set(0, -0.14, 0.04); bag.visible = false; handL.add(bag);
  return {
    kind: "mannequin", root, mixer, actions, bones: { hips: bones.Hips, head: bones.Head, chest: bones.Chest, handR, handL },
    handOffset: new THREE.Vector3(0, -0.09, 0.03), props: { bread, bag }, calib: null, skinned: mesh,
    resolve: s => (actions[s] ? s : null),
  };
}

// ============================================================================================================
// 2. Rigged CC0 character (Quaternius): loader, clip mapping, calibration
// ============================================================================================================
const SLOTS = ["idle", "walk", "sit", "sit_desk", "lie", "lie_phone", "eat", "stand", "look_window", "serve"];
const SLOT_FALLBACK = { sit_desk: ["sit"], eat: ["sit"], lie_phone: ["lie"], stand: ["idle"], look_window: ["idle"], serve: ["stand", "idle"], baker_idle: ["idle"] };
const NAME_RULES = {    // first clip whose name matches (case-insensitive) wins; rules go from specific to generic
  idle: [/^idle[_ -]?loop$/, /^idle/, /idle/],
  walk: [/^walk[_ -]?(fwd[_ -]?)?loop$/, /^walk(?!.*(back|left|right|carry|injured|formal))/, /walk/],
  sit: [/sit.*idle|idle.*sit/, /^sit(ting)?[_ -]?loop/, /^sit(ting)?(?!.*(enter|exit|stand|up|down))/],
  sit_desk: [/sit.*(type|desk|work|laptop|table)/, /type|typing/],
  lie: [/^(lie|lay|laying|lying)[_ -]?idle/, /^sleep/, /(lie|lay|sleep|bed)/],
  lie_phone: [/(lie|lay).*(phone|scroll)/, /phone/],
  eat: [/eat|drink|consume/],
  stand: [/^stand(ing)?[_ -]?(idle|loop)/, /talk/],
  look_window: [/look|gaze|lean|think|ponder/],
  serve: [/serve|give|hand[_ -]?over|offer|wave|talk/],
};
const norm = s => String(s).toLowerCase().replace(/^mixamorig[:_]?/, "").replace(/[^a-z0-9]/g, "");

function resolveSlots(clipNames, mapping = {}) {
  const out = {};
  for (const slot of SLOTS) {
    const explicit = mapping[slot];
    if (explicit && clipNames.includes(explicit)) { out[slot] = explicit; continue; }
    for (const re of NAME_RULES[slot]) { const hit = clipNames.find(n => re.test(n.toLowerCase())); if (hit) { out[slot] = hit; break; } }
  }
  for (const [slot, alts] of Object.entries(SLOT_FALLBACK)) if (!out[slot]) { const a = alts.find(x => out[x]); if (a) out[slot] = out[a]; }
  return out;
}
const findBone = (root, res) => { let f = null; root.traverse(o => { if (!f && o.isBone && res.some(r => r.test(o.name))) f = o; }); return f; };

// clone the loaded glTF for one actor and build a rig with the same shape as the mannequin's
async function buildGltfRig(assets, cfg, styleName, log) {
  const gltf = await assets.gltf(cfg.url);
  if (!gltf) return null;
  const { clone } = await import("three/addons/utils/SkeletonUtils.js");
  const extras = (await Promise.all((cfg.animations || []).map(u => assets.gltf(u)))).filter(Boolean);
  const root = clone(gltf.scene);
  root.name = styleName + "-glb";
  const nodeNames = new Map(); root.traverse(o => { if (o.name) nodeNames.set(norm(o.name), o.name); });
  const clips = new Map();
  for (const g of [gltf, ...extras]) for (const c of g.animations || []) {
    if (clips.has(c.name)) continue;
    const cc = c.clone();
    cc.tracks = cc.tracks.filter(t => {       // retarget by bone name; drop tracks whose bone does not exist
      const { nodeName, propertyName } = THREE.PropertyBinding.parseTrackName(t.name);
      if (root.getObjectByName(nodeName)) return true;
      const alt = nodeNames.get(norm(nodeName));
      if (!alt) return false;
      t.name = `${alt}.${propertyName}`; return true;
    });
    if (cc.tracks.length) clips.set(c.name, cc);
  }
  const names = [...clips.keys()];
  const slots = resolveSlots(names, cfg.clips || {});
  const need = ["idle", "walk", "sit", "lie"].filter(s => !slots[s]);
  if (need.length) { log(`character file rejected: no clip for ${need.join(", ")} (clips: ${names.join(", ") || "none"})`); return null; }
  const mixer = new THREE.AnimationMixer(root);
  const actions = {};
  for (const [slot, name] of Object.entries(slots)) actions[slot] = mixer.clipAction(clips.get(name));
  actions.baker_idle = actions.idle; actions.serve = actions.serve || actions.stand || actions.idle;
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; } });
  if (styleName === "baker") {       // light tint so the baker is told apart from SUB-01 when the same file is used
    root.traverse(o => { if (o.isMesh && o.material) { o.material = o.material.clone(); o.material.color?.multiply(new THREE.Color(0xf2dcc8)); } });
  }
  const bones = {
    hips: findBone(root, [/pelvis/i, /hips/i]) || findBone(root, [/^root$/i]) || findBone(root, [/./]),
    head: findBone(root, [/^head$/i, /head(?!.*end)/i]), chest: findBone(root, [/chest/i, /spine[_.]?0?3/i, /spine[_.]?0?2/i, /spine/i]),
    handR: findBone(root, [/(hand|wrist)[_.]?r(ight)?$/i, /right[_ ]?hand/i, /r[_.]?hand/i]),
    handL: findBone(root, [/(hand|wrist)[_.]?l(eft)?$/i, /left[_ ]?hand/i, /l[_.]?hand/i]),
  };
  if (!bones.hips || !bones.head) { log("character file rejected: no hips / head bone found"); return null; }
  // scale to ~1.78 m (Quaternius characters already are; only correct big deviations)
  actions.idle.reset().play(); mixer.update(0); root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root, true);
  const h = box.max.y - box.min.y;
  if (h > 0.2 && Math.abs(h - HEIGHT) / HEIGHT > 0.12) root.scale.multiplyScalar(HEIGHT / h);
  const wrap = new THREE.Group(); wrap.add(root);
  const rig = {
    kind: "gltf", root: wrap, mixer, actions, bones, handOffset: new THREE.Vector3(), props: {}, calib: {}, skinned: null,
    resolve: s => (actions[s] ? s : null), slots,
  };
  calibrate(rig);
  return rig;
}

// Where does the pelvis sit in each clip? Derive the vertical offset (so sitting / lying poses rest on the seat / the
// mattress), the horizontal centring and the yaw that makes the lying body point its head toward -z.
const CAL_TARGET = { sit: [0.12, -0.03], sit_desk: [0.12, -0.03], eat: [0.12, -0.03], lie: [0.12, 0.08], lie_phone: [0.12, 0.2] };
function calibrate(rig) {
  const { mixer, actions, bones, root: wrap } = rig;
  for (const slot of Object.keys(CAL_TARGET)) {
    const act = actions[slot]; if (!act) continue;
    mixer.stopAllAction(); act.reset().setEffectiveWeight(1).play(); act.time = 0; mixer.update(0);
    wrap.updateMatrixWorld(true);
    const hp = wrap.worldToLocal(bones.hips.getWorldPosition(new THREE.Vector3()));
    const hd = wrap.worldToLocal(bones.head.getWorldPosition(new THREE.Vector3()));
    let yaw = 0;
    if (slot.startsWith("lie")) { const d = hd.clone().sub(hp); if (Math.hypot(d.x, d.z) > 0.25) yaw = wrapAngle(Math.PI - Math.atan2(d.x, d.z)); }
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const rx = c * hp.x + s * hp.z, rz = -s * hp.x + c * hp.z;   // hips position after rotating the holder by yaw about y
    const [ty, tz] = CAL_TARGET[slot];
    rig.calib[slot] = { y: ty - hp.y, x: -rx, z: tz - rz, yaw };
  }
  mixer.stopAllAction();
}

// ============================================================================================================
// 3. Actor: position / heading smoothing, pose selection, crossfades, props, tag
// ============================================================================================================
const SURFACE = { sit: "seat", sit_desk: "seat", eat: "seat", lie: "bed", lie_phone: "bed" };
const FADE = { default: 0.4, walk: 0.35, lie: 0.5, lie_phone: 0.5 };

function readAnchor(a) {
  if (!a) return null;
  if (a.isObject3D) {
    const p = a.getWorldPosition(new THREE.Vector3()), d = a.getWorldDirection(new THREE.Vector3());
    return { x: p.x, y: p.y, z: p.z, heading: Math.atan2(d.x, d.z), hasY: false };
  }
  if (a.isVector3) return { x: a.x, y: a.y, z: a.z, heading: undefined, hasY: false };
  const pos = a.position || a.pos || a, seat = a.seat || pos;
  const arr = Array.isArray(seat);
  const x = arr ? seat[0] : seat.x, z = arr ? seat[2] : seat.z;
  const y = a.seatY ?? a.topY ?? a.surfaceY ?? a.y;
  return { x, z, y, hasY: y != null, heading: a.heading ?? a.rotationY ?? a.facing };
}

function createActor(scene, rigFactory, { name, tag }) {
  const group = new THREE.Group(); group.name = name;
  const holder = new THREE.Group(); group.add(holder);       // holds the rig; calibrated offset / yaw for loaded rigs
  scene.add(group);
  let rig = rigFactory();
  holder.add(rig.root);
  const st = { x: 0, z: 0, y: 0, h: 0, init: false, speed: 0, clip: null, action: null, hx: 0, hy: 0, hz: 0, hyaw: 0, time: 0 };

  let tagSprite = null;      // floating tag above the head
  if (tag) {
    tagSprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: labelTexture(tag, "#ff6a00", "#0a0a0a", 320, 80, "bold 46px Menlo, Consolas, monospace"),
      transparent: true, depthWrite: false, fog: false, toneMapped: false }));
    tagSprite.scale.set(0.5, 0.125, 1); tagSprite.name = "sub01-tag"; tagSprite.renderOrder = 5; scene.add(tagSprite);
    // small up close, grows with the camera distance (up to 2.4x) so it stays readable from the follow camera
    tagSprite.onBeforeRender = (renderer, sc, camera) => {
      const k = THREE.MathUtils.clamp(camera.position.distanceTo(tagSprite.position) / 8, 1, 2.4);
      tagSprite.scale.set(0.5 * k, 0.125 * k, 1); tagSprite.updateMatrixWorld();
    };
  }
  // phone prop (SUB-01): a mount that tracks the right hand and faces the head; the phone stream puts its texture on phoneScreen
  let phoneMount = null, phoneScreen = null, zzz = null;
  if (name === "sub01") {
    phoneMount = new THREE.Group(); phoneMount.name = "phoneMount";
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.078, 0.15, 0.009), new THREE.MeshStandardMaterial({ color: 0x101114, roughness: 0.4, metalness: 0.3 }));
    phoneScreen = new THREE.Mesh(new THREE.PlaneGeometry(0.07, 0.12), new THREE.MeshBasicMaterial({ color: 0x1b2a44 }));
    phoneScreen.position.z = 0.0052; phoneScreen.name = "phoneScreen"; body.castShadow = true;
    phoneMount.add(body, phoneScreen); phoneMount.visible = false; group.add(phoneMount);
    zzz = new THREE.Sprite(new THREE.SpriteMaterial({ map: labelTexture("z z z", "rgba(0,0,0,0)", "#bcd0ff", 192, 64, "bold 40px Menlo, Consolas, monospace"), transparent: true, depthWrite: false }));
    zzz.scale.set(0.42, 0.14, 1); zzz.visible = false; scene.add(zzz);
  }

  function setRig(next) {
    if (!next) return;
    rig.mixer.stopAllAction(); holder.remove(rig.root);
    rig = next; holder.add(rig.root); st.clip = null; st.action = null;     // the next update() starts the right clip
  }
  function playClip(slot, fade) {
    const act = rig.actions[rig.resolve(slot) || "idle"];
    if (!act) return;
    st.clip = slot;
    if (act === st.action) return;
    act.reset().setEffectiveWeight(1).setLoop(THREE.LoopRepeat, Infinity).play();
    if (st.action && fade > 0) act.crossFadeFrom(st.action, fade, false);
    st.action = act;
  }

  function update(dt, tgt) {
    // tgt = {x, z, heading, y, clip, bread, walking, calibSlot, asleep, hide, snap}
    st.time += dt;
    if (tgt.hide) { group.visible = false; if (tagSprite) tagSprite.visible = false; if (zzz) zzz.visible = false; return; }
    group.visible = true;
    if (!st.init || tgt.snap) { st.x = tgt.x; st.z = tgt.z; st.h = tgt.heading; st.y = tgt.y; st.init = true; st.speed = 0; }
    // ticks arrive at ~20 Hz: dead-reckon between them with the measured velocity so walking is steady, then glide
    // toward that point (no teleport jitter); jumps > 3 m snap. Speed is measured from the actual motion.
    let tx = tgt.x, tz = tgt.z;
    if (st.rawX === undefined || tgt.snap) { st.rawX = tx; st.rawZ = tz; st.rawT = st.time; st.vx = st.vz = 0; }
    if (Math.hypot(tx - st.rawX, tz - st.rawZ) > 1e-4) {
      const gap = Math.min(0.25, Math.max(0.015, st.time - st.rawT)), jump = Math.hypot(tx - st.rawX, tz - st.rawZ);
      if (tgt.walking && jump < 0.6) { st.vx = lerp(st.vx, (tx - st.rawX) / gap, 0.35); st.vz = lerp(st.vz, (tz - st.rawZ) / gap, 0.35); } else { st.vx = st.vz = 0; }
      st.rawX = tx; st.rawZ = tz; st.rawT = st.time;
    }
    if (tgt.walking) { const a = Math.min(0.12, st.time - st.rawT); tx += st.vx * a; tz += st.vz * a; } else { st.vx = st.vz = 0; }
    const dx = tx - st.x, dz = tz - st.z, dist = Math.hypot(dx, dz), px = st.x, pz = st.z;
    if (dist > 3) { st.x = tx; st.z = tz; } else { const k = damp(dt, tgt.walking ? 14 : 7); st.x += dx * k; st.z += dz * k; }
    const moved = dt > 0 ? Math.hypot(st.x - px, st.z - pz) / dt : 0;
    st.speed = lerp(st.speed, dist > 3 ? 0 : moved, damp(dt, 6));
    st.y += (tgt.y - st.y) * damp(dt, 8);
    st.h += wrapAngle(tgt.heading - st.h) * damp(dt, tgt.walking ? 11 : 7);
    group.position.set(st.x, st.y, st.z); group.rotation.y = st.h;

    // calibrated holder offset for loaded rigs
    const cal = rig.calib && tgt.calibSlot && rig.calib[tgt.calibSlot], kc = damp(dt, 7);
    st.hx = lerp(st.hx, cal ? cal.x : 0, kc); st.hy = lerp(st.hy, cal ? cal.y : 0, kc); st.hz = lerp(st.hz, cal ? cal.z : 0, kc);
    st.hyaw += wrapAngle((cal ? cal.yaw : 0) - st.hyaw) * kc;
    holder.position.set(st.hx, st.hy, st.hz); holder.rotation.y = st.hyaw;

    // clip selection + walk cycle speed matched to the measured movement speed
    if (tgt.clip !== st.clip) playClip(tgt.clip, FADE[tgt.clip] ?? FADE.default);
    if (st.action) st.action.setEffectiveTimeScale(tgt.clip === "walk" ? THREE.MathUtils.clamp((st.speed || WALK_SPEED * 0.8) / WALK_SPEED, 0.45, 1.8) : 1);
    rig.mixer.update(dt);

    if (rig.props.bread) rig.props.bread.visible = tgt.clip === "eat";
    if (rig.props.bag) rig.props.bag.visible = !!tgt.bread && (tgt.clip === "walk" || tgt.clip === "stand");
    const { head, handR, hips } = rig.bones;
    if (phoneMount) {
      const on = tgt.clip === "lie_phone" && handR && head;
      phoneMount.visible = !!on;
      if (on) {       // in the hand, screen (+z) toward the eyes, top edge along the body axis toward the head
        group.updateMatrixWorld(true);
        handR.localToWorld(tmpV.copy(rig.handOffset));
        head.getWorldPosition(tmpV2);
        tmpV.addScaledVector(tmpV3.copy(tmpV2).sub(tmpV).normalize(), 0.045);
        const up = tmpV3.copy(tmpV2).sub(hips.getWorldPosition(new THREE.Vector3())).normalize();
        group.worldToLocal(tmpV); group.worldToLocal(tmpV2); up.transformDirection(tmpM.copy(group.matrixWorld).invert());
        phoneMount.position.copy(tmpV);
        tmpM.lookAt(tmpV2, tmpV, up);         // +z from the phone toward the head
        phoneMount.quaternion.setFromRotationMatrix(tmpM);
      }
    }
    if (tagSprite || zzz) {
      const hp = head ? head.getWorldPosition(tmpV) : tmpV.set(st.x, 1.7, st.z);
      if (tagSprite) { tagSprite.visible = true; tagSprite.position.set(hp.x, hp.y + 0.3, hp.z); }
      if (zzz) { zzz.visible = !!tgt.asleep; zzz.position.set(hp.x + 0.25, hp.y + 0.55 + Math.sin(st.time * 1.2) * 0.04, hp.z); }
    }
  }
  const debug = () => ({ clip: st.clip, speed: st.speed, timeScale: st.action ? st.action.getEffectiveTimeScale() : 0, x: st.x, z: st.z, y: st.y, heading: st.h, rig: rig.kind });
  return { group, update, setRig, phoneMount, phoneScreen, debug, get rig() { return rig; } };
}

// -------- shared loader: look for a rigged character file described by manifest.character (or ?charGlb=) ----------
function characterConfig(assets) {
  let q = null;
  try { q = new URLSearchParams(location.search).get("charGlb"); } catch { /* no location */ }
  const c = assets?.manifest?.character;
  if (q) return { ...(c || {}), url: q };
  return c && c.url ? c : null;
}
// polls (cheap, once a second) because the manifest may load after createCharacter(); gives up when it is loaded
// and names no character file
function makeRigLoader(assets, styleName, onRig) {
  let started = false, tries = 0, lastCheck = -9;
  return function poll(t) {
    if (started || !assets || typeof assets.gltf !== "function" || t - lastCheck < 1) return;
    lastCheck = t;
    const cfg = characterConfig(assets);
    if (!cfg) { const loaded = assets.manifest && Object.keys(assets.manifest).length; if (++tries > (loaded ? 2 : 60)) started = true; return; }
    started = true;
    buildGltfRig(assets, cfg, styleName, m => console.warn("[character]", m))
      .then(r => { if (r) onRig(r); })
      .catch(e => console.warn("[character] rig load failed, keeping the procedural figure:", e?.message || e));
  };
}

// ============================================================================================================
// 4. SUB-01
// ============================================================================================================
const DEFAULTS = { seatY: 0.45, benchSeatY: 0.456, bedYaw: 0 };

export function createCharacter(scene, assets) {
  const actor = createActor(scene, () => buildMannequin("sub01"), { name: "sub01", tag: "SUB-01" });
  const model = k => assets?.manifest?.models?.[k];
  const poll = makeRigLoader(assets, "sub01", r => actor.setRig(r));
  let A = null, elapsed = 0;
  const anchorOf = name => readAnchor(A?.[name] || A?.places?.[name]);
  const discover = () => { if (!A) { const w = scene.getObjectByName("world"); A = assets?.anchors || scene.userData?.anchors || w?.userData?.anchors || null; } };
  const tgt = { x: 0, z: 0, heading: 0, y: 0, clip: "idle", bread: 0, walking: false, calibSlot: null, asleep: false, hide: false, snap: false };

  return {
    object: actor.group, phoneMount: actor.phoneMount, phoneScreen: actor.phoneScreen,
    get rig() { return actor.rig; }, debug: actor.debug,
    setAnchors(a) { A = a; },
    setPhoneTexture(tex) { const m = actor.phoneScreen?.material; if (m) { m.map = tex; m.color.setHex(0xffffff); m.needsUpdate = true; } },
    update(dt, life) {
      elapsed += dt; discover(); poll(elapsed);
      if (!life) { tgt.hide = true; actor.update(dt, tgt); return; }
      tgt.hide = false;
      const walking = !!life.walking || life.pose === "walking", asleep = !!life.stage && life.stage !== "AWAKE";
      const pose = life.pose, act = life.activity;
      let clip = "idle";
      if (walking) clip = "walk";
      else if (asleep && (life.place === "bed" || pose === "lying" || pose === "lying_phone")) clip = "lie";
      else if (pose === "lying") clip = "lie";
      else if (pose === "lying_phone") clip = "lie_phone";
      else if (pose === "sitting_desk") clip = "sit_desk";
      else if (pose === "sitting") clip = act === "eat" ? "eat" : "sit";
      else if (pose === "standing") clip = act === "window" ? "look_window" : act === "buy_bread" ? "stand" : "idle";
      const surface = SURFACE[clip];
      let x = life.x, z = life.z, heading = life.heading || 0, y = 0;
      if (surface === "bed") {
        const a = anchorOf("bed");
        if (a && a.x != null) { x = a.x; z = a.z; }
        heading = a?.heading ?? DEFAULTS.bedYaw;
        y = a?.hasY ? a.y : (model("old_bed_frame")?.surfaceY ?? 0.49) + 0.15;
      } else if (surface === "seat") {
        const key = life.place === "bench" ? "bench" : life.place === "desk" ? "desk" : "table";
        const a = anchorOf(key);
        if (a && a.x != null) { x = a.x; z = a.z; }
        heading = a?.heading ?? (key === "bench" ? 0 : Math.PI);
        y = a?.hasY ? a.y : key === "bench" ? (model("painted_wooden_bench")?.seatY ?? DEFAULTS.benchSeatY) : (model("WoodenChair_01")?.seatY ?? DEFAULTS.seatY);
      } else if (clip === "look_window") {
        const a = anchorOf("window");
        heading = a && a.x != null && Math.hypot(a.x - x, a.z - z) > 0.3 ? Math.atan2(a.x - x, a.z - z) : Math.PI;
      }
      tgt.x = x; tgt.z = z; tgt.heading = heading; tgt.y = y; tgt.clip = clip; tgt.walking = walking;
      tgt.bread = life.bread || 0; tgt.calibSlot = surface ? clip : null; tgt.asleep = asleep && clip === "lie";
      actor.update(dt, tgt);
    },
  };
}

// ============================================================================================================
// 5. Baker NPC
// ============================================================================================================
export function createBaker(scene, assets, anchors) {
  const actor = createActor(scene, () => buildMannequin("baker"), { name: "baker", tag: null });
  let A = anchors || null, elapsed = 0;
  const poll = makeRigLoader(assets, "baker", r => actor.setRig(r));
  const spot = () => {
    const b = readAnchor(A?.baker || A?.places?.baker);
    if (b && b.x != null) return { x: b.x, z: b.z, heading: b.heading ?? Math.PI };
    const c = readAnchor(A?.counter || A?.places?.counter);
    if (c && c.x != null) return { x: c.x, z: c.z + 1.4, heading: Math.PI };     // behind the counter, faces the door (north)
    return { x: 21, z: 17.8, heading: Math.PI };
  };
  const tgt = { x: 0, z: 0, heading: Math.PI, y: 0, clip: "baker_idle", bread: 0, walking: false, calibSlot: null, asleep: false, hide: false, snap: false };
  return {
    object: actor.group, get rig() { return actor.rig; }, debug: actor.debug,
    setAnchors(a) { A = a; },
    update(dt, life) {
      elapsed += dt; poll(elapsed);
      const b = life?.npc?.baker, serving = !!b && b.pose === "serving", s = spot();
      tgt.hide = b ? !b.present : false;
      tgt.x = s.x; tgt.z = s.z; tgt.heading = s.heading;
      tgt.clip = serving ? "serve" : "baker_idle";
      actor.update(dt, tgt);
      if (actor.rig.props.bag) actor.rig.props.bag.visible = serving;
    },
  };
}
