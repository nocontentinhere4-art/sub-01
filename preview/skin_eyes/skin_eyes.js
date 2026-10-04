// Skin and eyes that read as real under the room's lights (#98, owner's realism pass; G6). three.js r169, no textures:
// the head is the MakeHuman base mesh (CC0), everything else is computed here.
//
//   buildHead(THREE, data, {env})  ->  THREE.Group with the skin, both eyes (sclera + iris, a wet cornea), the tear lines
//                                      and the caruncles; data = head.json (positions in metres, origin at joint-head)
//
// Skin (MeshPhysicalMaterial, patched in onBeforeCompile):
//   - subsurface-style softness: per-channel wrap lighting (red wraps furthest past the terminator, blue least), so
//     the shadow edge is soft and warm instead of a hard grey line;
//   - translucency where the skin is thin (the ears, the nose's rim): light from behind shows through red;
//   - pore-level detail: a procedural bump (object-space cellular + value noise, ~1 mm), faded out when a pixel is
//     wider than a pore so it never shimmers at the room distance;
//   - colour variation: warmer and redder nose, cheeks and ears, lips, a faint mottle, a darker eye socket ring and
//     brow line, all as vertex data from landmarks found on the mesh;
//   - specular: skin's F0 (~0.028, IOR 1.4), a tighter, stronger lobe on the forehead and nose (the T-zone), a faint
//     sheen for the fine hair. No clearcoat (that is what makes skin look like plastic).
// Eyes:
//   - the eyeball's sclera and iris are one procedural texture (fibres, a dark limbal ring, a pupil, faint veins);
//     the lids' occlusion darkens it under the upper lid and in the corners (a socket ring that does not depend on
//     shadows);
//   - a wet cornea: a separate, slightly bulging cap drawn additively with a near-mirror specular lobe and the
//     environment, so the highlight sits on the cornea, not on the iris;
//   - the tear line: a thin wet tube along the lower lid margin, and the pink caruncle in the inner corner.

const EYE_K = 0.85;                                 // the eyeball's radius, as a share of MakeHuman's eye helper sphere
const SKIN_SRGB = [0.81, 0.645, 0.55];            // base albedo (sRGB): the agreed tone, a little warmer

// ---------- landmarks and per-vertex skin data ----------
function smoothNormals(THREE, geo){
  // normals averaged over every vertex at the same position (the UV seams split vertices; their normals must not)
  const p = geo.attributes.position, n = new Float32Array(p.count * 3), key = new Map(), id = new Int32Array(p.count);
  for (let i = 0; i < p.count; i++) { const k = `${p.getX(i).toFixed(5)},${p.getY(i).toFixed(5)},${p.getZ(i).toFixed(5)}`;
    if (!key.has(k)) key.set(k, key.size); id[i] = key.get(k); }
  const acc = new Float32Array(key.size * 3), idx = geo.index.array, a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let t = 0; t < idx.length; t += 3) {
    a.fromBufferAttribute(p, idx[t]); b.fromBufferAttribute(p, idx[t + 1]); c.fromBufferAttribute(p, idx[t + 2]);
    const f = b.sub(a).cross(c.sub(a));            // area-weighted
    for (const v of [idx[t], idx[t + 1], idx[t + 2]]) { acc[3 * id[v]] += f.x; acc[3 * id[v] + 1] += f.y; acc[3 * id[v] + 2] += f.z; }
  }
  for (let i = 0; i < p.count; i++) { const j = id[i], l = Math.hypot(acc[3 * j], acc[3 * j + 1], acc[3 * j + 2]) || 1;
    n[3 * i] = acc[3 * j] / l; n[3 * i + 1] = acc[3 * j + 1] / l; n[3 * i + 2] = acc[3 * j + 2] / l; }
  geo.setAttribute("normal", new THREE.BufferAttribute(n, 3));
  return id;
}

export function landmarks(data){
  const P = data.position, n = P.length / 3, E = data.eyes;
  let nose = 0;
  for (let i = 0; i < n; i++) if (Math.abs(P[3 * i]) < 0.006 && P[3 * i + 2] > P[3 * nose + 2]) nose = i;
  const N = [P[3 * nose], P[3 * nose + 1], P[3 * nose + 2]];
  let earX = 0; for (let i = 0; i < n; i++) earX = Math.max(earX, Math.abs(P[3 * i]));
  // the lips: the front-most point on the midline between 2.5 and 7.5 cm under the nose tip (the upper lip)
  let lip = -1;
  for (let i = 0; i < n; i++) { const y = P[3 * i + 1]; if (Math.abs(P[3 * i]) < 0.005 && y < N[1] - 0.025 && y > N[1] - 0.075 && (lip < 0 || P[3 * i + 2] > P[3 * lip + 2])) lip = i; }
  return {nose: N, earX, lip: [P[3 * lip], P[3 * lip + 1], P[3 * lip + 2]], eyeY: E.l.center[1], eyeZ: E.l.center[2], eyeX: E.l.center[0], eyeR: E.l.radius};
}

