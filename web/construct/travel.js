// STUB travel (core stream). The travel stream replaces this file; keep the exports.
//
// createTravel(camera, controls, data, {scene}?) -> {update(dt, life, env), setView('first'|'orbit'), view, position}
//   life   tick.life snapshot (+ stage) or null. While walking it carries route (life.py place names, start..goal) and
//          progress (0..1 of the walked distance, timed by life.py WALK_SPEED); main.js fills both in from the waypoint
//          graph when the server does not send them yet.
//   first  (default) first-person camera: on a walk it travels along data.pathBetween(start district, goal district)
//          (real fibre paths) at life.progress; otherwise it stands in the district of life.place looking over the city.
//   orbit  OrbitControls overview of the whole construct; with env.follow the target drifts to where SUB-01 is.
//   position  Vector3: where SUB-01 is now in city space (also marked by a small beacon when a scene is given).
import * as THREE from "three";
import { pointAt } from "./data.js";

const EYE = 4, LOOK_AHEAD = 40;

export function createTravel(camera, controls, data, { scene } = {}) {
  const home = data.districtOf("home");
  const here = new THREE.Vector3().copy(data.districts[home].pos);
  const camGoal = new THREE.Vector3(), lookGoal = new THREE.Vector3(), look = new THREE.Vector3(), ahead = new THREE.Vector3();
  const tmp = new THREE.Vector3();
  let view = "first", path = null, pathKey = "", t = 0, snapped = false;

  // beacon: where SUB-01 is (seen in the overview)
  let beacon = null;
  if (scene) {
    beacon = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 160, 8, 1, true).translate(0, 80, 0),
      new THREE.MeshBasicMaterial({ color: 0xffe0b0, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
    beacon.visible = false; scene.add(beacon);
  }

  const resolve = place => {
    const d = data.placeDistrict(place);
    if (d != null) return d;
    if (/park/.test(place || "")) return data.districtOf("park");
    if (/bakery/.test(place || "")) return data.districtOf("reward");
    return home;
  };

  function setView(v) {
    view = v === "orbit" ? "orbit" : "first";
    controls.enabled = view === "orbit";
    if (view === "orbit") {
      const R = data.radius;
      camera.position.set(here.x * 0.3 + R * 0.2, R * 1.25, here.z * 0.3 + R * 1.35);
      controls.target.set(here.x * 0.3, 0, here.z * 0.3);
      controls.update();
    } else snapped = false;
    api.view = view;
  }

  function update(dt, life, env) {
    t += dt;
    let walking = false;
    if (life && life.walking && Array.isArray(life.route) && life.route.length >= 2) {
      const a = resolve(life.route[0]), b = resolve(life.route[life.route.length - 1]), key = a + ">" + b;
      if (key !== pathKey) { pathKey = key; path = data.pathBetween(a, b); }
      if (path && path.length > 1) {
        const u = Math.max(0, Math.min(1, +life.progress || 0));
        pointAt(path, u, here);
        pointAt(path, Math.min(1, u + LOOK_AHEAD / Math.max(1, path.total)), ahead);
        if (ahead.distanceToSquared(here) < 1) { pointAt(path, Math.max(0, u - 0.01), tmp); ahead.copy(here).multiplyScalar(2).sub(tmp); }
        walking = true;
      }
    }
    if (!walking) {
      pathKey = ""; path = null;
      here.lerp(data.districts[resolve(life?.place || "bed")].pos, 1 - Math.exp(-dt * 2));
    }
    if (beacon) { beacon.position.copy(here); beacon.visible = view === "orbit"; }

    if (view === "orbit") {
      if (env?.follow) controls.target.lerp(tmp.set(here.x, 0, here.z), 1 - Math.exp(-dt * 0.8));
      return;
    }
    if (walking) {
      camGoal.copy(here).y += EYE;
      lookGoal.copy(ahead).y += EYE * 0.8;
    } else {
      // standing in the district: step back from the tower, look out over the city with a slow sway
      const out = tmp.set(here.x, 0, here.z);
      if (out.lengthSq() < 1) out.set(0, 0, 1);
      out.normalize();
      camGoal.copy(here).addScaledVector(out, 40).y += EYE + 10;
      const yaw = Math.sin(t * 0.07) * 0.5;
      const dx = -out.x * Math.cos(yaw) + out.z * Math.sin(yaw), dz = -out.z * Math.cos(yaw) - out.x * Math.sin(yaw);
      lookGoal.set(camGoal.x + dx * 100, EYE + 4, camGoal.z + dz * 100);
    }
    if (!snapped) { camera.position.copy(camGoal); look.copy(lookGoal); snapped = true; }
    const k = 1 - Math.exp(-dt * (walking ? 6 : 2));
    camera.position.lerp(camGoal, k);
    look.lerp(lookGoal, k);
    camera.lookAt(look);
  }

  const api = { update, setView, view, position: here };
  controls.enabled = false;
  return api;
}
