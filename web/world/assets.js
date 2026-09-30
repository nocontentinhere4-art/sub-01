// STUB assets loader (foundation). The world stream replaces this file with the manifest loader.
//
// Files come from branch assets/cc0 (web/assets/, CC0 Poly Haven, credits in web/assets/CREDITS.md):
//   /assets/hdri/<name>_1k.hdr, /assets/textures/<set>/<set>_diffuse|_nor_gl|_rough_1k.jpg, /assets/models/<name>.glb (Draco)
//
// createAssets(renderer, quality) -> {
//   manifest: {} (filled by loadManifest()), loadManifest(url?) -> Promise<manifest>,
//   gltf(url) -> Promise<gltf | null>, texture(url, {srgb=true}) -> Promise<Texture | null>,
//   model(name) -> Promise<Object3D clone | null>          (/assets/models/<name>.glb, shadows on)
//   pbr(set, {repeat: [u, v], maps}) -> Promise<{map, normalMap, roughnessMap} | null>   (low quality = diffuse only)
//   hdri(name) -> Promise<Texture (PMREM, for scene.environment) with .userData.equirect (for scene.background) | null>
//   loaders: {gltf, draco, ktx2}  (created lazily, decoders from the vendored three: /vendor/three/examples/jsm/libs/)
// }
// Every call resolves to null (never rejects) when a file is missing or fails, so callers keep a procedural fallback.
// Nothing is fetched until a stream asks for it.
import * as THREE from "three";

export const DECODERS = {
  draco: "/vendor/three/examples/jsm/libs/draco/gltf/",
  basis: "/vendor/three/examples/jsm/libs/basis/",
};
export const ROOT = "/assets/";

export function createAssets(renderer, quality) {
  let gltfLoader = null, draco = null, ktx2 = null, pmrem = null;
  const cache = new Map();

  async function loaders() {
    if (gltfLoader) return { gltf: gltfLoader, draco, ktx2 };
    const [{ GLTFLoader }, { DRACOLoader }, { KTX2Loader }, { MeshoptDecoder }] = await Promise.all([
      import("three/addons/loaders/GLTFLoader.js"), import("three/addons/loaders/DRACOLoader.js"),
      import("three/addons/loaders/KTX2Loader.js"), import("three/addons/libs/meshopt_decoder.module.js")]);
    draco = new DRACOLoader().setDecoderPath(DECODERS.draco);
    ktx2 = new KTX2Loader().setTranscoderPath(DECODERS.basis).detectSupport(renderer);
    gltfLoader = new GLTFLoader().setDRACOLoader(draco).setKTX2Loader(ktx2).setMeshoptDecoder(MeshoptDecoder);
    return { gltf: gltfLoader, draco, ktx2 };
  }

  function once(key, make) {
    if (!cache.has(key)) cache.set(key, make().catch(e => { console.warn("[assets] missing or failed:", key, e?.message || e); return null; }));
    return cache.get(key);
  }

  const api = {
    manifest: {},
    loaders: null,
    async loadManifest(url = ROOT + "manifest.json") {
      const r = await fetch(url).catch(() => null);
      api.manifest = r && r.ok ? await r.json().catch(() => ({})) : {};
      return api.manifest;
    },
    gltf(url) { return once("gltf:" + url, async () => { const l = await loaders(); api.loaders = l; return l.gltf.loadAsync(url); }); },
    texture(url, { srgb = true } = {}) {
      return once("tex:" + url, async () => {
        const t = url.endsWith(".ktx2") ? await (await loaders()).ktx2.loadAsync(url) : await new THREE.TextureLoader().loadAsync(url);
        t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.anisotropy = quality.lod >= 1 ? Math.min(8, renderer.capabilities.getMaxAnisotropy()) : 1;
        return t;
      });
    },
    async model(name) {
      const g = await api.gltf(`${ROOT}models/${name}.glb`);
      if (!g) return null;
      const o = g.scene.clone(true);
      o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
      return o;
    },
    async pbr(set, { repeat = [1, 1], maps } = {}) {
      const want = maps || (quality.lod >= 1 ? ["diffuse", "nor_gl", "rough"] : ["diffuse"]);
      const base = `${ROOT}textures/${set}/${set}_`;
      const [map, normalMap, roughnessMap] = await Promise.all(["diffuse", "nor_gl", "rough"].map(k =>
        want.includes(k) ? api.texture(`${base}${k}_1k.jpg`, { srgb: k === "diffuse" }) : null));
      if (!map) return null;
      const out = {};
      for (const [k, t] of Object.entries({ map, normalMap, roughnessMap })) {
        if (!t) continue;
        const c = t.clone(); c.repeat.set(repeat[0], repeat[1]); c.needsUpdate = true; out[k] = c;
      }
      return out;
    },
    hdri(name) {
      return once("hdri:" + name, async () => {
        const { HDRLoader } = await import("three/addons/loaders/HDRLoader.js");
        const eq = await new HDRLoader().loadAsync(`${ROOT}hdri/${name}_1k.hdr`);
        eq.mapping = THREE.EquirectangularReflectionMapping;
        pmrem ||= new THREE.PMREMGenerator(renderer);
        const env = pmrem.fromEquirectangular(eq).texture;
        env.userData.equirect = eq;
        return env;
      });
    },
  };
  return api;
}