export function skinData(THREE, geo, data){
  const L = landmarks(data), P = geo.attributes.position, n = P.count;
  const col = new Float32Array(n * 3), sd = new Float32Array(n * 4);   // sd: thin, oily (T-zone), cavity AO, lips
  const g = (d, s) => Math.exp(-(d * d) / (2 * s * s));
  const lin = c => Math.pow(c, 2.2);
  const base = SKIN_SRGB.map(lin), red = [0.74, 0.36, 0.32].map(lin), lip = [0.62, 0.27, 0.28].map(lin), brow = [0.30, 0.22, 0.18].map(lin);
  const eyes = [data.eyes.l, data.eyes.r];
  for (let i = 0; i < n; i++) {
    const x = P.getX(i), y = P.getY(i), z = P.getZ(i), ax = Math.abs(x);
    // redness: nose tip and wings, cheeks, ears, a little on the chin and forehead
    const nose = g(Math.hypot(x, y - L.nose[1] + 0.004, z - L.nose[2]), 0.011);
    const cheek = g(Math.hypot(ax - 0.044, y - (L.eyeY - 0.034), z - (L.eyeZ - 0.008)), 0.013);
    const ear = ax > L.earX - 0.012 && z < 0.05 ? Math.min(1, (ax - (L.earX - 0.012)) / 0.01) * g(y - 0.02, 0.035) : 0;   // the rim
    const chin = g(Math.hypot(x, y - (L.lip[1] - 0.045), z - (L.lip[2] - 0.01)), 0.014);
    let redK = 0.6 * nose + 0.32 * cheek + 0.7 * ear + 0.12 * chin;
    // lips: a band under the nose, centred, on the front of the face
    const lips = Math.min(1, 1.6 * g(y - (L.lip[1] - 0.005), 0.0062) * g(x, 0.02) * (z > L.lip[2] - 0.03 ? 1 : 0));
    // eye socket ring (cavity) and the under-eye; the brow line above
    let cav = 0, browK = 0;
    for (const e of eyes) {
      const d = Math.hypot(x - e.center[0], (y - e.center[1]) * 1.25, z - e.center[2]);
      cav = Math.max(cav, g(d - e.radius * EYE_K * 1.1, 0.004) * 0.7 + g(d - e.radius * 1.45, 0.009) * 0.35);
      browK = Math.max(browK, g(y - (e.center[1] + 0.024 + 0.006 * Math.cos((x - e.center[0]) * 60)), 0.0042) * g(x - e.center[0] * 1.15, 0.019) * (z > e.center[2] - 0.02 ? 1 : 0));
    }
    // the lash line: the upper lid's margin, dark (lashes and their shadow) and narrow; a softer shadow just above it
    let lash = 0;
    for (const e of eyes) {
      const d = Math.hypot(x - e.center[0], y - e.center[1], z - e.center[2]);
      if (y > e.center[1] + e.radius * 0.12 && z > e.center[2] + e.radius * 0.3 && Math.abs(x - e.center[0]) < e.radius * 1.05)
        lash = Math.max(lash, 0.4 * g(d - e.radius * EYE_K * 1.1, 0.0025));   // a soft lid shadow (the line itself is per pixel)
    }
    lash = Math.min(1, lash);
    // the inner corners: the skin there is pinker (the caruncle's fold)
    let pinkK = 0;
    for (const e of eyes) { const r = e.radius * EYE_K;
      pinkK = Math.max(pinkK, g(Math.hypot(x - (e.center[0] - Math.sign(e.center[0]) * r * 0.95), y - (e.center[1] - 0.1 * r), z - (e.center[2] + 0.35 * r)), 0.0025)); }
    redK += 0.8 * pinkK;
    // the fold under the nose, the corners of the mouth, behind the ears: small cavities
    cav = Math.max(cav, 0.4 * g(Math.hypot(ax - 0.026, y - (L.nose[1] - 0.05)), 0.006));
    const c = [0, 1, 2].map(k => {
      let v = base[k];
      v = v * (1 - 0.35 * redK) + red[k] * 0.35 * redK;
      v = v * (1 - 0.9 * lips) + lip[k] * 0.9 * lips;
      v = v * (1 - 0.35 * browK) + brow[k] * 0.35 * browK;
      v = v * (1 - 0.30 * cav);
      return v * (1 - 0.82 * lash) + 0.012 * 0.82 * lash;
    });
    col.set(c, 3 * i);
    const thin = Math.max(ear, 0.8 * g(Math.hypot(ax - 0.012, y - L.nose[1] + 0.012, z - L.nose[2] + 0.012), 0.008));
    const oily = Math.max(0.9 * g(Math.hypot(x, y - L.nose[1] + 0.002, z - L.nose[2]), 0.022),
                          0.7 * g(x, 0.035) * (y > L.eyeY + 0.03 && y < L.eyeY + 0.085 && z > 0.06 ? 1 : 0), 0.5 * g(Math.hypot(x, y - (L.nose[1] - 0.085)), 0.015));
    sd.set([thin, oily, Math.max(cav, 0.8 * lash), lips], 4 * i);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.setAttribute("skinData", new THREE.BufferAttribute(sd, 4));
  return L;
}

// ---------- the skin material ----------
const NOISE = /* glsl */`
  // a hash that keeps its precision far from the origin (the body's skin sits 1-1.7 m up; D. Hoskins' hash13)
  float sk_hash(vec3 p){ p = fract(p * 0.1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
  float sk_noise(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(sk_hash(i), sk_hash(i + vec3(1,0,0)), f.x), mix(sk_hash(i + vec3(0,1,0)), sk_hash(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(sk_hash(i + vec3(0,0,1)), sk_hash(i + vec3(1,0,1)), f.x), mix(sk_hash(i + vec3(0,1,1)), sk_hash(i + vec3(1,1,1)), f.x), f.y), f.z); }
  // pores: distance to the nearest jittered cell centre (a cellular noise), pits where it is small; the second
  // distance too (F2 - F1 small: the cell walls, the fine furrows that net the skin into little polygons)
  vec2 sk_cell2(vec3 x){ vec3 i = floor(x), f = fract(x); float d1 = 8.0, d2 = 8.0;
    for (int a = -1; a <= 1; a++) for (int b = -1; b <= 1; b++) for (int c = -1; c <= 1; c++) {
      vec3 o = vec3(a, b, c), r = o + vec3(sk_hash(i + o), sk_hash(i + o + 17.0), sk_hash(i + o + 31.0)) - f; float d = dot(r, r);
      if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) d2 = d; }
    return sqrt(vec2(d1, d2)); }
  float sk_cell(vec3 x){ return sk_cell2(x).x; }
`;

// the lash line: on the upper lid, the skin within ~1.5 mm of where it meets the ball is dark (lashes and their
// shadow), with a soft 3 mm shadow above it and darker toward the outer corner; per pixel, the lids are coarse
const LASH = /* glsl */`
  float sk_lashAt(vec3 p, vec4 e){
    if (e.w <= 0.0) return 0.0;
    vec3 q = p - e.xyz; float d = length(q) - e.w;
    float up = smoothstep(-0.05, 0.22, q.y / e.w), front = smoothstep(0.1, 0.4, q.z / e.w), side = 1.0 - smoothstep(0.85, 1.1, abs(q.x) / e.w);
    float outer = 1.0 + 0.4 * smoothstep(0.0, 0.9, q.x * sign(e.x) / e.w);
    float line = (1.0 - smoothstep(0.0016, 0.0032, d)) * smoothstep(-0.004, -0.002, d), shade = 0.4 * (1.0 - smoothstep(0.0032, 0.0065, d)) * step(-0.002, d);
    return clamp((line + shade) * up * front * side * outer, 0.0, 0.92);
  }
`;

// the hands (attribute handData, from buildHandData in body.js): x = along the finger in phalanges (0 at the last
// joint, 1 at the tip, -1 the middle joint, -2 the knuckle), y = across it (-1..1, the finger's radius), z = toward
// the back of the hand (1 on top, -1 on the pad), w = 1 off the fingers (the default for a mesh without the attribute)
const HAND = /* glsl */`
  // the back of the hand: the tendons over each metacarpal (ridges along it, s in -3..-2) and a few veins that
  // wander across it, as height (m)
  float sk_handBump(){
    float fg = 1.0 - vHand.w;
    if (fg <= 0.001) return 0.0;
    float s = vHand.x, la = vHand.y, dz = vHand.z;
    float top = smoothstep(0.2, 0.6, dz);
    float onBack = smoothstep(-3.05, -2.8, s) * (1.0 - smoothstep(-2.15, -1.95, s));
    float tendon = exp(-la * la / 0.09) * onBack * (0.6 + 0.4 * smoothstep(-2.9, -2.3, s));
    float vn = sk_noise(vObj * 28.0 + 4.0), vein = (1.0 - smoothstep(0.0, 0.11, abs(vn - 0.5))) * smoothstep(-3.2, -2.6, s) * (1.0 - smoothstep(-2.3, -2.0, s));
    return (0.0009 * tendon + 0.00045 * vein * vein) * top * fg;
  }
  // fine body hair (vellus) where hairData.w < 1: short, thin, dark strands lying along hairData.xyz, one root per
  // ~2.2 mm cell (sparse); returns the coverage of this pixel, faded to a faint tint once a strand is sub-pixel
  float sk_hair(vec3 p, vec3 n, vec4 hd){
    float dens = 1.0 - hd.w;
    if (dens <= 0.01) return 0.0;
    float px = max(length(fwidth(p)), 1e-6);
    float cs = 0.0042; vec3 x = p / cs, i = floor(x); float cov = 0.0;
    vec3 flow = normalize(hd.xyz - n * dot(hd.xyz, n) + 1e-5);
    for (int a = -1; a <= 1; a++) for (int b = -1; b <= 1; b++) for (int c = -1; c <= 1; c++) {
      vec3 cell = i + vec3(a, b, c);
      if (sk_hash(cell + 5.3) > 0.8 * dens) continue;
      vec3 root = (cell + vec3(sk_hash(cell), sk_hash(cell + 17.0), sk_hash(cell + 31.0))) * cs;
      vec3 d = normalize(flow + 0.45 * (vec3(sk_hash(cell + 3.1), sk_hash(cell + 7.7), sk_hash(cell + 9.9)) - 0.5));
      d = normalize(d - n * dot(d, n));
      float L = cs * (0.7 + 0.6 * sk_hash(cell + 2.2)), t = clamp(dot(p - root, d), 0.0, L);
      vec3 q = p - root - d * t; float dist = length(q - n * dot(q, n));   // the distance across the skin
      float w = 0.00006 * (1.0 - 0.6 * t / L);
      float c1 = (1.0 - smoothstep(0.0, w + px, dist)) * min(1.0, w * 3.0 / px);
      cov = max(cov, c1 * (0.6 + 0.4 * sk_hash(cell + 4.4)));
    }
    return cov;
  }
  void sk_hand(inout vec3 col, inout float nail, inout float crease){
    float fg = 1.0 - vHand.w;
    if (fg <= 0.001) return;
    float s = vHand.x, la = vHand.y, dz = vHand.z;
    float top = smoothstep(0.25, 0.6, dz), pad = smoothstep(0.1, 0.6, -dz);
    vec3 skin = col;
    // where the blood shows: the fingertips (most on the pads), the pad side of the fingers, the knuckles
    float fin = smoothstep(-2.3, -1.9, s);                       // on the fingers (not the back of the hand)
    float tip = smoothstep(0.1, 0.85, s) * (0.6 + 0.4 * pad);
    float blot = smoothstep(0.35, 0.8, sk_noise(vObj * 160.0));
    col = mix(col, col * vec3(1.07, 0.78, 0.74), (0.6 * tip + 0.25 * pad * fin * (0.7 + 0.3 * blot)) * fg);
    col *= mix(vec3(1.0), vec3(1.05, 0.9, 0.87), fg);    // the fingers a little pinker than the arm
    // the creases: over each joint on the back, a cluster of curved rings round the joint's bump (the photo's
    // "eyes" over the knuckles), broken and uneven; on the pad side one or two deep straight lines
    float cr = 0.0, knuckle = 0.0;
    for (int j = 0; j < 3; j++) {
      float k = -float(j);                                       // 0 the last joint, -1 the middle joint, -2 the knuckle
      float d = s - k + 0.03 * la * la;
      float rr = length(vec2((s - k - 0.02) * (j == 0 ? 3.2 : 2.4), la * 0.85));   // distance from the joint's bump
      float n = sk_noise(vec3(s * 9.0, la * 3.0, float(j) * 7.0));
      float db = (s - k) - 0.07 * la * la;                        // lines across the finger, bowed round the joint
      float rings = (1.0 - smoothstep(0.0, 0.16, abs(fract(db * 15.0 + 0.7 * n) - 0.5) * 2.0))
                  * smoothstep(0.25, 0.55, sk_noise(vec3(s * 7.0, la * 2.5, float(j) * 3.0 + 11.0)))
                  * (1.0 - smoothstep(0.12, 0.26, abs(db)));
      float back = top * rings * (j == 2 ? 0.5 : 1.0) * (1.0 - smoothstep(0.75, 0.95, abs(la)));
      float palm = pad * (1.0 - smoothstep(0.0, 0.045, abs(d - 0.04))) * (j == 2 ? 0.6 : 1.0);
      cr = max(cr, max(back, palm));
      knuckle = max(knuckle, top * (1.0 - smoothstep(0.15, 0.6, rr)) * (j == 2 ? 1.0 : 0.7));
    }
    // the skin over the joints is darker and redder (the photo's knuckles)
    col *= mix(vec3(1.0), vec3(1.0, 0.84, 0.82), knuckle * fg * (0.7 + 0.3 * blot));
    crease = cr * fg;
    col *= 1.0 - 0.3 * crease;
    // the nail: on top of the last phalanx, its base a curve (the cuticle) a third of the way down, its sides inside
    // the finger's width, to the tip and a little past (the free edge)
    float base = 0.26 + 0.16 * la * la;
    float side = 1.0 - smoothstep(0.72, 0.84, abs(la));
    float inN = smoothstep(base, base + 0.03, s) * side * smoothstep(0.22, 0.4, dz);
    nail = inN * fg;
    vec3 bed = col * vec3(1.02, 0.86, 0.84);                     // the bed seen through the plate: the skin, a bit pinker
    vec3 lun = col * vec3(1.08, 1.02, 1.0);                      // the lunula: a little paler, not white
    vec3 edge = vec3(0.80, 0.74, 0.64);                          // the free edge: off-white, a little yellow
    float lu = (1.0 - smoothstep(0.08, 0.14, (s - base) / max(0.2, 1.0 - 1.6 * la * la))) * (1.0 - smoothstep(0.35, 0.55, abs(la)));
    // the free edge: an uneven line (the nail is cut, not drawn)
    float fe = smoothstep(0.0, 0.035, s - (0.9 + 0.025 * (sk_noise(vec3(la * 7.0, 3.0, vObj.y * 50.0)) - 0.5) + 0.02 * la * la));
    vec3 nc = mix(bed, lun, 0.55 * lu);
    nc = mix(nc, edge, 0.75 * fe);
    // the cuticle and the nail folds: a soft shadow where the fold overlaps the plate, a drier rim round it
    float rim = smoothstep(base - 0.08, base, s) * (1.0 - smoothstep(base, base + 0.05, s)) * side * top
              + (smoothstep(0.66, 0.8, abs(la)) * (1.0 - smoothstep(0.84, 0.96, abs(la)))) * smoothstep(base, base + 0.05, s) * top;
    col *= 1.0 - 0.16 * clamp(rim, 0.0, 1.0) * fg;
    nc *= 1.0 - 0.25 * (1.0 - smoothstep(0.0, 0.06, s - base)) * side;   // the fold's shadow on the plate's base
    col = mix(col, nc, nail);
  }
`;
export function makeSkinMaterial(THREE, {envMapIntensity = 0.6} = {}){
  const m = new THREE.MeshPhysicalMaterial({
    vertexColors: true, color: 0xffffff, roughness: 0.52, metalness: 0, ior: 1.4, specularIntensity: 0.55,
    sheen: 0.25, sheenRoughness: 0.5, sheenColor: new THREE.Color(0.55, 0.45, 0.42), envMapIntensity,
    clearcoat: 0.0001, clearcoatRoughness: 0.12,             // only the nails use it (set per pixel below)
  });
  m.userData.uniforms = {uEyeL: {value: new THREE.Vector4(0, 0, 0, 0)}, uEyeR: {value: new THREE.Vector4(0, 0, 0, 0)}, uPore: {value: 1.0}, uWrap: {value: new THREE.Vector3(0.44, 0.24, 0.15)}, uTrans: {value: 0.9}};
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, m.userData.uniforms);
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", `#include <common>\nattribute vec4 skinData; attribute vec4 handData; attribute vec4 hairData; varying vec4 vSkin; varying vec4 vHand; varying vec4 vHairD; varying vec3 vObj; varying vec3 vObjN;`)
      .replace("#include <begin_vertex>", `#include <begin_vertex>\nvSkin = skinData; vHand = handData; vHairD = hairData; vObj = position; vObjN = normal;`);
    const direct = THREE.ShaderChunk.lights_physical_pars_fragment.replace(
      "reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );\n}\nvoid RE_IndirectDiffuse_Physical",
      `// subsurface-style softness: per-channel wrap past the terminator (energy kept by the 1 + w divisor)
      float sk_nl = dot( geometryNormal, directLight.direction );
      vec3 sk_wrapNL = clamp( ( vec3( sk_nl ) + uWrap ) / ( 1.0 + uWrap ), 0.0, 1.0 ) / ( 1.0 + 0.5 * uWrap );
      reflectedLight.directDiffuse += sk_wrapNL * directLight.color * BRDF_Lambert( material.diffuseColor );
      // translucency where the skin is thin: light from behind, seen through (red, it has crossed the blood)
      float sk_back = pow( saturate( dot( geometryViewDir, -normalize( directLight.direction + 0.35 * geometryNormal ) ) ), 3.0 );
      reflectedLight.directDiffuse += uTrans * vSkin.x * sk_back * directLight.color * vec3( 0.85, 0.28, 0.16 ) * material.diffuseColor;
}
void RE_IndirectDiffuse_Physical`);
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", `#include <common>\nvarying vec4 vSkin; varying vec4 vHand; varying vec4 vHairD; varying vec3 vObj; varying vec3 vObjN; uniform float uPore; uniform vec3 uWrap; uniform float uTrans; uniform vec4 uEyeL, uEyeR;\n${NOISE}\n${LASH}\n${HAND}`)
      .replace("#include <lights_physical_pars_fragment>", direct)
      // colour: a faint mottle (freckle-scale and blotch-scale), the vertex colours already carry the regions
      .replace("#include <color_fragment>", `#include <color_fragment>
        float sk_m = sk_noise(vObj * 90.0) * 0.6 + sk_noise(vObj * 340.0) * 0.4;
        diffuseColor.rgb *= mix(vec3(1.0), vec3(1.04, 0.97, 0.96), smoothstep(0.35, 0.75, sk_m)) * (0.97 + 0.06 * sk_noise(vObj * 25.0));
        // blotchy redness at a few cm (the capillaries are uneven): a low-frequency patchwork, stronger where the
        // regions are already red (cheeks, nose, ears: the vertex colour's red excess)
        float sk_bl = sk_noise(vObj * 16.0 + 7.0) * 0.6 + sk_noise(vObj * 47.0) * 0.4;
        float sk_redz = clamp((vColor.r - vColor.g) * 4.0 - 0.5, 0.0, 1.0);
        diffuseColor.rgb *= mix(vec3(1.0), vec3(1.06, 0.88, 0.86), smoothstep(0.42, 0.8, sk_bl) * (0.55 + 0.6 * sk_redz));
        float sk_lash = max(sk_lashAt(vObj, uEyeL), sk_lashAt(vObj, uEyeR));
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.018, 0.013, 0.011), sk_lash);
        float sk_nail = 0.0, sk_crease = 0.0;
        sk_hand(diffuseColor.rgb, sk_nail, sk_crease);
        float sk_hairC = sk_hair(vObj, normalize(vObjN), vHairD);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.05, 0.032, 0.022), 0.8 * sk_hairC);`)
      // the T-zone: tighter and stronger specular; cavities: less specular
      .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.31, vSkin.y);
        roughnessFactor = mix(roughnessFactor, 0.30, vSkin.w);
        roughnessFactor = mix(roughnessFactor, 0.62, sk_crease);          // the creases are drier, matte
        roughnessFactor = mix(roughnessFactor, 0.30, sk_nail);            // the nail plate: smooth keratin`)
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
        {
          // pores (~1 mm cells, pits 0.25 mm deep in effect) and fine wrinkles, as a bump on the shading normal;
          // faded out once a pixel covers more than ~0.6 mm, so they never alias at the room distance
          float px = length(fwidth(vObj));
          float k = uPore * (1.0 - smoothstep(0.00025, 0.0006, px));
          float h = 0.0;
          if (k > 0.0) {
            float pf = mix(1150.0, 700.0, vSkin.y);                     // pore spacing: ~0.9 mm, ~1.4 mm on the nose
            float c = sk_cell(vObj * pf);
            h = -smoothstep(0.5, 0.05, c) * mix(0.00002, 0.000036, vSkin.y) * (1.0 - vSkin.w);   // soft, dense pits, not specks
            h += (sk_noise(vObj * vec3(2400.0, 900.0, 2400.0)) - 0.5) * 0.000008;
            // the furrow net: cells ~0.6 mm, grooves along their walls, broken here and there
            vec2 fn = sk_cell2(vObj * 1600.0 + 0.3);
            h -= (1.0 - smoothstep(0.0, 0.14, fn.y - fn.x)) * 0.000016 * smoothstep(0.2, 0.55, sk_noise(vObj * 600.0)) * (1.0 - vSkin.w);
            h *= k;
          }
          h += sk_handBump();
          // the knuckles' creases: shallow grooves, faded out a little later than the pores (they are wider)
          h -= sk_crease * 0.0001 * (1.0 - smoothstep(0.0004, 0.0009, px));
          vec3 sx = dFdx(-vViewPosition), sy = dFdy(-vViewPosition);
          vec3 r1 = cross(sy, normal), r2 = cross(normal, sx);
          float det = dot(sx, r1) * faceDirection;
          vec3 grad = sign(det) * (dFdx(h) * r1 + dFdy(h) * r2);
          normal = normalize(abs(det) * normal - grad);
        }`)
      // the cavities hold less ambient light too (a baked AO that does not need shadows)
      .replace("#include <lights_physical_fragment>", `#include <lights_physical_fragment>
        material.specularColor *= 1.0 + 0.7 * vSkin.y;                    // more sheen where the skin is oily
        #ifdef USE_CLEARCOAT
          material.clearcoat = 0.35 * sk_nail;                            // the nails' gloss: a thin, sharp coat
          material.clearcoatRoughness = 0.09;
        #endif`)
      .replace("#include <aomap_fragment>", `#include <aomap_fragment>
        reflectedLight.indirectDiffuse *= 1.0 - 0.45 * vSkin.z;
        reflectedLight.indirectSpecular *= 1.0 - 0.6 * vSkin.z;`);
  };
  m.customProgramCacheKey = () => "skin-v9";
  return m;
}

