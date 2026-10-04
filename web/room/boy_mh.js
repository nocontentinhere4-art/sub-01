// The MakeHuman rig with real mocap (preview/room-mh, a crude first integration; #98). When room/boy.glb is the MakeHuman
// body (163 bones with fingers, metres, feet at y = 0, bones world-aligned at rest; on this branch G2's boy_g2.glb with
// preview/mh-motion's clips_g2 in room/mh/, which go together), the old rig's clips and procedural layers do not fit it:
// this module takes over.
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
// and a node named "mouse" follows the right palm while he uses it (within 6 cm of where it lies on the pad). In the
// room on main both are part of the merged static mesh, so the numbers below are used and the mouse stays put.
//
// The room's moves: the recorded walk loop (the page moves him along his path), sit down / stand up on the chair, lie
// down / get up on the bed, each pose step lasting its clip's stretch and placed by the clip's own pose (the seat, the
// bed's edge, lying on the duvet). Still frames stand in for standing (room_window's first) and for sitting on the bed's
// edge and lying; the old rig's interludes, breathing, look-at, foot IK and phone hold are off.

const CLIPS = {desk_type: "desk_type_ik", desk_mouse: "desk_mouse_ik", desk_watch: "desk_watch", stand: "room_window",
  walk: "room_walk", sit_down: "room_sit_down", stand_up: "room_stand_up", bed_lie: "room_bed_lie", bed_wake: "room_bed_wake"};
// the room (main): keycaps (G10d) centre, top y, turn about y, size; the mouse centre on the pad; the desk / pad top
const ROOM = {keys: {c: [-1.070, 1.001, -0.976], ry: 0.06, w: 0.356, d: 0.134}, mouse: [-0.755, 0.973, -0.950], pad: 0.973};
// the clips' frame (root at the feet, facing +z; measured in the page: the recorded wrists sit on the README's pins in
// it): the keyboard the typing was pinned to (keycaps' centre at KEYTOP; the wrists' pins (0.03 / -0.13, 0.878, 0.32)
// lie over its near half) and the mouse dome's hump (on DESK_Y), from preview/mh-motion's README. G2's clips (clips_g2)
// sit the typing and the mouse higher (DY 0.023 at 52a1070, for the slides and trousers on the 0.505 m seat); measured
// in the page, raising the clip's keyboard and mouse by 1.7 cm puts the pressing fingertips 2-5 mm over the keycaps
const DY = 0.017;
const CLIP = {kb: [-0.05, 0.83 + DY, 0.33], mouse: [-0.36, 0.807 + DY, 0.39], desk: 0.809 + DY,
  home: [-0.003, 0.83 + DY, 0.317]};                         // the same keyboard's home row (F/J, KB_HOME): 4.7 cm left, 1.3 cm nearer
// the room clips (preview/mh-motion README): sit_down ends facing +z with the chair's seat centre at (-0.26, -0.13) (boy_mh;
// measured from the clips at load: G2's is at (-0.28, -0.15));
// stand_up starts seated with it at (0, 0); the bed clips are lifted to the 0.66 m mattress (the room's: 0.82 - 0.16)
const SEAT = {down: [-0.26, -0.13], up: [0, 0]};
const BED = {hips: [-1.0, 0.89], head: -1,                 // where his hips lie on the duvet (x, z), the head toward -x (the headboard),
  edge: [-0.40, 0.36], face: Math.PI,                        // where he sits on its edge (ANCHOR.bedside's seat), facing the desk (-z),
  box: [-1.90, -0.20, 0.25, 1.50], top: 0.805};              // and the mattress (x0, x1, z0, z1) with its top less 1.5 cm of give
