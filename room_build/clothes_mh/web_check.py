"""The clothes as web materials: build_clothes.py's out/web_check.glb (the seated figure with the baked fabric maps,
sheen as KHR_materials_sheen) rendered by three.js r169 with the room page's lights: daylight (the sun 0xfff0dc, the sky
fill, the hemisphere light) and the evening desk lamp (0xffb468, distance 2.2, decay 1.8), ACES tone mapping, the
room environment map. Two distances: a medium shot (2.3 m) and the room's distance (5 m). Headless Chromium draws WebGL
in software here: the look is the page's, not its speed.
    python web_check.py [glb] [out.jpg]"""
import os, sys, json
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
THREE = HERE.parent / "node_modules" / "three"
GLB = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "out" / "web_check.glb").resolve()
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else HERE.parent.parent / "docs" / "design" / "clothes-mh" / "web_check.jpg")

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>
</head><body><script type="module">
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
const W = innerWidth, H = innerHeight;
const renderer = new THREE.WebGLRenderer({antialias:true, preserveDrawingBuffer:true}); renderer.setSize(W, H); renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d1e22);
const pmrem = new THREE.PMREMGenerator(renderer); scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.35;
const camera = new THREE.PerspectiveCamera(30, W / H, 0.02, 100);
const hemi = new THREE.HemisphereLight(0xfff1dd, 0x1a1a24, 0.6); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff0dc, 1); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02;
Object.assign(sun.shadow.camera, {left:-2, right:2, top:2, bottom:-2, near:0.1, far:20}); scene.add(sun, sun.target);
const lamp = new THREE.PointLight(0xffb468, 0, 2.2, 1.8); lamp.castShadow = true; lamp.shadow.bias = -0.002; lamp.shadow.normalBias = 0.02; scene.add(lamp);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({color:0x6b5440, roughness:0.7}));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
const mats = []; let box = null;
new GLTFLoader().load("model.glb", g => {
  const root = g.scene; root.scale.setScalar(0.1); scene.add(root); root.updateMatrixWorld(true);
  root.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; if (!mats.includes(o.material)) mats.push(o.material);
    for (const k of ["map", "normalMap"]) if (o.material[k]) o.material[k].anisotropy = 8; } });
  const b = new THREE.Box3().setFromObject(root); floor.position.y = b.min.y;
  const desk = root.getObjectByName("desk"); box = new THREE.Box3().setFromObject(desk || root);
  window.info = {mats: mats.map(m => ({name: m.name, type: m.type, map: !!m.map, normal: !!m.normalMap, sheen: m.sheen || 0}))};
  window.ready = true;
});
window.shoot = (mode, dist) => {
  const night = mode === "lamp", day = night ? 0 : 1;
  sun.intensity = 0.15 + 3.2 * day; sun.color.set(night ? 0x7d93d8 : 0xfff0dc);
  sun.position.set(-3, 3.2, 1.2); sun.target.position.set(0, 0.4, 0);
  hemi.intensity = night ? 0.14 : 0.7; hemi.color.setHSL(0.085, 0.45, night ? 0.58 : 0.8);
  hemi.groundColor.setRGB(0.20, 0.13, 0.08).lerp(new THREE.Color(0.22, 0.27, 0.50), night ? 1 : 0);
  for (const m of mats) m.envMapIntensity = night ? 0.09 : 0.54;
  lamp.intensity = night ? 2.8 : 0; const c = box.getCenter(new THREE.Vector3());
  lamp.position.set(box.max.x - 0.15, box.max.y + 0.45, c.z);
  renderer.toneMappingExposure = night ? 0.82 : 1.02;
  const t = new THREE.Vector3(0, c.y, c.z + 0.25), dir = new THREE.Vector3(-0.75, 0.32, 0.58).normalize();
  camera.position.copy(t).addScaledVector(dir, dist); camera.lookAt(t); camera.updateProjectionMatrix();
  renderer.render(scene, camera); return true;
};
</script></body></html>"""


def main():
    from playwright.sync_api import sync_playwright
    import mimetypes
    tmp = HERE / "out" / "web"; tmp.mkdir(parents=True, exist_ok=True); shots = []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"),
                               args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = br.new_page(viewport={"width": 640, "height": 640})
        def three(route):
            u = route.request.url
            f = THREE / "build" / u.split("/build/")[1] if "/build/" in u else THREE / "examples" / "jsm" / u.split("/examples/jsm/")[1]
            route.fulfill(path=str(f), content_type=mimetypes.guess_type(str(f))[0] or "text/javascript")
        pg.route("https://cdn.jsdelivr.net/**", three)
        pg.route("**/page.html", lambda r: r.fulfill(body=PAGE, content_type="text/html"))
        pg.route("**/model.glb", lambda r: r.fulfill(path=str(GLB), content_type="model/gltf-binary"))
        pg.goto("http://clothes.local/page.html"); pg.wait_for_function("window.ready === true", timeout=180000)
        print(json.dumps(pg.evaluate("window.info")))
        for mode in ("day", "lamp"):
            for dist in (2.3, 5.0):
                pg.evaluate(f"shoot('{mode}', {dist})"); pg.wait_for_timeout(300)
                f = tmp / f"{mode}_{dist}.png"; pg.screenshot(path=str(f)); shots.append(f); print("shot", f.name)
        br.close()
    ims = [Image.open(f).convert("RGB") for f in shots]; g = 6
    sheet = Image.new("RGB", (2 * 640 + g, 2 * 640 + g), (20, 20, 22))
    for k, im in enumerate(ims): sheet.paste(im, ((k % 2) * (640 + g), (k // 2) * (640 + g)))
    OUT.parent.mkdir(parents=True, exist_ok=True); sheet.save(OUT, quality=88); print("wrote", OUT)


if __name__ == "__main__":
    main()
