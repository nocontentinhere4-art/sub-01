import * as T from "three";
import { RoundedBoxGeometry } from "./vendor/RoundedBoxGeometry.js";
import { GLTFExporter } from "./vendor/GLTFExporter.js";
import { RoomEnvironment } from "./vendor/RoomEnvironment.js";
import { HDRLoader } from "./vendor/HDRLoader.js";
import { mergeGeometries } from "./vendor/BufferGeometryUtils.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";
import { MeshoptDecoder } from "./vendor/meshopt_decoder.module.js";
import { createWindowView } from "/room/window_view.js?v=home1";
const lite =
  new URLSearchParams(location.search).has("lite") ||
  innerWidth < 700 ||
  (navigator.deviceMemory && navigator.deviceMemory <= 4);
const assetRoot = "/house/assets/" + (lite ? "lite/" : "");
const scene = new T.Scene();
scene.background = new T.Color("#a6b7bc");
scene.fog = new T.Fog("#b2b8b1", 22, 80);
const renderer = new T.WebGLRenderer({
  antialias: true,
  preserveDrawingBuffer: false,
});
renderer.setPixelRatio(
  Math.min(
    devicePixelRatio,
    Math.sqrt((lite ? 750000 : 1800000) / (innerWidth * innerHeight)),
    1.5,
  ),
);
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = T.SRGBColorSpace;
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = T.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;
document.body.prepend(renderer.domElement);
renderer.domElement.addEventListener("webglcontextlost", (event) => {
  event.preventDefault();
  if (!lite) {
    const url = new URL(location.href);
    url.searchParams.set("lite", "1");
    location.replace(url);
  } else notice("The room renderer paused. Reload to reconnect.");
});
renderer.domElement.addEventListener("webglcontextrestored", () => {
  renderer.shadowMap.needsUpdate = true;
  notice("The room is connected again.");
});
const environment = new RoomEnvironment();
const pmrem = new T.PMREMGenerator(renderer);
const envTarget = pmrem.fromScene(environment, 0.04);
scene.environment = envTarget.texture;
scene.environmentIntensity = 0.38;
environment.dispose();
pmrem.dispose();
// A real indoor lighting capture replaces the cheap startup environment after loading.
new HDRLoader().load(
  "/house/assets/lighting/room-light.hdr",
  (hdr) => {
    hdr.mapping = T.EquirectangularReflectionMapping;
    const generator = new T.PMREMGenerator(renderer);
    const capturedEnvironment = generator.fromEquirectangular(hdr);
    scene.environment = capturedEnvironment.texture;
    scene.environmentIntensity = 0.65;
    envTarget.dispose();
    hdr.dispose();
    generator.dispose();
  },
  undefined,
  () => {
    /* The initial room environment remains usable offline. */
  },
);
const camera = new T.PerspectiveCamera(64, innerWidth / innerHeight, 0.04, 110);
camera.rotation.order = "YXZ";
let yaw = 0,
  pitch = 0;
let seed = 9241;
const random = () => {
  seed = (1664525 * seed + 1013904223) >>> 0;
  return seed / 4294967296;
};
T.DefaultLoadingManager.onProgress = (url, loaded, total) => {
  const label = document.querySelector("#load span");
  if (label) label.textContent = "Opening his home · " + loaded + " / " + total;
};
T.DefaultLoadingManager.onLoad = () =>
  (document.getElementById("load").style.display = "none");
const loader = new T.TextureLoader();
const gltfLoader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const modelCache = new Map();
function pbr(name, repeat = [1, 1]) {
  const base = assetRoot + name + "/";
  const textures = ["diff", "normal", "rough"].map((n, i) => {
    const t = loader.load(
      base +
        (i === 0 &&
        ["white_plaster_02", "quatrefoil_jacquard_fabric"].includes(name)
          ? "neutral"
          : n) +
        ".jpg",
    );
    t.wrapS = t.wrapT = T.RepeatWrapping;
    t.repeat.set(...repeat);
    t.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
    if (i === 0) t.colorSpace = T.SRGBColorSpace;
    return t;
  });
  return new T.MeshStandardMaterial({
    map: textures[0],
    normalMap: textures[1],
    roughnessMap: textures[2],
    roughness: 1,
    normalScale: new T.Vector2(0.12, 0.12),
  });
}
const scannedWood = pbr("wooden_floor_02", [1, 1]),
  scannedWall = pbr("white_plaster_02", [2, 2]),
  scannedFabric = pbr("quatrefoil_jacquard_fabric", [2, 2]),
  scannedTiles = pbr("interior_tiles", [2, 2]),
  scannedLinen = pbr("rough_linen", [2, 2]);
const woodTex = scannedWood.map,
  fabricTex = scannedFabric.map,
  plasterTex = scannedWall.map;
const mat = (color, roughness = 0.8, map) =>
  new T.MeshStandardMaterial({ color, roughness, ...(map ? { map } : {}) });
const M = {
  wood: scannedWood,
  darkwood: pbr("fine_grained_wood", [1, 1]),
  wall: scannedWall,
  cream: scannedFabric,
  sofa: scannedFabric.clone(),
  white: mat("#f3efde", 0.6),
  metal: mat("#353a35", 0.38),
  black: mat("#151b1b", 0.55),
  stone: pbr("marble_01", [1, 1]),
  linen: scannedLinen,
  blue: scannedLinen.clone(),
  brass: new T.MeshStandardMaterial({
    color: "#b19762",
    metalness: 0.55,
    roughness: 0.4,
  }),
};
M.darkwood.color.set("#c5aa83");
M.stone.roughness = 0.35;
M.blue.color.set("#9bb0ad");
M.sofa.color.set("#9ca995");
let meshCount = 0;
const blockers = [],
  interactions = [];
function box(w, h, d, x, y, z, m = M.wood, r = 0.012) {
  const o = new T.Mesh(
    r
      ? new RoundedBoxGeometry(w, h, d, 2, Math.min(r, w / 3, h / 3, d / 3))
      : new T.BoxGeometry(w, h, d),
    m,
  );
  o.position.set(x, y, z);
  o.castShadow = o.receiveShadow = true;
  if (m === M.wood && !(w > 4 || d > 5)) {
    o.material = M.darkwood;
  }
  scene.add(o);
  meshCount++;
  return o;
}
function cylinder(rad, h, x, y, z, m = M.white) {
  const o = new T.Mesh(new T.CylinderGeometry(rad, rad, h, 24), m);
  o.position.set(x, y, z);
  o.castShadow = o.receiveShadow = true;
  scene.add(o);
  meshCount++;
  return o;
}
function beam(a, b, r = 0.022, m = M.darkwood) {
  const A = new T.Vector3(...a),
    B = new T.Vector3(...b),
    D = B.clone().sub(A),
    o = new T.Mesh(new T.CylinderGeometry(r, r, D.length(), 10), m);
  o.position.copy(A.add(B).multiplyScalar(0.5));
  o.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), D.normalize());
  o.castShadow = true;
  scene.add(o);
  return o;
}
function obstacle(x, z, w, d, level = 0) {
  blockers.push({
    x0: x - w / 2 - 0.16,
    x1: x + w / 2 + 0.16,
    z0: z - d / 2 - 0.16,
    z1: z + d / 2 + 0.16,
    level,
  });
}
function floor(w, d, x, y, z) {
  const material = scannedWood.clone();
  for (const k of ["map", "normalMap", "roughnessMap"]) {
    material[k] = scannedWood[k].clone();
    material[k].repeat.set(w / 2, d / 2);
  }
  const o = new T.Mesh(new T.PlaneGeometry(w, d), material);
  o.rotation.x = -Math.PI / 2;
  o.position.set(x, y + 0.025, z);
  o.receiveShadow = true;
  scene.add(o);
  box(w, 0.12, d, x, y - 0.06, z, M.darkwood, 0);
}
function rug(w, d, x, y, z, color = "#c4b49a") {
  const m = mat(color, 0.98, fabricTex);
  box(w, 0.018, d, x, y + 0.021, z, m, 0.008);
  for (let i = 0; i < 12; i++)
    box(
      w - 0.08,
      0.003,
      0.012,
      x,
      y + 0.034,
      z - d / 2 + 0.08 + (i * d) / 12,
      M.linen,
      0,
    );
}
function drape(w, d, x, y, z, m, drop) {
  const g = new T.PlaneGeometry(w, d, 36, 28);
  g.rotateX(-Math.PI / 2);
  const a = g.attributes.position;
  for (let i = 0; i < a.count; i++) {
    const xx = a.getX(i),
      zz = a.getZ(i),
      edge = T.MathUtils.smoothstep(Math.abs(xx), w * 0.39, w * 0.5),
      front = T.MathUtils.smoothstep(zz, d * 0.36, d * 0.5),
      crease = Math.sin(xx * 8 + Math.sin(zz * 3.1) * 1.4);
    a.setX(i, xx + 0.012 * Math.sin(zz * 7.3) * edge);
    a.setZ(i, zz + 0.01 * Math.sin(xx * 9.2) * front);
    a.setY(
      i,
      0.012 * crease +
        0.006 * Math.sin(zz * 12.7 - xx * 4.3) -
        drop * edge -
        0.25 * drop * front,
    );
  }
  g.computeVertexNormals();
  const material = m.clone();
  material.side = T.DoubleSide;
  const mesh = new T.Mesh(g, material);
  mesh.userData.flexibleCloth = true;
  mesh.position.set(x, y, z);
  mesh.castShadow = mesh.receiveShadow = true;
  scene.add(mesh);
}
function plant(x, y, z, size = 0.7) {
  furnished("potted_plant_01", x, y, z, size * 0.55);
}
function books(x, y, z, n = 8) {
  for (let i = 0; i < n; i++) {
    const h = 0.16 + random() * 0.12,
      w = 0.035 + random() * 0.02;
    const colors = ["#ac714f", "#d7cbb2", "#718085", "#74755e"];
    box(w, h, 0.14, x + i * 0.054, y + h / 2, z, mat(colors[i % 4]), 0.003);
  }
}
function frame(x, y, z, w = 0.65, h = 0.85) {
  box(w + 0.04, h + 0.04, 0.035, x, y, z, M.darkwood, 0.005);
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 384;
  const q = c.getContext("2d");
  q.fillStyle = "#dfd0b0";
  q.fillRect(0, 0, 256, 384);
  q.fillStyle = "#a56043";
  q.beginPath();
  q.arc(130, 145, 70, 0, Math.PI * 2);
  q.fill();
  q.fillStyle = "#435254";
  q.beginPath();
  q.moveTo(0, 330);
  q.lineTo(120, 195);
  q.lineTo(256, 330);
  q.fill();
  q.fillStyle = "#303e38";
  q.font = "20px serif";
  q.fillText("TOKYO / 01", 58, 360);
  const t = new T.CanvasTexture(c);
  t.colorSpace = T.SRGBColorSpace;
  const p = new T.Mesh(
    new T.PlaneGeometry(w, h),
    new T.MeshBasicMaterial({ map: t }),
  );
  p.position.set(x, y, z + 0.021);
  scene.add(p);
}
// Architecture: loft over the living/kitchen, double-height studio and continuous wooden staircase.
floor(8, 8, 0, 0, 0);
floor(3.8, 8, -2.1, 3, 0);
floor(1, 2, 0.3, 3, -2.85);
floor(3.8, 1.25, -2.1, 3, 4.625);
box(8, 0.2, 8, 0, 6.05, 0, M.wall, 0);
box(8, 6, 0.18, 0, 3, -4, M.wall, 0);
box(0.18, 6, 8, 4, 3, 0, M.wall, 0);
// West window openings, not glass pasted over a solid wall.
box(0.18, 0.7, 8, -4, 0.35, 0, M.wall, 0);
box(0.18, 0.45, 8, -4, 2.8, 0, M.wall, 0);
box(0.18, 3.05, 8, -4, 4.55, 0, M.wall, 0);
for (const z of [-3.9, -1.35, 1.35, 3.9])
  box(0.18, 2.15, 0.12, -4, 1.675, z, M.wall, 0);
