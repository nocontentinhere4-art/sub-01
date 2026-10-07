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
// Hands: the page's phone (its body and screen, not the rigid gripping hand made for the finger-less rig) on the right
// hand for the phone clips; a socket (an empty Object3D, "socket_R" / "socket_L", in the palm) on both hands for the
// rest: the tablet has no prop in the page, and the controller (room/controller.glb) is left on the desk for now.
import { prep, fixClip, pageName } from "./char_mixamo.js";

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
  if (row.hold === "phone" && phone) {
    // the page's phone: its body (a rounded slab) and its screen, the long side along the fingers, the screen out of the palm
    const ph = new THREE.Group(); ph.name = "mx_phone";
    const body = phone.children[0].clone(); body.visible = true; ph.add(body);
    const scr = phone.userData.screen.mesh.clone(); scr.visible = true; ph.add(scr);
    // (its glass lit with a plain made-up feed: cards on a dark blue ground, no app, no brand)
    const cv = document.createElement("canvas"); cv.width = 144; cv.height = 300; const x = cv.getContext("2d");
    x.fillStyle = "#16223a"; x.fillRect(0, 0, 144, 300);
    [[10, 22, 124, 70, "#d9e4f5"], [10, 100, 124, 40, "#8fb3e8"], [10, 148, 124, 70, "#e9d9c6"], [10, 226, 124, 40, "#8fb3e8"]].forEach(([a, b, w, h, c]) => { x.fillStyle = c; x.fillRect(a, b, w, h); });
    const tx = new THREE.CanvasTexture(cv); tx.colorSpace = THREE.SRGBColorSpace; scr.material = new THREE.MeshBasicMaterial({map: tx, toneMapped: false});
    const [w, h, d] = [0.078, 0.162, 0.008];
    scr.geometry = new THREE.PlaneGeometry(w * 0.92, h * 0.95); scr.position.set(0, 0, d / 2 + 0.0006);
    sockets.R.add(ph); SP.phone = ph; SP.phoneSize = [w, h, d];
    // as the page lifts its own phone: off the palm just enough that no skin of his right hand is inside it or in front
    // of its screen, over the whole clip (every 0.25 s): it rests on his curled fingers
    const parts = []; ch.traverse(o => { if (o.isSkinnedMesh) parts.push(o); });
    const idx = parts.map(sm => { const I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight, r = [];
      for (let i = 0; i < I.count; i++) { let bb = 0, bw = 0; for (let q = 0; q < 4; q++) if (W.getComponent(i, q) > bw) { bw = W.getComponent(i, q); bb = I.getComponent(i, q); }
        if (/^(RightHand|finger\d-\d\.R)$/.test(sm.skeleton.bones[bb].name)) r.push(i); } return r; });
    const v = new THREE.Vector3(), inv = new THREE.Matrix4(); let top = -0.01;
    const PY = 0.02; ph.position.set(0, PY, 0);
    for (let t = 0; t <= anim.duration; t += 0.25) { mixer.setTime(t); holder.updateMatrixWorld(true); inv.copy(sockets.R.matrixWorld).invert();
      parts.forEach((sm, pi) => { for (const i of idx[pi]) { sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld).applyMatrix4(inv);
        if (Math.abs(v.x) < w / 2 && Math.abs(v.y - PY) < h / 2) top = Math.max(top, v.z); } }); }
    ph.position.z = top + d / 2 + 0.001; SP.phoneLift = +top.toFixed(4); mixer.setTime(0); holder.updateMatrixWorld(true);
  }

  SP.step = dt => { SP.t = (SP.t + dt) % anim.duration; mixer.setTime(SP.t); holder.updateMatrixWorld(true); return true; };
  SP.setTime = t => { SP.t = t % anim.duration; mixer.setTime(SP.t); holder.updateMatrixWorld(true); };
  // a camera for a look at him: "front" (his forward, turned up to 40 deg until it is inside the room), "side" (his
  // right or left, whichever is inside the room); distance d from his hips, looking at his middle
  SP.view = (k, d = 1.9) => {
    const c = holder.position, f = new THREE.Vector3(0, 0, 1).applyQuaternion(holder.quaternion), r = new THREE.Vector3(-f.z, 0, f.x);
    const inRoom = p => p.x > -1.9 && p.x < 1.9 && p.z > -1.38 && p.z < 1.5;
    const tries = k === "side" ? [r, r.clone().negate(), r.clone().lerp(f, 0.3), r.clone().negate().lerp(f, 0.3)]
      : [0, 20, -20, 30, -30, 40, -40, 50, -50, 60, -60].map(a => f.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), a * Math.PI / 180));
    let dir = tries[0], dd = d;
    for (const dd2 of [d, d * 0.85, d * 0.7]) { const t = tries.find(u => inRoom(c.clone().addScaledVector(u.clone().normalize(), dd2))); if (t) { dir = t.clone().normalize(); dd = dd2; break; } }
    const target = new THREE.Vector3(c.x, c.y + (row.spot === "chair" ? 0.7 : 0.9), c.z);
    return {pos: target.clone().addScaledVector(dir, dd).setY(c.y + 1.15), target};
  };
  SP.bone = bone; SP.pageName = pageName; SP.ready = true;
  return SP;
}