// ---------- the eyes ----------
export function irisTexture(THREE, {w = 1024, h = 512, iris = [0.24, 0.13, 0.06], irisDeg = 23.5, pupilDeg = 6.8} = {}){
  // equirectangular, the iris centred on the top pole (row 0 = the front of the eye once the ball is turned)
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d"), img = g.createImageData(w, h), d = img.data;
  const rnd = (a) => { const s = Math.sin(a * 12.9898) * 43758.5453; return s - Math.floor(s); };
  const fib = new Float32Array(w); for (let x = 0; x < w; x++) fib[x] = rnd(x * 0.37) * 0.6 + rnd(Math.floor(x / 3) * 1.7) * 0.4;
  const crypt = new Float32Array(w); for (let x = 0; x < w; x++) crypt[x] = rnd(Math.floor(x / 23) * 3.1);
  for (let y = 0; y < h; y++) {
    const th = y / h * 180;
    for (let x = 0; x < w; x++) {
      let r, gg, b;
      if (th < irisDeg) {
        const t = (th - pupilDeg) / (irisDeg - pupilDeg);            // 0 at the pupil's edge, 1 at the limbus
        const f = 0.65 + 0.55 * fib[x] * (0.6 + 0.4 * Math.sin(t * 9 + x * 0.05));
        const collar = Math.exp(-Math.pow((t - 0.3) / 0.08, 2));    // the collarette: a lighter ring a third of the way out
        const cr = crypt[x] > 0.75 ? 1 - 0.3 * Math.max(0, Math.sin(Math.PI * Math.min(1, Math.max(0, (t - 0.38) / 0.36)))) * Math.sin(Math.PI * ((x % 23) / 23)) : 1;  // crypts: soft darker pits in the outer iris
        const limbus = Math.pow(Math.min(1, Math.max(0, (t - 0.78) / 0.22)), 1.6);
        const k = f * (1 + 0.6 * collar) * cr * (1 - 0.8 * limbus);
        [r, gg, b] = [iris[0] * k * 1.1, iris[1] * k, iris[2] * k];
        if (th < pupilDeg) [r, gg, b] = [0.012, 0.010, 0.010];
        else if (th < pupilDeg + 0.6) [r, gg, b] = [r * 0.4, gg * 0.4, b * 0.4];
      } else {
        // sclera: off-white, a little greyer and pinker away from the cornea, faint veins toward the corners
        const t = Math.min(1, (th - irisDeg) / 70);
        const vein = Math.max(0, Math.sin(x * 0.11 + Math.sin(th * 0.3) * 3) * Math.sin(x * 0.023 + th * 0.07)) ;
        const v = t > 0.35 ? Math.pow(vein, 18) * (t - 0.35) : 0;
        [r, gg, b] = [0.78 - 0.08 * t + 0.45 * v, 0.74 - 0.12 * t - 0.22 * v, 0.70 - 0.12 * t - 0.22 * v];
        if (th < irisDeg + 1.2) { const s = (th - irisDeg) / 1.2; [r, gg, b] = [r * (0.35 + 0.65 * s), gg * (0.35 + 0.65 * s), b * (0.35 + 0.65 * s)]; }
      }
      const o = 4 * (y * w + x);
      d[o] = 255 * Math.pow(Math.min(1, r), 1 / 2.2); d[o + 1] = 255 * Math.pow(Math.min(1, gg), 1 / 2.2); d[o + 2] = 255 * Math.pow(Math.min(1, b), 1 / 2.2); d[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}

function eyeballMaterial(THREE, map){
  const m = new THREE.MeshPhysicalMaterial({map, roughness: 0.32, metalness: 0, ior: 1.376, specularIntensity: 0.6, envMapIntensity: 0.6});
  m.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vEyeN;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvEyeN = normalize((modelMatrix * vec4(normal, 0.0)).xyz);");
    // the lids' shadow on the ball: under the upper lid and in both corners (in the head's frame: the eye group is
    // not rotated with the ball's own turn), a soft socket ring that does not depend on shadow maps
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vEyeN;")
      .replace("#include <aomap_fragment>", `#include <aomap_fragment>
        float eo = 1.0 - 0.85 * smoothstep(0.0, 0.34, vEyeN.y) - 0.45 * smoothstep(0.42, 0.85, abs(vEyeN.x)) - 0.35 * smoothstep(0.25, 0.6, -vEyeN.y);
        eo = clamp(eo, 0.12, 1.0);
        reflectedLight.directDiffuse *= eo; reflectedLight.indirectDiffuse *= eo;
        reflectedLight.directSpecular *= eo; reflectedLight.indirectSpecular *= eo;`);
  };
  m.customProgramCacheKey = () => "eyeball-v1";
  return m;
}

function corneaMaterial(THREE){
  // additive: black base, only the specular and the environment's reflection are added on top of the iris
  return new THREE.MeshPhysicalMaterial({color: 0x000000, roughness: 0.035, metalness: 0, ior: 1.376, specularIntensity: 1,
    envMapIntensity: 1.6, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending});
}

// the eyes, the lash and tear lines and the caruncles, added to group in the skin's own frame; P = the skin's
// positions (the lid margins are found on it), eyes = {l: {center, radius}, r: ...} with the helper sphere's radius
// the lashes: thin curved ribbons along a lid margin (sorted across the eye), leaning out of the lid and curling up
// (upper) or down (lower); longest past the middle toward the outer corner, a little uneven in length and angle
function lashStrands(THREE, pts, C, up, {count, len, width}){
  const curve = new THREE.CatmullRomCurve3(pts), pos = [], idx = [];
  const rnd = a => { const x = Math.sin(a * 91.345 + up * 13.1) * 43758.5453; return x - Math.floor(x); };
  const Y = new THREE.Vector3(0, up, 0), Z = new THREE.Vector3(0, 0, 1), SEG = 6;
  const outerSign = Math.sign(pts[pts.length - 1].x - pts[0].x) * Math.sign(C.x);   // +1 when t = 1 is the outer corner
  for (let n = 0; n < count; n++) {
    const t = Math.min(0.995, Math.max(0.005, (n + 0.5 + 0.6 * (rnd(n) - 0.5)) / count));
    const T = curve.getTangentAt(t), m = curve.getPointAt(t);
    // the root on the lid's visible edge, just out of the skin
    const p0 = m.clone().addScaledVector(m.clone().sub(C).normalize(), 0.0003);
    const tOut = outerSign > 0 ? t : 1 - t;                      // 0 at the inner corner, 1 at the outer
    const L = len * (0.45 + 0.55 * Math.sin(Math.PI * Math.min(1, 0.15 + 0.85 * tOut))) * (0.8 + 0.4 * rnd(n + 50));
    const out = p0.clone().sub(C).normalize();
    const d0 = out.clone().multiplyScalar(0.3).addScaledVector(Z, 0.85).addScaledVector(Y, 0.22).normalize();
    d0.applyAxisAngle(T, (rnd(n + 9) - 0.5) * 0.35);
    const p1 = p0.clone().addScaledVector(d0, L * 0.6), p2 = p0.clone().addScaledVector(d0, L * 0.75).addScaledVector(Y, L * 0.5);
    const base = pos.length / 3;
    for (let k = 0; k <= SEG; k++) {
      const u = k / SEG, a = (1 - u) * (1 - u), b = 2 * u * (1 - u), c = u * u;
      const q = new THREE.Vector3().addScaledVector(p0, a).addScaledVector(p1, b).addScaledVector(p2, c);
      const w = width * (1 - 0.85 * u);
      pos.push(q.x - T.x * w / 2, q.y - T.y * w / 2, q.z - T.z * w / 2, q.x + T.x * w / 2, q.y + T.y * w / 2, q.z + T.z * w / 2);
      if (k < SEG) { const o = base + 2 * k; idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2); }
    }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}

export function addEyes(THREE, group, P, eyes, {iris = [0.24, 0.13, 0.06], index = null} = {}){
  const loopsN = {};
  const map = irisTexture(THREE, {iris});
  const ballMat = eyeballMaterial(THREE, map), corneaMat = corneaMaterial(THREE);
  const lashMat = new THREE.MeshStandardMaterial({color: new THREE.Color(0.02, 0.016, 0.014), roughness: 0.6});
  const tearMat = new THREE.MeshPhysicalMaterial({color: new THREE.Color(0.86, 0.66, 0.64), roughness: 0.02, metalness: 0, clearcoat: 1,
    clearcoatRoughness: 0.01, transparent: true, opacity: 0.85, envMapIntensity: 2.2, specularIntensity: 1});
  const strandMat = new THREE.MeshStandardMaterial({color: new THREE.Color(0.022, 0.017, 0.014), roughness: 0.45, side: THREE.DoubleSide});
  group.userData.cornea = corneaMat; group.userData.tear = tearMat;
  const carMat = new THREE.MeshPhysicalMaterial({color: new THREE.Color(0.82, 0.45, 0.45), roughness: 0.2, clearcoat: 0.8, clearcoatRoughness: 0.08});
  for (const [side, e] of Object.entries(eyes)) {
    // the ball: 0.85 of the helper sphere (12.7 mm; MakeHuman's lid margins sit at 0.81-0.91 of it, so a full-size
    // ball would poke through the lids)
    const C = new THREE.Vector3(...e.center), r = e.radius * EYE_K;   // e.radius: the helper sphere's
    const eye = new THREE.Group(); eye.position.copy(C); eye.name = "eye_" + side;
    // the ball looks ahead and very slightly out (a relaxed gaze converges a little at the room distance)
    const fwd = new THREE.Vector3(Math.sign(C.x) * 0.03, -0.02, 1).normalize();
    const ball = new THREE.Mesh(new THREE.SphereGeometry(r, 64, 48), ballMat);
    ball.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), fwd);   // the texture's top pole (the iris) forward
    eye.add(ball);
    // the cornea: a cap of a smaller sphere (radius 0.53 r, as 7.8 mm on a 12 mm ball) that bulges 0.05 r out of the ball
    const rc = r * 0.53, off = r - rc + r * 0.05;
    const cap = new THREE.Mesh(new THREE.SphereGeometry(rc, 48, 24, 0, Math.PI * 2, 0, 0.78), corneaMat);
    cap.position.copy(fwd).multiplyScalar(off); cap.quaternion.copy(ball.quaternion); cap.renderOrder = 2;
    eye.add(cap);
    group.add(eye);
    // the tear line: the lower lid margin is where the skin meets the ball (this mesh is closed over the eye: the
    // ball shows through where the lids part, so the margin is the ring of skin vertices just outside the ball's
    // radius, in front of its centre)
    // the lid margins: in each 1.5 mm slice across the eye, the skin vertex nearest the ball, above (upper lid) and
    // below (lower lid) the centre, in front of it
    const v = new THREE.Vector3();
    // the visible margin is where the lid's skin crosses the ball's surface (the skin may run on inside the ball,
    // hidden). With the mesh's triangles: per 1.5 mm slice, the front-most point where an edge crosses the sphere,
    // above (upper lid) or below (lower lid) the centre. Without them: the skin vertex nearest the ball.
    const crossings = [];
    if (index) {
      const a = new THREE.Vector3(), b = new THREE.Vector3(), seen = new Set();
      for (let t = 0; t < index.length; t += 3) for (let e = 0; e < 3; e++) {
        const i = index[t + e], j = index[t + (e + 1) % 3], key = i < j ? i * 1e6 + j : j * 1e6 + i;
        if (seen.has(key)) continue; seen.add(key);
        a.fromBufferAttribute(P, i).sub(C); b.fromBufferAttribute(P, j).sub(C);
        const la = a.length() - r, lb = b.length() - r;
        if (la * lb > 0 || a.z < 0 && b.z < 0) continue;
        const f = la / (la - lb), p = a.clone().lerp(b, f);
        if (p.z > r * 0.2) crossings.push(p.add(C));
      }
    }
    const margin = up => { const bins = new Map();
      if (crossings.length) {
        for (const p of crossings) { const q = p.clone().sub(C);
          if (Math.abs(q.x) > r * 1.0 || (up ? q.y < -r * 0.02 : q.y > r * 0.02)) continue;
          const k = Math.round(q.x / 0.0015), o = bins.get(k); if (!o || p.z > o.z) bins.set(k, p.clone()); }
      } else {
        for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i); const q = v.clone().sub(C);
          if (q.z < r * 0.35 || Math.abs(q.x) > r * 0.95 || (up ? q.y < r * 0.05 : q.y > -r * 0.3) || q.length() > r * 1.4) continue;
          const k = Math.round(q.x / 0.0015), o = bins.get(k); if (!o || q.length() < o.distanceTo(C)) bins.set(k, v.clone()); }
      }
      return [...bins.entries()].sort((a, b) => a[0] - b[0]).map(e => e[1]); };
    const lower = margin(false).slice(1, -1), upper = margin(true);
    if (upper.length > 3) {
      // the lash line: a dark tube on the upper margin (lashes and their shadow), thicker toward the outer corner
      const pts = upper.map(p => p.clone().add(p.clone().sub(C).normalize().multiplyScalar(0.0003)));
      const lash = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, 0.00075, 6, false), lashMat);
      lash.name = "lash_" + side; group.add(lash);
      // the lash strands need the visible margin (the edge crossings: a mesh open at the lids, as G2's body)
      if (crossings.length) {
        const strands = new THREE.Mesh(lashStrands(THREE, upper, C, 1, {count: 90, len: 0.0082, width: 0.00012}), strandMat);
        strands.name = "lashes_up_" + side; group.add(strands);
      }
    }
    if (lower.length > 4) {
      const pts = lower.map(p => p.clone().lerp(C, 0.03));
      const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, 0.00045, 6, false), tearMat);
      // the lower lashes: fewer, shorter, from just outside the wet line
      if (crossings.length) {
        const lows = new THREE.Mesh(lashStrands(THREE, lower, C, -1, {count: 40, len: 0.004, width: 0.00009}), strandMat);
        lows.name = "lashes_low_" + side; group.add(lows);
      }
      tube.name = "tear_" + side; tube.renderOrder = 3; group.add(tube);
      // the caruncle: the pink corner on the nose side
      const inner = (Math.sign(C.x) > 0 ? lower[0] : lower[lower.length - 1]);
      const car = new THREE.Mesh(new THREE.SphereGeometry(0.0016, 16, 12), carMat);
      car.position.copy(C).addScaledVector(inner.clone().sub(C).normalize(), r * 1.0).add(new THREE.Vector3(0, r * 0.12, 0));
      car.scale.set(0.9, 1.3, 0.8); group.add(car);
    }
    loopsN[side] = [upper.length, lower.length];
  }
  return loopsN;
}

export function buildHead(THREE, data, {iris = [0.24, 0.13, 0.06]} = {}){
  const group = new THREE.Group();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(data.position), 3));
  geo.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(data.uv), 2));
  geo.setIndex(data.index);
  const ids = smoothNormals(THREE, geo);
  const L = skinData(THREE, geo, data);
  const skin = new THREE.Mesh(geo, makeSkinMaterial(THREE));
  { const u = skin.material.userData.uniforms, E = data.eyes;
    u.uEyeL.value.set(...E.l.center, E.l.radius * EYE_K); u.uEyeR.value.set(...E.r.center, E.r.radius * EYE_K); }
  skin.name = "skin"; group.add(skin);

  const loopsN = addEyes(THREE, group, geo.attributes.position, data.eyes, {iris});
  group.userData.landmarks = L;
  group.userData.lidLoops = loopsN;
  return group;
}