// Front: tall studio windows and balcony doors upstairs.
box(5.45, 0.7, 0.18, -1.275, 0.35, 4, M.wall, 0);
box(1.45, 0.7, 0.18, 3.275, 0.35, 4, M.wall, 0);
box(8, 0.45, 0.18, 0, 2.8, 4, M.wall, 0);
box(4.15, 3, 0.18, 1.925, 4.55, 4, M.wall, 0);
box(3.85, 0.6, 0.18, -2.075, 5.75, 4, M.wall, 0);
function windowFrame(x, y, z, w, h, rotate = false) {
  const g = new T.Group();
  const dark = M.darkwood;
  for (const [ww, hh, xx, yy] of [
    [w, 0.055, 0, -h / 2],
    [w, 0.055, 0, h / 2],
    [0.045, h, -w / 2, 0],
    [0.045, h, w / 2, 0],
    [0.035, h, 0, 0],
  ]) {
    const b = new T.Mesh(new T.BoxGeometry(ww, hh, 0.06), dark);
    b.position.set(xx, yy, 0);
    g.add(b);
  }
  g.position.set(x, y, z);
  if (rotate) g.rotation.y = Math.PI / 2;
  scene.add(g);
}
for (const z of [-2.6, 0, 2.6]) windowFrame(-3.85, 1.7, z, 2.48, 2.02, true);
windowFrame(-2, 1.7, 3.85, 3.65, 2.02);
windowFrame(0.65, 1.7, 3.85, 0.9, 2.02);
windowFrame(3.25, 1.7, 3.85, 0.9, 2.02);
windowFrame(-2, 4.45, 3.85, 3.6, 2.5);
// Reuse the existing photographed Tokyo layers; no second scene or reflection render.
const windowViews = [];
let sharedWindowTextures;
for (const surface of [
  { c: [-3.94, 1.675, 0], w: 7.9, h: 2.15, ry: Math.PI / 2 },
  { c: [-1.3, 1.675, 3.94], w: 5.35, h: 2.15, ry: Math.PI },
  { c: [3.25, 1.675, 3.94], w: 1.35, h: 2.15, ry: Math.PI },
  { c: [-2.075, 4.45, 3.94], w: 3.7, h: 2.5, ry: Math.PI },
]) {
  const view = createWindowView(T, {
    base: lite ? "/house/assets/lite/window/" : "/room/window/",
    textures: sharedWindowTextures,
  });
  if (!sharedWindowTextures) {
    sharedWindowTextures = {};
    for (const [name, uniform] of Object.entries({
      near: "tNear",
      mid: "tMid",
      mid_n: "tMidN",
      mid_l: "tMidL",
      far: "tFar",
      sky: "tSky",
      noise: "tNoise",
    })) {
      sharedWindowTextures[name] = view.material.uniforms[uniform].value;
    }
  }
  view.build(surface, scene, null);
  windowViews.push(view);
}
// A real exit through the front wall to the entrance terrace.
floor(2.5, 1.8, 2, 0, 4.9);
windowFrame(2, 1.12, 3.87, 1.1, 2.24);
const frontDoorGroup = new T.Group();
frontDoorGroup.position.set(1.47, 0, 3.9);
scene.add(frontDoorGroup);
const frontDoor = box(1.05, 2.2, 0.075, 0, 0, 0, M.darkwood, 0.012);
scene.remove(frontDoor);
frontDoor.position.set(0.525, 1.1, 0);
frontDoorGroup.add(frontDoor);
const knob = new T.Mesh(new T.SphereGeometry(0.027, 12, 8), M.brass);
knob.position.set(0.94, 1.05, -0.06);
frontDoorGroup.add(knob);
let entranceOpen = false;
plant(2.9, 0, 5.3, 1);
plant(1, 0, 5.3, 0.85);
for (const x of [-3.96, 3.96]) box(0.025, 0.09, 8, x, 0.055, 0, M.darkwood, 0);
box(8, 0.09, 0.025, 0, 0.055, -3.89, M.darkwood, 0);
const STEP = {
  x0: -0.2,
  x1: 0.8,
  zBottom: 2.55,
  zTop: -1.7,
  rise: 3,
  count: 17,
};
for (let i = 0; i < 17; i++) {
  const z = 2.55 - (i + 0.5) * 0.25,
    h = ((i + 1) * 3) / 17;
  box(0.96, h, 0.25, 0.3, h / 2, z, M.darkwood, 0);
  box(1.02, 0.035, 0.27, 0.3, h + 0.006, z, M.darkwood, 0.007);
}
for (const x of [-0.25, 0.85]) {
  beam([x, 0.9, 2.55], [x, 3.9, -1.7], 0.03, M.darkwood);
  for (let i = 0; i < 9; i++) {
    const z = 2.55 - i * 0.5,
      h = (3 * (2.55 - z)) / 4.25;
    beam([x, h, z], [x, h + 0.9, z], 0.013, M.brass);
  }
}
// Safe landing and loft edge, passage onto the bedroom at the rear.
for (let z = -1.6; z < 4; z += 0.34)
  beam([-0.12, 3, z], [-0.12, 3.95, z], 0.014, M.brass);
beam([-0.12, 3.98, -1.7], [-0.12, 3.98, 4], 0.033, M.darkwood);
for (let z = -3.8; z < -1.7; z += 0.35)
  beam([0.85, 3, z], [0.85, 3.98, z], 0.014, M.brass);
beam([0.85, 3.98, -3.9], [0.85, 3.98, -1.7], 0.033, M.darkwood);
const aoCanvas = document.createElement("canvas");
aoCanvas.width = aoCanvas.height = 128;
const ao = aoCanvas.getContext("2d"),
  gradient = ao.createRadialGradient(64, 64, 8, 64, 64, 64);
gradient.addColorStop(0, "rgba(28,23,17,.32)");
gradient.addColorStop(1, "rgba(28,23,17,0)");
ao.fillStyle = gradient;
ao.fillRect(0, 0, 128, 128);
const aoTex = new T.CanvasTexture(aoCanvas);
function contact(x, y, z, w, d) {
  const o = new T.Mesh(
    new T.PlaneGeometry(w, d),
    new T.MeshBasicMaterial({
      map: aoTex,
      transparent: true,
      depthWrite: false,
    }),
  );
  o.rotation.x = -Math.PI / 2;
  o.position.set(x, y + 0.042, z);
  scene.add(o);
}
contact(-2, 0, 1.85, 3.2, 1.6);
contact(-2, 0, 0.3, 2.2, 1.4);
contact(2, 0, -1.9, 1.2, 1.2);
contact(-2.4, 3, -2.35, 2.2, 2.8);
// Ground floor lounge: rounded upholstery, cushions, coffee table and ceramic objects.
rug(2.9, 2.8, -2, 0, 0.9);
obstacle(-2, 1.85, 2.7, 1.08);
obstacle(-2, 0.3, 1.7, 0.9);