const WALK_V = 0.67;                                         // room_walk's travel speed (m/s)
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
  // a clip's pose at a time, in its own frame (the root at the feet): the hips' and the head's positions
  function sampler(clip) {
    const mx = new THREE.AnimationMixer(env.boy), a = mx.clipAction(clip); a.play();
    const B = env.bones, out = t => { a.time = t; mx.update(0); env.boy.updateMatrixWorld(true);
      const loc = n => env.boy.worldToLocal(B[n].getWorldPosition(V()));
      return {t, hips: loc("Hips"), head: loc("Head"), knee: loc("LeftLeg").add(loc("RightLeg")).multiplyScalar(0.5),
        foot: Math.max(loc("LeftFoot").y, loc("RightFoot").y)}; };
    out.done = () => { a.stop(); mx.uncacheRoot(env.boy); };
    return out;
  }
  function segments(got) {
    const scan = (clip, dt = 0.05) => { const s = sampler(clip), r = []; for (let t = 0; t <= clip.duration + 1e-6; t += dt) r.push(s(Math.min(t, clip.duration))); s.done(); return r; };
    const S = {};
    // sit_down: the last moment the hips are still high (standing) before they drop onto the seat
    const sd = scan(got.sit_down); let i = sd.length - 1; while (i > 0 && sd[i].hips.y < 0.80) i--;
    S.sit = {from: Math.max(0, sd[i].t - 0.3), to: got.sit_down.duration};
    // the chair's seat centre in sit_down's frame: where it leaves the hips, less where stand_up starts them (its seat at 0, 0)
    const su = sampler(got.stand_up), h0 = su(0).hips; su.done();
    S.seatDown = [sd[sd.length - 1].hips.x - h0.x, sd[sd.length - 1].hips.z - h0.z];
    // bed_lie: on the edge = hips low with the head up; lying = the head low
    const bl = scan(got.bed_lie);
    const e0 = bl.find(p => p.hips.y < 0.80 && p.head.y > 1.05) || bl[Math.floor(bl.length / 3)];
    const l0 = bl.find(p => p.t > e0.t && p.head.y < 1.0) || bl[Math.floor(bl.length * 2 / 3)];
    // sitting on the edge: the middle of the stretch where he sits upright with his feet down (before they swing up to lie)
    const up = bl.filter(p => p.t >= e0.t && p.t <= l0.t && p.hips.y < 0.76 && p.head.y > 1.3 && p.foot < 0.3), sat = up.length ? up[up.length >> 1] : e0;
    S.lie = {stand: Math.max(0, e0.t - 1.6), edge: sat.t, end: got.bed_lie.duration, endPose: bl[bl.length - 1]};
    // bed_wake: lying -> sitting up (head high again) -> standing (hips high)
    const bw = scan(got.bed_wake);
    const s0 = bw.find(p => p.head.y > 1.05 && p.hips.y < 0.80) || bw[Math.floor(bw.length / 3)];
    S.wake = {sat: Math.min(s0.t + 0.6, got.bed_wake.duration), end: got.bed_wake.duration, startPose: bw[0]};
    // the bed's placement: the lying pose turned so the head points toward the headboard, the hips on the duvet
    S.bedLie = bedPlace(S.lie.endPose); S.bedWake = bedPlace(S.wake.startPose);
    // on the edge: the clip's bed is not laid out like the room's, so the sitting moments get their own placement
    const atT = (r, t) => r.reduce((b, q) => Math.abs(q.t - t) < Math.abs(b.t - t) ? q : b);
    S.lieEdge = edgePlace(atT(bl, S.lie.edge)); S.wakeEdge = edgePlace(atT(bw, S.wake.sat));
    return S;
  }
  function edgePlace(p) {                                    // the root that seats this pose on the room's bed edge, facing out
    const a = Math.atan2(p.knee.z - p.hips.z, p.knee.x - p.hips.x);                 // the way his knees point (local)
    const want = Math.atan2(Math.cos(BED.face), Math.sin(BED.face)), ry = a - want;
    const c = Math.cos(ry), s = Math.sin(ry), hx = p.hips.x * c + p.hips.z * s, hz = -p.hips.x * s + p.hips.z * c;
    return {ry, x: BED.edge[0] - hx, z: BED.edge[1] - hz};
  }
  // two placements blended about his hips (not the root, which sits a metre away when he lies and would swing him
  // through the bed): h is the clip's hips at this moment, in its own frame
  function mixPlace(A, B, k, h) {
    const rot = ry => { const c = Math.cos(ry), s = Math.sin(ry); return [h[0] * c + h[2] * s, -h[0] * s + h[2] * c]; };
    const ha = rot(A.ry), hb = rot(B.ry), ry = angLerp(A.ry, B.ry, k), hr = rot(ry);
    const wx = A.x + ha[0] + (B.x + hb[0] - A.x - ha[0]) * k, wz = A.z + ha[1] + (B.z + hb[1] - A.z - ha[1]) * k;
    return {ry, x: wx - hr[0], z: wz - hr[1]};
  }
  function bedPlace(p) {                                     // the root's turn and position that lay this pose on the room's bed
    const vx = p.head.x - p.hips.x, vz = p.head.z - p.hips.z, a = Math.atan2(vz, vx);
    const ry = a - (BED.head < 0 ? Math.PI : 0);             // (a local direction at angle a ends at angle a - ry in the room)
    const c = Math.cos(ry), s = Math.sin(ry), hx = p.hips.x * c + p.hips.z * s, hz = -p.hips.x * s + p.hips.z * c;
    return {ry, x: BED.hips[0] - hx, z: BED.hips[1] - hz};
  }
  async function load() {
    const got = {};
    await Promise.all(Object.entries(CLIPS).map(([k, f]) => env.load(`room/mh/${f}.glb`).then(g => { got[k] = g.animations[0]; })));
    const mixer = env.mixer, A = env.actions, H = env.HIPS;
    // watching "simply sits in the chair": the recorded clip (boy_mh's and G2's alike) slouches and props its feet up at
    // the desk's height, so its pelvis (turn and height) and legs come from the mouse clip (seated on the seat, feet on
    // the floor); the back, arms and head stay relaxed. A watch clip with its feet already down plays as recorded.
    const ws = sampler(got.desk_watch), feetUp = ws(0).foot > 0.12; ws.done();
    const LEGS = /^(Left|Right)(UpLeg|Leg|Foot|ToeBase)\.|^Hips\.(quaternion|position)$/;
    if (feetUp) got.desk_watch = new THREE.AnimationClip("desk_watch", Math.max(got.desk_watch.duration, got.desk_mouse.duration),
      [...got.desk_watch.tracks.filter(t => !LEGS.test(t.name)), ...got.desk_mouse.tracks.filter(t => LEGS.test(t.name))]);
    M.watchLegs = feetUp ? "desk_mouse" : "recorded";
    const make = c => mixer.clipAction(c);
    M.clips = got;
    // the transitions' moments, from the clips' own poses: on the bed edge (hips low, head up), lying (head low)
    const seg = segments(got);
    M.seg = seg; M.sampler = sampler;                          // (?debug: a clip's hips, head, knees and feet at a time)
    const stand = stillClip("mh_stand", got.stand, 0), lie = stillClip("mh_lie", got.bed_lie, got.bed_lie.duration),
      edge = stillClip("mh_edge", got.bed_lie, seg.lie.edge);
    for (const k of ["desk_type", "desk_mouse", "desk_watch"]) { M.actions[k] = make(got[k]); H[k] = hipsAt(got[k], 0); }
    M.actions.stand = make(stand); H.mh_stand = hipsAt(stand, 0);
    M.actions.walk = make(got.walk); H.room_walk = hipsAt(got.walk, 0);
    M.actions.lie = make(lie); H.mh_lie = hipsAt(lie, 0);
    M.actions.edge = make(edge); H.mh_edge = hipsAt(edge, 0);
    for (const k of ["sit_down", "stand_up", "bed_lie", "bed_wake"]) { const a = M.actions[k] = make(got[k]); a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
    // every slot the page plays: seated at the desk -> relaxed in the chair, on the bed's edge -> the edge, standing ->
    // the stand, walking -> the walk loop (the page scales it to his speed), lying -> the lie
    const seated = ["sit", "dine", "eat", "type"], onEdge = ["edge", "phone_sit"], upright = ["idle", "stand", "lean", "deliver", "phone_stand", "door"],
      lying = ["sleep", "phone_lie", "listen", "lie_phone"];
    for (const k of seated) { A[k] = M.actions.desk_watch; H[k] = H.desk_watch.slice(); }
    for (const k of onEdge) { A[k] = M.actions.edge; H[k] = H.mh_edge.slice(); }
    for (const k of upright) { A[k] = M.actions.stand; H[k] = H.mh_stand.slice(); }
    A.walk = M.actions.walk; H.walk = H.room_walk.slice(); if (env.setStride) env.setStride(WALK_V);
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
  // (G10d's are top-level scene nodes: "keyboard" with its origin on the home row (the middle of F and J) on the desk
  // top, and "mouse" with its origin at its base centre on the pad, already placed next to the keyboard's right end)
  const P = {keys: ROOM.keys, ref: CLIP.kb, mouse: ROOM.mouse, pad: ROOM.pad, mouseNode: null, mouseHome: null, kbNode: null, seen: 0};
  function props(force) {
    const sc = env.scene; if (!sc || (!force && P.kbNode && P.mouseNode)) return;
    if (!P.kbNode) { const kb = sc.getObjectByName("keyboard");
      if (kb && kb.children.length) {                        // the keycaps' top from its meshes; the home row is its origin
        kb.updateMatrixWorld(true); const bb = new THREE.Box3().setFromObject(kb);
        const ry = new THREE.Euler().setFromQuaternion(kb.getWorldQuaternion(new THREE.Quaternion()), "YXZ").y;
        P.keys = {c: [kb.position.x, Math.min(bb.max.y, kb.position.y + 0.045), kb.position.z], ry, w: ROOM.keys.w, d: ROOM.keys.d};
        P.ref = CLIP.home; P.kbNode = kb; } }
    if (!P.mouseNode) { const ms = sc.getObjectByName("mouse");
      if (ms && ms.parent === sc) {                          // where G10d put it; it follows the palm while he holds it
        P.mouseNode = ms; P.mouseHome = ms.position.clone(); P.pad = ms.position.y; P.mouse = [ms.position.x, ms.position.y, ms.position.z]; } }
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
    _k.set(...P.keys.c); dK.subVectors(_k, toWorld(P.ref, _c));
    const ry = env.boy.rotation.y; _m.set(P.mouse[0] - Math.sin(ry) * HUMP, P.mouse[1], P.mouse[2] - Math.cos(ry) * HUMP);
    dM.subVectors(_m, toWorld(CLIP.mouse, _c));
    const keyFloor = P.keys.c[1] + 0.003, padFloor = P.pad + 0.011;
    if (M.w.type > 0.01) { pin("Left", dK, keyFloor, M.w.type); pin("Right", dK, keyFloor, M.w.type); }
    if (M.w.mouse > 0.01) { pin("Right", dM, padFloor, M.w.mouse); pin("Left", dK, keyFloor, M.w.mouse); }
    // a separate room mouse follows the right palm (60% from the wrist to the middle knuckle) while he holds it
    if (P.mouseNode) {
      const hand = env.bones.RightHand, kn = env.bones["finger3-1R"] || env.bones["finger3-1.R"];
      if (hand && kn && M.w.mouse > 0.97) {                     // (once the hand is on it: the pin puts the palm on the hump at home)
        hand.getWorldPosition(_hp).lerp(kn.getWorldPosition(_a), 0.6);
        if (!M.grab) M.grab = P.mouseHome.clone().sub(_hp).setY(0);
        const H0 = P.mouseHome, cl = v => Math.max(-0.06, Math.min(0.06, v));   // (it stays on the pad: within 6 cm of home)
        P.mouseNode.position.set(H0.x + cl(_hp.x + M.grab.x - H0.x), H0.y, H0.z + cl(_hp.z + M.grab.z - H0.z)); P.mouseNode.updateMatrixWorld(true);
      } else M.grab = null;
    }
  }
  // watching (or just sitting, eating): relaxed in the chair he leans back, a little further from the desk: he and the
  // chair roll 0.12 m back, and in again for the keys and the mouse (to 8.5 cm back for the keys, 6 for the mouse: the hoodie's front clears the desk's edge)
  function roll(dt) {
    const want = M.mode === "desk_watch" || !M.mode ? 0.12 : M.mode === "desk_mouse" ? 0.06 : 0.085, k = 1 - Math.exp(-dt / 0.35);
    const p = env.boy.position;
    if (M.rollAt && (Math.abs(p.x - M.rollAt[0]) > 1e-6 || Math.abs(p.z - M.rollAt[1]) > 1e-6)) M.off = 0;   // (the page placed him anew)
    const off = M.off || 0, nxt = off + (want - off) * k, d = nxt - off; M.off = nxt;
    const ry = env.boy.rotation.y, bx = -Math.sin(ry) * d, bz = -Math.cos(ry) * d;      // back: against the way he faces
    p.x += bx; p.z += bz; M.rollAt = [p.x, p.z];
    if (Math.abs(d) < 1e-6) return;
    const ch = env.chairNode && env.chairNode(); if (ch) { ch.position.x += bx; ch.position.z += bz; ch.updateMatrixWorld(true); }
  }

  // ---------- getting on and off the chair and the bed: the room clips, inside the page's own pose steps ----------
  // The page moves his hips along keyed paths between two poses (posePose); here the matching stretch of a room clip
  // plays instead, its time following the step's progress, placed rigidly on the chair or the bed (its root on the
  // floor), and it hands back to the page's poses at both ends (the first and last 15 % blend).
  const sstep = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
  const angLerp = (a, b, k) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * k;
  function chairPlace(off) {                                 // the root for a clip whose seat centre is at off (x, z), on the room's chair
    const ch = env.chairNode && env.chairNode(); if (!ch) return null;
    ch.updateMatrixWorld(true); const p = ch.getWorldPosition(V()), cry = ch.rotation.y;
    const r = Math.atan2(-Math.sin(cry), -Math.cos(cry)), c = Math.cos(r), s = Math.sin(r);   // the way a person on it faces
    return {ry: r, x: p.x - (off[0] * c + off[1] * s), z: p.z - (-off[0] * s + off[1] * c)};
  }
  function transitionFor(S) {
    if (!S || S.k !== "pose" || S.t == null) return null;
    const G = M.seg, to = S.to, from = S.from;
    if (to === "desk" && from !== "desk") return {k: "sit_down", a: G.sit.from, b: G.sit.to, at: () => chairPlace(G.seatDown || SEAT.down), back: true};
    if (!to && from === "desk") return {k: "stand_up", a: 0, b: M.clips.stand_up.duration, at: () => chairPlace(SEAT.up), back: true};
    if (to === "bedside" && from !== "bedlie") return {k: "bed_lie", a: G.lie.stand, b: G.lie.edge, at: () => G.lieEdge};
    const hips = (clip, a, b) => u => hipsAt(M.clips[clip], a + (b - a) * u);
    if (to === "bedlie" && from !== "bedlie") { const h = hips("bed_lie", G.lie.edge, G.lie.end);   // (lying already: no lie-down)
      return {k: "bed_lie", a: G.lie.edge, b: G.lie.end, at: u => mixPlace(G.lieEdge, G.bedLie, sstep(0.1, 0.7, u), h(u))}; }
    if (to === "bedside" && from === "bedlie") { const h = hips("bed_wake", 0, G.wake.sat);
      return {k: "bed_wake", a: 0, b: G.wake.sat, at: u => mixPlace(G.bedWake, G.wakeEdge, sstep(0.3, 0.9, u), h(u))}; }
    if (!to && from === "bedside") return {k: "bed_wake", a: G.wake.sat, b: G.wake.end, at: () => G.wakeEdge, back: true};
    return null;
  }
  function transition(st) {
    const S = st.step, T = transitionFor(S);
    for (const k of ["sit_down", "stand_up", "bed_lie", "bed_wake"]) if (!T || T.k !== k) { const a = M.actions[k]; if (a.isRunning() || a.getEffectiveWeight() > 0) { a.setEffectiveWeight(0); a.stop(); } }
    if (!T) return false;
    const place = T.at(Math.min(1, Math.max(0, S.t))); if (!place) return false;
    if (S.mhd === undefined) { S.mhd = S.d; S.d = Math.max(S.d, T.b - T.a); }   // the step lasts as long as the clip's stretch (the page's ~1 s is too quick)
    const u = Math.min(1, Math.max(0, S.t)), w = sstep(0, 0.15, u) * (1 - sstep(0.85, 1, u));
    const a = M.actions[T.k]; if (!a.isRunning()) { a.reset(); a.play(); }
    a.paused = true; a.time = T.a + (T.b - T.a) * u; a.setEffectiveWeight(w);
    if (S.A && S.A !== a) S.A.setEffectiveWeight(u < 0.5 ? 1 - w : 0);          // the page's poses only at the two ends
    if (S.B && S.B !== a) S.B.setEffectiveWeight(u < 0.5 ? 0 : 1 - w);
    env.mixer.update(0);
    const b = env.boy, wr = T.back ? w : sstep(0, 0.15, u);  // the root: from the page's toward the clip's placement (onto the bed: kept)
    b.position.set(b.position.x + (place.x - b.position.x) * wr, b.position.y + (env.F - b.position.y) * wr, b.position.z + (place.z - b.position.z) * wr);
    b.rotation.y = angLerp(b.rotation.y, place.ry, wr);
    return true;
  }
  // the clips were recorded on another bed: while he sits on, lies down on or gets up from this one, any of his skin
  // that dips into the mattress lifts him by as much (eased back down when clear)
  let skin = null;
  function baseY() {                                         // his height as the page has it, without the lifts below
    const y = env.boy.position.y; if (M.lastY === undefined || Math.abs(y - M.lastY) > 1e-7) M.baseY = y;
    env.boy.position.y = M.baseY; return M.baseY;
  }
  function bedLift(st, dt) {
    const on = st.at === "bedlie" || st.at === "bedside" || (st.step && (st.step.to === "bedlie" || st.step.to === "bedside" || st.step.from === "bedlie" || st.step.from === "bedside"));
    if (!on && !M.lift) return;
    const b = env.boy; let need = 0, every = 3;
    if (on && !st.step) {                                      // still on the bed: every vertex, once a second (cheap on a phone)
      M.liftT = (M.liftT || 0) - dt; if (M.liftT > 0) { b.position.y += M.lift; return; }
      M.liftT = 1; every = 1; M.lift = 0;
    }
    if (on) {
      if (!skin) b.traverse(o => { if (o.isSkinnedMesh && !skin) skin = o; });
      b.updateMatrixWorld(true);
      const P = skin.geometry.attributes.position, v = V();
      for (let i = 0; i < P.count; i += every) { skin.getVertexPosition(i, v).applyMatrix4(skin.matrixWorld);
        const e = Math.min(v.x - BED.box[0], BED.box[1] - v.x, v.z - BED.box[2], BED.box[3] - v.z);
        if (e > 0) need = Math.max(need, BED.top - (e < 0.05 ? 0.05 - Math.sqrt(0.0025 - (0.05 - e) ** 2) : 0) - v.y); }   // (its edge is rounded, r 5 cm)
    }
    M.lift = Math.max(need, (M.lift || 0) - 0.1 * dt);
    if (M.lift < 1e-4) M.lift = 0;
    b.position.y += M.lift;
  }
  // the soles: no vertex of his feet (or of the slides on them) under the floor; a step that dips lifts him by as much,
  // eased back down (the vertices whose main bone is a foot or a toe, gathered once over every skinned part)
  let feet = null;
  function floorLift(dt) {
    const b = env.boy;
    if (!feet) { feet = []; b.traverse(o => { if (!o.isSkinnedMesh) return; const g = o.geometry, I = g.attributes.skinIndex, W = g.attributes.skinWeight, ids = [];
      for (let i = 0; i < g.attributes.position.count; i++) { let k0 = 0, w0 = 0; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > w0) { w0 = W.getComponent(i, k); k0 = I.getComponent(i, k); }
        if (/Foot|ToeBase|toe/.test(o.skeleton.bones[k0].name)) ids.push(i); }
      if (ids.length) feet.push([o, ids.filter((_, j) => j % 2 === 0)]); }); }
    b.updateMatrixWorld(true); let low = 9; const v = V();
    for (const [o, ids] of feet) for (const i of ids) { o.getVertexPosition(i, v).applyMatrix4(o.matrixWorld); if (v.y < low) low = v.y; }
    const need = Math.max(0, env.F - 0.002 - low);
    M.flift = Math.max(need, (M.flift || 0) - 0.1 * dt); if (M.flift < 1e-4) M.flift = 0;
    b.position.y += M.flift;
  }
  function onBed(st) {                                       // lying on, or sitting on the edge of, the bed: placed by the lie clip's pose
    if (st.step || (st.at !== "bedlie" && st.at !== "bedside")) return;
    const p = st.at === "bedlie" ? M.seg.bedLie : M.seg.lieEdge, b = env.boy; b.position.set(p.x, env.F, p.z); b.rotation.y = p.ry;
  }

  // ---------- one step (instead of the page's animate: the mixer, his plan and walk, the desk modes, the wrists) ----------
  function animate(dt) {
    const moving = env.step0(dt);
    if (!M.ready) return moving;
    if (!P.kbNode || !P.mouseNode) { P.seen += dt; if (P.seen > 1) { P.seen = 0; props(); } }   // (G10d's nodes may arrive late)
    const st = env.state(), m = wanted(st);
    if (m) setMode(m); else if (M.mode) {                    // off the desk modes (eating, leaving): seated he just sits back
      M.mode = null; M.w.type = M.w.mouse = 0; const a = M.actions.desk_watch, cur = st.current;
      for (const k of ["sit", "dine", "type"]) env.actions[k] = a;
      if (st.at === "desk" && !st.step && cur !== a) { a.reset(); a.setEffectiveWeight(1); a.fadeIn(FADE).play(); if (cur) cur.fadeOut(FADE); env.setCurrent(a); }
    }
    if (!transition(st)) onBed(st);
    baseY(); bedLift(st, dt); floorLift(dt); M.lastY = env.boy.position.y;
    if (st.at === "desk" && !st.step) roll(dt); else { M.off = 0; M.rollAt = null; }   // (off the desk the page places him and the chair)
    if (M.mode) hands(dt);
    return moving;
  }
  // ?debug: where the wrists are in the clip's frame (to check the pins), and the tips' clearance
  function dbg() {
    env.boy.updateMatrixWorld(true);
    const loc = b => { const p = env.bones[b].getWorldPosition(V()); return env.boy.worldToLocal(p).toArray().map(v => +v.toFixed(3)); };
    return {mode: M.mode, L: loc("LeftHand"), R: loc("RightHand"), tipsL: +lowestTip("Left").toFixed(3), tipsR: +lowestTip("Right").toFixed(3),
      root: env.boy.position.toArray().map(v => +v.toFixed(3)), keys: P.keys, mouse: P.mouse,
      mouseAt: P.mouseNode ? P.mouseNode.position.toArray().map(v => +v.toFixed(3)) : null, grab: M.grab ? M.grab.toArray().map(v => +v.toFixed(3)) : null};
  }
  load().catch(e => console.warn("MakeHuman clips:", e));
  return {animate, dbg, M, get ready() { return M.ready; }, get mode() { return M.mode; }};
}
