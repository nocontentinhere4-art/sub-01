// The MakeHuman rig with real mocap (preview/room-mh, a crude first integration; #98). When room/boy.glb is the MakeHuman
// body (163 bones with fingers, metres, feet at y = 0, bones world-aligned at rest; G2's boy_g2.glb on the same skeleton
// drops in as room/boy.glb), the old rig's clips and procedural layers do not fit it: this module takes over.
//
// The desk follows the owner's rule ("deve scrivere sulla tastiera quando cerca qualcosa, usare il mouse per cliccare e
// selezionare cose, e quando guarda video sta semplicemente sulla sedia"):
//   research: a new screen that carries a search query -> desk_type_ik for about the time to type it (4-8 s), else the mouse
//   watch_video, and any screen of kind video / short -> desk_watch (relaxed in the chair)
//   chart, play_chess -> desk_mouse_ik
// with 0.4 s crossfades between the modes. desk_type_ik and desk_mouse_ik (the owner approved both) already carry the
// arms, the wrists and the fingers against a keyboard and a mouse placed in the clip's own frame; here the wrists are only
// re-pinned to the room's real keyboard and mouse: the recorded wrist (with its drift) moves by the offset between the
// clip's reference point and the room's, and no fingertip goes below the keycaps (+3 mm) or into the pad (+1.1 cm).
//
// Swappable parts: a room node named "keyboard" (G10d's Tripo keyboard) replaces the keycap numbers below by its bounds,
// and a node named "mouse" is moved next to the keyboard's right end and follows the right palm while he uses it. In the
// room on main both are part of the merged static mesh, so the numbers below are used and the mouse stays put.
//
// Everything else is crude on purpose: still poses from the source clips stand in for standing / walking (a stand that
// glides) and for lying (the last frame of a lie-down); the old rig's interludes, breathing, look-at, foot IK and phone
// hold are off.

const CLIPS = {desk_type: "desk_type_ik", desk_mouse: "desk_mouse_ik", desk_watch: "desk_watch", stand: "04_Open_Window", lie: "02_Lie_Down_01"};
// the room (main): keycaps (G10d) centre, top y, turn about y, size; the mouse centre on the pad; the desk / pad top
const ROOM = {keys: {c: [-1.070, 1.001, -0.976], ry: 0.06, w: 0.356, d: 0.134}, mouse: [-0.755, 0.973, -0.950], pad: 0.973};
// the clips' frame (root at the feet, facing +z; measured in the page: the recorded wrists sit on the README's pins in
// it): the keyboard the typing was pinned to (keycaps' centre at KEYTOP; the wrists' pins (0.03 / -0.13, 0.878, 0.32)
// lie over its near half) and the mouse dome's hump (on DESK_Y), from preview/mh-motion's README
const CLIP = {kb: [-0.05, 0.83, 0.33], mouse: [-0.36, 0.807, 0.39], desk: 0.809};
const HUMP = 0.02;                                           // a room mouse's hump: 2 cm behind its centre (the back third)
const FADE = 0.4;

export const isMH = bones => !!(bones && (bones["metacarpal1L"] || bones["metacarpal1.L"]));   // (three.js drops the dot)

