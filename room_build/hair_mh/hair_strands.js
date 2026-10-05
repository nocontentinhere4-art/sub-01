// Runtime for the strand hair (three.js r169). hair_mh.glb carries the hairs as plain line segments (one polyline per
// hair; NORMAL = the scalp normal under it; COLOR_0 = t along the hair, a per-hair random, the self-shadow, the
// distance to the tip in cm capped at 1); here
// they become camera-facing ribbons with a hair shader.
//   const mesh = strandMesh(THREE, linesGeometry, {lod: false});   // lod: true draws the uniform half, 0.25 a quarter
//   mesh.material.uniforms.* : the lights (world directions and colours) and the base colour; set them from the room.
// Ribbons: each hair point becomes two vertices pushed apart across the view in the vertex shader, ~0.08 mm wide,
// full width and opacity until the last ~2 mm, then tapering to the tip. A hair is far thinner than a pixel, so the ribbon is drawn at least ~0.7 px wide
// and its alpha carries the true coverage; blended, thousands of overlapping hairs build up into soft fuzz, not
// needles. Drawn after the head and the scalp base (renderOrder 3), without depth writes.
// Shading: Kajiya-Kay along the strand with two lobes (a dim near-white primary shifted toward the root, a dimmer
// warm secondary toward the tip; dry, matte), a natural black-brown base (#1b1512) with a per-hair tint and slightly
// browner tips, a wrap term over the scalp normal, and the self-shadow (darker deep in the hair and at the roots).
// f < 1 keeps only the leading fraction of the hairs (their points come first), so a thinned set also costs less memory.
export function strandRibbons(THREE, lines, f = 1){
  const P = lines.attributes.position, Nn = lines.attributes.normal, Cc = lines.attributes.color;
  let I = lines.index.array; if (f < 1) I = I.subarray(0, Math.floor(I.length / 2 * f) * 2);
  let n = 0; for (let i = 0; i < I.length; i++) if (I[i] >= n) n = I[i] + 1;
  const next = new Int32Array(n).fill(-1), prev = new Int32Array(n).fill(-1);
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
uniform float collarOn; uniform mat4 collarMat, collarInv; uniform sampler2D collarMap; uniform vec4 collarGrid, collarPD; uniform vec2 collarN;
varying vec3 vT, vN, vW; varying vec4 vS; varying float vCov;
// The collar (collar_map.mjs): the hoodie in the Spine bone's frame as two height maps, packed in one texture: R = the
// backmost z over (x, y), G = the topmost y of its upward-facing parts over (x, z). A hair point in front of the back
// (within collarPD.y) goes back to collarPD.x behind it; one just under the top (within collarPD.z) goes up to collarPD.w
// over it (more room there: the rim round the neck rises a little as the neck turns).
float collarAt(vec2 g, int ch){                                   // bilinear in grid units; > 9 where there is no hoodie
  if (g.x < 0.0 || g.y < 0.0 || g.x >= collarN.x - 1.0 || g.y >= collarN.y - 1.0) return 99.0;
  ivec2 c = ivec2(floor(g)); vec2 u = g - vec2(c);
  vec4 a = texelFetch(collarMap, c, 0), b = texelFetch(collarMap, c + ivec2(1, 0), 0), e = texelFetch(collarMap, c + ivec2(0, 1), 0), f = texelFetch(collarMap, c + ivec2(1, 1), 0);
  vec4 m = max(max(a, b), max(e, f)); if ((ch == 0 ? m.r : m.g) > 9.0) return 99.0;
  vec4 v = mix(mix(a, b, u.x), mix(e, f, u.x), u.y); return ch == 0 ? v.r : v.g;
}
vec3 collar(vec3 w){
  vec3 q = (collarInv * vec4(w, 1.0)).xyz, q0 = q;
  float zb = collarAt((q.xy - collarGrid.xy) / collarGrid.w, 0);
  if (zb < 9.0){ float over = q.z - (zb - collarPD.x); if (over > 0.0 && over < collarPD.y) q.z = zb - collarPD.x; }
  float yt = collarAt((q.xz - collarGrid.xz) / collarGrid.w, 1);
  if (yt < 9.0){ float under = yt + collarPD.w - q.y; if (under > 0.0 && under < collarPD.z) q.y = yt + collarPD.w; }
  return q == q0 ? w : (collarMat * vec4(q, 1.0)).xyz;
}
void main(){
  vec4 wp = modelMatrix * vec4(position, 1.0);
  if (collarOn > 0.5) wp.xyz = collar(wp.xyz);
  vec3 T = normalize(mat3(modelMatrix) * tangentDir), Vd = normalize(cameraPosition - wp.xyz);
  vec3 Sd = cross(T, Vd); float sl = length(Sd); Sd = sl > 1e-4 ? Sd / sl : vec3(1.0, 0.0, 0.0);
  float w = width * mix(0.12, 1.0, smoothstep(0.0, 0.2, strand.w));   // full width until the last 2 mm, then a taper
  float px = pxScale * length(cameraPosition - wp.xyz);          // a pixel's size at this distance
  float wd = max(w, 0.7 * px);
  vCov = pow(clamp(w / wd, 0.0, 1.0), 0.8);                      // the coverage (eased a little: hairs shadow each other)
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
  vec3 spec = (vec3(0.018) * kk(T1, H, 50.0) + vec3(0.016, 0.011, 0.007) * kk(T2, H, 16.0)) * (0.3 + 1.2 * vS.y);   // dry, soft sheen, varied per lock
  return col * wrap * (alb * dif + spec);
}
void main(){
  float t = vS.x, id = vS.y - 0.5, sh = vS.z;
  vec3 T = normalize(vT), N = normalize(vN), V = normalize(cameraPosition - vW);
  vec3 alb = base * (0.8 + 0.45 * vS.y) * mix(vec3(1.0), vec3(1.6, 1.4, 1.2), t * t) * sh;   // tint, browner tips, self-shadow
  vec3 c = light(T, N, V, keyDir, keyCol, alb, id) + light(T, N, V, rimDir, rimCol, alb, id);
  c += alb * mix(ground, sky, N.y * 0.5 + 0.5);
  gl_FragColor = vec4(c, vCov * smoothstep(0.0, 0.15, vS.w));   // opaque to the last ~1.5 mm
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
      collarOn: {value: 0}, collarMat: {value: new THREE.Matrix4()}, collarInv: {value: new THREE.Matrix4()}, collarMap: {value: null},
      collarGrid: {value: new THREE.Vector4()}, collarPD: {value: new THREE.Vector4()}, collarN: {value: new THREE.Vector2()},
      base: {value: new THREE.Color(0x14100e)},                  // near-black #14100e; sRGB in, linear in the shader
      keyDir: {value: new THREE.Vector3(0.4, 0.75, 0.55).normalize()}, keyCol: {value: new THREE.Color(1.7, 1.7, 1.7)},
      rimDir: {value: new THREE.Vector3(-0.5, 0.45, -0.7).normalize()}, rimCol: {value: new THREE.Color(0.5, 0.5, 0.5)},
      sky: {value: new THREE.Color(0.55, 0.55, 0.55)}, ground: {value: new THREE.Color(0.25, 0.23, 0.22)},
    },
  });
  return m;
}

