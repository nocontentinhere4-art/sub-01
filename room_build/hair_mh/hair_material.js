// The hair's look in three.js (r169). glTF has no alpha-to-coverage, so hair_mh.glb carries a plain MASK material;
// call setupHair(THREE, gltf.scene) after loading to switch the cards to:
//  - alpha-to-coverage (needs an antialiased renderer, as room.html's is): the strand alpha becomes MSAA coverage, so
//    the cards need no sorting, write depth, and their tips stay soft and see-through;
//  - an alpha boost per mip level, so thin strands don't fade away as the head gets small on screen;
//  - an anisotropic highlight running along the strands (KHR_materials_anisotropy, rotated onto the uv.y axis),
//    plus a faint warm sheen standing in for Kajiya-Kay's secondary (tinted) lobe, so the black reads as hair.
export function hairCardMaterial(THREE, map){
  const m = new THREE.MeshPhysicalMaterial({
    name: "hair_cards", map, vertexColors: true, side: THREE.DoubleSide,
    color: 0xffffff, roughness: 0.46, metalness: 0, specularIntensity: 0.4, specularColor: new THREE.Color(0xd8ccc0),
    anisotropy: 0.85, anisotropyRotation: Math.PI / 2,
    sheen: 0.2, sheenRoughness: 0.4, sheenColor: new THREE.Color(0x5a3a26),
    alphaTest: 0.5, alphaToCoverage: false,
  });
  return m;
}

export function setupHair(THREE, root){
  root.traverse(o => {
    if (!o.isMesh || !o.material) return;
    const m = o.material;
    if (/hair_cards/.test(m.name)){
      m.alphaTest = 0; m.alphaToCoverage = true; m.transparent = false; m.depthWrite = true; m.side = THREE.DoubleSide;
      if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; }
      m.onBeforeCompile = sh => {
        sh.fragmentShader = sh.fragmentShader.replace("#include <map_fragment>", `#include <map_fragment>
          #ifdef USE_MAP
            vec2 hdx = dFdx(vMapUv * vec2(textureSize(map, 0))), hdy = dFdy(vMapUv * vec2(textureSize(map, 0)));
            float hmip = max(0.0, 0.5 * log2(max(dot(hdx, hdx), dot(hdy, hdy))));
            diffuseColor.a = clamp(diffuseColor.a * (1.0 + 0.32 * hmip), 0.0, 1.0);
          #endif`);
      };
      m.customProgramCacheKey = () => "hair_cards_a2c";
      m.needsUpdate = true;
    }
    if (/hair_scalp/.test(m.name)){
      m.transparent = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -1; m.needsUpdate = true;
    }
  });
}