async function furnished(name, x, y, z, width, rotation = 0) {
  try {
    const url = assetRoot + name + "/" + name + ".gltf";
    if (!modelCache.has(url)) modelCache.set(url, gltfLoader.loadAsync(url));
    const gltf = await modelCache.get(url);
    const root = gltf.scene.clone(true);
    root.rotation.y = rotation;
    let bounds = new T.Box3().setFromObject(root),
      size = bounds.getSize(new T.Vector3());
    root.scale.setScalar(width / size.x);
    bounds = new T.Box3().setFromObject(root);
    const center = bounds.getCenter(new T.Vector3());
    root.position.set(x - center.x, y - bounds.min.y, z - center.z);
    root.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = o.receiveShadow = true;
      }
    });
    scene.add(root);
    renderer.shadowMap.needsUpdate = true;
  } catch (e) {
    console.warn("Home asset:", name, e.message);
    notice("An item could not load. Reconnect to retry.");
  }
}
furnished("sofa_03", -2, 0, 1.85, 2.5);
furnished("modern_coffee_table_01", -2, 0, 0.3, 1.65, Math.PI / 2);
furnished("potted_plant_01", -3.45, 0, 2.7, 0.7);
furnished("modern_arm_chair_01", -1.2, 3, 4.5, 0.65);
furnished("throw_pillows_01", -2, 0.42, 2.02, 1.25);
furnished("desk_lamp_arm_01", 2.78, 0.855, -3.15, 0.32, -0.7);
// Kitchen, integrated oak cabinetry, stone countertop, sink and coffee corner.
box(3.05, 0.86, 0.62, -2.2, 0.43, -3.55, M.wood, 0.015);
box(3.16, 0.055, 0.7, -2.2, 0.895, -3.53, M.stone, 0.018);
for (const x of [-3.3, -2.6, -1.9, -1.2]) {
  box(0.65, 0.76, 0.035, x, 0.44, -3.215, M.wood, 0.006);
  beam([x - 0.15, 0.75, -3.18], [x + 0.15, 0.75, -3.18], 0.01, M.brass);
}
box(3.1, 0.7, 0.36, -2.2, 2.05, -3.71, M.white, 0.012);
box(
  3.1,
  0.035,
  0.43,
  -2.2,
  1.68,
  -3.69,
  new T.MeshStandardMaterial({
    color: "#fce9bd",
    emissive: "#eecb88",
    emissiveIntensity: 0.6,
  }),
  0,
);
box(0.66, 0.012, 0.4, -2.7, 0.929, -3.48, M.black, 0.035);
beam([-2.7, 0.93, -3.7], [-2.7, 1.16, -3.7], 0.019, M.brass);
beam([-2.7, 1.16, -3.7], [-2.7, 1.16, -3.49], 0.019, M.brass);
box(0.33, 0.4, 0.29, -1.25, 1.12, -3.5, M.black, 0.035);
cylinder(0.06, 0.08, -1.24, 0.98, -3.27, M.white);
cylinder(0.09, 0.29, -3.4, 1.07, -3.45, M.stone);
obstacle(-2.2, -3.5, 3.2, 0.75);
plant(-0.82, 0.94, -3.55, 0.5);
// Double-height office.
box(2.4, 0.09, 0.8, 2, 0.8, -3.1, M.wood, 0.045);
for (const x of [0.95, 3.05])
  box(0.08, 0.74, 0.7, x, 0.39, -3.1, M.darkwood, 0.008);
obstacle(2, -3.1, 2.4, 0.8);
box(0.72, 0.44, 0.035, 2, 1.16, -3.3, M.black, 0.025);
box(0.12, 0.12, 0.09, 2, 0.88, -3.3, M.metal, 0.005);
box(0.35, 0.018, 0.2, 2, 0.856, -2.94, M.black, 0.015);
box(0.095, 0.028, 0.06, 2.4, 0.857, -2.91, M.black, 0.02);
plant(3, 0.855, -3.25, 0.45);
const screenCanvas = document.createElement("canvas");
screenCanvas.width = 1024;
screenCanvas.height = 600;
const sx = screenCanvas.getContext("2d");
const st = new T.CanvasTexture(screenCanvas);
st.colorSpace = T.SRGBColorSpace;
const screen = new T.Mesh(
  new T.PlaneGeometry(0.68, 0.4),
  new T.MeshBasicMaterial({ map: st, toneMapped: false }),
);
screen.position.set(2, 1.16, -3.276);
scene.add(screen);
interactions.push({
  object: screen,
  label: "E · Open his computer",
  fn: () => openPanel("computer"),
});
const officeChair = [];
officeChair.push(box(0.64, 0.16, 0.6, 2, 0.5, -1.9, M.sofa, 0.06));
officeChair.push(box(0.63, 0.65, 0.12, 2, 0.87, -1.63, M.sofa, 0.07));
officeChair.push(cylinder(0.055, 0.4, 2, 0.23, -1.9, M.metal));
officeChair.push(beam([1.7, 0.12, -1.9], [2.3, 0.12, -1.9], 0.025, M.metal));
officeChair.push(beam([2, 0.12, -2.2], [2, 0.12, -1.6], 0.025, M.metal));
// Reuse the owner's existing repaired/optimised chair, including its 512px textures.
gltfLoader
  .loadAsync("/room/chair_owner.glb")
  .then((gltf) => {
    const chair = gltf.scene;
    chair.position.set(2, 0, -1.9);
    chair.traverse((o) => {
      if (o.isMesh) o.castShadow = o.receiveShadow = true;
    });
    for (const item of officeChair) {
      scene.remove(item);
      item.geometry.dispose();
    }
    officeChair.splice(0, officeChair.length, chair);
    scene.add(chair);
    renderer.shadowMap.needsUpdate = true;
  })
  .catch((error) => console.warn("Chair fallback:", error.message));
obstacle(2, -1.9, 0.7, 0.7);
rug(2.7, 2.3, 2, 0, -1.2, "#a2aa9d");
// Shelving and art.
for (const x of [1, 3.25])
  box(0.08, 2.25, 0.33, x, 1.25, -3.72, M.darkwood, 0.007);
