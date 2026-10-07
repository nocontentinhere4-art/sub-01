// ?char=mixamo&clip=<Clip>: one of G22's standing / in-between clips (web/room/mx_standing/<Clip>.glb, baked by
// room_build/kimodo/standing_rebake.sh) played in a loop on the Mixamo-rigged character (room/char_mixamo.glb through
// char_mixamo.js), in the room, where standing_clips.meta.json and the spot table below put it. A preview entry only:
// the page's own day (the v5 body, its planner, its clips) is switched off while it runs, and without ?clip the page
// does not load this file at all.
//
// Spots: standing clips on a floor point with a heading; chair clips in the desk chair, the chair rolled back from the
// desk by the clip's own reach (its skin, every 0.1 s, by 10 cm height band) plus 3 cm, as boy_mh.js rare() does, and
// to the side; the sit-down and the stand-up with the chair where the page has it for them ("out": pulled out and
// turned); the two that get up and move about (Scared, Standing_Clap) in the chair out in the open ("open").
// Hands: a socket (an empty Object3D, "socket_R" / "socket_L", in the palm) on both hands. The phone clips carry the
// page's phone (its body and screen, not the rigid gripping hand made for the finger-less rig) on the right one, its
// screen turned to his eyes (Texting_While_Standing, two-handed: between his palms); Gaming holds the page's controller (room/controller.glb) and the tablet clip a plain
// tablet (the page has none), each between his palms, every frame.
import { prep, fixClip, pageName } from "./char_mixamo.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

// standing: x, z on the floor (y is the page's floor), heading = the world direction his +z (Mixamo's forward) turns to
export const SPOTS = {
  rug: {x: 0.45, z: -0.10, ry: -Math.PI / 2},             // the open middle of the room, on the rug, facing the window
};
// chair clips: the clip's origin (his seated hips) on this point of the chair, in its own frame (front -z); his +z
// forward is the chair's -z
// (a row's seatAt, its z, when the clip has one: how far forward on the cushion he sits, swept per clip in the room;
// his knee is 0.49 m up with the foot flat and the cushion's top 0.505 m, so further back the front edge runs into his
// thighs)
export const SEAT_AT = {x: 0, z: -0.055};
// the chair rolled back from the desk by the clip's reach, and CHAIR_DX to the side (+x), clear of the plant and the
// things on the floor beside the desk (x < -1.30, z -0.60..-0.10) that a chair rolled straight back would sit him in
const FLOOR = 0.16, DESK_FRONT = -0.84, CLEAR = 0.03, ROLL_MAX = 0.60, CHAIR_DX = 0.28;
// the chair in the open (spot "open"): on the rug, facing the shelf wall (-z), clear of the bed's corner and the props
export const CHAIR_OPEN = {x: 0.50, z: 0.10, ry: 0};

