// STUB character (foundation). The character stream replaces this file.
//
// createCharacter(scene, assets) -> {update(dt, life), object}
//   life = the tick's life snapshot (x, z, heading, pose, walking, activity, bread, phone, npc, ...) plus
//          life.stage (sleep stage, added by main.js). Position smoothing / animation are the character's job.
// createBaker(scene, assets, anchors) -> {update(dt, life), object}; anchors = world.anchors (places.counter ...),
//   life.npc.baker = {present, pose} once the server sends it (shown by default until then).
// The character is a stylised figure with no face: it is never the real person and is not modelled on anyone.
import * as THREE from "three";

const mat = c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 });

function tagMesh(text, bg, fg, w, h) {
  const c = document.createElement("canvas"); c.width = 256; c.height = 64; const x = c.getContext("2d");
  x.fillStyle = bg; x.fillRect(0, 0, 256, 64); x.fillStyle = fg; x.font = "bold 34px Menlo, monospace";
  x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(text, 128, 35);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: t }));
}

function figure(shirtColor, pantsColor) {
  const body = new THREE.Group();
  const skin = mat(0xd9bfa2), shirt = mat(shirtColor), pants = mat(pantsColor);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.22, 0.45, 4, 12), shirt); torso.position.y = 1.15;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 14), skin); head.position.y = 1.72;
  body.add(torso, head);
  const legs = [], arms = [];
  for (const s of [-1, 1]) {
    const l = new THREE.Mesh(new THREE.CapsuleGeometry(0.075, 0.65, 3, 8), pants); l.geometry.translate(0, -0.4, 0);
    l.position.set(0.11 * s, 0.8, 0); body.add(l); legs.push(l);
    const a = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.5, 3, 8), shirt); a.geometry.translate(0, -0.31, 0);
    a.position.set(0.3 * s, 1.45, 0); body.add(a); arms.push(a);
  }
  body.traverse(o => { if (o.isMesh) o.castShadow = o.receiveShadow = true; });
  return { body, legs, arms };
}

export function createCharacter(scene, assets) {
  const { body, legs, arms } = figure(0xeeeeee, 0x3a4a6a);
  body.name = "sub01";
  const tag = tagMesh("SUB-01", "#ff6a00", "#0a0a0a", 0.36, 0.09); tag.position.set(0, 1.28, 0.25); body.add(tag);
  const phone = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.17, 0.015), new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0x6688cc, emissiveIntensity: 0.6 }));
  phone.visible = false; body.add(phone);
  const loaf = new THREE.Mesh(new THREE.SphereGeometry(0.12, 10, 8), mat(0xc98b43)); loaf.scale.set(1.8, 0.8, 1); loaf.visible = false; body.add(loaf);
  const zc = document.createElement("canvas"); zc.width = 128; zc.height = 48; const zx = zc.getContext("2d");
  zx.fillStyle = "#bcd0ff"; zx.font = "bold 30px Menlo, monospace"; zx.fillText("z z z", 10, 34);
  const zt = new THREE.CanvasTexture(zc); zt.colorSpace = THREE.SRGBColorSpace;
  const zzz = new THREE.Sprite(new THREE.SpriteMaterial({ map: zt, transparent: true, depthWrite: false }));
  zzz.scale.set(0.8, 0.3, 1); zzz.visible = false;
  scene.add(body, zzz);

  const shown = { x: 1.6, z: 1.3, h: 0, init: false };
  let time = 0;
  return {
    object: body,
    update(dt, life) {
      time += dt;
      if (!life) { body.visible = false; return; }
      body.visible = true;
      if (!shown.init) { shown.x = life.x; shown.z = life.z; shown.h = life.heading; shown.init = true; }
      const k = 1 - Math.exp(-dt * 9);
      shown.x += (life.x - shown.x) * k; shown.z += (life.z - shown.z) * k;
      let dh = life.heading - shown.h; dh = Math.atan2(Math.sin(dh), Math.cos(dh)); shown.h += dh * (1 - Math.exp(-dt * 12));
      body.position.set(shown.x, 0, shown.z); body.rotation.set(0, shown.h, 0);
      const asleep = life.stage && life.stage !== "AWAKE";
      const pose = asleep ? "lying" : life.pose, walk = pose === "walking";
      legs.forEach((l, i) => { l.rotation.x = walk ? Math.sin(time * 7 + i * Math.PI) * 0.6 : 0; });
      arms.forEach((a, i) => { a.rotation.x = walk ? Math.sin(time * 7 + i * Math.PI + Math.PI) * 0.5 : 0; });
      body.position.y = walk ? Math.abs(Math.sin(time * 7)) * 0.05 : 0;
      if (pose === "sitting" || pose === "sitting_desk") {
        body.position.y = -0.35; legs.forEach(l => { l.rotation.x = -1.45; }); body.rotation.y = Math.PI;
        if (pose === "sitting_desk") arms.forEach(a => { a.rotation.x = -1.0; });
      }
      if (pose === "lying" || pose === "lying_phone") {
        body.rotation.set(-Math.PI / 2, 0, Math.PI / 2); body.position.set(1.35, 0.95, 1.2);
        if (pose === "lying_phone") arms[1].rotation.x = -2.3;
      }
      phone.visible = pose === "lying_phone";
      if (phone.visible) { phone.position.set(0.25, 1.5, 0.55); phone.rotation.set(-0.3, 0, 0); }
      loaf.visible = walk && life.bread > 0; loaf.position.set(0.32, 1.0, 0.18);
      zzz.visible = !!asleep; zzz.position.set(1.5, 2.1 + Math.sin(time) * 0.1, 1.2);
    },
  };
}

export function createBaker(scene, assets, anchors) {
  const { body, arms } = figure(0xf4f1ea, 0x4a4a4a);
  body.name = "baker";
  const hat = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.15, 0.2, 12), mat(0xffffff)); hat.position.y = 1.95; hat.castShadow = true; body.add(hat);
  const c = anchors?.places?.counter;
  if (c) body.position.set(c.x, 0, c.z + 1.4);
  body.rotation.y = Math.PI;       // faces the shop door (north)
  scene.add(body);
  let time = 0;
  return {
    object: body,
    update(dt, life) {
      time += dt;
      const b = life?.npc?.baker;
      body.visible = b ? !!b.present : true;
      arms.forEach((a, i) => { a.rotation.x = -0.5 + Math.sin(time * 2 + i) * 0.15; });
    },
  };
}
