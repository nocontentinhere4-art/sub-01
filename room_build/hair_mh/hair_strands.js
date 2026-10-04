// Runtime for the strand hair (three.js r169). hair_mh.glb carries the hairs as plain line segments (one polyline per
// hair; NORMAL = the scalp normal under it; COLOR_0 = t along the hair, a per-hair random, the self-shadow); here
// they become camera-facing ribbons with a hair shader.
//   const mesh = strandMesh(THREE, linesGeometry, {lod: false});   // lod: true draws the uniform half of the hairs
//   mesh.material.uniforms.* : the lights (world directions and colours) and the base colour; set them from the room.
// Ribbons: each hair point becomes two vertices pushed apart across the view in the vertex shader, ~0.08 mm wide and
// tapering to nothing at the tip. A hair is far thinner than a pixel, so the ribbon is drawn at least ~0.7 px wide
// and its alpha carries the true coverage; blended, thousands of overlapping hairs build up into soft fuzz, not
// needles. Drawn after the head and the scalp base (renderOrder 3), without depth writes.
// Shading: Kajiya-Kay along the strand with two lobes (a dim near-white primary shifted toward the root, a dimmer
// warm secondary toward the tip; dry, matte), a natural black-brown base (#1b1512) with a per-hair tint and slightly
// browner tips, a wrap term over the scalp normal, and the self-shadow (darker deep in the hair and at the roots).
export function strandRibbons(THREE, lines){
  const P = lines.attributes.position, Nn = lines.attributes.normal, Cc = lines.attributes.color, I = lines.index.array;
  const n = P.count, next = new Int32Array(n).fill(-1), prev = new Int32Array(n).fill(-1);
  for (let i = 0; i < I.length; i += 2){ next[I[i]] = I[i + 1]; prev[I[i + 1]] = I[i]; }
  const pos = new Float32Array(n * 6), tan = new Float32Array(n * 6), nor = new Float32Array(n * 6), st = new Float32Array(n * 8), side = new Float32Array(n * 2);
  for (let i = 0; i < n; i++){
    const a = prev[i] < 0 ? i : prev[i], b = next[i] < 0 ? i : next[i];
    const tx = P.getX(b) - P.getX(a), ty = P.getY(b) - P.getY(a), tz = P.getZ(b) - P.getZ(a), l = Math.hypot(tx, ty, tz) || 1;
    for (let s = 0; s < 2; s++){
      const v = i * 2 + s;
      pos.set([P.getX(i), P.getY(i), P.getZ(i)], v * 3); tan.set([tx / l, ty / l, tz / l], v * 3);
      nor.set([Nn.getX(i), Nn.getY(i), Nn.getZ(i)], v * 3);
      st.set([Cc.getX(i), Cc.getY(i), Cc.getZ(i), Cc.getW(i)], v * 4); side[v] = s ? 1 : -1;
    }
  }
  const idx = new Uint32Array(I.length * 3);
  for (let i = 0, k = 0; i < I.length; i += 2){ const a = I[i] * 2, b = I[i + 1] * 2; idx.set([a, a + 1, b, a + 1, b + 1, b], k); k += 6; }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("tangentDir", new THREE.BufferAttribute(tan, 3));
  g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  g.setAttribute("strand", new THREE.BufferAttribute(st, 4));
  g.setAttribute("side", new THREE.BufferAttribute(side, 1));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  return g;
}