export async function start(ctx) {
  const {THREE, scene, load, clip, chairNode, chairAt, phone} = ctx;
  const [g, cg, meta] = await Promise.all([load("room/char_mixamo.glb"), load(`room/mx_standing/${clip}.glb`),
    fetch("room/mx_standing/standing_clips.meta.json").then(r => r.json())]);
  const M = meta[clip]; if (!M) throw new Error(`standing_preview: no clip ${clip}`);
  const conv = prep(THREE, g);
  const ch = g.scene; ch.traverse(o => { if (o.isMesh) { o.frustumCulled = false; o.castShadow = true; o.receiveShadow = true; } });
  const holder = new THREE.Group(); holder.name = "mx_preview"; holder.add(ch); scene.add(holder);
  const anim = fixClip(THREE, cg.animations[0], conv);                // (baked on this skeleton: no hip-height scale)
  const mixer = new THREE.AnimationMixer(ch), act = mixer.clipAction(anim); act.play();
  const bone = n => { let b = null; ch.traverse(o => { if (o.isBone && o.name === n) b = o; }); return b; };

  // where: a floor spot, or the chair rolled back by the clip's reach
  const row = M.row || {}, SP = {clip, meta: M, char: ch, holder, mixer, action: act, t: 0, duration: anim.duration};
  let roll = 0;
  // (what is under a point: the floor, or the rug's top; him and the chair left out)
  const floorAt = (x, z, skip) => { const ray = new THREE.Raycaster(new THREE.Vector3(x, 0.5, z), new THREE.Vector3(0, -1, 0)), under = [];
    scene.traverse(o => { if (o.isMesh && o.visible) { for (let q = o; q; q = q.parent) if (skip.includes(q)) return; under.push(o); } });
    const hit = ray.intersectObjects(under, false).find(h => h.point.y >= FLOOR - 0.001); return hit ? hit.point.y : FLOOR; };
  if (row.spot === "out") {
    // the chair where the page itself has it for his sit-down and stand-up: pulled out and turned (room.html chairAt(1))
    const n = chairNode(), sz = row.seatAt ?? SEAT_AT.z; const ry = chairAt(1, n.position); n.rotation.y = ry; n.updateMatrixWorld(true);
    const p = new THREE.Vector3(SEAT_AT.x, 0, sz).applyMatrix4(n.matrixWorld), feet = new THREE.Vector3(SEAT_AT.x, 0, sz - 0.45).applyMatrix4(n.matrixWorld);
    // (his feet there are on the rug's edge, the chair on the floor: he stands on what is under his feet, and the row's
    // seatTop is the cushion over that)
    const y = floorAt(feet.x, feet.z, [holder, n]);
    holder.position.set(p.x, y, p.z); holder.rotation.y = ry + Math.PI; SP.floor = +y.toFixed(4);
    SP.chair = {x: +n.position.x.toFixed(3), z: +n.position.z.toFixed(3), ry: +ry.toFixed(4), seatAt: sz, pageSitDown: true};
  } else if (row.spot === "open") {
    // the chair out in the open middle of the room (on the rug), for the clips that get up out of it and need the
    // floor in front and behind (Scared jumps up and steps back, Standing_Clap rises with his arms overhead)
    const n = chairNode(), s = CHAIR_OPEN, sz = row.seatAt ?? SEAT_AT.z;
    const y = Math.max(...[[0, 0], [0.3, 0], [-0.3, 0], [0, 0.3], [0, -0.3]].map(([dx, dz]) => floorAt(s.x + dx, s.z + dz, [holder, n])));
    n.position.set(s.x, y, s.z); n.rotation.y = s.ry; n.updateMatrixWorld(true);
    const p = new THREE.Vector3(SEAT_AT.x, 0, sz).applyMatrix4(n.matrixWorld);
    holder.position.set(p.x, y, p.z); holder.rotation.y = s.ry + Math.PI; SP.floor = +y.toFixed(4);
    SP.chair = {x: s.x, z: s.z, y: +y.toFixed(4), ry: s.ry, seatAt: sz, open: true};
  } else if (row.spot === "chair") {
    const n = chairNode(); n.updateMatrixWorld(true);
    const home = n.position.clone(), ry = n.rotation.y;
    // his body's forward-most skin over the clip (clip frame +z) -> the world (-z of the chair, ry 0): keep it off the desk
    const reach = Math.max(...Object.values(M.reach_z_by_10cm)), sz = row.seatAt ?? SEAT_AT.z;
    const front = home.z + sz - reach;                                   // (the chair at home, ry 0)
    roll = Math.min(ROLL_MAX, Math.max(0, DESK_FRONT + CLEAR - front));
    n.position.z = home.z + roll; n.position.x = home.x + CHAIR_DX; n.updateMatrixWorld(true);
    const p = new THREE.Vector3(SEAT_AT.x, 0, sz).applyMatrix4(n.matrixWorld);
    holder.position.set(p.x, FLOOR, p.z); holder.rotation.y = ry + Math.PI;
    SP.chair = {x: +n.position.x.toFixed(3), z: +n.position.z.toFixed(3), roll: +roll.toFixed(3), dx: CHAIR_DX, reach: +reach.toFixed(3), seatAt: sz};
  } else {
    const s = SPOTS[row.spot] || SPOTS.rug;
    holder.position.set(s.x, floorAt(s.x, s.z, [holder]), s.z); holder.rotation.y = s.ry; SP.floor = +holder.position.y.toFixed(4);
  }

  // the hands: a frame in each palm from its own bones (fingers along +y, the palm's normal +z, out of the palm),
  // taken on the clip's first frame; the phone on the right one
  mixer.setTime(0); holder.updateMatrixWorld(true);
  const sockets = {};
  for (const [s, x] of [["R", "Right"], ["L", "Left"]]) {
    const h = bone(`${x}Hand`), m1 = bone(`finger3-1.${s}`), m3 = bone(`finger3-3.${s}`), i1 = bone(`finger2-1.${s}`), p1 = bone(`finger5-1.${s}`);
    const w = v => v.getWorldPosition(new THREE.Vector3());
    const H = w(h), Y = w(m1).sub(H).normalize(), across = w(i1).sub(w(p1)).normalize();
    // (the palm side: the side the fingers curl towards, from the knuckle to the tip; else the index-pinky cross)
    let Z = w(m3).sub(w(m1)); Z.addScaledVector(Y, -Z.dot(Y));
    if (Z.length() < 0.004) Z = new THREE.Vector3().crossVectors(across, Y).multiplyScalar(s === "R" ? 1 : -1);
    Z.normalize(); const X = new THREE.Vector3().crossVectors(Y, Z).normalize();
    const sock = new THREE.Object3D(); sock.name = `socket_${s}`;
    const wm = new THREE.Matrix4().makeBasis(X, Y, Z).setPosition(H.clone().addScaledVector(Y, 0.055).addScaledVector(Z, 0.018));
    sock.matrix.copy(h.matrixWorld).invert().multiply(wm); sock.matrix.decompose(sock.position, sock.quaternion, sock.scale);
    h.add(sock); sockets[s] = sock;
  }
  SP.sockets = sockets;
  // the hand skin, by side (each vertex whose main bone is that hand or one of its fingers)
  const parts = []; ch.traverse(o => { if (o.isSkinnedMesh) parts.push(o); });
  const handIdx = side => parts.map(sm => { const I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight, r = [], re = new RegExp(`^(${side === "R" ? "Right" : "Left"}Hand|finger\\d-\\d\\.${side})$`);
    for (let i = 0; i < I.count; i++) { let bb = 0, bw = 0; for (let q = 0; q < 4; q++) if (W.getComponent(i, q) > bw) { bw = W.getComponent(i, q); bb = I.getComponent(i, q); }
      if (re.test(sm.skeleton.bones[bb].name)) r.push(i); } return r; });
  const eyes = () => bone("Head").localToWorld(new THREE.Vector3(0, 8, 9));       // (the head bone, in its centimetres: about his eyes)
  const T_ = []; for (let t = 0; t <= anim.duration + 1e-6; t += 0.25) T_.push(Math.min(t, anim.duration - 1e-4));
  const glass = (W, H, cards) => {                                                // a plain made-up screen: cards on a dark blue ground
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H; const x = cv.getContext("2d");
    x.fillStyle = "#16223a"; x.fillRect(0, 0, W, H); cards.forEach(([a, b, w, h, c]) => { x.fillStyle = c; x.fillRect(a * W, b * H, w * W, h * H); });
    const tx = new THREE.CanvasTexture(cv); tx.colorSpace = THREE.SRGBColorSpace; return new THREE.MeshBasicMaterial({map: tx, toneMapped: false}); };
  SP.props = [];
  // how far each prop's screen (or face) turns from his eyes over the clip, every 0.25 s
  const facing = (obj, axis) => { let worst = 0, sum = 0, in30 = 0; const n = new THREE.Vector3(), p = new THREE.Vector3();
    for (const t of T_) { mixer.setTime(t); holder.updateMatrixWorld(true); place(); obj.updateMatrixWorld(true);
      n.copy(axis).transformDirection(obj.matrixWorld); obj.getWorldPosition(p); const a = THREE.MathUtils.radToDeg(n.angleTo(eyes().sub(p)));
      worst = Math.max(worst, a); sum += a; if (a <= 30) in30++; }
    return {meanDeg: +(sum / T_.length).toFixed(1), worstDeg: +worst.toFixed(1), within30: +(in30 / T_.length).toFixed(3), samples: T_.length}; };
  let place = () => {};
  if (row.hold === "phone" && phone) {
    // the page's phone (its body, a rounded slab, and its screen; not the rigid gripping hand made for the finger-less
    // rig) on his right palm: its screen turned to his eyes (their direction in the palm's frame, averaged over the clip),
    // its long side along his fingers as far as that allows; then, as the page lifts its own phone, off the palm just
    // enough that no skin of his right hand is inside it or in front of its screen, over the whole clip
    const ph = new THREE.Group(); ph.name = "mx_phone";
    const body = phone.children[0].clone(); body.visible = true; ph.add(body);
    const scr = phone.userData.screen.mesh.clone(); scr.visible = true; ph.add(scr);
    scr.material = glass(144, 300, [[0.07, 0.07, 0.86, 0.23, "#d9e4f5"], [0.07, 0.33, 0.86, 0.13, "#8fb3e8"], [0.07, 0.49, 0.86, 0.23, "#e9d9c6"], [0.07, 0.75, 0.86, 0.13, "#8fb3e8"]]);
    const [w, h, d] = [0.078, 0.162, 0.008];
    scr.geometry = new THREE.PlaneGeometry(w * 0.92, h * 0.95); scr.position.set(0, 0, d / 2 + 0.0006);
    const S = sockets.R, inv = new THREE.Matrix4(), n = new THREE.Vector3(), v = new THREE.Vector3();
    for (const t of T_) { mixer.setTime(t); holder.updateMatrixWorld(true); inv.copy(S.matrixWorld).invert(); n.add(eyes().applyMatrix4(inv).normalize()); }
    n.normalize(); const up = new THREE.Vector3(0, 1, 0).addScaledVector(n, -n.y).normalize(), X = new THREE.Vector3().crossVectors(up, n);
    const PY = 0.02, base = new THREE.Vector3(0, PY, 0); ph.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, up, n)); ph.position.copy(base);
    S.add(ph); ph.updateMatrixWorld(true);
    const idx = handIdx("R"); let top = -0.02;
    for (const t of T_) { mixer.setTime(t); holder.updateMatrixWorld(true); inv.copy(ph.matrixWorld).invert();
      parts.forEach((sm, pi) => { for (const i of idx[pi]) { sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld).applyMatrix4(inv);
        if (Math.abs(v.x) < w / 2 && Math.abs(v.y) < h / 2) top = Math.max(top, v.z); } }); }
    ph.position.copy(base).addScaledVector(n, top + d / 2 + 0.001);
    SP.phone = ph; SP.phoneSize = [w, h, d]; SP.phoneLift = +top.toFixed(4);
    SP.props.push({name: "phone", obj: ph, min: [-w / 2, -h / 2, -d / 2], max: [w / 2, h / 2, d / 2]});
    SP.phoneFacing = facing(ph, new THREE.Vector3(0, 0, 1));
  } else if (row.hold === "controller" || row.hold === "tablet" || row.hold === "phone2") {
    // held in both hands: placed every frame between his palms (the two sockets), across them from his left palm to his
    // right, its face (the controller's buttons, the tablet's screen) turned towards his eyes as far as that allows
    let obj, face, box;
    if (row.hold === "phone2") {
      // (the page's phone held in both hands, two-handed texting: its body and screen, the made-up feed on the glass)
      const [w, h, d] = [0.078, 0.162, 0.008]; obj = new THREE.Group();
      const body = phone.children[0].clone(); body.visible = true; obj.add(body);
      const sc = phone.userData.screen.mesh.clone(); sc.visible = true; sc.geometry = new THREE.PlaneGeometry(w * 0.92, h * 0.95); sc.position.set(0, 0, d / 2 + 0.0006);
      sc.material = glass(144, 300, [[0.07, 0.07, 0.86, 0.23, "#d9e4f5"], [0.07, 0.33, 0.86, 0.13, "#8fb3e8"], [0.07, 0.49, 0.86, 0.23, "#e9d9c6"], [0.07, 0.75, 0.86, 0.13, "#8fb3e8"]]);
      obj.add(sc); face = new THREE.Vector3(0, 0, 1); box = {min: [-w / 2, -h / 2, -d / 2], max: [w / 2, h / 2, d / 2]};
    } else if (row.hold === "controller") {
      const g = await load("room/controller.glb"); obj = g.scene.getObjectByName("controller") || g.scene;   // (room_build/build_desk_tech.mjs; origin the middle of its footprint, grips +z)
      obj.traverse(m => { if (m.isMesh) { m.castShadow = true; if (/_contact$/.test(m.name)) m.visible = false; } });
      face = new THREE.Vector3(0, 1, 0); box = {min: [-0.087, 0, -0.056], max: [0.087, 0.056, 0.064]};
    } else {
      // (no tablet in the page: a plain one, a rounded slab 25 x 17 x 0.7 cm, its screen made up like the phone's)
      const [w, h, d] = [0.25, 0.17, 0.007]; obj = new THREE.Group();
      obj.add(new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 4, 0.006), new THREE.MeshStandardMaterial({color: 0x1b1c22, roughness: 0.35, metalness: 0.6})));
      const sc = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.92, h * 0.88), glass(300, 204, [[0.05, 0.08, 0.42, 0.84, "#d9e4f5"], [0.52, 0.08, 0.43, 0.38, "#8fb3e8"], [0.52, 0.54, 0.43, 0.38, "#e9d9c6"]]));
      sc.position.z = d / 2 + 0.0006; obj.add(sc); face = new THREE.Vector3(0, 0, 1); box = {min: [-w / 2, -h / 2, -d / 2], max: [w / 2, h / 2, d / 2]};
    }
    obj.name = "mx_" + row.hold; holder.add(obj);
    const L = new THREE.Vector3(), R_ = new THREE.Vector3(), c = new THREE.Vector3(), x = new THREE.Vector3(), f = new THREE.Vector3(), up = new THREE.Vector3(), z = new THREE.Vector3(), m = new THREE.Matrix4(), hi = new THREE.Matrix4();
    place = () => {
      sockets.L.getWorldPosition(L); sockets.R.getWorldPosition(R_); c.addVectors(L, R_).multiplyScalar(0.5);
      x.subVectors(R_, L).normalize();                                             // (his left palm to his right)
      f.subVectors(eyes(), c); f.addScaledVector(x, -f.dot(x)).normalize();        // (towards his eyes, square to that)
      if (row.hold === "controller") { up.copy(f); z.crossVectors(x, up); } else { z.copy(f); up.crossVectors(z, x); }
      if (row.hold === "phone2") c.addScaledVector(z, 0.012);                    // (on his palms, not in them)
      m.makeBasis(x, up, z).setPosition(c); hi.copy(holder.matrixWorld).invert(); m.premultiply(hi);
      m.decompose(obj.position, obj.quaternion, obj.scale); obj.updateMatrixWorld(true); };
    SP.props.push({name: row.hold === "phone2" ? "phone" : row.hold, obj, min: box.min, max: box.max});
    SP.propFacing = facing(obj, face); if (row.hold === "phone2") { SP.phone = obj; SP.phoneFacing = SP.propFacing; }
  }
  mixer.setTime(0); holder.updateMatrixWorld(true); place();

  SP.step = dt => { SP.t = (SP.t + dt) % anim.duration; mixer.setTime(SP.t); holder.updateMatrixWorld(true); place(); return true; };
  SP.setTime = t => { SP.t = t % anim.duration; mixer.setTime(SP.t); holder.updateMatrixWorld(true); place(); };
  // a camera for a look at him: "front" (from his forward, turned up to 80 deg), "side" (from his right or left, up to
  // 40 deg off), the first direction and distance (d, then closer) that is inside the room with nothing between it and
  // him (his chair aside); looking at his middle
  const blockers = []; scene.traverse(o => { if (!o.isMesh || !o.visible) return; for (let q = o; q; q = q.parent) if (q === holder || q === chairNode()) return; blockers.push(o); });
  SP.view = (k, d = 1.9) => {
    const c = holder.position, f = new THREE.Vector3(0, 0, 1).applyQuaternion(holder.quaternion), Y = new THREE.Vector3(0, 1, 0);
    const target = new THREE.Vector3(c.x, c.y + (row.spot === "chair" || row.spot === "out" || row.spot === "open" ? 0.7 : 0.9), c.z);
    const inRoom = p => p.x > -1.9 && p.x < 1.9 && p.z > -1.38 && p.z < 1.5;
    const angles = k === "side" ? [90, -90, 70, -70, 110, -110, 55, -55, 125, -125] : [0, 20, -20, 35, -35, 50, -50, 65, -65, 80, -80];
    const ray = new THREE.Raycaster();
    for (const dd of [d, d * 0.85, d * 0.7, d * 0.55]) for (const a of angles) {
      const u = f.clone().applyAxisAngle(Y, a * Math.PI / 180), pos = target.clone().addScaledVector(u, dd).setY(c.y + 1.15);
      if (!inRoom(pos)) continue;
      const dir = pos.clone().sub(target), L = dir.length(); ray.set(target, dir.normalize()); ray.far = L;
      if (!ray.intersectObjects(blockers, false).length) return {pos, target};
    }
    return {pos: target.clone().addScaledVector(f, d).setY(c.y + 1.15), target};
  };
  SP.bone = bone; SP.pageName = pageName; SP.ready = true;
  return SP;
}
