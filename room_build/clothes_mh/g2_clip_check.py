"""G2's motion clips on the dressed body: three.js r169 loads assets/g2/boy_g2_dressed.glb and a clip from G2's
clips_g2 (preview/mh-motion, room_build/mh/glb/clips_g2), binds the clip to the dressed scene by node name (as the room
page does) and renders frames, so the clothes are seen following the body through the motion.
    python g2_clip_check.py [out.jpg]
The clips are read from g2/<name>.glb (git show origin/preview/mh-motion:room_build/mh/glb/clips_g2/<name>.glb)."""
import os, sys, json, mimetypes
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
THREE = HERE.parent / "node_modules" / "three"
GLB = HERE / "assets" / "g2" / "boy_g2_dressed.glb"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else HERE.parent.parent / "docs" / "design" / "clothes-mh" / "g2_clips.jpg")
# (clip, time in s (negative: from the end), view, props). COORD A's rows: walking and standing (the trousers' front);
# on the bed's edge (4 s) and lying (12 s) with the bed (mattress top 0.66 m, x -1.0..0.75, z 0.74..1.99 in the clip's
# frame); sitting down onto a chair (seat top 0.505 m, centre (-0.26, -0.13) in room_sit_down's frame) and typing at
# the desk on a chair under the hips
SHOTS = [("room_walk", 0.3, "front", ""), ("room_walk", 0.85, "side", ""), ("room_stand_up", -0.01, "frontclose", ""),
         ("room_bed_lie", 4.0, "side", "bed"), ("room_bed_lie", 12.0, "side", "bed"), ("room_bed_lie", 12.0, "top", "bed"),
         ("room_sit_down", -0.01, "side", "chair"), ("room_sit_down", -0.01, "front", "chair"), ("desk_type_ik", 3.0, "side", "chairhips")]

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>
</head><body><script type="module">
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
const W = innerWidth, H = innerHeight;
const renderer = new THREE.WebGLRenderer({antialias:true, preserveDrawingBuffer:true}); renderer.setSize(W, H); renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a2b30);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.5;
scene.add(new THREE.HemisphereLight(0xfff1dd, 0x1a1a24, 0.8));
const sun = new THREE.DirectionalLight(0xfff0dc, 2.6); sun.position.set(-2, 3.5, 2.5); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; Object.assign(sun.shadow.camera, {left:-2, right:2, top:2, bottom:-2}); scene.add(sun);
const propMat = new THREE.MeshStandardMaterial({color:0x9a958c, roughness:0.85});
const bed = new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.66, 1.25), new THREE.MeshStandardMaterial({color:0xd8d4cc, roughness:0.9}));
bed.position.set((-1.0 + 0.75) / 2, 0.33, (0.74 + 1.99) / 2); bed.castShadow = bed.receiveShadow = true;
const chair = new THREE.Group();
{ const seat = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.05, 0.44), propMat); seat.position.y = 0.52 - 0.025; chair.add(seat);
  for (const [x, z] of [[-0.19, -0.19], [0.19, -0.19], [-0.19, 0.19], [0.19, 0.19]]) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.495, 0.03), propMat); l.position.set(x, 0.2475, z); chair.add(l); }
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.45, 0.03), propMat); back.position.set(0, 0.52 + 0.225, -0.22); chair.add(back);
  chair.traverse(o => { if (o.isMesh) o.castShadow = o.receiveShadow = true; }); }
const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({color:0x6b5440, roughness:0.75}));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
const camera = new THREE.PerspectiveCamera(32, W / H, 0.02, 50);
const loader = new GLTFLoader(); let root, mixer; const clips = {};
let CORR = null;
// the clothes' corrective shapes (morph targets), weighted from the skeleton each frame after the animation: exactly what
// the room page must do (the drivers are in the file: extras.correctives; README.md, g2_pose.py)
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
window.applyCorrectives = () => {
  if (!CORR) return {};
  const p = n => { const v = new THREE.Vector3(); root.getObjectByName(n).getWorldPosition(v); return v; };
  const down = p("Hips").sub(p("neck")).normalize(), deg = (a, b) => THREE.MathUtils.radToDeg(a.angleTo(b)), w = {};
  for (const [name, d] of Object.entries(CORR.drivers)) {
    let v = 0;
    if (d.type === "hip_bend") v = (deg(p("LeftLeg").sub(p("LeftUpLeg")), down) + deg(p("RightLeg").sub(p("RightUpLeg")), down)) / 2;
    else if (d.type === "elbow_bend") v = deg(p(d.side + "ForeArm").sub(p(d.side + "Arm")), p(d.side + "Hand").sub(p(d.side + "ForeArm")));
    else if (d.type === "chest_up") { const f = new THREE.Vector3().crossVectors(p("LeftArm").sub(p("RightArm")), down.clone().negate()).normalize(); v = f.y; }
    w[name] = smooth(d.from, d.to, v);
  }
  root.traverse(o => { if (o.isMesh && o.morphTargetDictionary) for (const [nm, i] of Object.entries(o.morphTargetDictionary)) o.morphTargetInfluences[i] = w[nm] || 0; });
  return w;
};
loader.load("dressed.glb", g => { root = g.scene; CORR = (g.parser.json.extras || {}).correctives || null; root.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; o.frustumCulled = false; } });
  scene.add(root); mixer = new THREE.AnimationMixer(root); window.ready = true; });
