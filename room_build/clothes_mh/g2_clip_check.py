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
SHOTS = [("desk_type", 0.5, "front"), ("desk_type", 0.5, "side"), ("room_walk", 0.35, "front"),
         ("room_walk", 0.7, "side"), ("room_sit_down", 0.55, "side"), ("room_sit_down", 1.0, "front")]

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
const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({color:0x6b5440, roughness:0.75}));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
const camera = new THREE.PerspectiveCamera(32, W / H, 0.02, 50);
const loader = new GLTFLoader(); let root, mixer; const clips = {};
loader.load("dressed.glb", g => { root = g.scene; root.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; o.frustumCulled = false; } });
  scene.add(root); mixer = new THREE.AnimationMixer(root); window.ready = true; });
window.loadClip = (name) => new Promise(res => loader.load(name + ".glb", g => { clips[name] = g.animations[0]; res(g.animations[0].duration); }));
window.shoot = (name, f, view) => {
  mixer.stopAllAction(); const clip = clips[name], act = mixer.clipAction(clip); act.play(); mixer.setTime(f * clip.duration);
  root.updateMatrixWorld(true);
  const box = new THREE.Box3(); root.traverse(o => { if (o.isSkinnedMesh) { o.skeleton.update(); } });
  const hips = root.getObjectByName("Hips"); const c = new THREE.Vector3(); hips.getWorldPosition(c);
  const t = new THREE.Vector3(c.x, 0.8, c.z), dir = view === "side" ? new THREE.Vector3(1, 0.15, 0.25) : new THREE.Vector3(0.35, 0.18, 1);
  camera.position.copy(t).addScaledVector(dir.normalize(), 4.2); camera.lookAt(t); camera.updateProjectionMatrix();
  sun.target.position.copy(t); scene.add(sun.target);
  renderer.render(scene, camera); return clip.tracks.length;
};
</script></body></html>"""


def main():
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
        for name, f, view in SHOTS:
            n = pg.evaluate(f"shoot('{name}', {f}, '{view}')"); pg.wait_for_timeout(200)
            out = tmp / f"{name}_{f}_{view}.png"; pg.screenshot(path=str(out)); shots.append(out); print("shot", out.name, "tracks", n)
        br.close()
    ims = [Image.open(f).convert("RGB") for f in shots]; w, h = ims[0].size; g = 6; cols = 3
    sheet = Image.new("RGB", (cols * w + (cols - 1) * g, 2 * h + g), (20, 20, 22))
    for k, im in enumerate(ims): sheet.paste(im, ((k % cols) * (w + g), (k // cols) * (h + g)))
    OUT.parent.mkdir(parents=True, exist_ok=True); sheet.save(OUT, quality=88); print("wrote", OUT)


if __name__ == "__main__":
    main()
