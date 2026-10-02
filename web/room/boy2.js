// The second character's extras (#76), shared by room.html (?boy=new) and boy_test.html: finger poses layered over
// any body clip, a blink every few seconds and small eye glances. The body clips are the old ones (same names, same
// bones); only the fingers, the eyes and the blink are new.
//
//   const x = boy2Extras(gltf, mixer);        // gltf: room/boy2.glb, mixer: the boy's AnimationMixer
//   await x.loadHands(loadFn);                // loadFn(url) -> Promise<gltf>; room/boy2_hands.glb
//   x.pose("hand_phone");                     // hand_relaxed | hand_phone | hand_chopsticks | hand_spoon | hand_type | hand_mouse
//   x.update(dt, {awake: true});              // after mixer.update(dt): blink and eyes (eyes closed while asleep)
//   x.sockets.phone                           // Object3D under RightHand: the phone's centre (+y its top, +z out of the screen, cm)
import * as THREE from "three";

export function boy2Extras(gltf, mixer) {
  const root = gltf.scene, bones = {}, morphs = [];
  root.traverse(o => { if (o.isBone) bones[o.name] = o; if (o.isMesh && o.morphTargetDictionary && "blink" in o.morphTargetDictionary) morphs.push(o);
    // soft shading: a faint warm light through the colour map lifts the shadowed side (skin reads less flat, like light
    // under the skin); on the dark clothes it is too faint to see
    if (o.isMesh && o.material && o.material.map && o.material.name === "boy2_body") {
      o.material.emissiveMap = o.material.map; o.material.emissive.setRGB(1.0, 0.82, 0.72); o.material.emissiveIntensity = 0.07; }
  });
  const sockets = {phone: root.getObjectByName("socket_phone"), chopsticks: root.getObjectByName("socket_chopsticks"), spoon: root.getObjectByName("socket_spoon")};
  const hands = {}, eyes = [bones.LeftEye, bones.RightEye].filter(Boolean), eyeRest = eyes.map(b => b.quaternion.clone());
  let current = null, closed = 0, blinkT = -1, nextBlink = 1.5 + Math.random() * 3, look = {y: 0, p: 0, ty: 0, tp: 0, next: 1};
  const _q = new THREE.Quaternion(), _e = new THREE.Euler();
  return {
    bones, sockets,
    async loadHands(load) { for (const a of (await load("room/boy2_hands.glb")).animations) hands[a.name] = mixer.clipAction(a); if (!current) this.pose("hand_relaxed"); },
    pose(name, fade = 0.25) {
      const a = hands[name]; if (!a || (a === current && a.isRunning())) return;
      if (fade > 0) { a.reset().fadeIn(fade).play(); if (current && current !== a) current.fadeOut(fade); }
      else { if (current && current !== a) current.stop(); a.reset().play(); }
      current = a;
    },
    get poseName() { return current ? current.getClip().name : null; },
    // w: how closed the lids are, 0..1 (on top of the blink); call after mixer.update
    update(dt, {awake = true, lids = 0} = {}) {
      if (awake) { nextBlink -= dt; if (nextBlink <= 0) { blinkT = 0; nextBlink = 2.5 + Math.random() * 4.5; } }
      let b = 0;
      if (blinkT >= 0) { blinkT += dt; b = blinkT < 0.07 ? blinkT / 0.07 : blinkT < 0.1 ? 1 : Math.max(0, 1 - (blinkT - 0.1) / 0.12); if (blinkT > 0.25) blinkT = -1; }
      closed += ((awake ? lids : 1) - closed) * Math.min(1, dt * 6);
      const w = Math.max(b, closed);
      for (const m of morphs) m.morphTargetInfluences[m.morphTargetDictionary.blink] = w;
      // the eyes: a glance every 1-3 s (a few degrees; now and then further), quick to move, resting in between
      look.next -= dt;
      if (look.next <= 0) { const far = Math.random() < 0.25; look.next = 1 + Math.random() * 2;
        look.ty = (Math.random() - 0.5) * (far ? 0.4 : 0.14); look.tp = (Math.random() - 0.5) * 0.12; }
      const k = Math.min(1, dt * 18); look.y += (look.ty - look.y) * k; look.p += (look.tp - look.p) * k;
      eyes.forEach((e, i) => e.quaternion.copy(eyeRest[i]).multiply(_q.setFromEuler(_e.set(-look.p, look.y, 0))));
    },
    look(yaw, pitch) { look.ty = look.y = yaw; look.tp = look.p = pitch; look.next = 1e9; },
  };
}
