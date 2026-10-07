// ?char=mixamo&clip=<Clip>: one of G22's standing / in-between clips (web/room/mx_standing/<Clip>.glb, baked by
// room_build/kimodo/standing_rebake.sh) played in a loop on the Mixamo-rigged character (room/char_mixamo.glb through
// char_mixamo.js), in the room, where standing_clips.meta.json and the spot table below put it. A preview entry only:
// the page's own day (the v5 body, its planner, its clips) is switched off while it runs, and without ?clip the page
// does not load this file at all.
//
// Spots: standing clips on a floor point with a heading; chair clips in the desk chair, the chair rolled back from the
// desk by the clip's own reach (its skin, every 0.1 s, by 10 cm height band) plus 3 cm, as boy_mh.js rare() does.
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
export const SEAT_AT = {x: 0, z: -0.055};
const FLOOR = 0.16, DESK_FRONT = -0.84, CLEAR = 0.03, ROLL_MAX = 0.60;

export async function start(ctx) {
  const {THREE, scene, load, clip, chairNode, phone} = ctx;
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
  if (row.spot === "chair") {
    const n = chairNode(); n.updateMatrixWorld(true);
    const home = n.position.clone(), ry = n.rotation.y;
    // his body's forward-most skin over the clip (clip frame +z) -> the world (-z of the chair, ry 0): keep it off the desk
    const reach = Math.max(...Object.values(M.reach_z_by_10cm));
    const front = home.z + SEAT_AT.z - reach;                            // (the chair at home, ry 0)
    roll = Math.min(ROLL_MAX, Math.max(0, DESK_FRONT + CLEAR - front));
    n.position.z = home.z + roll; n.updateMatrixWorld(true);
    const p = new THREE.Vector3(SEAT_AT.x, 0, SEAT_AT.z).applyMatrix4(n.matrixWorld);
    holder.position.set(p.x, FLOOR, p.z); holder.rotation.y = ry + Math.PI;
    SP.chair = {x: +n.position.x.toFixed(3), z: +n.position.z.toFixed(3), roll: +roll.toFixed(3), reach: +reach.toFixed(3)};
  } else {
    // (on what is under the spot: the floor, or the rug's top)
    const s = SPOTS[row.spot] || SPOTS.rug, ray = new THREE.Raycaster(new THREE.Vector3(s.x, 0.5, s.z), new THREE.Vector3(0, -1, 0));
    const under = []; scene.traverse(o => { if (o.isMesh && o.visible && o !== holder) under.push(o); });
    const hit = ray.intersectObjects(under, false).find(h => h.point.y >= FLOOR - 0.001);
    holder.position.set(s.x, hit ? hit.point.y : FLOOR, s.z); holder.rotation.y = s.ry; SP.floor = +holder.position.y.toFixed(4);
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
    ph.position.set(0, 0.02, d / 2 + 0.004);                            // its back on the palm (the socket is on the skin)
    sockets.R.add(ph); SP.phone = ph; SP.phoneSize = [w, h, d];
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
