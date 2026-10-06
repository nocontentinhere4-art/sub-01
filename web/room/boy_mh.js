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
//
// Leaving the desk is one take of room_bedtime's get-up (flow()): seated he rolls back and swivels with the chair, rises
// (his legs push it on; it stays there), turns as he walks off and the walk loop takes over mid-stride. The walk plays
// as recorded (knees and elbows bend, the arms swing).

const CLIPS = {desk_type: "desk_type_ik", desk_mouse: "desk_mouse_ik", desk_watch: "desk_watch", stand: "room_window",
  walk: "room_walk", sit_down: "room_sit_down", stand_up: "room_stand_up", bed_lie: "room_bed_lie", bed_wake: "room_bed_wake",
  eat: "room_eat", read: "room_read", phone: "room_phone", phone_scroll: "room_phone_scroll", drink: "room_drink", door: "room_door", window: "room_window",
  bedtime: "room_bedtime"};
// the room (main): keycaps (G10d) centre, top y, turn about y, size; the mouse centre on the pad; the desk / pad top
const ROOM = {keys: {c: [-1.070, 1.001, -0.976], ry: 0.06, w: 0.356, d: 0.134}, mouse: [-0.755, 0.973, -0.950], pad: 0.973};
// the clips' frame (root at the feet, facing +z; measured in the page: the recorded wrists sit on the README's pins in
// it): the keyboard the typing was pinned to (keycaps' centre at KEYTOP; the wrists' pins (0.03 / -0.13, 0.878, 0.32)
// lie over its near half) and the mouse dome's hump (on DESK_Y), from preview/mh-motion's README. G2's clips (clips_g2)
// sit the typing and the mouse higher (DY 0.032 at 4f1f995, on the 0.52 m seat); measured in the page, raising the clip's
// keyboard and mouse by 2.6 cm puts the pressing fingertips 2-5 mm over the keycaps
const DY = 0.026;
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
  // the hips for the page's own table (HIPS: where it puts his root so the hips land on a seat, the bed, a spot). G14
  // tuned v5's seat placement (env.seatIn, the chair rolled in, the hips centred) while char_v5.js still hung the Hip
  // under its turned group, i.e. against these values turned back into that group's frame; env.pageHips does that turn,
  // so the page places him exactly as tuned. boy_mh.js's own sums (the segments, the re-rooted get-up, the bed's
  // placements) use hipsAt, in the body's frame like its sampler
  const pageHips = (clip, at) => env.pageHips ? env.pageHips(hipsAt(clip, at)) : hipsAt(clip, at);
  // a clip's pose at a time, in its own frame (the root at the feet): the hips' and the head's positions
  function sampler(clip) {
    const mx = new THREE.AnimationMixer(env.boy), a = mx.clipAction(clip); a.play();
    const B = env.bones, out = t => { a.time = t; mx.update(0); env.boy.updateMatrixWorld(true);
      const loc = n => env.boy.worldToLocal(B[n].getWorldPosition(V()));
      return {t, hips: loc("Hips"), head: loc("Head"), knee: loc("LeftLeg").add(loc("RightLeg")).multiplyScalar(0.5),
        foot: Math.max(loc("LeftFoot").y, loc("RightFoot").y), fl: loc("LeftFoot").y, fr: loc("RightFoot").y, hand: Math.max(loc("LeftHand").y, loc("RightHand").y),
        feet: loc("LeftFoot").add(loc("RightFoot")).add(loc("LeftToeBase")).add(loc("RightToeBase")).multiplyScalar(0.25)}; };
    out.done = () => { a.stop(); mx.uncacheRoot(env.boy); };
    return out;
  }
  function segments(got) {
    const scan = (clip, dt = 0.05) => { const s = sampler(clip), r = []; for (let t = 0; t <= clip.duration + 1e-6; t += dt) r.push(s(Math.min(t, clip.duration))); s.done(); return r; };
    const S = {};
    // sit_down: the last moment the hips are still high (standing) before they drop onto the seat
    const sd = scan(got.sit_down); let i = sd.length - 1; while (i > 0 && sd[i].hips.y < 0.80 * M.k) i--;
    S.sit = {from: Math.max(0, sd[i].t - 0.3), to: got.sit_down.duration};
    // the chair's seat centre in sit_down's frame: where it leaves the hips, less where stand_up starts them (its seat at 0, 0)
    const su = sampler(got.stand_up), h0 = su(0).hips; su.done();
    S.seatDown = [sd[sd.length - 1].hips.x - h0.x, sd[sd.length - 1].hips.z - h0.z];
    // bed_lie: on the edge = hips low with the head up; lying = the head low
    const bl = scan(got.bed_lie);
    const e0 = bl.find(p => p.hips.y < 0.80 * M.k && p.head.y > 1.05 * M.k) || bl[Math.floor(bl.length / 3)];
    const l0 = bl.find(p => p.t > e0.t && p.head.y < 1.0 * M.k) || bl[Math.floor(bl.length * 2 / 3)];
    // sitting on the edge: the middle of the stretch where he sits upright with his feet down (before they swing up to lie)
    const up = bl.filter(p => p.t >= e0.t && p.t <= l0.t && p.hips.y < 0.76 * M.k && p.head.y > 1.3 * M.k && p.foot < 0.3), sat = up.length ? up[up.length >> 1] : e0;
    S.lie = {stand: Math.max(0, e0.t - 1.6), edge: sat.t, end: got.bed_lie.duration, endPose: bl[bl.length - 1]};
    // bed_wake: lying -> sitting up (head high again) -> standing (hips high)
    const bw = scan(got.bed_wake);
    const s0 = bw.find(p => p.head.y > 1.05 * M.k && p.hips.y < 0.80 * M.k) || bw[Math.floor(bw.length / 3)];
    S.wake = {sat: Math.min(s0.t + 0.6, got.bed_wake.duration), end: got.bed_wake.duration, startPose: bw[0]};
    // the bed's placement: the lying pose turned so the head points toward the headboard, the hips on the duvet
    S.bedLie = bedPlace(S.lie.endPose); S.bedWake = bedPlace(S.wake.startPose);
    // on the edge: the clip's bed is not laid out like the room's, so the sitting moments get their own placement
    const atT = (r, t) => r.reduce((b, q) => Math.abs(q.t - t) < Math.abs(b.t - t) ? q : b);
    S.lieEdge = edgePlace(atT(bl, S.lie.edge)); S.wakeEdge = edgePlace(atT(bw, S.wake.sat));
    // room_bedtime (the late "go to sleep"): seated stretch -> up at the chair; walk in -> on the edge; -> lying. Its chair
    // and bed are not this room's (2.4 m apart, here 1.6 m): the first part plays at the room's chair, the page walks him
    // across, and the rest plays at the bed's edge and on the duvet, placed like room_bed_lie's
    if (got.bedtime) {
      const bt = scan(got.bedtime), up = bt.find(p => p.hips.y > 0.9 * M.k) || bt[Math.floor(bt.length / 4)];
      const e1 = bt.find(p => p.t > up.t + 2 && p.hips.y < 0.80 * M.k && p.head.y > 1.05 * M.k) || bt[Math.floor(bt.length / 2)];
      const l1 = bt.find(p => p.t > e1.t && p.head.y < 1.0 * M.k) || bt[Math.floor(bt.length * 3 / 4)];
      const sit = bt.filter(p => p.t >= e1.t && p.t <= l1.t && p.head.y > 1.3 * M.k && p.foot < 0.3), on = sit.length ? sit[sit.length >> 1] : e1;
      const s0 = bt[0], face = Math.atan2(s0.knee.z - s0.hips.z, s0.knee.x - s0.hips.x);
      const su0 = sampler(got.stand_up), h0 = su0(0).hips; su0.done();
      S.bt = {up: up.t, walk: Math.max(up.t + 0.5, e1.t - 1.6), edge: on.t, end: got.bedtime.duration,
        seat: [s0.hips.x - h0.x, s0.hips.z - h0.z], face, edgePl: edgePlace(on), lie: bedPlace(bt[bt.length - 1])};
    }
    // the get-up (room_bedtime, re-rooted as seated at the desk: see getupClips): seated (the stretch first after a long
    // sit) -> up (the hips over 0.9 m, times M.k) -> turning while he walks off over about three steps -> walking straight. Its
    // moments from the clip's own poses: the chair rolls back under him from 2.0 to 1.0 s before the hips are up (they
    // start rising at 1.1 s), his legs push it on until 0.2 s after, he turns from 0.9 s to 3.1 s after, walks by 3.7 s.
    // Two of them: as recorded (he turns to his left) and mirrored (to his right)
    if (got.getupL) {
      const W = (() => { const w = sampler(got.walk), r = []; for (let t = 0; t < got.walk.duration; t += 1 / 30) r.push(w(t)); w.done(); return r; })();
      for (const side of ["L", "R"]) {
        const s = sampler(got["getup" + side]), R = [], dt = 1 / 30; let up = null;
        for (let t = 0; t <= got.bedtime.duration; t += dt) { const p = s(t); R.push(p); if (!up && p.hips.y > 0.9 * M.k) up = t; if (up && t > up + 4.2) break; }
        s.done();
        const at = t => R[Math.min(R.length - 1, Math.round(t / dt))], d = p => p.fl - p.fr;
        // where the walk loop may take over (after two, three or four steps), each with the loop's moment whose feet match
        // the get-up's as it takes over (the foot heights and their change)
        const ends = [2.2, 2.9, 3.7].map(k => { const end = up + k, e = at(end - 0.4), slope = d(at(end - 0.4 + dt)) - d(e);
          let best = 0, bc = 1e9; W.forEach((p, i) => { const q = W[(i + 1) % W.length], c = (d(p) - d(e)) ** 2 + 9 * ((d(q) - d(p)) - slope) ** 2; if (c < bc) { bc = c; best = i; } });
          return {end, phase: best * dt}; });
        // (from the desk it starts once the seated stretch is over: 0.4 s after his hands were last over his head; the chair
        // rolls back from then on)
        let st0 = 0; R.forEach((p, k) => { if (k * dt < up && p.hand > p.head.y) st0 = k * dt + 0.4; });
        const start = Math.max(up - 2.1, Math.min(st0, up - 1.2));
        S["gu" + side] = {side, rows: R, dt, up, start, stand: up + 0.8, ride: [Math.max(up - 2.0, start), up - 1.0], push: [up - 0.9, up + 0.2],
          turn: [up + 0.9, up + 3.1], ends, end: ends[ends.length - 1].end};
      }
    }
    return S;
  }
  // a clip mirrored left <-> right (the rig is symmetric with every bone world-aligned at rest: a local turn (x, y, z, w)
  // mirrors to (x, -y, -z, w) on the other side's bone, a position's x flips)
  function mirrorClip(clip, name) {
    const B = env.bones, mir = n => { const m = /Left/.test(n) ? n.replace("Left", "Right") : /Right/.test(n) ? n.replace("Right", "Left")
      : /L$/.test(n) ? n.slice(0, -1) + "R" : /R$/.test(n) ? n.slice(0, -1) + "L" : n; return B[m] ? m : n; };
    const tracks = clip.tracks.map(tr => { const i = tr.name.lastIndexOf("."), bone = tr.name.slice(0, i), prop = tr.name.slice(i + 1), v = tr.values.slice();
      if (prop === "quaternion") for (let k = 0; k < v.length; k += 4) { v[k + 1] = -v[k + 1]; v[k + 2] = -v[k + 2]; }
      else if (prop === "position") for (let k = 0; k < v.length; k += 3) v[k] = -v[k];
      return new tr.constructor(mir(bone) + "." + prop, tr.times.slice(), v); });
    return new THREE.AnimationClip(name, clip.duration, tracks);
  }
  // a clip turned about y by r and moved by (dx, dz) in his frame (the hips carry the whole body: rest-aligned, a root bone)
  function rerootClip(clip, r, dx, dz) {
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), r), p = new THREE.Quaternion();
    for (const tr of clip.tracks) { const v = tr.values;
      if (tr.name === "Hips.position") for (let k = 0; k < v.length; k += 3) { const x = v[k], z = v[k + 2]; v[k] = x * Math.cos(r) + z * Math.sin(r) + dx; v[k + 2] = -x * Math.sin(r) + z * Math.cos(r) + dz; }
      else if (tr.name === "Hips.quaternion") for (let k = 0; k < v.length; k += 4) { p.fromArray(v, k).premultiply(q); p.toArray(v, k); } }
    return clip;
  }
  // the get-ups: room_bedtime as recorded and mirrored, each re-rooted so its seated pose sits where the desk clips' does
  // (facing +z, the hips over the same spot): from the desk he goes straight into it, no root jump, no turn of the frame
  const GETUP_FWD = 0.05;                                      // (its recorded chair's back was further back: his clears this one's in the stretch)
  function getupClips(got) {
    const hd = hipsAt(got.desk_watch, 0);
    for (const [side, c] of [["L", got.bedtime.clone()], ["R", mirrorClip(got.bedtime, "room_getup_R")]]) {
      c.name = "room_getup_" + side;
      const s = sampler(c); let t = 0; while (t < c.duration && s(t).hips.y <= 0.9 * M.k) t += 0.1; const p = s(Math.max(0, t - 2.1)); s.done();
      const face = Math.atan2(p.knee.z - p.hips.z, p.knee.x - p.hips.x), r = face - Math.PI / 2;
      const hx = p.hips.x * Math.cos(r) + p.hips.z * Math.sin(r), hz = -p.hips.x * Math.sin(r) + p.hips.z * Math.cos(r);
      got["getup" + side] = rerootClip(c, r, hd[0] - hx, hd[2] - hz + GETUP_FWD);
    }
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
    // (the clips' folder and their fit to the body come from the page: room/mh as recorded, room/mh_v5 for v5 through char_v5.js)
    await Promise.all(Object.entries(CLIPS).map(([k, f]) => env.load(`${env.clipDir || "room/mh"}/${f}.glb`).then(g => { got[k] = env.fixClip ? env.fixClip(g.animations[0]) : g.animations[0]; },
      e => { throw new Error(`${env.clipDir || "room/mh"}/${f}.glb: ${e && e.message || e}`); })));   // (which clip is missing: all are needed)
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
    // the heights in segments() and getupClips() ("the hips over 0.9 m", the head over 1.05 m, ...) are the MakeHuman
    // body's (its hips 0.977 m up, walking): scaled to this body's by its own walking hips (v5's are about 0.87 m up, so they
    // never passed 0.9 m and the get-up from the desk started at room_bedtime's seated stretch, the arms up)
    M.k = hipsAt(got.walk, 0)[1] / 0.977;
    if (got.bedtime) getupClips(got);
    // the transitions' moments, from the clips' own poses: on the bed edge (hips low, head up), lying (head low)
    const seg = segments(got);
    M.seg = seg; M.sampler = sampler;                          // (?debug: a clip's hips, head, knees and feet at a time)
    const stand = stillClip("mh_stand", got.stand, 0), lie = stillClip("mh_lie", got.bed_lie, got.bed_lie.duration),
      edge = stillClip("mh_edge", got.bed_lie, seg.lie.edge);
    for (const k of ["desk_type", "desk_mouse", "desk_watch"]) { M.actions[k] = make(got[k]); H[k] = pageHips(got[k], 0); }
    M.actions.stand = make(stand); H.mh_stand = pageHips(stand, 0);
    // the walk as recorded: knees and elbows bend and the arms swing (the owner: "più liberi"); the paths keep him clear
    M.actions.walk = make(got.walk); H.room_walk = pageHips(got.walk, 0);
    M.actions.lie = make(lie); H.mh_lie = pageHips(lie, 0);
    M.actions.edge = make(edge); H.mh_edge = pageHips(edge, 0);
    for (const k of ["sit_down", "stand_up", "bed_lie", "bed_wake", "bedtime", "getupL", "getupR"]) { if (!got[k]) continue; const a = M.actions[k] = make(got[k]); a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
    // every slot the page plays: seated at the desk -> relaxed in the chair, on the bed's edge -> the edge, standing ->
    // the stand, walking -> the walk loop (the page scales it to his speed), lying -> the lie
    const seated = ["sit", "dine", "eat", "type"], onEdge = ["edge", "phone_sit"], upright = ["idle", "stand", "lean", "deliver", "phone_stand", "door"],
      lying = ["sleep", "phone_lie", "listen", "lie_phone"];
    for (const k of seated) { A[k] = M.actions.desk_watch; H[k] = H.desk_watch.slice(); }
    // eating at the desk: room_eat (the food to his lips); the other activity clips play in the preview showcase (show())
    for (const k of ["eat", "read", "phone", "phone_scroll", "drink", "door", "window"]) { M.actions["act_" + k] = make(got[k]); H["act_" + k] = pageHips(got[k], 0); }
    for (const k of ["dine", "eat"]) { A[k] = M.actions.act_eat; H[k] = H.act_eat.slice(); }
    for (const k of onEdge) { A[k] = M.actions.edge; H[k] = H.mh_edge.slice(); }
    for (const k of upright) { A[k] = M.actions.stand; H[k] = H.mh_stand.slice(); }
    A.walk = M.actions.walk; H.walk = H.room_walk.slice(); if (env.setStride) env.setStride(WALK_V);
    for (const k of lying) { A[k] = M.actions.lie; H[k] = H.mh_lie.slice(); }
    if (seg.bt) {                                             // asleep: lying as room_bedtime ends (it is how he got there)
      const sl = stillClip("mh_sleep", got.bedtime, got.bedtime.duration); M.actions.sleep = make(sl); H.mh_sleep = pageHips(sl, 0);
      A.sleep = M.actions.sleep; H.sleep = H.mh_sleep.slice(); }
    for (let i = 0; i < 600 && !(env.chairNode && env.chairNode()); i++) await new Promise(r => setTimeout(r, 100));   // (the room may still be loading)
    { const sp = sampler(stand); M.standFeet = sp(0).feet; sp.done(); }     // (he turns on the spot about his feet, not the root)
    raiseChair(); seatHeight(); props();
    for (const a of Object.values(M.actions)) a.stop();
    mixer.stopAllAction();
    const first = A[env.state().want] || M.actions.stand; first.reset().setEffectiveWeight(1).play(); env.setCurrent(first);
    env.resnap();                                            // placed for the old clips: again, with these hips
    if (seg.guL && env.flow && env.chairPose) env.flow(true);   // leaving the desk: one take (flow())
    M.ready = true;
  }
  // the page puts the root at the seat anchor less the clip's hips; the MakeHuman clips have the feet at y = 0, so the
  // seated slots' hip height is the seat anchor's height over the floor: the root (his feet) stays on the floor
  // G2's seated clips all sit on a 0.52 m seat (preview/mh-motion 4f1f995): the room's chair (seat top 0.504 m) is raised
  // 1.6 cm at the gas lift: every vertex above 0.30 m (the seat, the back, the armrests) moves up, the lift's column stretches
  // (v5 on the live room keeps the live chair: env.seatUp 0)
  const SEAT_UP = env.seatUp ?? 0.016, LIFT_CUT = 0.30;
  function raiseChair() {
    const n = env.chairNode && env.chairNode(); if (!n || n.userData.raised || !SEAT_UP) return;
    n.updateMatrixWorld(true); const v = V(), floor = env.F;
    n.traverse(o => { if (!o.isMesh) return;
      const g = o.geometry.clone(), A = g.attributes.position, f = new Float32Array(A.count * 3), inv = o.matrixWorld.clone().invert();
      for (let i = 0; i < A.count; i++) { v.fromBufferAttribute(A, i).applyMatrix4(o.matrixWorld);
        if (v.y > floor + LIFT_CUT) v.y += SEAT_UP; v.applyMatrix4(inv); f.set([v.x, v.y, v.z], 3 * i); }
      g.setAttribute("position", new THREE.BufferAttribute(f, 3)); g.computeBoundingBox(); g.computeBoundingSphere(); o.geometry = g; });
    n.userData.raised = true; if (env.chairChanged) env.chairChanged();
  }
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
    for (const k of ["sit", "type"]) env.actions[k] = a;   // the page's own play("sit") then keeps this mode
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
  // the right hand over a separate room mouse (on its way between the keys and the mouse): its tips, knuckles and palm
  // (60% from the wrist to the middle knuckle) stay over the mouse's shell, by their half thickness (8 / 12 / 20 mm)
  const _ray = new THREE.Raycaster(), _dn = V(0, -1, 0), _o = V();
  function overMouse(side) {
    if (side !== "Right" || !P.mouseNode) return -1;
    const B = env.bones, s = "R", f = n => B[n + s] || B[n + "." + s], pts = [];
    for (const b of tipNames(side)) pts.push([b, 0.008]);
    for (let i = 1; i <= 5; i++) if (f(`finger${i}-1`)) pts.push([f(`finger${i}-1`), 0.012]);
    let need = -1;
    for (const [b, r] of pts) need = Math.max(need, shell(b.getWorldPosition(_a), r));
    const hand = B.RightHand, kn = f("finger3-1");
    if (hand && kn) need = Math.max(need, shell(hand.getWorldPosition(_a).lerp(kn.getWorldPosition(_b), 0.6), 0.02));
    return need;
  }
  function shell(p, r) {                                     // how far p (r thick) is into the mouse's shell under it
    _ray.set(_o.set(p.x, p.y + 0.3, p.z), _dn); _ray.far = 0.6;
    const x = _ray.intersectObject(P.mouseNode, true)[0];
    return x ? x.point.y - (p.y - r) : -1;
  }
  function pin(side, delta, floor, weight, fit) {            // the recorded wrist + delta, lifted until no tip is under the floor
    const hand = env.bones[side + "Hand"]; if (!hand || weight <= 0) return;
    const w0 = hand.getWorldPosition(V()), t = w0.clone().add(delta), q0 = hand.getWorldQuaternion(new THREE.Quaternion());   // (the clip's hand turn)
    const keepTurn = () => { const pq = hand.parent.getWorldQuaternion(new THREE.Quaternion()).invert(); hand.quaternion.slerp(pq.multiply(q0), weight); hand.updateMatrixWorld(true); };
    for (let it = 0; it < (fit ? 5 : 3); it++) {
      ccd(side, t, weight); keepTurn();
      if (fit) { const d = fit(); if (d.length() <= 0.001) break; t.addScaledVector(d, weight); continue; }
      const deficit = Math.max(floor - lowestTip(side), overMouse(side)); if (deficit <= 0.001) break;
      t.y += deficit;
    }
  }
  // the right hand ON a separate room mouse (the owner: hold it, not rest next to it; references mouse1/mouse2, a palm
  // grip): the palm lies on the shell's hump, the knuckles arch over it, and each finger is laid down, joint by joint,
  // onto the shell (or the pad beside it) until it touches it: contact, the shell the hard limit. Half thicknesses:
  // palm 16 mm (below the bones' line, wrist to middle knuckle at 60%), knuckles 11, fingers 10 (measured off his skin).
  const PALM_R = 0.016, KN_R = 0.011, FING_R = 0.010, GRIP_BACK = 0.022, GRIP_RIGHT = 0.012;
  // (the palm 2.2 cm behind the hump's top, so the fingertips end at the front edge, and 1.2 cm right of it, so index and
  // middle lie on the two buttons and the ring and little finger on the right flank, as mouse2)
  let HM = null;                                             // the shell's top as a height map in the mouse's own frame (2.5 mm)
  function shellMap() {
    const ms = P.mouseNode; ms.updateMatrixWorld(true); const g = ms.geometry; g.computeBoundingBox(); const bb = g.boundingBox.clone(), s = 0.0025;
    const nx = Math.ceil((bb.max.x - bb.min.x) / s) + 1, nz = Math.ceil((bb.max.z - bb.min.z) / s) + 1, h = new Float32Array(nx * nz).fill(NaN);
    const ray = new THREE.Raycaster(), o = V(), dn = V(0, -1, 0); let peak = -1e9; const pk = V();
    for (let i = 0; i < nx; i++) for (let k = 0; k < nz; k++) {
      const lx = bb.min.x + i * s, lz = bb.min.z + k * s; ms.localToWorld(o.set(lx, bb.max.y + 0.1, lz)); ray.set(o, dn);
      const x = ray.intersectObject(ms, false)[0]; if (!x) continue;
      const ly = ms.worldToLocal(x.point.clone()).y; h[i * nz + k] = ly; if (ly > peak) { peak = ly; pk.set(lx, ly, lz); } }
    return {bb, s, nx, nz, h, peak: pk};
  }
  const _l = V();
  function shellTop(p) {                                     // the shell's top under p (world y), null off the shell
    if (!HM) HM = shellMap();
    P.mouseNode.worldToLocal(_l.copy(p)); const i = Math.round((_l.x - HM.bb.min.x) / HM.s), k = Math.round((_l.z - HM.bb.min.z) / HM.s);
    if (i < 0 || k < 0 || i >= HM.nx || k >= HM.nz) return null; const y = HM.h[i * HM.nz + k]; if (Number.isNaN(y)) return null;
    return P.mouseNode.localToWorld(_l.set(_l.x, y, _l.z)).y;
  }
  const below = p => { const y = shellTop(p); return y == null ? P.pad : y; };   // what is under p: the shell, else the pad
  const fbone = (i, j) => env.bones[`finger${i}-${j}R`] || env.bones[`finger${i}-${j}.R`];
  const _p = V(), _n = V(), _s = V(), _e = V();
  const fwdV = () => V(Math.sin(env.boy.rotation.y), 0, Math.cos(env.boy.rotation.y));
  function palmAt(out) { return env.bones.RightHand.getWorldPosition(out).lerp(fbone(3, 1).getWorldPosition(_e), 0.6); }
  function gripFit() {                                       // the wrist's correction: palm over the hump, resting on it; no knuckle in the shell
    palmAt(_p); HM || (HM = shellMap());
    const hump = P.mouseNode.localToWorld(_n.copy(HM.peak)), f = fwdV(), d = V(hump.x - GRIP_BACK * f.x - GRIP_RIGHT * f.z - _p.x, 0, hump.z - GRIP_BACK * f.z + GRIP_RIGHT * f.x - _p.z);
    let dy = below(_p) + PALM_R - _p.y;                      // (down onto it, or up out of it)
    for (let i = 2; i <= 5; i++) { const k = fbone(i, 1); if (!k) continue; k.getWorldPosition(_s); dy = Math.max(dy, below(_s) + KN_R - _s.y); }
    return d.setY(dy);
  }
  const _sd = V(), _g = V(), _up1 = V(0, 1, 0);
  // the fingertip, measured once off his skin (the end bone's farthest vertex, less a finger's half thickness), carried
  // in the end bone's own frame so it follows that joint
  const TIP = {};
  function tipOf(i, out) {
    const b3 = fbone(i, 3);
    if (!TIP[i]) {
      const p3 = b3.getWorldPosition(V()), d = p3.clone().sub(fbone(i, 2).getWorldPosition(V())).normalize(), v = V(); let best = null, far = -1;
      env.boy.traverse(o => { if (!o.isSkinnedMesh || /_inside$/.test(o.name)) return; const P = o.geometry.attributes.position, I = o.geometry.attributes.skinIndex, W = o.geometry.attributes.skinWeight;
        for (let n = 0; n < P.count; n++) { let k0 = 0, w0 = 0; for (let k = 0; k < 4; k++) if (W.getComponent(n, k) > w0) { w0 = W.getComponent(n, k); k0 = I.getComponent(n, k); }
          if (o.skeleton.bones[k0] !== b3) continue; o.getVertexPosition(n, v).applyMatrix4(o.matrixWorld); const a = v.clone().sub(p3).dot(d); if (a > far) { far = a; best = p3.clone().addScaledVector(d, a); } } });
      if (!best) best = p3.clone().addScaledVector(d, 0.015);
      best.sub(p3).multiplyScalar(Math.max(0, 1 - FING_R / Math.max(far, 1e-3))).add(p3);   // (to the pad's centre, a half thickness back from the end)
      TIP[i] = b3.worldToLocal(best);
    }
    return b3.localToWorld(out.copy(TIP[i]));
  }
  function gap(i, j) {                                       // finger i from its joint j to the tip: the least clearance over what is under it
    let low = 1e9;
    for (let k = j; k <= 3; k++) {
      fbone(i, k).getWorldPosition(_s);
      if (k < 3) fbone(i, k + 1).getWorldPosition(_e); else tipOf(i, _e);
      _sd.subVectors(_e, _s).cross(_up1).setY(0).normalize().multiplyScalar(0.7 * FING_R);   // (across the finger: on a slope its uphill side is lower over the shell)
      for (let u = 0.25; u <= 1.0001; u += 0.25) { _p.lerpVectors(_s, _e, u);
        const top = Math.max(below(_p), below(_g.copy(_p).add(_sd)), below(_g.copy(_p).sub(_sd))); low = Math.min(low, _p.y - FING_R - top); }
    }
    return low;
  }
  const _q0 = new THREE.Quaternion(), _rq = new THREE.Quaternion(), _ax = V(), _dn2 = V(0, -1, 0);
  // the page's own turns of the right fingers, undone the next frame where the clip has not written them again (they never add up)
  const GR = new Map();
  function gripRestore() { for (const [b, r] of GR) if (r.post && b.quaternion.angleTo(r.post) < 1e-3) { b.quaternion.copy(r.pre); b.updateMatrixWorld(true); } GR.clear(); }
  function layFingers(weight) {                              // each joint bends (down) or straightens (up) until its part of the finger touches
    gripRestore(); env.bones.RightHand.updateMatrixWorld(true);
    for (let i = 1; i <= 5; i++) for (let j = 1; j <= 3; j++) { const b = fbone(i, j); if (b) GR.set(b, {pre: b.quaternion.clone(), post: null}); }
    gripTurn(weight);
    for (const [b, r] of GR) r.post = b.quaternion.clone();
  }
  function gripTurn(weight) {
    thumbOnFlank(weight);
    // index and ring set beside the middle finger (mouse2: index and middle together on the buttons, the ring beside),
    // as a fixed angle to the middle finger's line, seen from above (index 3 deg in, ring along it)
    const yawOf = i => { const b = fbone(i, 1), c = fbone(i, 2); return Math.atan2(c.getWorldPosition(_e).x - b.getWorldPosition(_s).x, _e.z - _s.z); };
    const ym = yawOf(3), dx = Math.sin(ym), dz = Math.cos(ym), o = fbone(2, 1).getWorldPosition(V()).sub(fbone(3, 1).getWorldPosition(_g));
    const side = Math.sign(dz * o.x - dx * o.z) || 1;       // (the turn that takes a line from the middle finger's toward the index knuckle's side)
    for (const [i, deg] of [[2, -3], [4, 0]]) { const b = fbone(i, 1); if (!b) continue;
      let dy = ym + side * deg * Math.PI / 180 - yawOf(i); dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      _rq.setFromAxisAngle(_up1, dy * weight); const pq = b.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
      b.quaternion.copy(pq.multiply(b.getWorldQuaternion(_q0).premultiply(_rq))); b.updateMatrixWorld(true); }
    for (let i = 2; i <= 5; i++) for (let j = 1; j <= 3; j++) {
      const b = fbone(i, j), c = j < 3 ? fbone(i, j + 1) : null; if (!b) continue;
      b.getWorldPosition(_s); (c ? c.getWorldPosition(_e) : _e.copy(_s).sub(fbone(i, j - 1).getWorldPosition(_n)).add(_s));
      _ax.subVectors(_e, _s).normalize().cross(_dn2); if (_ax.lengthSq() < 1e-8) continue; _ax.normalize();
      b.getWorldQuaternion(_q0); const pq = b.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
      const set = a => { _rq.setFromAxisAngle(_ax, a); b.quaternion.copy(pq).multiply(_rq.clone().multiply(_q0)); b.updateMatrixWorld(true); };
      let lo = j === 1 ? -0.6 : -0.15, hi = 1.2;             // (the middle and end joints barely over-straighten)
      set(lo); if (gap(i, j) < 0) { set(lo * weight); continue; }   // (in it even straightened: as far out as it goes)
      set(hi); if (gap(i, j) > 0) { set(hi * weight); continue; }
      for (let it = 0; it < 12; it++) { const m = (lo + hi) / 2; set(m); if (gap(i, j) > 0) lo = m; else hi = m; }
      set(lo * weight);
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
    if (M.w.mouse > 0.01) {
      pin("Right", dM, padFloor, M.w.mouse);                 // the recorded hand carried to the room's mouse: where it goes, the mouse goes
      if (P.mouseNode) { follow(); pin("Right", V(), padFloor, M.w.mouse, gripFit); layFingers(M.w.mouse); }   // then the hand onto the mouse
      pin("Left", dK, keyFloor, M.w.mouse);
    } else { M.grab = null; if (GR.size) gripRestore(); }
  }
  // a separate room mouse follows the recorded right palm (60% from the wrist to the middle knuckle) while he holds it
  function follow() {
    const hand = env.bones.RightHand, kn = env.bones["finger3-1R"] || env.bones["finger3-1.R"];
    if (!hand || !kn || M.w.mouse <= 0.97) { M.grab = null; return; }   // (once the hand is on it)
    hand.getWorldPosition(_hp).lerp(kn.getWorldPosition(_a), 0.6);
    if (!M.grab) M.grab = P.mouseHome.clone().sub(_hp).setY(0);
    const H0 = P.mouseHome, cl = v => Math.max(-0.06, Math.min(0.06, v));   // (it stays on the pad: within 6 cm of home)
    P.mouseNode.position.set(H0.x + cl(_hp.x + M.grab.x - H0.x), H0.y, H0.z + cl(_hp.z + M.grab.z - H0.z)); P.mouseNode.updateMatrixWorld(true);
  }
  // the thumb along the shell's left flank (mouse2): its tip on the flank 1 cm ahead of the palm, 1.5 cm over the pad
  function thumbOnFlank(weight) {
    const f = fwdV(), lt = V(f.z, 0, -f.x);                 // (his left)
    palmAt(_p); const q = _p.clone().addScaledVector(f, 0.01); let edge = null;
    for (let k = 0; k < 40; k++) { q.addScaledVector(lt, 0.002); if (shellTop(q) == null) { edge = q; break; } }
    if (!edge) return;
    const T = edge.clone().addScaledVector(lt, FING_R).setY(P.pad + 0.016);   // (the tip's pad against the flank)
    const b1 = fbone(1, 1), b2 = fbone(1, 2), b3 = fbone(1, 3); if (!b1 || !b2 || !b3) return;
    const B = b1.getWorldPosition(V()), Mid = B.clone().lerp(T, 0.5).addScaledVector(lt, 0.006).setY(Math.max(B.y, T.y) + 0.004);   // (the joint between: out from the shell, a little higher)
    const aim = (bone, from, to) => { bone.getWorldPosition(_a); _u.subVectors(from(), _a).normalize(); _v.subVectors(to, _a).normalize();
      if (_u.dot(_v) > 0.99999) return; _q.setFromUnitVectors(_u, _v); _q.slerp(new THREE.Quaternion(), 1 - weight);
      bone.parent.getWorldQuaternion(_pq); bone.quaternion.copy(_pq.invert().multiply(bone.getWorldQuaternion(_wq).premultiply(_q))); bone.updateMatrixWorld(true); };
    const tip = () => b3.getWorldPosition(_s).clone().sub(b2.getWorldPosition(_n)).multiplyScalar(0.8).add(b3.getWorldPosition(_e));
    aim(b1, () => b2.getWorldPosition(V()), Mid); aim(b2, tip, T); aim(b3, tip, T);
  }
  // watching (or just sitting, eating): relaxed in the chair he leans back, a little further from the desk: he and the
  // chair roll 0.12 m back, and in again for the keys and the mouse (to 8.5 cm back for the keys, 6 for the mouse: the hoodie's front clears the desk's edge)
  function roll(dt) {
    const lap = M.sc && ["read", "phone", "phone_scroll"].includes(M.sc.k);   // (a book or a phone on his lap: clear of the desk)
    // env.seatIn (v5: 0.06): G14's v5 clips sit him that much deeper on the seat (clear of the arm pads' front ends, against
    // the backrest); he and the chair roll in by as much, so his hands stay on the keys / mouse / book and his elbows keep their angle
    const want = (lap ? 0.45 : M.mode === "desk_watch" || !M.mode ? 0.12 : M.mode === "desk_mouse" ? 0.06 : 0.085) - (env.seatIn || 0), k = 1 - Math.exp(-dt / 0.35);
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
  function chairPlace(off, face) {                           // the root for a clip whose seat centre is at off (x, z), on the room's chair
    const ch = env.chairNode && env.chairNode(); if (!ch) return null;   // (face: the way the seated clip faces, in its frame; +z if not given)
    ch.updateMatrixWorld(true); const p = ch.getWorldPosition(V()), cry = ch.rotation.y;
    let r = Math.atan2(-Math.sin(cry), -Math.cos(cry));                 // the way a person on it faces
    if (face != null) r = face - Math.atan2(Math.cos(r), Math.sin(r));   // (a local direction at angle a ends at a - ry in the room)
    const c = Math.cos(r), s = Math.sin(r);
    return {ry: r, x: p.x - (off[0] * c + off[1] * s), z: p.z - (-off[0] * s + off[1] * c)};
  }
  function transitionFor(S) {
    if (!S || S.k !== "pose" || S.t == null) return null;
    const G = M.seg, to = S.to, from = S.from, g = env.state().goal, B = G.bt;
    if (S.flow && G.guL && !to && from === "desk") {            // up from the desk and away: one take (see flow())
      const sleepy = g && g.clip === "sleep", U = G.guL;          // (both sides share the clip's timing)
      return {k: "getup", flow: true, a: S.stiff || sleepy ? 0 : U.start, b: S.next ? U.end : U.stand}; }
    if (B && g && g.clip === "sleep" && g.anchor === "bedlie") {          // going to sleep: room_bedtime
      if (!to && from === "desk") return {k: "bedtime", a: 0, b: B.up, at: () => chairPlace(B.seat, B.face), back: true};
      if (to === "bedside" && from !== "bedlie") return {k: "bedtime", a: B.walk, b: B.edge, at: () => B.edgePl};
      if (to === "bedlie" && from === "bedside") { const h = u => hipsAt(M.clips.bedtime, B.edge + (B.end - B.edge) * u);
        return {k: "bedtime", a: B.edge, b: B.end, at: u => mixPlace(B.edgePl, B.lie, sstep(0.1, 0.7, u), h(u))}; }
    }
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
  // Up from the desk and away in one take (the owner: no standing still to turn round, no chair put back by itself).
  // Seated, he and the chair roll back and swivel toward the side he leaves by; his legs push the chair on as he rises
  // (back, and to the other side) and it stays there; his hips then follow the clip's own travel, its heading turned a
  // little more or less while he turns and walks (W, spread over those steps) so he leaves toward the page's next
  // waypoint; over the last 0.4 s the walk loop takes over at the moment whose feet match, the root moving under his
  // hips, and the page walks on from there. The room is tight (the bed 30-60 cm behind the chair, the plant on its left,
  // the desk in front): of the two get-ups (turning left, turning right) and a few swivels and pushes, the one needing
  // the smallest W whose hips keep off the desk and the furniture, whose walk-off passes the pushed chair, and from
  // whose end the page's path to the next waypoint is clear with the chair where he left it. Where no push leaves a way
  // (the window sill: its only way is the 30 cm gap behind the chair), the path is planned with the chair parked under
  // the desk and he shoves it there in passing (shove(): a hand on it for 0.35 s, it rolls on by itself; he never stops)
  const rotXZ = (h, r) => [h[0] * Math.cos(r) + h[1] * Math.sin(r), -h[0] * Math.sin(r) + h[1] * Math.cos(r)];
  const CHAIR_R = 0.33, BODY_R = 0.17, LEG_PUSH = 0.05;       // the chair's footprint (a circle), half his width, his legs' last push
  function flowPlan(S, T0, G, swivel, back, side, after, end) {
    const T = {a: T0.a, b: end ? end.end : T0.b}, turn = [G.turn[0], Math.min(G.turn[1], T.b - 0.3)];
    const R = G.rows, n = Math.max(1, Math.ceil((T.b - T.a) / G.dt)), b = env.boy, ch = env.chairNode();
    const hAt = t => { const f = Math.min(R.length - 1, Math.max(0, t / G.dt)), i = Math.floor(f), j = Math.min(R.length - 1, i + 1), k = f - i;
      return [R[i].hips.x + (R[j].hips.x - R[i].hips.x) * k, R[i].hips.z + (R[j].hips.z - R[i].hips.z) * k]; };
    const hw = [env.HIPS.walk[0], env.HIPS.walk[2]], r0 = b.rotation.y, x0 = b.position.x, z0 = b.position.z;
    const c0 = [ch.position.x, ch.position.z, ch.rotation.y], bk = [-Math.sin(r0), -Math.cos(r0)], rt = [-Math.cos(r0), Math.sin(r0)], v = [x0 - c0[0], z0 - c0[1]];
    const ride = back, sw = Math.sign(swivel);                     // (rt: his right as he sits; side > 0 pushes it to his right)
    const legs = t => { const e = sstep(G.ride[0], G.ride[1], t), e2 = sstep(G.push[0], G.push[1], t), d = ride * e + LEG_PUSH * e2;
      return [c0[0] + bk[0] * d + rt[0] * side * e2, c0[1] + bk[1] * d + rt[1] * side * e2, c0[2] + swivel * e + sw * 0.15 * e2]; };
    const chairAt = legs, cEnd = chairAt(T.b), home = after && env.chairHome ? env.chairHome() : null, cWay = home || cEnd;
    const why = {desk: 0, room: 0, chair: 0, bed: 0};
    { const into = c => Math.max(0, ...env.boxes().map(([x0, x1, z0, z1], i) => i === 1 || i === 2 ? 0     // (how deep its footprint is in the bed,
        : CHAIR_R - Math.hypot(Math.max(x0 - c[0], 0, c[0] - x1), Math.max(z0 - c[1], 0, c[1] - z1))));        //  the shelf, the fridge, the plant)
      if (into(chairAt(T.b)) > into(c0) + 0.02) why.bed = 50; }                                                  // (pushed no deeper than it was)
    const build = W => { const out = []; let hx = 0, hz = 0, hp = null, bad = why.bed; for (const k of ["desk", "room", "chair"]) why[k] = 0;
      for (let i = 0; i <= n; i++) { const t = T.a + (T.b - T.a) * i / n, h = hAt(t);
        let ry, rx, rz;
        if (t <= G.ride[1]) {                                   // riding the chair: his root turns and moves with it
          const e = sstep(G.ride[0], G.ride[1], t), dr = swivel * e, rv = rotXZ(v, dr);
          ry = r0 + dr; rx = c0[0] + bk[0] * ride * e + rv[0]; rz = c0[1] + bk[1] * ride * e + rv[1];
          const r = rotXZ(h, ry); hx = rx + r[0]; hz = rz + r[1];
        } else {                                                // on his feet: the hips' own travel, its heading turned by W
          ry = r0 + swivel + W * sstep(turn[0], turn[1], t);
          if (!hp) { hp = h; const r = rotXZ(h, ry); hx = x0 + r[0]; hz = z0 + r[1]; }   // (a clip whose ride ends before the take starts: on his feet from where he is)
          const d = rotXZ([h[0] - hp[0], h[1] - hp[1]], ry); hx += d[0]; hz += d[1];
          const r = rotXZ(h, ry); rx = hx - r[0]; rz = hz - r[1];
          if (t > G.up - 1.1 && env.blocked(hx, hz, t < G.up + 0.5 ? 0.14 : BODY_R)) { bad++; why[t < G.up + 0.5 ? "desk" : "room"]++; }  // (rising: the belly clear of the desk)
          if (t > G.up + 1.0) { const c = chairAt(t); if (Math.hypot(hx - c[0], hz - c[1]) < CHAIR_R + BODY_R - 0.08) { bad++; why.chair++; } } }   // (his hips past the seat's edge)
        hp = h; const rw = rotXZ(hw, ry); out.push([rx, rz, ry, hx - rw[0], hz - rw[1]]); }
      return {out, bad}; };
    let W = 0, P = build(0), way = true, be = 0, left = 9;
    if (S.next && env.chairRoute) {                            // the turn W that leaves him walking toward the next waypoint
      const e0 = hAt(T.b - 0.4), e1 = hAt(T.b), ac = Math.atan2(e1[0] - e0[0], e1[1] - e0[1]);
      const err = W => { const B = build(W), L = B.out[n], q = env.chairRoute([L[3], L[4]], S.next, cWay).pts[0], want = Math.atan2(q[0] - L[3], q[1] - L[4]);
        return Math.abs(Math.atan2(Math.sin(want - r0 - swivel - W - ac), Math.cos(want - r0 - swivel - W - ac))); };
      be = 1e9; for (let w = -1.2; w <= 1.2001; w += 0.1) { const e = err(w); if (e < be) { be = e; W = w; } }
      for (const d of [-0.05, -0.025, 0.025, 0.05]) { const e = err(W + d); if (e < be) { be = e; W += d; } }
      P = build(W); const L = P.out[n], rt = env.chairRoute([L[3], L[4]], S.next, cWay); way = rt.ok;
      left = 0; let p = [L[3], L[4]]; for (const q of rt.pts) { left += Math.hypot(q[0] - p[0], q[1] - p[1]); p = q; } }   // (the walk left after it)
    return {G, n, W, a: T.a, b: T.b, phase: end ? end.phase : 0, arr: P.out, bad: P.bad, why: {...why}, way, chairAt, swivel, back, side, shove: home, err: be, left,
      cost: Math.abs(W) + 2 * be + P.bad * 0.1 + (way ? 0 : 20) - 0.3 * (back + Math.abs(side)) + (home ? 1 : 0) + (left < 0.5 ? 3 * (0.5 - left) : 0)};
  }
  // the chair shoved in in passing: once his near hand can reach its backrest or an armrest (from the shoulder, 0.65 m),
  // the hand goes to it (0.15 s), pushes for 0.35 s while the chair speeds up, lets go, and the chair rolls on to its
  // place under the desk, slowing over 0.9 s (a constant push, then rolling friction); he walks on all the while
  const GRIPS = [[0.15, 1.26, 0.36], [-0.15, 1.26, 0.36], [0.26, 0.92, 0.0], [-0.26, 0.92, 0.0]];   // (chair's frame: the backrest's top, the armrests)
  const SHOVE = {reach: 0.65, hand: 0.15, push: 0.35, roll: 0.9};
  function shove(st, dt) {
    const H = M.shove, S = st.step; if (!H) return;
    const going = S ? S.k === "walk" || (S.k === "pose" && S.flow) : !st.at;          // (between two steps: still going)
    if (!going && H.tau == null) { M.shove = null; return; }                         // (the plan changed before he got there)
    const ch = env.chairNode(); if (!ch) return; env.boy.updateMatrixWorld(true); ch.updateMatrixWorld(true);
    if (H.tau == null) {                                       // not yet: within reach?
      let bd = 1e9, pick = null;
      for (const side of ["Right", "Left"]) { const sh = env.bones[side + "Arm"].getWorldPosition(V());
        for (const g of GRIPS) { const d = sh.distanceTo(ch.localToWorld(V(...g))); if (d < bd) { bd = d; pick = [side, g]; } } }
      if (bd > SHOVE.reach || !S || (S.k === "pose" && S.t < 0.6)) return;
      H.tau = 0; H.grip = pick; H.from = [ch.position.x, ch.position.z, ch.rotation.y];
    }
    H.tau += dt;
    const s = H.tau - SHOVE.hand, ta = SHOVE.push, td = SHOVE.roll, v = 2 / (ta + td);
    const p = s <= 0 ? 0 : s < ta ? v * s * s / (2 * ta) : s < ta + td ? v * ta / 2 + v * (s - ta) - v * (s - ta) ** 2 / (2 * td) : 1;
    const f = H.from, h = H.home;
    env.chairPose(f[0] + (h[0] - f[0]) * p, f[1] + (h[1] - f[1]) * p, f[2] + Math.atan2(Math.sin(h[2] - f[2]), Math.cos(h[2] - f[2])) * p);
    const w = sstep(0, SHOVE.hand, H.tau) * (1 - sstep(SHOVE.hand + ta, SHOVE.hand + ta + 0.2, H.tau));
    if (w > 0.01) { ch.updateMatrixWorld(true); ccd(H.grip[0], ch.localToWorld(V(...H.grip[1])), w); }
    if (p >= 1 && w <= 0.01) M.shove = null;
  }
  function flow(S, T) {
    if (!S.fl) {
      if (!env.chairNode()) return false;
      let best = null;                                         // (left: swivel +, the chair pushed to his right; right: the mirror)
      const all = [];
      for (const G of [M.seg.guL, M.seg.guR]) for (const sv of [0.3, 0.6, 0.9]) {
        const sg = G.side === "L" ? 1 : -1;
        for (const E of S.next ? G.ends : [null]) for (const after of [false, true])
          for (const bk of [0.15, 0.25, 0.32]) for (const sd of [0, 0.1, 0.2]) { const P = flowPlan(S, T, G, sg * sv, bk, sg * sd, after, E); all.push(P); if (!best || P.cost < best.cost) best = P; } }
      S.fl = best; S.mhd = S.d; S.d = best.b - best.a;
      M.flowLog = {side: best.G.side, W: +best.W.toFixed(2), bad: best.bad, way: best.way, swivel: best.swivel, back: best.back, push: best.side, shove: !!best.shove,
        end: +(best.b - best.G.up).toFixed(1), err: +best.err.toFixed(2), left: +best.left.toFixed(2),
        top: all.sort((a, b) => a.cost - b.cost).slice(0, 5).map(P => [P.G.side, P.swivel, P.back, P.side, !!P.shove, +(P.b - P.G.up).toFixed(1), +P.W.toFixed(2), P.why, P.way, +P.cost.toFixed(2)])};
    }
    const F = S.fl, G = F.G, n = F.n, u = Math.min(1, Math.max(0, S.t)), f = u * n, i = Math.min(n - 1, Math.floor(f)), k = f - i, A0 = F.arr[i], A1 = F.arr[i + 1];
    const L = j => A0[j] + (A1[j] - A0[j]) * k, t = F.a + (F.b - F.a) * u;
    const win = sstep(F.a, F.a + 0.5, t), kout = sstep(F.b - 0.4, F.b, t);
    const a = M.actions["getup" + G.side]; if (!a.isRunning()) { a.reset(); a.play(); }
    a.paused = true; a.time = t; a.setEffectiveWeight(win * (1 - kout));
    if (S.A && S.A !== S.B && S.A !== a) S.A.setEffectiveWeight(1 - win);
    if (S.B) { S.B.setEffectiveWeight(kout);
      if (S.next && S.B === M.actions.walk) { S.B.timeScale = 1; S.B.time = (F.phase + Math.max(0, t - (F.b - 0.4))) % M.clips.walk.duration; } }
    const c = F.chairAt(t); env.chairPose(c[0], c[1], c[2]);
    env.mixer.update(0);
    const b = env.boy, ry = A0[2] + Math.atan2(Math.sin(A1[2] - A0[2]), Math.cos(A1[2] - A0[2])) * k;
    b.position.set(L(0) + (L(3) - L(0)) * kout, env.F, L(1) + (L(4) - L(1)) * kout); b.rotation.y = ry;
    if (F.shove && !M.shove) M.shove = {home: F.shove, from: null, tau: null};   // (the shove in passing: shove())
    if (F.shove && kout > 0.5) env.chairBlock(F.shove[0], F.shove[1]);         // (the page walks on as if it were in)
    return true;
  }
  function transition(st) {
    const S = st.step, T = transitionFor(S);
    const on = !T ? null : T.flow ? (S.fl ? "getup" + S.fl.G.side : null) : T.k;
    for (const k of ["sit_down", "stand_up", "bed_lie", "bed_wake", "bedtime", "getupL", "getupR"]) if (k !== on) { const a = M.actions[k]; if (a && (a.isRunning() || a.getEffectiveWeight() > 0)) { a.setEffectiveWeight(0); a.stop(); } }
    if (!T) return false;
    if (T.flow) return flow(S, T);
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
  // a body thicker than the clips' (v5: the hoodie, the thighs) sits higher on the seat: env.seatLift (m), seated at the
  // desk; it eases in and out over the sit-down and the stand-up (?debug: window.__seatLift overrides it)
  function seatLift(st) {
    const L = window.__seatLift ?? env.seatLift ?? 0; if (!L) return;
    const s = st.step, t = s ? Math.min(1, Math.max(0, s.t || 0)) : 0;     // (a step's t runs 0 -> 1)
    const k = st.at === "desk" && (!s || s.k === "chair") ? 1 : s && s.k === "pose" && s.to === "desk" ? t : s && s.k === "pose" && st.at === "desk" ? 1 - t : 0;
    env.boy.position.y += L * k;
  }
  function bedLift(st, dt) {
    const on = st.at === "bedlie" || st.at === "bedside" || (st.step && (st.step.to === "bedlie" || st.step.to === "bedside" || st.step.from === "bedlie" || st.step.from === "bedside"));
    if (!on && !M.lift) return;
    const b = env.boy; let need = 0, every = 3;
    if (on && !st.step) {                                      // still on the bed: every other vertex, once a second (cheap on a phone)
      M.liftT = (M.liftT || 0) - dt; if (M.liftT > 0) { b.position.y += M.lift; return; }
      M.liftT = 1; every = 2; M.lift = 0;
    }
    if (on) {
      if (!skin) { skin = []; b.traverse(o => { if (o.isSkinnedMesh && !/_inside$/.test(o.name)) skin.push(o); }); }     // every part (dressed: his clothes too; not the page's drawn inside)
      b.updateMatrixWorld(true); const v = V();
      for (const o of skin) { if (!o.visible) continue; const P = o.geometry.attributes.position;
      for (let i = 0; i < P.count; i += every) { o.getVertexPosition(i, v).applyMatrix4(o.matrixWorld);
        const e = Math.min(v.x - BED.box[0], BED.box[1] - v.x, v.z - BED.box[2], BED.box[3] - v.z);
        if (e > 0) need = Math.max(need, BED.top - (e < 0.05 ? 0.05 - Math.sqrt(0.0025 - (0.05 - e) ** 2) : 0) - v.y); } }   // (its edge is rounded, r 5 cm)
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
    if (!feet) { feet = []; b.traverse(o => { if (!o.isSkinnedMesh || /_inside$/.test(o.name)) return; const g = o.geometry, I = g.attributes.skinIndex, W = g.attributes.skinWeight, ids = [];
      for (let i = 0; i < g.attributes.position.count; i++) { let k0 = 0, w0 = 0; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > w0) { w0 = W.getComponent(i, k); k0 = I.getComponent(i, k); }
        if (/Foot|ToeBase|toe/.test(o.skeleton.bones[k0].name)) ids.push(i); }
      if (ids.length) feet.push([o, ids.filter((_, j) => j % 2 === 0)]); }); }
    b.updateMatrixWorld(true); let low = 9; const v = V();
    for (const [o, ids] of feet) for (const i of ids) { o.getVertexPosition(i, v).applyMatrix4(o.matrixWorld); if (v.y < low) low = v.y; }
    const need = Math.max(0, env.F - 0.002 - low);
    M.flift = Math.max(need, (M.flift || 0) - 0.1 * dt); if (M.flift < 1e-4) M.flift = 0;
    b.position.y += M.flift;
  }
  // in bed: the slides come off before he sits on the bed's edge (a pair parked on the floor by it, toes toward the bed,
  // their own geometry as in his bind pose: standing, feet flat) and go back on as he stands up; asleep at night the
  // page's duvet is drawn up over him to his chest (a daytime rest stays on top of it)
  const SL = {on: [], pair: null, off: false, duv: 0};
  function slidesInit() {
    env.boy.traverse(o => { if (o.isSkinnedMesh && /slide/i.test(o.name) && !/_inside$/.test(o.name)) SL.on.push(o); });
    if (!SL.on.length) return;
    const pair = new THREE.Group(), box = new THREE.Box3(), c = V();
    for (const o of SL.on) { const g = o.geometry.clone(); g.applyMatrix4(o.bindMatrix); for (const k of ["skinIndex", "skinWeight"]) g.deleteAttribute(k);
      const m = new THREE.Mesh(g, o.material); m.castShadow = m.receiveShadow = true; pair.add(m); g.computeBoundingBox(); box.union(g.boundingBox); }
    box.getCenter(c); for (const m of pair.children) m.geometry.translate(-c.x, -box.min.y, -c.z);
    pair.position.set(-0.66, env.F + 0.002, 0.08); pair.rotation.y = 0.25; pair.visible = false; pair.name = "slides_parked";
    env.scene.add(pair); SL.pair = pair;
  }
  function bedThings(st, dt) {
    if (!SL.pair && !SL.tried) { SL.tried = true; slidesInit(); }
    const S = st.step, u = S && S.t != null ? S.t : 1;
    const off = st.at === "bedlie" || st.at === "bedside" || !!(S && S.k === "pose" && (S.to === "bedlie" || S.from === "bedlie" ||
      (S.to === "bedside" && u > 0.6) || (S.from === "bedside" && !S.to && u < 0.25)));
    if (SL.pair && off !== SL.off) { SL.off = off; SL.pair.visible = off; for (const o of SL.on) o.visible = !off; }
    if (!env.cover) return;
    const asleep = !!(st.goal && st.goal.clip === "sleep") && (st.at === "bedlie" || !!(S && S.k === "pose" && S.to === "bedlie" && u > 0.8));
    SL.duv = SL.duv === 0 && asleep && st.at === "bedlie" && !S ? 1 : Math.min(1, Math.max(0, SL.duv + (asleep ? dt / 2.2 : -dt / 1.2)));
    env.cover(SL.duv, dt);
  }
  // turning on the spot (a walk or turn step before he moves off): the walk loop's full stride would swing a foot 30 cm
  // out (into the bed at the sill), so the stride shrinks with his speed: the walk blends toward the stand
  const _lp = V();
  function pivot(st, dt) {
    const S = st.step, W = M.actions.walk, St = M.actions.stand, b = env.boy;
    const speed = M.lpOk ? Math.hypot(b.position.x - _lp.x, b.position.z - _lp.z) / Math.max(dt, 1e-3) : 1;
    _lp.copy(b.position); M.lpOk = true;
    const walking = !!(S && (S.k === "walk" || S.k === "turn") && st.current === W);
    const want = walking ? Math.min(1, Math.max(0.15, speed / 0.35)) : 1;
    if (walking && !M.wasWalking) M.ww = S.flow ? 1 : 0.15;     // (from standing: the first steps are short ones; after the get-up he is mid-stride)
    M.wasWalking = walking;
    M.ww = (M.ww == null ? 1 : M.ww) + (want - (M.ww == null ? 1 : M.ww)) * (1 - Math.exp(-dt / 0.15));
    if (!walking) { M.ry0 = null; if (M.pivoting) { M.pivoting = false; if (St !== st.current) { St.setEffectiveWeight(0); St.stop(); } } M.ww = 1; return; }
    if (M.ry0 == null || M.ww > 0.99) M.ry0 = b.rotation.y;    // (where this turn on the spot started)
    if (M.ww > 0.995 && !M.pivoting) return;
    M.pivoting = M.ww <= 0.995;
    if (!St.isRunning()) { St.reset(); St.play(); }
    W.setEffectiveWeight(M.ww); St.setEffectiveWeight(1 - M.ww); env.mixer.update(0);
    // and he turns about his feet, not the root (the stand's feet are ahead of it: at the sill his toes would reach the
    // bed): his hips move by the turn of that offset (the mixer sets them anew each frame), fading out as he walks off
    const H = env.bones.Hips, f = M.standFeet; if (!H || !f) return;
    const rot = r => [f.x * Math.cos(r) + f.z * Math.sin(r), -f.x * Math.sin(r) + f.z * Math.cos(r)];
    // (halfway to the feet: the hips' swing stays clear of the chair, the toes of the bed)
    const a0 = rot(M.ry0), a1 = rot(b.rotation.y), k = 0.5 * Math.min(1, Math.max(0, (1 - M.ww) / 0.85));
    b.updateMatrixWorld(true); const w0 = H.getWorldPosition(V()), w1 = w0.clone().add(V((a0[0] - a1[0]) * k, 0, (a0[1] - a1[1]) * k));
    H.position.add(H.parent.worldToLocal(w1).sub(H.parent.worldToLocal(w0)));
  }
  // the clothes' corrective shapes (G4's morph targets on the hoodie and the trousers: seated, elbow_L/R, lying), weighted
  // each frame after the animation from the joints, by the drivers the file carries (extras.correctives)
  const CORR = {drivers: null, meshes: []};
  fetch("room/boy.glb").then(r => r.arrayBuffer()).then(buf => {
    const dv = new DataView(buf), n = dv.getUint32(12, true);
    const js = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, n)));
    CORR.drivers = ((js.extras || {}).correctives || {}).drivers || null;
  }).catch(() => {});
  const smooth = (a, b, x) => sstep(a, b, x);
  function correctives() {
    if (!CORR.drivers) return;
    if (!CORR.meshes.length) env.boy.traverse(o => { if (o.isMesh && o.morphTargetDictionary && o.morphTargetInfluences) CORR.meshes.push(o); });
    if (!CORR.meshes.length) return;
    const B = env.bones, p = n => B[n].getWorldPosition(V());
    const down = p("Hips").sub(p("neck")).normalize(), deg = (a, b) => THREE.MathUtils.radToDeg(a.angleTo(b)), w = {};
    for (const [name, d] of Object.entries(CORR.drivers)) {
      let v = 0;
      if (d.type === "hip_bend") v = (deg(p("LeftLeg").sub(p("LeftUpLeg")), down) + deg(p("RightLeg").sub(p("RightUpLeg")), down)) / 2;
      else if (d.type === "elbow_bend") v = deg(p(d.side + "ForeArm").sub(p(d.side + "Arm")), p(d.side + "Hand").sub(p(d.side + "ForeArm")));
      else if (d.type === "chest_up") v = V().crossVectors(p("LeftArm").sub(p("RightArm")), down.clone().negate()).normalize().y;
      w[name] = smooth(d.from, d.to, v);
    }
    for (const o of CORR.meshes) for (const [nm, i] of Object.entries(o.morphTargetDictionary)) o.morphTargetInfluences[i] = w[nm] || 0;
    M.corr = w;
  }
  // ---------- the activity clips' props (room/mh/props_g2.json: placeholder boxes and cylinders, real models later) ----------
  // held ones ride a hand bone (offset and turn in its frame), the others stand in the clip's own frame (a child of him:
  // his root is that frame); each set shows while its clip plays. The door's swing and the window's sash follow the
  // clip's keys [t, rotY, dx, dy, dz].
  const PR = {json: null, sets: {}, sash: null};
  fetch("room/mh/props_g2.json").then(r => r.json()).then(j => { PR.json = j; }).catch(() => {});
  const COLOR = w => /screen/.test(w) ? 0x6aa0ff : /phone/.test(w) ? 0x111214 : /plate/.test(w) ? 0xf2f0ea : /glass/.test(w) ? 0xcfe8f5
    : /bottle/.test(w) ? 0x6fb37a : /cover/.test(w) ? 0x9a3b30 : /page|paperback|half/.test(w) ? 0xf5f1e6 : /counter/.test(w) ? 0xb79c7e : 0xd9a35b;
  function propMesh(p) {
    const z = p.size, geo = p.shape === "cyl" ? new THREE.CylinderGeometry(z[0], z[2] != null ? z[2] : z[0], z[1], 20) : new THREE.BoxGeometry(z[0], z[1], z[2]);
    const mat = new THREE.MeshStandardMaterial({color: p.color ? Number(p.color) : COLOR(p.what || ""), roughness: p.rough != null ? p.rough : 0.6,
      transparent: p.opacity != null || /glass/.test(p.what || ""), opacity: p.opacity != null ? p.opacity : /glass/.test(p.what || "") ? 0.45 : 1,
      emissive: /screen/.test(p.what || "") ? 0x335599 : 0x000000});
    const m = new THREE.Mesh(geo, mat); m.castShadow = m.receiveShadow = true;
    if (p.rot) m.rotation.set(...p.rot.map(d => THREE.MathUtils.degToRad(d)));
    return m;
  }
  function propSet(k) {                                      // built once per clip
    if (PR.sets[k] !== undefined || !PR.json) return PR.sets[k] || null;
    const spec = PR.json["room_" + k]; if (!spec) return PR.sets[k] = null;
    const set = {held: [], world: new THREE.Group()};
    const MHB = {"wrist.L": "LeftHand", "wrist.R": "RightHand"};          // (MakeHuman's names for the room rig's)
    for (const p of spec.held || []) { const nm = MHB[p.bone] || p.bone, bone = env.bones[nm.replace(".", "")] || env.bones[nm]; if (!bone) { console.warn("prop bone", p.bone); continue; }
      const m = propMesh(p); m.position.set(...p.off); m.visible = false; bone.add(m); set.held.push(m); }
    for (const p of spec.world || []) { const m = propMesh(p); m.position.set(...p.pos); set.world.add(m); }
    set.pages = [];                                           // turning pages: hinged on the spine (a group at the pivot), turned
    for (const p of spec.pages || []) {                       // about the axis by the keys [t, deg] (0 on the right half, -160 on the left)
      const m = propMesh({...p, rot: null}); m.geometry.translate(p.size[0] / 2, 0, 0); m.rotation.set(...p.rot.map(d => THREE.MathUtils.degToRad(d)));
      const g = new THREE.Group(); g.position.set(...p.pivot); g.add(m); set.world.add(g);
      set.pages.push({g, axis: V(...p.axis).normalize(), keys: p.keys}); }
    set.world.visible = false; env.boy.add(set.world);
    return PR.sets[k] = set;
  }
  function showProps(k, on) { const set = propSet(k); if (!set) return; set.world.visible = on; for (const m of set.held) m.visible = on; }
  const keyAt = (keys, t) => { if (!keys || !keys.length) return [0, 0, 0, 0]; let i = 0; while (i < keys.length - 2 && keys[i + 1][0] <= t) i++;
    const a = keys[i], b = keys[Math.min(i + 1, keys.length - 1)], u = b[0] > a[0] ? Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))) : 0;
    return [1, 2, 3, 4].map(j => a[j] + (b[j] - a[j]) * u); };
  function props_(st) {                                      // which clip's props are out, and the door / the sash
    if (!PR.json) return;
    for (const k of ["eat", "read", "phone", "phone_scroll", "drink"]) { const a = M.actions["act_" + k]; showProps(k, !!a && a.isRunning() && a.getEffectiveWeight() > 0.5); }
    const rd = PR.sets.read, ra = M.actions.act_read;
    if (rd && rd.pages && ra && rd.world.visible) for (const pg of rd.pages) {
      const K = pg.keys, t = ra.time; let i = 0; while (i < K.length - 2 && K[i + 1][0] <= t) i++;
      const a = K[i], b = K[Math.min(i + 1, K.length - 1)], u = b[0] > a[0] ? Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))) : 0;
      const deg = t <= K[0][0] ? K[0][1] : t >= K[K.length - 1][0] ? K[K.length - 1][1] : a[1] + (b[1] - a[1]) * u;
      pg.g.quaternion.setFromAxisAngle(pg.axis, THREE.MathUtils.degToRad(deg)); }
    const sc = M.sc;
    // (the clip pulls the door toward him, rotY < 0: in this room that is a negative setDoor, the leaf's free edge to +z)
    if (sc && sc.k === "door" && env.setDoor) { const [ry] = keyAt(PR.json.room_door.anim[0].keys, sc.a.time); env.setDoor(THREE.MathUtils.degToRad(ry)); }
    if (sc && sc.k === "window") {
      const W = PR.json.room_window, an = W.anim[0];
      if (!PR.sash) { PR.sash = new THREE.Group(); for (const p of W.anim) { const m = propMesh(p); PR.sash.add(m); } env.scene.add(PR.sash); }
      const [, dx] = keyAt(an.keys, sc.a.time), b = env.boy;
      // the room's window is higher than the clip's (sill 1.11 m above the floor, the clip's 0.825): the sash sits in
      // the real opening, just inside the glass, and slides as keyed
      const loc = V(an.pivot[0] + dx, an.pivot[1] + 0.24, 1.05); b.updateMatrixWorld(true); PR.sash.position.copy(b.localToWorld(loc));
      PR.sash.rotation.y = b.rotation.y; PR.sash.visible = true;
    } else if (PR.sash) PR.sash.visible = false;
  }
  // ---------- the preview showcase (?debug: mh.show("read" | "phone" | "drink" | "door" | "window"), mh.show(null) ends it):
  // the activity clips awaiting the owner's word, played where they belong in the room ----------
  const SHOW = {read: null, phone: null, phone_scroll: null,  // at the desk, seated: where the page has him
    drink: [0.50, 0.05, 0],                                  // standing, a counter in front (the clip's own placeholder)
    door: [1.73, -0.48, Math.PI],                            // facing the door: its handle where the clip's hand reaches
    window: [-0.90, -0.06, -Math.PI / 2]};                   // facing the window between the chair and the bed
  function show(k) {
    if (M.sc) { M.sc.a.setEffectiveWeight(0); M.sc.a.stop(); if (M.sc.k === "door" && env.setDoor) env.setDoor(0); M.sc = null;
      if (!k) env.resnap(); }                                // (back where the page has him, its clip at full weight)
    if (!k || !M.actions["act_" + k]) return;
    const a = M.actions["act_" + k]; a.reset(); a.setLoop(THREE.LoopRepeat, Infinity); a.play(); M.sc = {k, a, root: SHOW[k]};
  }
  function showStep() {
    const sc = M.sc; if (!sc) return;
    const b = env.boy; if (sc.root) { b.position.set(sc.root[0], env.F, sc.root[1]); b.rotation.y = sc.root[2]; }
    for (const a of env.mixer._actions) if (a !== sc.a && a.getEffectiveWeight() > 0) a.setEffectiveWeight(0);
    sc.a.setEffectiveWeight(1); env.mixer.update(0);
  }
  // ---------- G11's hair (room/hair: ~60,000 strands grown on G2's head; preview/hair-mh): on the Head bone (its frame is
  // the bone's rest frame), the half-density LOD at room distance, lit from the room's own lights; preview/hair-mh 875d61c ----------
  const HAIR = {mesh: null, t: 9};
  function hairInit() {
    if (HAIR.tried || env.noHair) return; HAIR.tried = true;      // (v5 has its own hair)
    Promise.all([env.load("room/hair/hair_mh.glb"), import("./hair/hair_strands.js")]).then(([g, mod]) => {
      const hair = g.scene.getObjectByName("hair_mh") || g.scene, head = env.bones.Head; if (!head) return;
      hair.position.set(0, 0, 0); head.add(hair); HAIR.root = hair;
      // (half the hairs at room distance; the spine turns on the collar collider: the nape hair stays on the hood)
      HAIR.mesh = mod.useStrands(THREE, hair, {lod: 0.5, spine: env.boy.getObjectByName("Spine")});
      hair.traverse(o => { if (o.isMesh) o.castShadow = false; });
    }).catch(e => console.warn("hair:", e));
  }
  const _ld = V(), _lt = V();
  function hairLights(dt) {                                  // twice a second: the strongest directional light is the key, the next
    const m = HAIR.mesh; if (!m || !m.material || !m.material.uniforms) return;   // the rim; the hemisphere / ambient the sky and ground
    HAIR.t += dt; if (HAIR.t < 0.5) return; HAIR.t = 0;
    const U = m.material.uniforms, dirs = [], amb = new THREE.Color(0, 0, 0); let hemi = null;
    env.scene.traverse(o => { if (!o.visible) return; if (o.isDirectionalLight || o.isSpotLight) dirs.push(o); else if (o.isHemisphereLight) hemi = o;
      else if (o.isAmbientLight) amb.add(o.color.clone().multiplyScalar(o.intensity)); });
    dirs.sort((a, b) => b.intensity - a.intensity);
    const set = (L, dirU, colU) => { if (!L) { U[colU].value.setRGB(0, 0, 0); return; }
      L.getWorldPosition(_ld); (L.target ? L.target.getWorldPosition(_lt) : _lt.set(0, 0, 0)); U[dirU].value.copy(_ld.sub(_lt).normalize());
      U[colU].value.copy(L.color).multiplyScalar(Math.min(3, L.intensity * 0.6)); };
    set(dirs[0], "keyDir", "keyCol"); set(dirs[1], "rimDir", "rimCol");
    if (hemi) { U.sky.value.copy(hemi.color).multiplyScalar(hemi.intensity * 0.5).add(amb); U.ground.value.copy(hemi.groundColor).multiplyScalar(hemi.intensity * 0.5).add(amb); }
    else { U.sky.value.copy(amb); U.ground.value.copy(amb).multiplyScalar(0.6); }
  }
  function onBed(st) {                                       // lying on, or sitting on the edge of, the bed: placed by the lie clip's pose
    if (st.step || (st.at !== "bedlie" && st.at !== "bedside")) return;
    const sleep = M.seg.bt && st.goal && st.goal.clip === "sleep";
    const p = st.at === "bedlie" ? (sleep ? M.seg.bt.lie : M.seg.bedLie) : (sleep ? M.seg.bt.edgePl : M.seg.lieEdge), b = env.boy;
    b.position.set(p.x, env.F, p.z); b.rotation.y = p.ry;
  }

  // ---------- one step (instead of the page's animate: the mixer, his plan and walk, the desk modes, the wrists) ----------
  function animate(dt) {
    const moving = env.step0(dt);
    if (!M.ready) return moving;
    if (!P.kbNode || !P.mouseNode) { P.seen += dt; if (P.seen > 1) { P.seen = 0; props(); } }   // (G10d's nodes may arrive late)
    const st = env.state(), m = M.sc ? null : wanted(st);       // (the showcase plays its own clip: no desk modes, no arm pins)
    if (m) setMode(m); else if (M.mode) {                    // off the desk modes (eating, leaving): seated he just sits back
      M.mode = null; M.w.type = M.w.mouse = 0; const a = st.goal && st.goal.clip === "dine" ? M.actions.act_eat : M.actions.desk_watch, cur = st.current;
      for (const k of ["sit", "type"]) env.actions[k] = M.actions.desk_watch;
      if (st.at === "desk" && !st.step && cur !== a) { a.reset(); a.setEffectiveWeight(1); a.fadeIn(FADE).play(); if (cur) cur.fadeOut(FADE); env.setCurrent(a); }
    }
    if (!transition(st)) onBed(st);
    pivot(st, dt);
    showStep();                                                // (the showcase's clip, before the guards measure him)
    baseY(); seatLift(st); bedLift(st, dt); floorLift(dt); M.lastY = env.boy.position.y;
    shove(st, dt);                                             // (after the root is final: the hand reaches the chair where it is)
    bedThings(st, dt);
    if (st.at === "desk" && !st.step) roll(dt); else { M.off = 0; M.rollAt = null; }   // (off the desk the page places him and the chair)
    if (M.mode) hands(dt);
    props_(st); hairInit(); hairLights(dt);
    env.boy.updateMatrixWorld(true); correctives();           // (last: on the final pose)
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
  return {animate, dbg, show, M, get ready() { return M.ready; }, get mode() { return M.mode; }};
}