const VS = `
attribute vec3 tangentDir; attribute vec4 strand; attribute float side;
uniform float width, pxScale;
varying vec3 vT, vN, vW; varying vec4 vS; varying float vCov;
void main(){
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vec3 T = normalize(mat3(modelMatrix) * tangentDir), Vd = normalize(cameraPosition - wp.xyz);
  vec3 Sd = cross(T, Vd); float sl = length(Sd); Sd = sl > 1e-4 ? Sd / sl : vec3(1.0, 0.0, 0.0);
  float w = width * (1.0 - 0.92 * strand.x);                    // tapers to (almost) nothing at the tip
  float px = pxScale * length(cameraPosition - wp.xyz);          // a pixel's size at this distance
  float wd = max(w, 0.7 * px);
  vCov = clamp(w / wd, 0.0, 1.0);                                // the true coverage
  wp.xyz += Sd * (0.5 * wd * side);
  vT = T; vN = normalize(mat3(modelMatrix) * normal); vW = wp.xyz; vS = strand;
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const FS = `
uniform vec3 base, keyDir, keyCol, rimDir, rimCol, sky, ground;
varying vec3 vT, vN, vW; varying vec4 vS; varying float vCov;
float kk(vec3 T, vec3 H, float e){ float c = dot(T, H); return pow(sqrt(max(0.0, 1.0 - c * c)), e) * smoothstep(-1.0, 0.0, c); }
vec3 light(vec3 T, vec3 N, vec3 V, vec3 L, vec3 col, vec3 alb, float id){
  vec3 H = normalize(L + V);
  float wrap = clamp((dot(N, L) + 0.4) / 1.4, 0.0, 1.0);
  float dif = mix(0.3, 1.0, sqrt(max(0.0, 1.0 - pow(dot(T, L), 2.0))));
  vec3 T1 = normalize(T + N * (0.10 + 0.12 * id)), T2 = normalize(T + N * (-0.10 + 0.16 * id));
  vec3 spec = vec3(0.020) * kk(T1, H, 120.0) + vec3(0.016, 0.010, 0.006) * kk(T2, H, 30.0);   // dry: the albedo is ~0.01
  return col * wrap * (alb * dif + spec);
}
void main(){
  float t = vS.x, id = vS.y - 0.5, sh = vS.z;
  vec3 T = normalize(vT), N = normalize(vN), V = normalize(cameraPosition - vW);
  vec3 alb = base * (0.8 + 0.45 * vS.y) * mix(vec3(1.0), vec3(1.25, 1.12, 1.0), t * t) * sh;   // tint, browner tips, self-shadow
  vec3 c = light(T, N, V, keyDir, keyCol, alb, id) + light(T, N, V, rimDir, rimCol, alb, id);
  c += alb * mix(ground, sky, N.y * 0.5 + 0.5);
  gl_FragColor = vec4(c, vCov * (1.0 - smoothstep(0.8, 1.0, t) * 0.6));
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function strandMaterial(THREE){
  const m = new THREE.ShaderMaterial({
    name: "hair_strands", vertexShader: VS, fragmentShader: FS, side: THREE.DoubleSide,
    transparent: true, depthWrite: false,                      // blended: overlapping hairs add up (alpha-to-coverage gives
    // every hair of the same alpha the same sample pattern, so thousands of them don't accumulate); dark hair over dark
    // hair hardly cares about the draw order
    uniforms: {
      width: {value: 0.00008}, pxScale: {value: 0.001},
      base: {value: new THREE.Color(0x1b1512)},                  // sRGB in, linear in the shader
      keyDir: {value: new THREE.Vector3(0.4, 0.75, 0.55).normalize()}, keyCol: {value: new THREE.Color(1.7, 1.7, 1.7)},
      rimDir: {value: new THREE.Vector3(-0.5, 0.45, -0.7).normalize()}, rimCol: {value: new THREE.Color(0.5, 0.5, 0.5)},
      sky: {value: new THREE.Color(0.55, 0.55, 0.55)}, ground: {value: new THREE.Color(0.25, 0.23, 0.22)},
    },
  });
  return m;
}

// The mesh: ribbons + material, the pixel scale kept up to date from the camera and the viewport at draw time.
export function strandMesh(THREE, lines, {lod = false} = {}){
  const g = strandRibbons(THREE, lines), mesh = new THREE.Mesh(g, strandMaterial(THREE));
  mesh.name = "hair_strands"; mesh.frustumCulled = false; mesh.renderOrder = 3;
  if (lod) g.setDrawRange(0, Math.floor(g.index.count / 12) * 6);
  const vp = new THREE.Vector4();
  mesh.onBeforeRender = (renderer, scene, camera) => {
    renderer.getCurrentViewport(vp);
    mesh.material.uniforms.pxScale.value = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / Math.max(1, vp.w);
  };
  return mesh;
}

// After loading hair_mh.glb (with MeshoptDecoder): swaps its line segments for the ribbon mesh (keeping the node's
// transform, which carries the quantization's scale) and sets up the scalp base. Returns the strand mesh.
//   const gltf = await loader.loadAsync("hair_mh.glb"); const hair = gltf.scene.getObjectByName("hair_mh");
//   hair.position.set(0, 0, 0); headBone.add(hair); useStrands(THREE, hair, {lod});
export function useStrands(THREE, root, {lod = false} = {}){
  let mesh = null;
  root.traverse(o => {
    if (o.isLineSegments && /hair_strands/.test(o.name)){
      mesh = strandMesh(THREE, o.geometry, {lod});
      mesh.position.copy(o.position); mesh.quaternion.copy(o.quaternion); mesh.scale.copy(o.scale);
      o.parent.add(mesh); o.visible = false;
    }
    if (o.isMesh && o.material && /hair_scalp/.test(o.material.name)){
      const m = o.material; m.transparent = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -1;
      if (m.map) { m.map.wrapS = THREE.RepeatWrapping; m.map.colorSpace = THREE.SRGBColorSpace; m.needsUpdate = true; }
      o.renderOrder = 1;
    }
  });
  return mesh;
}