for (let y = 0.25; y < 2.6; y += 0.45) {
  box(2.35, 0.035, 0.34, 2.125, y, -3.72, M.wood, 0.007);
  if (y > 1.6) books(1.2, y + 0.02, -3.71, 15);
}
frame(2, 3.75, -3.885, 1.3, 1.8);
frame(-2.2, 4.65, -3.88, 0.9, 1.2);
// Bedroom upstairs: upholstered bed, layered linen and bedside light.
box(1.65, 0.3, 2.25, -2.4, 3.25, -2.35, M.darkwood, 0.06);
box(1.65, 0.98, 0.16, -2.4, 3.63, -3.5, M.cream, 0.08);
box(1.6, 0.2, 2.13, -2.4, 3.47, -2.35, M.white, 0.09);
drape(1.82, 1.7, -2.4, 3.615, -2.03, M.blue, 0.17);
for (const x of [-2.78, -2.02]) {
  const p = box(0.65, 0.13, 0.43, x, 3.64, -3.1, M.linen, 0.06);
  p.rotation.y = x < -2.4 ? 0.08 : -0.08;
}
drape(1.86, 0.55, -2.4, 3.69, -1.44, M.linen, 0.22);
obstacle(-2.4, -2.35, 1.75, 2.3, 1);
rug(2.65, 3, -2.2, 3, -1.7, "#d3c4a9");
box(0.48, 0.5, 0.45, -3.55, 3.25, -3.1, M.wood, 0.025);
plant(-3.3, 3, 2.7, 0.9);
books(-3.3, 3.035, 1, 5);
// Bathroom on the loft. Entry is through the openable door on the aisle side.
const bathroomBounds = { x0: -3.78, x1: -0.85, z0: 0.5, z1: 2.7 };
const tiles = scannedTiles;
box(3.05, 0.035, 2.2, -2.325, 3.035, 1.6, tiles, 0);
for (const z of [0.5, 2.7]) {
  box(3.1, 2.85, 0.1, -2.325, 4.46, z, M.wall, 0);
}
for (const [z, d] of [
  [0.675, 0.35],
  [2.25, 0.9],
]) {
  box(0.1, 2.85, d, -0.85, 4.46, z, M.wall, 0);
}
obstacle(-2.325, 0.5, 3.1, 0.1, 1);
obstacle(-2.325, 2.7, 3.1, 0.1, 1);
obstacle(-0.85, 0.675, 0.1, 0.35, 1);
obstacle(-0.85, 2.25, 0.1, 0.9, 1);
box(0.1, 0.9, 0.9, -0.85, 5.45, 1.35, M.wall, 0);
const bathDoor = box(0.065, 2, 0.89, -0.85, 4.05, 1.35, M.darkwood, 0.012);
const doorLabel = frame(-2.4, 4.45, 0.557, 0.48, 0.6);
box(0.62, 0.66, 0.48, -3.5, 3.36, 1.1, M.wood, 0.02);
box(0.68, 0.1, 0.5, -3.5, 3.73, 1.1, M.white, 0.04);
cylinder(0.12, 0.05, -3.5, 3.81, 1.1, M.white);
beam([-3.5, 3.8, 0.92], [-3.5, 4.01, 0.92], 0.017, M.brass);
beam([-3.5, 4.01, 0.92], [-3.5, 4.01, 1.04], 0.017, M.brass);
obstacle(-3.5, 1.1, 0.68, 0.5, 1);
box(0.42, 0.42, 0.6, -2.9, 3.24, 2.23, M.white, 0.11);
box(0.43, 0.64, 0.18, -2.9, 3.47, 2.49, M.white, 0.07);
box(0.36, 0.04, 0.46, -2.9, 3.48, 2.18, M.cream, 0.08);
obstacle(-2.9, 2.23, 0.45, 0.72, 1);
box(0.9, 0.1, 1, -1.5, 3.08, 2.15, tiles, 0.015);
const showerGlass = new T.MeshStandardMaterial({
  color: "#c2d5d1",
  transparent: true,
  opacity: 0.22,
  roughness: 0.12,
  depthWrite: false,
});
box(0.025, 2, 1, -1.98, 4.1, 2.15, showerGlass, 0);
beam([-1.5, 3.2, 2.58], [-1.5, 5.2, 2.58], 0.019, M.brass);
beam([-1.5, 5.2, 2.58], [-1.5, 5.2, 2.3], 0.019, M.brass);
cylinder(0.1, 0.02, -1.5, 5.2, 2.3, M.brass);
// Privacy is rendered instead of the room: it is also present in recorded video.
const privateCanvas = document.createElement("canvas");
privateCanvas.width = 1600;
privateCanvas.height = 1000;
const px = privateCanvas.getContext("2d");
px.fillStyle = "#161b19";
px.fillRect(0, 0, 1600, 1000);
for (let i = 0; i < 45; i++) {
  px.fillStyle = i % 2 ? "#1c221f" : "#202824";
  px.fillRect((i * 137) % 1600, (i * 91) % 1000, 110, 90);
}
px.textAlign = "center";
px.fillStyle = "#ecb37f";
px.font = "20px monospace";
px.fillText("SUB-01 / PRIVACY MODE", 800, 410);
px.fillStyle = "#e9e4d8";
px.font = "64px sans-serif";
px.fillText("OCCUPIED.", 800, 510);
px.fillStyle = "#a2ada4";
px.font = "24px sans-serif";
px.fillText("Even a simulated brain needs a minute.", 800, 575);
const privacyScene = new T.Scene(),
  privacyCamera = new T.OrthographicCamera(-1, 1, 1, -1, 0.1, 2);
privacyCamera.position.z = 1;
const privacyTexture = new T.CanvasTexture(privateCanvas);
privacyTexture.colorSpace = T.SRGBColorSpace;
privacyScene.add(
  new T.Mesh(
    new T.PlaneGeometry(2, 2),
    new T.MeshBasicMaterial({ map: privacyTexture, toneMapped: false }),
  ),
);
let privacyActive = false;
// Balcony and a quiet reading chair.
for (let x = -3.9; x < -0.2; x += 0.25)
  beam([x, 3, 5.2], [x, 4, 5.2], 0.018, M.metal);
beam([-3.95, 4.03, 5.2], [-0.2, 4.03, 5.2], 0.028, M.darkwood);
for (const x of [-3.95, -0.2]) beam([x, 4, 4], [x, 4, 5.2], 0.028, M.darkwood);
plant(-3.4, 3, 4.65, 1.1);
box(0.65, 0.16, 0.68, -1.2, 3.44, 4.5, M.cream, 0.07);
box(0.65, 0.6, 0.16, -1.2, 3.77, 4.8, M.cream, 0.07);
for (const x of [-1.45, -0.95])
  for (const z of [4.28, 4.7]) beam([x, 3, z], [x, 3.4, z], 0.025, M.wood);
obstacle(-1.2, 4.55, 0.72, 0.8, 1);
// Curtains keep folds while opening: one group per window.
const curtains = new T.Group();
scene.add(curtains);
const curtainPanels = [];
for (const anchor of [-3.8, -0.2]) {
  const group = new T.Group();
  group.position.set(anchor, 4.43, 3.82);
  const side = anchor < -2 ? 1 : -1;
  for (let i = 0; i < 40; i++) {
    const o = new T.Mesh(
      new T.CylinderGeometry(0.027, 0.035, 2.48, 8),
      M.linen,
    );
    o.position.set(side * i * 0.045, 0, 0);
    o.scale.z = 0.6;
    o.castShadow = true;
    group.add(o);
  }
  curtains.add(group);
  curtainPanels.push(group);
}
// Warm practical lights and the afternoon sun.
const hemi = new T.HemisphereLight("#e4eced", "#8f7965", 1.7);
scene.add(hemi);
const sun = new T.DirectionalLight("#ffdeae", 3);
sun.position.set(-12, 10, 14);
sun.target.position.set(0, 1, 0);
sun.castShadow = true;
sun.shadow.mapSize.set(
  innerWidth < 700 ? 1024 : 2048,
  innerWidth < 700 ? 1024 : 2048,
);
Object.assign(sun.shadow.camera, {
  left: -10,
  right: 10,
  top: 10,
  bottom: -10,
  near: 0.1,
  far: 45,
});
sun.shadow.normalBias = 0.025;
sun.shadow.bias = -0.00025;
scene.add(sun, sun.target);
const glowMat = new T.MeshStandardMaterial({
  color: "#fff0ce",
  emissive: "#ffcf84",
  emissiveIntensity: 1.3,
  roughness: 1,
});
const deskLamp = cylinder(0.14, 0.035, 1.1, 1.3, -3.15, glowMat);
beam([1.1, 0.85, -3.15], [1.1, 1.3, -3.15], 0.014, M.brass);
const bedsideLamp = cylinder(0.14, 0.2, -3.55, 3.84, -3.1, M.linen);
cylinder(0.03, 0.23, -3.55, 3.62, -3.1, M.brass);
const warm = new T.PointLight("#ffd49a", 6, 5, 2);
warm.position.set(1.1, 1.35, -3.15);
scene.add(warm);
const bedLight = new T.PointLight("#ffc88a", 5, 4, 2);
bedLight.position.set(-3.55, 3.9, -3.1);
scene.add(bedLight);
for (const [x, y, z] of [
  [-2, 2.55, 0.5],
  [2, 5.1, -0.2],
]) {
  const pendant = cylinder(0.23, 0.15, x, y, z, M.white);
  beam([x, y + 0.1, z], [x, 6, z], 0.006, M.black);
  cylinder(0.18, 0.013, x, y - 0.077, z, glowMat);
}
// Distant city geometry, not a heavy second scene.
const facadeCanvas = document.createElement("canvas");
facadeCanvas.width = 128;
facadeCanvas.height = 256;
const fc = facadeCanvas.getContext("2d");
fc.fillStyle = "#a2aaa9";
fc.fillRect(0, 0, 128, 256);
for (let row = 0; row < 12; row++)
  for (let col = 0; col < 5; col++) {
    fc.fillStyle = random() > 0.8 ? "#ded5b5" : "#6b7f85";
    fc.fillRect(7 + col * 25, 7 + row * 21, 12, 13);
    fc.fillStyle = "#c0c5c0";
    fc.fillRect(7 + col * 25, 20 + row * 21, 15, 2);
  }
const facade = new T.CanvasTexture(facadeCanvas);
facade.colorSpace = T.SRGBColorSpace;
facade.anisotropy = 4;
const cityGeo = new T.BoxGeometry(1, 1, 1),
  cityMat = mat("#c7ccc8", 0.9, facade),
  city = new T.InstancedMesh(cityGeo, cityMat, 100);
for (let i = 0; i < 100; i++) {
  const x = i < 60 ? (random() - 0.5) * 55 : -11 - random() * 22,
    z = i < 60 ? 14 + random() * 30 : (random() - 0.5) * 45,
    h = 2 + random() * 11;
  city.setMatrixAt(
    i,
    new T.Matrix4().compose(
      new T.Vector3(x, h / 2 - 1, z),
      new T.Quaternion(),
      new T.Vector3(1.3 + random() * 2, h, 1 + random() * 2),
    ),
  );
  city.setColorAt(i, new T.Color().setHSL(0.1, 0.025, 0.75 + random() * 0.2));
}
scene.add(city);
box(100, 0.1, 100, 0, -0.2, 0, mat("#758177"), 0);
// A light skyline landmark, drawn in the same scene with original geometry.
const towerPaint = mat("#c87848", 0.65);
for (const sx of [-1, 1])
  for (const sz of [-1, 1]) {
    beam(
      [10 + sx * 1.7, 0, 24 + sz * 1.7],
      [10 + sx * 0.25, 9, 24 + sz * 0.25],
      0.09,
      towerPaint,
    );
    for (let j = 0; j < 5; j++) {
      const y = j * 1.55,
        r = 1.7 - y * 0.16,
        r2 = 1.7 - (y + 1.55) * 0.16;
      beam(
        [10 + sx * r, y, 24 + sz * r],
        [10 - sx * r2, y + 1.55, 24 + sz * r2],
        0.04,
        towerPaint,
      );
    }
  }