window.loadClip = (name) => new Promise(res => loader.load(name + ".glb", g => { clips[name] = g.animations[0]; res(g.animations[0].duration); }));
window.shoot = (name, time, view, props) => {
  mixer.stopAllAction(); const clip = clips[name], act = mixer.clipAction(clip); act.play(); mixer.setTime(time < 0 ? clip.duration + time : time);
  root.updateMatrixWorld(true); window.lastWeights = applyCorrectives();
  const box = new THREE.Box3(); root.traverse(o => { if (o.isSkinnedMesh) { o.skeleton.update(); } });
  const hips = root.getObjectByName("Hips"); const c = new THREE.Vector3(); hips.getWorldPosition(c);
  scene.remove(bed); scene.remove(chair);
  if (props === "bed") scene.add(bed);
  if (props === "chair") { chair.position.set(-0.26, 0, -0.13); chair.rotation.y = 0; scene.add(chair); }
  if (props === "chairhips") {                            // under the hips, facing where the knees point
    const k = new THREE.Vector3(), k2 = new THREE.Vector3(); root.getObjectByName("LeftLeg").getWorldPosition(k); root.getObjectByName("RightLeg").getWorldPosition(k2);
    const f = k.add(k2).multiplyScalar(0.5).sub(c); f.y = 0; f.normalize();
    chair.position.set(c.x + f.x * 0.08, 0, c.z + f.z * 0.08); chair.rotation.y = Math.atan2(f.x, f.z); scene.add(chair); }
  const ty = view === "frontclose" ? c.y - 0.12 : props === "bed" ? 0.75 : 0.8;
  const t = new THREE.Vector3(c.x, ty, c.z);
  const dir = view === "side" ? new THREE.Vector3(1, 0.15, 0.25) : view === "top" ? new THREE.Vector3(0.25, 1.6, 0.35) : new THREE.Vector3(0.35, 0.18, 1);
  camera.position.copy(t).addScaledVector(dir.normalize(), view === "frontclose" ? 1.4 : props === "bed" ? 3.6 : 4.2); camera.lookAt(t); camera.updateProjectionMatrix();
  sun.target.position.copy(t); scene.add(sun.target);
  renderer.render(scene, camera); return clip.tracks.length;
};
</script></body></html>"""


def main():
    global SHOTS
    if os.environ.get("ONLY"): SHOTS = [x for x in SHOTS if os.environ["ONLY"] in f"{x[0]}_{x[2]}"]
    from playwright.sync_api import sync_playwright
    tmp = HERE / "out" / "g2web"; tmp.mkdir(parents=True, exist_ok=True); shots = []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"),
                               args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = br.new_page(viewport={"width": 520, "height": 640})
        pg.on("console", lambda m: print("page:", m.text[:200], flush=True)); pg.on("pageerror", lambda e: print("pageerror:", e, flush=True))
        def three(route):
            u = route.request.url
            f = THREE / "build" / u.split("/build/")[1] if "/build/" in u else THREE / "examples" / "jsm" / u.split("/examples/jsm/")[1]
            route.fulfill(path=str(f), content_type=mimetypes.guess_type(str(f))[0] or "text/javascript")
        pg.route("https://cdn.jsdelivr.net/**", three)
        pg.route("**/page.html", lambda r: r.fulfill(body=PAGE, content_type="text/html"))
        pg.route("**/dressed.glb", lambda r: r.fulfill(path=str(GLB), content_type="model/gltf-binary"))
        for name in sorted({s[0] for s in SHOTS}):
            pg.route(f"**/{name}.glb", lambda r, *_, n=name: r.fulfill(path=str(HERE / "g2" / f"{n}.glb"), content_type="model/gltf-binary"))
        pg.goto("http://clothes.local/page.html"); pg.wait_for_function("window.ready === true", timeout=240000)
        for name in sorted({s[0] for s in SHOTS}): print(name, "duration", pg.evaluate(f"loadClip('{name}')"))
        for name, f, view, props in SHOTS:
            n = pg.evaluate(f"shoot('{name}', {f}, '{view}', '{props}')"); pg.wait_for_timeout(200)
            out = tmp / f"{name}_{f}_{view}.png"; pg.screenshot(path=str(out)); shots.append(out)
            print("shot", out.name, "tracks", n, "shapes", {k: round(v, 2) for k, v in (pg.evaluate("window.lastWeights") or {}).items()})
        br.close()
    ims = [Image.open(f).convert("RGB") for f in shots]; w, h = ims[0].size; g = 6; cols = 3
    rows_ = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols - 1) * g, rows_ * h + (rows_ - 1) * g), (20, 20, 22))
    for k, im in enumerate(ims): sheet.paste(im, ((k % cols) * (w + g), (k // cols) * (h + g)))
    OUT.parent.mkdir(parents=True, exist_ok=True); sheet.save(OUT, quality=88); print("wrote", OUT)


if __name__ == "__main__":
    main()
