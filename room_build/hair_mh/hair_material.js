// The hair's look in three.js (r169). glTF can carry neither alpha-to-coverage nor a hair shader, so hair_mh.glb holds
// plain PBR materials (cards: alpha MASK, the strand atlas as base colour and the data atlas in the occlusion slot);
// call setupHair(THREE, gltf.scene) after loading to switch the cards to:
//  - alpha-to-coverage (needs an antialiased renderer, as room.html's is): the strand alpha becomes MSAA coverage, so
//    the cards need no sorting, write depth, and their tips stay soft and see-through;
//  - an alpha boost per mip level once strands are sub-pixel, so the hair doesn't thin out at a distance;
//  - Kajiya-Kay highlights along the strands (tangent = the strand direction) in two lobes: a narrow, near-white
//    primary shifted toward the root and a broad, dim, brown-tinted secondary shifted toward the tip, each strand's
//    shift jittered by the data atlas's strand ID (G) and dimmed by its depth (R).
export function hairCardMaterial(THREE, map, data){
  return new THREE.MeshPhysicalMaterial({
    name: "hair_cards", map, aoMap: data, aoMapIntensity: 0.7, vertexColors: true, side: THREE.DoubleSide,
    color: 0xffffff, roughness: 0.7, metalness: 0, specularIntensity: 0.15,
    anisotropy: 0.01,                                // only so three hands the shader the strand tangent
    alphaTest: 0.5, alphaToCoverage: false,
  });
}

export function scalpMaterial(THREE, map){
  return new THREE.MeshStandardMaterial({name: "hair_scalp", map, vertexColors: true, transparent: true, roughness: 0.85, depthWrite: false});
}

const KK = `
#if defined( USE_TANGENT ) && defined( USE_AOMAP ) && NUM_DIR_LIGHTS > 0
{
  vec4 hd = texture2D( aoMap, vAoMapUv );
  float sid = hd.g - 0.5;
  vec3 T = normalize( vTangent ), N = normalize( geometryNormal ), V = geometryViewDir;
  vec3 T1 = normalize( T + N * ( 0.14 + 0.16 * sid ) );     // primary: toward the root
  vec3 T2 = normalize( T + N * ( -0.10 + 0.22 * sid ) );    // secondary: toward the tip
  for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
    vec3 L = directionalLights[ i ].direction, H = normalize( L + V );
    float wrap = clamp( ( dot( N, L ) + 0.35 ) / 1.35, 0.0, 1.0 );
    float a = dot( T1, H ), b = dot( T2, H );
    float s1 = pow( sqrt( max( 0.0, 1.0 - a * a ) ), 280.0 ) * smoothstep( -1.0, 0.0, a );
    float s2 = pow( sqrt( max( 0.0, 1.0 - b * b ) ), 60.0 ) * smoothstep( -1.0, 0.0, b );
    vec3 kk = vec3( 0.07 ) * s1 + vec3( 0.045, 0.028, 0.017 ) * s2 * ( 0.6 + 0.8 * hd.g );
    reflectedLight.directSpecular += directionalLights[ i ].color * wrap * kk * hd.r;
  }
}
#endif
`;

export function setupHair(THREE, root){
  root.traverse(o => {
    if (!o.isMesh || !o.material) return;
    const m = o.material;
    if (/hair_cards/.test(m.name)){
      m.alphaTest = 0; m.alphaToCoverage = true; m.transparent = false; m.depthWrite = true; m.side = THREE.DoubleSide;
      if (m.anisotropy <= 0) m.anisotropy = 0.01;
      if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; }
      if (m.aoMap) m.aoMap.colorSpace = THREE.NoColorSpace;
      m.onBeforeCompile = sh => {
        sh.fragmentShader = sh.fragmentShader
          .replace("#include <map_fragment>", `#include <map_fragment>
            #ifdef USE_MAP
              vec2 hdx = dFdx(vMapUv * vec2(textureSize(map, 0))), hdy = dFdy(vMapUv * vec2(textureSize(map, 0)));
              float hmip = max(0.0, 0.5 * log2(max(dot(hdx, hdx), dot(hdy, hdy))) - 3.0);   // only once strands are sub-pixel
              diffuseColor.a = clamp(diffuseColor.a * (1.0 + 0.25 * hmip), 0.0, 1.0);
            #endif`)
          .replace("#include <lights_fragment_end>", "#include <lights_fragment_end>\n" + KK);
      };
      m.customProgramCacheKey = () => "hair_cards_kk";
      m.needsUpdate = true;
    }
    if (/hair_scalp/.test(m.name)){
      m.transparent = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -1;
      if (m.map) { m.map.wrapS = THREE.RepeatWrapping; m.map.colorSpace = THREE.SRGBColorSpace; }
      m.needsUpdate = true;
    }
  });
}