box(1.8, 0.4, 1.8, 10, 6.4, 24, M.white, 0);
beam([10, 8.8, 24], [10, 12, 24], 0.07, towerPaint);
let lampOn = true,
  curtainOpen = false,
  mood = 0;
function lighting() {
  const night = mood === 1;
  sun.intensity = night ? 0.08 : 3.2;
  hemi.intensity = night ? 0.3 : 0.95;
  scene.background.set(night ? "#202e3e" : "#bcc8ce");
  scene.fog.color.copy(scene.background);
  warm.intensity = lampOn ? 3 : 0;
  bedLight.intensity = lampOn ? 2 : 0;
  glowMat.emissiveIntensity = lampOn ? 1.3 : 0;
  renderer.shadowMap.needsUpdate = true;
}
function shade() {
  curtainPanels.forEach((p) => (p.scale.x = curtainOpen ? 0.17 : 1));
}
async function toggleLamp() {
  await mutate("settings", { lamp: !lampOn });
}
async function toggleCurtain() {
  await mutate("settings", { curtain: !curtainOpen });
}
lighting();
shade();
interactions.push(
  { object: deskLamp, label: "E · Switch lamp", fn: toggleLamp },
  { object: bedsideLamp, label: "E · Switch lamp", fn: toggleLamp },
);
const places = {
  entry: { p: [2, 1.65, 3.1], look: [2, 1.65, 5.2], name: "La porta di casa" },
  outside: { p: [2, 1.65, 5.25], look: [10, 6, 24], name: "Fuori casa" },
  bathroom: {
    p: [-1.5, 4.65, 1.35],
    look: [-3.5, 4, 1.1],
    name: "Bagno · Privacy mode",
  },
  stairs: {
    p: [0.3, 1.65, 2.7],
    look: [0.3, 3.2, -1.7],
    name: "La scala in legno",
  },
  office: { p: [2, 1.65, -0.75], look: [2, 1.1, -3.3], name: "Lo studio" },
  living: {
    p: [-1.15, 1.65, -0.8],
    look: [-2, 0.8, 1.85],
    name: "Il soggiorno",
  },
  kitchen: {
    p: [-1.8, 1.65, -1.8],
    look: [-2.2, 1.2, -3.5],
    name: "La cucina",
  },
  bedroom: {
    p: [-1.2, 4.65, -0.2],
    look: [-2.4, 3.7, -2.5],
    name: "La camera",
  },
  balcony: { p: [-2.2, 4.65, 4.5], look: [-2, 4.5, 20], name: "Il balcone" },
};
let visitorStandTarget = null;
let following = true,
  drag = false,
  lastX = 0,
  lastY = 0,
  keys = {},
  lastZone = "",
  targetY = 1.65;
const clock = new T.Clock(),
  ray = new T.Raycaster();
let aimed = null;
function setLook(pos, look) {
  camera.position.fromArray(pos);
  camera.lookAt(new T.Vector3(...look));
  yaw = camera.rotation.y;
  pitch = camera.rotation.x;
  targetY = pos[1];
}
setLook(places.office.p, places.office.look);
function floorAt(x, z, feet) {
  if (x >= STEP.x0 && x <= STEP.x1 && z <= STEP.zBottom && z >= STEP.zTop)
    return (3 * (STEP.zBottom - z)) / (STEP.zBottom - STEP.zTop);
  if (feet > 1.4) {
    if (x <= -0.1 && x >= -3.85 && z <= 5.08) return 3;
    if (x <= 0.8 && x >= -0.2 && z <= -1.7) return 3;
    return null;
  }
  return 0;
}
function canWalk(x, z, feet) {
  const f = floorAt(x, z, feet);
  if (
    f === null ||
    Math.abs(f - feet) > 0.22 ||
    (feet > 1.4 && z > -1.7 && z < 4 && Math.abs(x + 0.12) < 0.18) ||
    x < -3.78 ||
    x > 3.78 ||
    z < -3.78 ||
    z > (f > 2 ? 5.04 : x >= 1.45 && x <= 2.55 ? 5.65 : 3.76)
  )
    return false;
  const level = f > 1.5 ? 1 : 0;
  return !blockers.some(
    (b) => b.level === level && x > b.x0 && x < b.x1 && z > b.z0 && z < b.z1,
  );
}
document.getElementById("follow").onclick = () => {
  following = true;
  visitorStandTarget = null;
  lookOffset.set(0, 0);
  document.getElementById("follow").classList.add("active");
  document.getElementById("explore").classList.remove("active");
};
document.getElementById("explore").onclick = () => {
  following = false;
  visitorStandTarget =
    homeState?.seated > 0.01
      ? new T.Vector3(...homeState.entry_position)
      : null;
  targetY = camera.position.y;
  document.getElementById("follow").classList.remove("active");
  document.getElementById("explore").classList.add("active");
  notice("Exploring as a visitor. SUB-01 continues his own day.");
};
document.getElementById("lamp").onclick = toggleLamp;
document.getElementById("curtain").onclick = toggleCurtain;
addEventListener("keydown", (e) => {
  if (e.target.matches("input,textarea")) return;
  if (
    [
      "w",
      "a",
      "s",
      "d",
      "ArrowUp",
      "ArrowDown",
      "ArrowLeft",
      "ArrowRight",
      "e",
    ].includes(e.key)
  ) {
    if (
      panelKind === "pong" &&
      tvGame === "pong" &&
      ["ArrowUp", "ArrowDown"].includes(e.key)
    ) {
      e.preventDefault();
      pongInput(e.key === "ArrowUp" ? -1 : 1);
      return;
    }
    if (following && e.key !== "e") return;
    e.preventDefault();
    if (e.key === "e") {
      aimed?.fn();
      return;
    }
    keys[e.key] = true;
  }
});
addEventListener("keyup", (e) => (keys[e.key] = false));
addEventListener("blur", () => (keys = {}));
renderer.domElement.addEventListener("pointerdown", (e) => {
  drag = true;
  lastX = e.clientX;
  lastY = e.clientY;
  renderer.domElement.setPointerCapture(e.pointerId);
});
renderer.domElement.addEventListener("pointermove", (e) => {
  if (!drag) return;
  if (following) {
    lookOffset.x = T.MathUtils.clamp(
      lookOffset.x - (e.clientX - lastX) * 0.003,
      -0.9,
      0.9,
    );
    lookOffset.y = T.MathUtils.clamp(
      lookOffset.y - (e.clientY - lastY) * 0.003,
      -0.6,
      0.6,
    );
  } else {
    yaw -= (e.clientX - lastX) * 0.003;
    pitch = T.MathUtils.clamp(pitch - (e.clientY - lastY) * 0.003, -1.25, 1.25);
  }
  lastX = e.clientX;
  lastY = e.clientY;
});
renderer.domElement.addEventListener("pointerup", () => (drag = false));
document.querySelectorAll("[data-key]").forEach((b) => {
  b.onpointerdown = (e) => {
    e.preventDefault();
    if (following) document.getElementById("explore").click();
    keys[b.dataset.key] = true;
    b.setPointerCapture(e.pointerId);
  };
  b.onpointerup = () => (keys[b.dataset.key] = false);
  b.onpointercancel = () => (keys[b.dataset.key] = false);
});
function update(dt) {
  officeChair.forEach(
    (o) =>
      (o.visible = !(
        (following || visitorStandTarget) &&
        homeState?.place === "desk" &&
        (!homeState?.walking || homeState?.seated > 0.01)
      )),
  );
  if (following && homeState) {
    const alpha = 1 - Math.exp(-dt * 10);
    camera.position.lerp(new T.Vector3(...homeState.position), alpha);
    targetY = camera.position.y;
    const target = new T.Vector3(...homeState.look);
    if (target.distanceTo(camera.position) > 0.1) {
      lookPoint.lerp(target, 1 - Math.exp(-dt * 3));
      camera.lookAt(lookPoint);
      camera.rotation.y += lookOffset.x;
      camera.rotation.x += lookOffset.y;
    }
    yaw = camera.rotation.y;
    pitch = camera.rotation.x;
  } else if (!following && visitorStandTarget) {
    const distance = camera.position.distanceTo(visitorStandTarget);
    camera.position.lerp(
      visitorStandTarget,
      Math.min(1, (dt * 0.9) / Math.max(0.001, distance)),
    );
    targetY = camera.position.y;
    camera.rotation.set(pitch, yaw, 0);
    if (distance < 0.02) visitorStandTarget = null;
  } else if (!following) {
    const f =
        (keys.w || keys.ArrowUp ? 1 : 0) - (keys.s || keys.ArrowDown ? 1 : 0),
      a =
        (keys.d || keys.ArrowRight ? 1 : 0) -
        (keys.a || keys.ArrowLeft ? 1 : 0),
      len = Math.hypot(f, a) || 1,
      speed = (1.4 * dt) / len,
      dx = (-Math.sin(yaw) * f + Math.cos(yaw) * a) * speed,
      dz = (-Math.cos(yaw) * f - Math.sin(yaw) * a) * speed,
      feet = targetY - 1.65;
    let x = camera.position.x,
      z = camera.position.z;
    if (canWalk(x + dx, z, feet)) x += dx;
    if (canWalk(x, z + dz, feet)) z += dz;
    camera.position.x = x;
    camera.position.z = z;
    const floor = floorAt(x, z, feet);
    if (floor !== null) targetY = floor + 1.65;
    camera.position.y = T.MathUtils.lerp(
      camera.position.y,
      targetY,
      Math.min(1, dt * 12),
    );
    camera.rotation.set(pitch, yaw, 0);
  }
  const p = camera.position;
  entranceOpen = p.y < 3 && Math.hypot(p.x - 2, p.z - 3.9) < 1.8;
  frontDoorGroup.rotation.y = T.MathUtils.lerp(
    frontDoorGroup.rotation.y,
    entranceOpen ? -Math.PI * 0.48 : 0,
    Math.min(1, dt * 7),
  );
  privacyActive =
    !!homeState?.privacy ||
    (p.y > 3 &&
      p.x < bathroomBounds.x1 &&
      p.x > bathroomBounds.x0 &&
      p.z > bathroomBounds.z0 &&
      p.z < bathroomBounds.z1);
  const doorOpen = p.y > 3 && Math.hypot(p.x + 0.85, p.z - 1.35) < 1.6;
  bathDoor.position.z = T.MathUtils.lerp(
    bathDoor.position.z,
    doorOpen ? 2.3 : 1.35,
    Math.min(1, dt * 8),
  );
  const zone = privacyActive
    ? "bathroom"
    : p.y < 3 && p.z > 3.9
      ? "outside"
      : p.y < 3 && p.z > 2.8 && p.x > 1.4 && p.x < 2.6
        ? "entry"
        : p.x >= -0.2 && p.x <= 0.8 && p.z <= 2.8 && p.z >= -1.7
          ? "stairs"
          : p.y > 3
            ? p.z > 3.7
              ? "balcony"
              : "bedroom"
            : p.x > 0.7
              ? "office"
              : p.z < -1
                ? "kitchen"
                : "living";
  if (zone !== lastZone) {
    lastZone = zone;
    document.getElementById("place").textContent = places[zone].name;
  }
  ray.setFromCamera(new T.Vector2(), camera);
  const hits = ray.intersectObjects(interactions.map((i) => i.object));
  aimed =
    hits.length && hits[0].distance < 2
      ? interactions.find((i) => i.object === hits[0].object)
      : null;
  const action = document.getElementById("action");
  action.style.display = aimed ? "block" : "none";
  action.textContent = aimed?.label || "";
}
// All devices are shared server state. A viewer never starts another brain or VM.
let homeState = null,
  computerState = {},
  panelKind = "",
  phoneApp = "home",
  onlineAt = 0,
  brainStage = "",
  homeTime = Date.now() / 1000;