export function createMH(env) {
  const {THREE} = env;
  const M = {ready: false, mode: null, typeUntil: 0, lastScreen: null, actions: {}, w: {type: 0, mouse: 0}, log: [], noIK: false, zoff: 0};
  const V = (...a) => new THREE.Vector3(...a);

  // ---------- clips: two approved desk loops, the relaxed one, and two still poses, under the page's slot names ----------
  function stillClip(name, clip, at) {                       // one frame of a clip as a 1 s still
    const tracks = clip.tracks.map(tr => { const v = tr.createInterpolant().evaluate(at).slice(); return new tr.constructor(tr.name, [0, 1], [...v, ...v]); });
    return new THREE.AnimationClip(name, 1, tracks);
  }
  function hipsAt(clip, at) {                               // where the clip has the hips at a time (metres, from the root)
    const tr = clip.tracks.find(t => t.name === "Hips.position");
    return tr ? Array.from(tr.createInterpolant().evaluate(at)) : [0, 0.87, -0.076];
  }
  async function load() {
    const got = {};
    await Promise.all(Object.entries(CLIPS).map(([k, f]) => env.load(`room/mh/${f}.glb`).then(g => { got[k] = g.animations[0]; })));
    const mixer = env.mixer, A = env.actions, H = env.HIPS;
    // watching "simply sits in the chair": the recorded clip slouches and props its feet up at the desk's height, so its
    // pelvis and legs come from the mouse clip (seated upright, feet on the floor); the back, arms and head stay relaxed
    const LEGS = /^(Left|Right)(UpLeg|Leg|Foot|ToeBase)\.|^Hips\.quaternion$/;
    got.desk_watch = new THREE.AnimationClip("desk_watch", Math.max(got.desk_watch.duration, got.desk_mouse.duration),
      [...got.desk_watch.tracks.filter(t => !LEGS.test(t.name)), ...got.desk_mouse.tracks.filter(t => LEGS.test(t.name))]);
    const stand = stillClip("mh_stand", got.stand, 0), lie = stillClip("mh_lie", got.lie, got.lie.duration);
    const make = c => mixer.clipAction(c);
    for (const k of ["desk_type", "desk_mouse", "desk_watch"]) { M.actions[k] = make(got[k]); H[k] = hipsAt(got[k], 0); }
    M.actions.stand = make(stand); H.mh_stand = hipsAt(stand, 0);
    M.actions.lie = make(lie); H.mh_lie = hipsAt(lie, 0);
    // every slot the page plays: seated -> relaxed in the chair, standing / walking -> the stand, lying -> the lie
    const seated = ["sit", "dine", "eat", "edge", "phone_sit", "type"], upright = ["idle", "stand", "lean", "deliver", "phone_stand", "door", "walk"],
      lying = ["sleep", "phone_lie", "listen", "lie_phone"];
    for (const k of seated) { A[k] = M.actions.desk_watch; H[k] = H.desk_watch.slice(); }
    for (const k of upright) { A[k] = M.actions.stand; H[k] = H.mh_stand.slice(); }
    for (const k of lying) { A[k] = M.actions.lie; H[k] = H.mh_lie.slice(); }
    for (let i = 0; i < 600 && !(env.chairNode && env.chairNode()); i++) await new Promise(r => setTimeout(r, 100));   // (the room may still be loading)
    seatHeight(); props();
    for (const a of Object.values(M.actions)) a.stop();
    mixer.stopAllAction();
    const first = A[env.state().want] || M.actions.stand; first.reset().setEffectiveWeight(1).play(); env.setCurrent(first);
    env.resnap();                                            // placed for the old clips: again, with these hips
    M.ready = true;
  }
  // the page puts the root at the seat anchor less the clip's hips; the MakeHuman clips have the feet at y = 0, so the
  // seated slots' hip height is the seat anchor's height over the floor: the root (his feet) stays on the floor
  function seatHeight() {
    const n = env.chairNode && env.chairNode(); if (!n) return;
    const p = n.localToWorld(V(0, 0.735, 0.02)), hy = p.y - env.F, H = env.HIPS;
    for (const k of ["desk_type", "desk_mouse", "desk_watch", "sit", "dine", "eat", "edge", "phone_sit", "type"]) if (H[k]) H[k][1] = hy;
  }
  // the room's keyboard and mouse: separate nodes when the room has them (G10d's), else the numbers above
  const P = {keys: null, mouse: null, mouseNode: null, mouseHome: null};
  function props() {
    const room = env.room && env.room();
    const kb = room && room.getObjectByName("keyboard");
    if (kb) {                                                // its bounds in its own frame: the top, the centre, the size
      kb.updateMatrixWorld(true);
      const inv = new THREE.Matrix4().copy(kb.matrixWorld).invert(), bb = new THREE.Box3();
      kb.traverse(o => { if (o.isMesh) { o.geometry.computeBoundingBox(); bb.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld).applyMatrix4(inv)); } });
      const c = kb.localToWorld(bb.getCenter(V())), top = kb.localToWorld(V(0, bb.max.y, 0)).y;
      P.keys = {c: [c.x, top, c.z], ry: kb.getWorldQuaternion(new THREE.Quaternion()) && new THREE.Euler().setFromQuaternion(kb.getWorldQuaternion(new THREE.Quaternion()), "YXZ").y,
        w: bb.max.x - bb.min.x, d: bb.max.z - bb.min.z};
    } else P.keys = ROOM.keys;
    const ms = room && room.getObjectByName("mouse");
    if (ms) {                                                // next to the keyboard's right end, 4 cm of gap
      const k = P.keys, half = new THREE.Box3().setFromObject(ms).getSize(V()).x / 2, u = k.w / 2 + 0.04 + half;
      ms.position.set(k.c[0] + Math.cos(k.ry) * u, ms.position.y, k.c[2] - Math.sin(k.ry) * u + 0.01); ms.updateMatrixWorld(true);
      P.mouseNode = ms; P.mouseHome = ms.position.clone();
      P.mouse = [ms.position.x, ROOM.pad, ms.position.z];
    } else P.mouse = ROOM.mouse;
  }

  // ---------- the desk modes ----------
  function wanted(st) {
    const life = st.life || {}, act = life.activity;
    const seatedAtDesk = st.at === "desk" && !st.step && ["research", "chat", "chart", "watch_video", "play_chess"].includes(act);
    if (!seatedAtDesk) return null;
    const sc = life.screen || {}, kind = sc.kind || (sc.info && sc.info.kind);
    const query = (sc.search && sc.search.query) || (sc.info && sc.info.search && sc.info.search.query) || "";
    if (sc.id && sc.id !== M.lastScreen) {                  // a new screen: a search on it means he typed its query
      M.lastScreen = sc.id;
      if (act === "research" && query) M.typeUntil = st.T + Math.min(8, Math.max(4, 2.5 + 0.18 * query.length));
    }
    if (act === "watch_video" || kind === "video" || kind === "short") return "desk_watch";
    if (act === "research" && st.T < M.typeUntil) return "desk_type";
    return "desk_mouse";
  }
  function setMode(m) {
    if (m === M.mode) return;
    const a = M.actions[m], cur = env.state().current;
    if (a !== cur) { a.reset(); a.setEffectiveWeight(1); a.fadeIn(FADE).play(); if (cur) cur.fadeOut(FADE); env.setCurrent(a); }
    for (const k of ["sit", "dine", "type"]) env.actions[k] = a;   // the page's own play("sit") then keeps this mode
    M.mode = m; M.log.push([+env.state().T.toFixed(2), m]); if (M.log.length > 50) M.log.shift();
  }

  // ---------- re-pinning the wrists (the arm's two bones turn; the wrist and the fingers keep the clip) ----------
  const _a = V(), _b = V(), _u = V(), _v = V(), _q = new THREE.Quaternion(), _pq = new THREE.Quaternion(), _wq = new THREE.Quaternion();
  const toWorld = (p, out) => env.boy.localToWorld(out.set(p[0], p[1], p[2] + M.zoff));   // the clip's frame -> the room
  function ccd(side, target, weight) {                       // move the wrist to target: forearm, then upper arm
    const B = env.bones, hand = B[side + "Hand"], chain = [B[side + "ForeArm"], B[side + "Arm"]];
    if (!hand || !chain[0] || !chain[1] || weight <= 0) return;
    for (let it = 0; it < 6; it++) for (const bone of chain) {
      bone.getWorldPosition(_a); hand.getWorldPosition(_b);
      _u.subVectors(_b, _a).normalize(); _v.subVectors(target, _a).normalize();
      if (_u.dot(_v) > 0.99999) continue;
      _q.setFromUnitVectors(_u, _v); _q.slerp(new THREE.Quaternion(), 1 - weight);
      bone.parent.getWorldQuaternion(_pq);
      bone.quaternion.copy(_pq.invert().multiply(bone.getWorldQuaternion(_wq).premultiply(_q)));
      bone.updateMatrixWorld(true);
    }
  }
  const tipNames = side => [1, 2, 3, 4, 5].map(f => env.bones[`finger${f}-3${side === "Left" ? "L" : "R"}`] || env.bones[`finger${f}-3.${side === "Left" ? "L" : "R"}`]).filter(Boolean);
  function lowestTip(side) {                                // the lowest fingertip: the end bone's head, a finger's half thickness lower
    let low = 1e9; for (const b of tipNames(side)) { b.getWorldPosition(_a); low = Math.min(low, _a.y - 0.008); } return low;
  }
  function pin(side, delta, floor, weight) {                 // the recorded wrist + delta, lifted until no tip is under the floor
    const hand = env.bones[side + "Hand"]; if (!hand || weight <= 0) return;
    const w0 = hand.getWorldPosition(V()), t = w0.clone().add(delta);
    for (let it = 0; it < 3; it++) {
      ccd(side, t, weight);
      const deficit = floor - lowestTip(side); if (deficit <= 0.001) break;
      t.y += deficit;
    }
  }
  const _k = V(), _c = V(), _m = V(), dK = V(), dM = V(), _hp = V();
  function hands(dt) {
    const typing = M.mode === "desk_type", mousing = M.mode === "desk_mouse";
    const k = 1 - Math.exp(-dt / 0.13);
    M.w.type += ((typing ? 1 : 0) - M.w.type) * k; M.w.mouse += ((mousing ? 1 : 0) - M.w.mouse) * k;
    if (M.noIK) return;
    env.boy.updateMatrixWorld(true);
    // the offsets: the clip's keyboard to the room's (keycaps' centre, top), the clip's mouse hump to the room's (on the pads)
    _k.set(...P.keys.c); dK.subVectors(_k, toWorld(CLIP.kb, _c));
    const ry = env.boy.rotation.y; _m.set(P.mouse[0] - Math.sin(ry) * HUMP, P.mouse[1], P.mouse[2] - Math.cos(ry) * HUMP);
    dM.subVectors(_m, toWorld(CLIP.mouse, _c));
    const keyFloor = P.keys.c[1] + 0.003, padFloor = ROOM.pad + 0.011;
    if (M.w.type > 0.01) { pin("Left", dK, keyFloor, M.w.type); pin("Right", dK, keyFloor, M.w.type); }
    if (M.w.mouse > 0.01) { pin("Right", dM, padFloor, M.w.mouse); pin("Left", dK, keyFloor, M.w.mouse); }
    // a separate room mouse follows the right palm (60% from the wrist to the middle knuckle) while he holds it
    if (P.mouseNode) {
      const hand = env.bones.RightHand, kn = env.bones["finger3-1R"] || env.bones["finger3-1.R"];
      if (hand && kn && M.w.mouse > 0.5) {
        hand.getWorldPosition(_hp).lerp(kn.getWorldPosition(_a), 0.6);
        if (!M.grab) M.grab = P.mouseNode.position.clone().sub(_hp).setY(0);
        P.mouseNode.position.set(_hp.x + M.grab.x, P.mouseHome.y, _hp.z + M.grab.z); P.mouseNode.updateMatrixWorld(true);
      } else M.grab = null;
    }
  }
  // watching: relaxed in the chair he leans back, a little further from the desk: he and the chair roll 0.12 m back,
  // and in again for the keys and the mouse
  function roll(dt) {
    const want = M.mode === "desk_watch" ? 0.12 : 0, k = 1 - Math.exp(-dt / 0.35);
    const off = M.off || 0, nxt = off + (want - off) * k, d = nxt - off; M.off = nxt;
    if (Math.abs(d) < 1e-6) return;
    const ry = env.boy.rotation.y, bx = -Math.sin(ry) * d, bz = -Math.cos(ry) * d;      // back: against the way he faces
    env.boy.position.x += bx; env.boy.position.z += bz;
    const ch = env.chairNode && env.chairNode(); if (ch) { ch.position.x += bx; ch.position.z += bz; ch.updateMatrixWorld(true); }
  }

  // ---------- one step (instead of the page's animate: the mixer, his plan and walk, the desk modes, the wrists) ----------
  function animate(dt) {
    const moving = env.step0(dt);
    if (!M.ready) return moving;
    const st = env.state(), m = wanted(st);
    if (m) setMode(m); else if (M.mode) { M.mode = null; M.w.type = M.w.mouse = 0; M.off = 0; for (const k of ["sit", "dine", "type"]) env.actions[k] = M.actions.desk_watch; }
    if (M.mode) { roll(dt); hands(dt); }
    return moving;
  }
  // ?debug: where the wrists are in the clip's frame (to check the pins), and the tips' clearance
  function dbg() {
    env.boy.updateMatrixWorld(true);
    const loc = b => { const p = env.bones[b].getWorldPosition(V()); return env.boy.worldToLocal(p).toArray().map(v => +v.toFixed(3)); };
    return {mode: M.mode, L: loc("LeftHand"), R: loc("RightHand"), tipsL: +lowestTip("Left").toFixed(3), tipsR: +lowestTip("Right").toFixed(3),
      root: env.boy.position.toArray().map(v => +v.toFixed(3)), keys: P.keys, mouse: P.mouse};
  }
  load().catch(e => console.warn("MakeHuman clips:", e));
  return {animate, dbg, M, get ready() { return M.ready; }, get mode() { return M.mode; }};
}