// The mesh: ribbons + material, the pixel scale kept up to date from the camera and the viewport at draw time.
// lod: false (all hairs), true (half) or a fraction (0.25: a quarter); hairs are shuffled, so any leading part of them
// is a uniform thinning; thinner sets get wider hairs so the coverage holds. Only the hairs drawn are built.
const WIDTH_EXP = 0.46;
export function strandMesh(THREE, lines, {lod = false, collar = null} = {}){
  const f = lod === true ? 0.5 : typeof lod === "number" && lod > 0 && lod < 1 ? lod : 1;
  const g = strandRibbons(THREE, lines, f), mesh = new THREE.Mesh(g, strandMaterial(THREE));
  mesh.name = "hair_strands"; mesh.frustumCulled = false; mesh.renderOrder = 3;
  if (f < 1) mesh.material.uniforms.width.value = 0.00008 * Math.pow(1 / f, WIDTH_EXP);
  const vp = new THREE.Vector4(), u = mesh.material.uniforms;
  if (collar) setCollar(THREE, mesh, collar.map, collar.bone);
  mesh.onBeforeRender = (renderer, scene, camera) => {
    renderer.getCurrentViewport(vp);
    u.pxScale.value = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / Math.max(1, vp.w);
    if (mesh.userData.collarBone){ u.collarMat.value.copy(mesh.userData.collarBone.matrixWorld); u.collarInv.value.copy(u.collarMat.value).invert(); }
  };
  return mesh;
}

// The collar collider: `map` is hair_mh's userData.collar (from collar_map.mjs), `bone` the dressed body's "Spine" bone.
export function setCollar(THREE, mesh, map, bone){
  const u = mesh.material.uniforms;
  if (!map || !bone){ u.collarOn.value = 0; mesh.userData.collarBone = null; return; }
  const z = new Float32Array(map.nx * map.ny * 2), mm = v => v === map.none ? 99 : v / 1000;
  for (let i = 0; i < map.nx * map.ny; i++){ z[i * 2] = mm(map.zmm[i]); z[i * 2 + 1] = mm(map.ymm[i]); }
  const tex = new THREE.DataTexture(z, map.nx, map.ny, THREE.RGFormat, THREE.FloatType); tex.needsUpdate = true;
  u.collarMap.value = tex; u.collarGrid.value.set(map.x0, map.y0, map.z0, map.cell); u.collarPD.value.set(map.pad, map.depth, map.depthTop, map.padTop); u.collarN.value.set(map.nx, map.ny);
  u.collarOn.value = 1; mesh.userData.collarBone = bone;
}

// After loading hair_mh.glb (with MeshoptDecoder): swaps its line segments for the ribbon mesh (keeping the node's
// transform, which carries the quantization's scale) and sets up the scalp base. Returns the strand mesh.
//   const gltf = await loader.loadAsync("hair_mh.glb"); const hair = gltf.scene.getObjectByName("hair_mh");
//   hair.position.set(0, 0, 0); headBone.add(hair); useStrands(THREE, hair, {lod, spine: body.getObjectByName("Spine")});
// spine: the dressed G2's "Spine" bone turns on the collar collider (hair stays out of the hood when the head tips back).
export function useStrands(THREE, root, {lod = false, spine = null} = {}){
  let mesh = null; const map = root.userData && root.userData.collar;
  root.traverse(o => {
    if (o.isLineSegments && /hair_strands/.test(o.name)){
      mesh = strandMesh(THREE, o.geometry, {lod, collar: spine && map ? {map, bone: spine} : null});
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