const lookPoint = new T.Vector3(2, 1.16, -3.3),
  lookOffset = new T.Vector2();
const panel = document.getElementById("panel"),
  panelBody = document.getElementById("panel-body");
function notice(text) {
  const n = document.getElementById("notice");
  n.textContent = text;
  n.style.display = "block";
  clearTimeout(notice.timer);
  notice.timer = setTimeout(() => (n.style.display = "none"), 5000);
}
function terminalOutput() {
  return (computerState.output || "Connecting to his Linux computer…")
    .replace(/\r/g, "")
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "")
    .replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g, "");
}
function operatorToken() {
  return sessionStorage.getItem("sub01-operator-token") || "";
}
async function mutate(action, data) {
  try {
    const response = await fetch("/api/home/" + action, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Token": operatorToken(),
      },
      body: JSON.stringify(data),
    });
    if (response.status === 403) {
      notice("Operator access is required to edit his devices.");
      return false;
    }
    if (!response.ok) throw Error(response.status);
    const result = await response.json();
    if (result.ok === false) {
      notice("This device is not ready yet. Try again after it connects.");
      return false;
    }
    return result;
  } catch (e) {
    notice("This action could not be completed.");
    return false;
  }
}
function textEl(tag, text, cls) {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function button(text, fn) {
  const e = textEl("button", text);
  e.onclick = fn;
  return e;
}
function openPanel(kind) {
  panelKind = kind;
  panel.hidden = false;
  renderPanel(true);
}
function browserFrame(device, parent) {
  const image = new Image(),
    message = textEl("p", "Connecting to his browser…", "muted");
  image.alt =
    device === "desk"
      ? "Live browser on SUB-01’s desk"
      : "SUB-01’s phone browser";
  image.dataset.screenDevice = device;
  image.onload = () => {
    image.hidden = false;
    message.hidden = true;
  };
  image.onerror = () => {
    image.hidden = true;
    message.hidden = false;
    message.textContent = "His browser has no public page to show right now.";
  };
  image.src = "/api/screen/" + device + ".jpg?t=" + Date.now();
  parent.append(image, message);
}
function refreshPanelScreens() {
  for (const image of panelBody.querySelectorAll("[data-screen-device]")) {
    image.src =
      "/api/screen/" + image.dataset.screenDevice + ".jpg?t=" + Date.now();
  }
}
function renderPanel(reset = false) {
  if (!panelKind) return;
  const title = document.getElementById("panel-title");
  if (panelKind === "computer") {
    title.textContent = "His computer";
    if (reset) {
      panelBody.replaceChildren();
      const apps = document.createElement("div");
      apps.className = "apps";
      apps.append(
        button("Linux", () => {
          phoneApp = "linux";
          renderPanel(true);
        }),
        button("Browser", () => {
          phoneApp = "browser";
          renderPanel(true);
        }),
      );
      panelBody.append(apps);
      if (phoneApp === "browser") {
        browserFrame("desk", panelBody);
        panelBody.append(
          textEl(
            "p",
            "The real browser selected by his brain. Public view is read-only.",
            "muted",
          ),
        );
      } else {
        const pre = textEl("pre", "");
        pre.id = "terminal";
        panelBody.append(pre);
        panelBody.append(
          textEl(
            "p",
            "A real x86 Linux guest. His commands are selected using the live brain signals.",
            "muted",
          ),
        );
        const form = document.createElement("form"),
          input = document.createElement("input");
        input.placeholder = "Operator: send a command to his Linux guest";
        form.append(
          input,
          button("Run", () => {}),
        );
        form.onsubmit = async (e) => {
          e.preventDefault();
          if (await mutate("computer", { input: input.value }))
            input.value = "";
        };
        panelBody.append(form);
      }
      const token = document.createElement("input");
      token.type = "password";
      token.placeholder = "Operator key (only needed for editing)";
      token.autocomplete = "off";
      token.value = operatorToken();
      token.oninput = () =>
        sessionStorage.setItem("sub01-operator-token", token.value);
      panelBody.append(
        token,
        button("Connect as operator", () => {
          sessionStorage.setItem("sub01-operator-token", token.value);
          notice("Operator key saved for this tab.");
        }),
      );
    }
    const terminal = document.getElementById("terminal");
    if (terminal)
      terminal.textContent =
        terminalOutput() + "\n\n[" + (computerState.status || "offline") + "]";
  } else if (panelKind === "pong") {
    title.textContent = "Wall TV / " + (tvGame === "chess" ? "Chess" : "Pong");
    if (reset) {
      panelBody.replaceChildren();
      const choices = document.createElement("div");
      choices.className = "apps";
      choices.append(
        button("Pong", () => {
          tvGame = "pong";
          renderPanel(true);
        }),
        button("Chess", () => {
          tvGame = "chess";
          renderPanel(true);
        }),
      );
      panelBody.append(choices);
      const c = document.createElement("canvas");
      c.id = "pong-panel";
      c.width = 800;
      c.height = 460;
      panelBody.append(c);
      panelBody.append(
        textEl(
          "p",
          tvGame === "chess"
            ? "His live chess board. Each of his moves goes through the existing brain vote. Send “play chess” through the phone to give him the idea."
            : "SUB-01 controls the left paddle through live motor and attention signals. You can control the right with ↑ / ↓. He plays when he chooses the console.",
          "muted",
        ),
      );
      if (tvGame === "pong")
        panelBody.append(
          button("↑", () => pongInput(-1)),
          button("↓", () => pongInput(1)),
        );
    }
    if (tvGame === "chess")
      drawChess(document.getElementById("pong-panel"), chessState?.game);
    else drawPong(document.getElementById("pong-panel"), homeState?.pong);
  } else if (panelKind === "phone") {
    title.textContent = "Phone · " + (homeState?.phone.battery ?? "—") + "%";
    if (reset) {
      panelBody.replaceChildren();
      const apps = document.createElement("div");
      apps.className = "apps";
      for (const name of [
        "home",
        "notes",
        "memory",
        "browser",
        "messages",
        "music",
      ])
        apps.append(
          button(name, () => {
            phoneApp = name;
            renderPanel(true);
          }),
        );
      panelBody.append(apps);
      const content = document.createElement("div");
      content.id = "phone-content";
      panelBody.append(content);
    }
    const content = document.getElementById("phone-content");
    if (!content) return;
    if (phoneApp === "notes") {
      if (reset) {
        content.replaceChildren();
        for (const note of homeState?.notes || [])
          content.append(textEl("div", note.text, "entry"));
        const form = document.createElement("form"),
          ta = document.createElement("textarea");
        ta.placeholder = "Operator: leave a note";
        form.append(
          ta,
          button("Save", () => {}),
        );
        form.onsubmit = async (e) => {
          e.preventDefault();
          if (await mutate("notes", { text: ta.value })) {
            await syncState();
            renderPanel(true);
          }
        };
        content.append(form);
      }
    } else if (phoneApp === "memory") {
      content.replaceChildren();
      for (const m of homeState?.memories || [])
        content.append(
          textEl(
            "div",
            m.command || m.what || m.activity + " · " + m.place,
            "entry",
          ),
        );
    } else if (phoneApp === "browser") {
      if (reset) {
        content.replaceChildren();
        browserFrame("phone", content);
      }
    } else if (phoneApp === "messages") {
      if (reset) {
        content.replaceChildren(
          textEl(
            "p",
            "Send an impulse. His needs and brain activity decide what happens next.",
            "muted",
          ),
        );
        const form = document.createElement("form"),
          input = document.createElement("input");
        input.placeholder = "Try: play Pong, go outside, use Linux…";
        form.append(
          input,
          button("Send impulse", () => {}),
        );
        form.onsubmit = (e) => {
          e.preventDefault();
          if (socket?.readyState === 1) {
            socket.send(
              JSON.stringify({
                type: "chat",
                text: input.value,
                nick: "a visitor",
              }),
            );
            input.value = "";
            notice("Impulse sent.");
          }
        };
        content.append(form);
      }
    } else if (phoneApp === "music") {
      if (reset) {
        content.replaceChildren(
          textEl("p", "Tracks chosen by SUB-01’s live brain model.", "muted"),
        );
        fetch("/api/music")
          .then((r) => r.json())
          .then((m) => {
            const songs = m.now ? [m.now, ...(m.today || [])] : m.today || [];
            if (!songs.length)
              content.append(
                textEl("p", "No track selected right now.", "muted"),
              );
            for (const song of songs.slice(0, 8)) {
              const row = textEl(
                "div",
                song.title + " · " + song.artist,
                "entry",
              );
              if (
                /^https:\/\/open\.spotify\.com\/track\/[A-Za-z0-9]+$/.test(
                  song.url || "",
                )
              ) {
                const a = textEl("a", "Listen");
                a.href = song.url;
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                row.append(document.createElement("br"), a);
              }
              content.append(row);
            }
          })
          .catch(() => {});
      }
    } else {
      content.replaceChildren(
        textEl(
          "h2",
          new Intl.DateTimeFormat("en-GB", {
            timeZone: "Asia/Tokyo",
            hour: "2-digit",
            minute: "2-digit",
          }).format(new Date(homeTime * 1000)),
        ),
        textEl("p", "Tokyo · " + brainStage, "muted"),
        textEl(
          "p",
          "Current activity: " + (homeState?.activity || "connecting"),
          "muted",
        ),
      );
    }
  }
}
let chessState = null,
  tvGame = "pong";
let lastPongInput = 0;
async function pongInput(direction) {
  if (Date.now() - lastPongInput < 100) return;
  lastPongInput = Date.now();
  try {
    await fetch("/api/home/pong", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction }),
    });
  } catch {}
}
function drawPong(canvas, state) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d"),
    w = canvas.width,
    h = canvas.height;
  ctx.fillStyle = "#0d191a";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#93a8a344";
  for (let y = 0; y < h; y += 24) ctx.fillRect(w / 2 - 1, y, 2, 12);
  ctx.fillStyle = "#ff9d58";
  ctx.font = "32px monospace";
  ctx.textAlign = "center";
  ctx.fillText((state?.score || [0, 0]).join("   :   "), w / 2, 48);
  const p = state?.paddles || [0.5, 0.5],
    b = state?.ball || [0.5, 0.5];
  ctx.fillStyle = "#d9e8d9";
  ctx.fillRect(w * 0.04, p[0] * h - h * 0.1, 8, h * 0.2);
  ctx.fillRect(w * 0.95, p[1] * h - h * 0.1, 8, h * 0.2);
  ctx.beginPath();
  ctx.arc(b[0] * w, b[1] * h, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.font = "16px monospace";
  ctx.fillStyle = "#acbbb6";
  ctx.fillText(
    state?.active ? "SUB-01 / LIVE" : "WAITING FOR SUB-01",
    w / 2,
    h - 24,
  );
}
function drawChess(canvas, game) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d"),
    w = canvas.width,
    h = canvas.height;
  ctx.fillStyle = "#10201a";
  ctx.fillRect(0, 0, w, h);
  const size = Math.min(h - 50, w * 0.72),
    cell = size / 8,
    x = (w - size) / 2,
    y = 18;
  const pieces = {
    p: "♟",
    r: "♜",
    n: "♞",
    b: "♝",
    q: "♛",
    k: "♚",
    P: "♙",
    R: "♖",
    N: "♘",
    B: "♗",
    Q: "♕",
    K: "♔",
  };
  const ranks = (game?.fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")
    .split(" ")[0]
    .split("/");
  for (let row = 0; row < 8; row++) {
    let column = 0;
    for (let col = 0; col < 8; col++) {
      ctx.fillStyle = (row + col) % 2 ? "#6b8374" : "#e1d6b9";
      ctx.fillRect(x + col * cell, y + row * cell, cell, cell);
    }
    column = 0;
    for (const piece of ranks[row]) {
      if (/[1-8]/.test(piece)) {
        column += Number(piece);
        continue;
      }
      ctx.font = Math.round(cell * 0.8) + "px serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.strokeStyle = "#182820";
      ctx.lineWidth = 1;
      ctx.fillStyle = piece === piece.toUpperCase() ? "#fff5df" : "#162720";
      ctx.strokeText(
        pieces[piece],
        x + (column + 0.5) * cell,
        y + (row + 0.5) * cell,
      );
      ctx.fillText(
        pieces[piece],
        x + (column + 0.5) * cell,
        y + (row + 0.5) * cell,
      );
      column++;
    }
  }
  ctx.font = "16px sans-serif";
  ctx.fillStyle = "#ffad6a";
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(
    game
      ? (game.moves || []).slice(-4).join(" · ") || "First move"
      : "Waiting for his next chess game",
    w / 2,
    h - 12,
  );
}
function drawTV() {
  if (tvGame === "chess" || homeState?.activity === "play_chess")
    drawChess(tvCanvas, chessState?.game);
  else drawPong(tvCanvas, homeState?.pong);
  tvTexture.needsUpdate = true;
}
const tvCanvas = document.createElement("canvas");
tvCanvas.width = 800;
tvCanvas.height = 460;
const tvTexture = new T.CanvasTexture(tvCanvas);
tvTexture.colorSpace = T.SRGBColorSpace;
box(0.085, 1.02, 1.74, -3.8, 1.65, -0.05, M.black, 0.03);
box(0.14, 2.8, 2.15, -3.84, 1.4, -0.05, M.wall, 0);
const tv = new T.Mesh(
  new T.PlaneGeometry(1.66, 0.95),
  new T.MeshBasicMaterial({ map: tvTexture, toneMapped: false }),
);
tv.rotation.y = Math.PI / 2;
tv.position.set(-3.747, 1.65, -0.05);
scene.add(tv);
interactions.push({
  object: tv,
  label: "E · TV / Pong",
  fn: () => openPanel("pong"),
});
drawPong(tvCanvas);
const phoneMesh = box(0.075, 0.015, 0.15, 2.7, 0.858, -2.92, M.black, 0.014);
interactions.push({
  object: phoneMesh,
  label: "E · Phone",
  fn: () => openPanel("phone"),
});
function drawComputer() {
  sx.fillStyle = "#10201a";
  sx.fillRect(0, 0, 1024, 600);
  sx.fillStyle = "#ffae69";
  sx.font = "24px monospace";
  sx.fillText(
    "SUB-01 / " + (homeState?.activity === "use_computer" ? "LINUX" : "DESK"),
    28,
    38,
  );
  sx.fillStyle = "#b7d9c4";
  sx.font = "15px monospace";
  const lines = terminalOutput().split("\n").slice(-29);
  lines.forEach((l, i) => sx.fillText(l.slice(0, 105), 28, 68 + i * 17));
  st.needsUpdate = true;
}
let screenFetching = false;
async function updateRealBrowser() {
  if (screenFetching || homeState?.activity === "use_computer") return;
  screenFetching = true;
  try {
    const res = await fetch("/api/screen/desk.jpg");
    if (res.ok) {
      const image = await createImageBitmap(await res.blob());
      sx.fillStyle = "#14201b";
      sx.fillRect(0, 0, 1024, 600);
      sx.drawImage(image, 0, 0, 1024, 600);
      image.close();
      st.needsUpdate = true;
    } else {
      sx.fillStyle = "#10201a";
      sx.fillRect(0, 0, 1024, 600);
      sx.fillStyle = "#cbd6c8";
      sx.font = "24px sans-serif";
      sx.textAlign = "left";
      sx.fillText("His browser has no public page to show right now.", 32, 300);
      st.needsUpdate = true;
    }
  } catch {
  } finally {
    screenFetching = false;
  }
}
function acceptHome(state) {
  if (!state) return;
  if (!homeState) {
    setLook(state.position, state.look);
    lookPoint.fromArray(state.look);
  }
  homeState = { ...homeState, ...state };
  if (!state.notes?.length && homeState.notes?.length === 0 && lastFullHome)
    homeState.notes = lastFullHome.notes;
  if (!state.memories?.length && lastFullHome)
    homeState.memories = lastFullHome.memories;
  onlineAt = performance.now();
  document.getElementById("activity").textContent = state.privacy
    ? "Bathroom · privacy mode"
    : state.activity.replaceAll("_", " ") + " · " + brainStage;
  const settings = state.settings || {};
  const changed = lampOn !== settings.lamp || curtainOpen !== settings.curtain;
  lampOn = settings.lamp !== false;
  curtainOpen = !!settings.curtain;
  if (changed) {
    lighting();
    shade();
  }
  drawTV();
  if (state.activity === "use_computer") drawComputer();
  renderPanel();
}
let lastFullHome = null;
async function syncState() {
  try {
    const r = await fetch("/api/home");
    if (!r.ok) {
      notice("The home is not enabled on this server yet.");
      return;
    }
    const s = await r.json();
    try {
      chessState = await (await fetch("/api/chess")).json();
    } catch {}
    lastFullHome = s.home;
    computerState = s.computer;
    homeTime = s.time;
    brainStage = s.stage;
    acceptHome(s.home);
    if (homeState.activity === "play_chess") {
      drawChess(screenCanvas, chessState?.game);
      st.needsUpdate = true;
    } else if (homeState.activity === "use_computer") drawComputer();
    else await updateRealBrowser();
    refreshPanelScreens();
  } catch {}
}
let socket, reconnectTimer;
function connect() {
  socket = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host +
      "/ws?rate=5&lite=1",
  );
  socket.onmessage = (e) => {
    try {
      const m = JSON.parse(e.data);
      if (m.type === "chess") {
        chessState = { ...chessState, game: m };
        drawTV();
        if (panelKind === "pong") renderPanel();
      }
      if (m.home) {
        brainStage = m.stage || m.sleep?.stage || brainStage;
        acceptHome(m.home);
      }
    } catch {}
  };
  socket.onclose = () => {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 2000);
  };
}
connect();
syncState();
setInterval(syncState, 3000);
setInterval(() => {
  const fresh = performance.now() - onlineAt < 5000;
  document.getElementById("connection").textContent = fresh
    ? "● LIVE / " + (following ? "his eyes" : "visitor mode")
    : "Reconnecting…";
}, 1000);
document.getElementById("pc").onclick = () => {
  phoneApp = "linux";
  openPanel("computer");
};
document.getElementById("tv").onclick = () => openPanel("pong");
document.getElementById("phone").onclick = () => {
  phoneApp = "home";
  openPanel("phone");
};
document.getElementById("close").onclick = () => {
  panel.hidden = true;
  panelKind = "";
};
addEventListener("pagehide", () => {
  socket?.close();
});
const protectedObjects = new Set([
  ...interactions.map((i) => i.object),
  ...officeChair,
  bathDoor,
]);
function batchArchitecture() {
  scene.updateMatrixWorld(true);
  const groups = new Map();
  for (const child of [...scene.children]) {
    if (
      !child.isMesh ||
      child.isInstancedMesh ||
      protectedObjects.has(child) ||
      Array.isArray(child.material)
    )
      continue;
    const key =
      child.material.uuid +
      ":" +
      child.castShadow +
      ":" +
      child.receiveShadow +
      ":" +
      !!child.geometry.index +
      ":" +
      Object.keys(child.geometry.attributes).sort().join(",");
    const items = groups.get(key) || [];
    items.push(child);
    groups.set(key, items);
  }
  for (const items of groups.values()) {
    if (items.length < 3) continue;
    const parts = items.map((o) =>
      o.geometry.clone().applyMatrix4(o.matrixWorld),
    );
    const geometry = mergeGeometries(parts);
    parts.forEach((g) => g.dispose());
    if (!geometry) continue;
    const mesh = new T.Mesh(geometry, items[0].material);
    mesh.castShadow = items[0].castShadow;
    mesh.receiveShadow = items[0].receiveShadow;
    scene.add(mesh);
    for (const old of items) {
      scene.remove(old);
      old.geometry.dispose();
    }
  }
  renderer.shadowMap.needsUpdate = true;
}
batchArchitecture();
// Stable IDs let offline light maps replace only geometry, preserving live devices.
const bakedObjects = new Map();
for (const child of scene.children) {
  if (
    !child.isMesh ||
    child.isInstancedMesh ||
    protectedObjects.has(child) ||
    Array.isArray(child.material) ||
    !child.receiveShadow
  )
    continue;
  const id = "house-static-" + bakedObjects.size;
  child.name = id;
  child.userData.bakeId = id;
  bakedObjects.set(id, child);
}
// Baked contact lighting is optional: geometry/material fallback remains functional.
async function applyContactLighting() {
  try {
    const [baked, ao] = await Promise.all([
      gltfLoader.loadAsync("/house/assets/lighting/architecture.glb"),
      loader.loadAsync(
        "/house/assets/lighting/contact-ao" + (lite ? "-lite" : "") + ".jpg",
      ),
    ]);
    ao.channel = 1;
    ao.colorSpace = T.NoColorSpace;
    scene.updateMatrixWorld(true);
    baked.scene.updateMatrixWorld(true);
    let applied = 0;
    baked.scene.traverse((part) => {
      if (!part.isMesh) return;
      const original = bakedObjects.get(part.userData.bakeId || part.name);
      if (!original || original.userData.flexibleCloth || !part.geometry.attributes.uv1) return;
      const geometry = part.geometry.clone();
      geometry.applyMatrix4(part.matrixWorld);
      geometry.applyMatrix4(original.matrixWorld.clone().invert());
      const oldBounds = new T.Box3().setFromBufferAttribute(
        original.geometry.attributes.position,
      );
      const newBounds = new T.Box3().setFromBufferAttribute(
        geometry.attributes.position,
      );
      // Reject outdated bakes after any layout change instead of distorting furniture.
      if (
        oldBounds.min.distanceTo(newBounds.min) > 0.03 ||
        oldBounds.max.distanceTo(newBounds.max) > 0.03
      ) {
        geometry.dispose();
        return;
      }
      original.geometry.dispose();
      original.geometry = geometry;
      original.material = original.material.clone();
      original.material.aoMap = ao;
      original.material.aoMapIntensity = 1;
      original.material.needsUpdate = true;
      applied++;
    });
    document.getElementById("status").dataset.contactMaps = String(applied);
    renderer.shadowMap.needsUpdate = true;
  } catch (error) {
    console.warn("Contact lighting unavailable:", error.message);
  }
}
applyContactLighting();

addEventListener("resize", () => {
  renderer.setPixelRatio(
    Math.min(
      devicePixelRatio,
      Math.sqrt((lite ? 750000 : 1800000) / (innerWidth * innerHeight)),
      1.5,
    ),
  );
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});
setTimeout(() => {
  document.getElementById("load").style.display = "none";
}, 15000);
renderer.shadowMap.needsUpdate = true;
let frames = 0,
  elapsed = 0,
  lastFrameTime = 0,
  accumulated = 0;
renderer.setAnimationLoop(() => {
  if (document.hidden) {
    clock.getDelta();
    return;
  }
  accumulated += clock.getDelta();
  if (accumulated < 1 / 60) return;
  const dt = Math.min(accumulated, 0.05);
  accumulated = 0;
  update(dt);
  if (!privacyActive)
    for (const view of windowViews)
      view.update(dt, homeTime ? (homeTime / 3600 + 9) % 24 : 14);
  renderer.render(
    privacyActive ? privacyScene : scene,
    privacyActive ? privacyCamera : camera,
  );
  frames++;
  elapsed += clock.elapsedTime - lastFrameTime;
  lastFrameTime = clock.elapsedTime;
  if (elapsed > 1) {
    document.getElementById("status").textContent =
      location.hostname === "127.0.0.1"
        ? `${Math.round(frames / elapsed)} fps · ${renderer.info.render.calls} draw calls · ${camera.position.y > 3 ? "piano 2" : "piano 1"}`
        : "";
    document.getElementById("status").dataset.direction = JSON.stringify([
      camera.rotation.x,
      camera.rotation.y,
    ]);
    document.getElementById("status").dataset.position = JSON.stringify([
      camera.position.x,
      camera.position.y,
      camera.position.z,
      yaw,
      pitch,
    ]);
    frames = 0;
    elapsed = 0;
  }
});

// Local operator tooling: export the actual house for offline lighting work.
if (
  location.hostname === "127.0.0.1" &&
  new URLSearchParams(location.search).has("bake")
) {
  const b = button("Export house geometry", async () => {
    const data = await new GLTFExporter().parseAsync(scene, {
      binary: true,
      onlyVisible: true,
    });
    const response = await fetch("/snap?name=home-bake-source&ext=png", {
      method: "POST",
      body: data,
    });
    if (response.ok) notice("House geometry exported for light baking.");
  });
  document.querySelector("footer").append(b);
}
