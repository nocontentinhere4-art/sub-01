// node dequant_slides.mjs built.glb unquantized_src.glb out.glb : give the "slides" mesh real (float) positions again, so
// a page can clone its geometry with bindMatrix and get metres (boy_mh.js parks the pair by the bed that way). meshopt's
// quantization stores the dequantization in each skin's inverse bind matrices: IBM' = IBM * Q, so p = Q * p_q and the
// skin gets IBM back from the unquantized source. Everything else in the file is left as built.
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const [,, IN, SRC, OUT] = process.argv;
const doc = await io.read(IN), src = await io.read(SRC);
const node = doc.getRoot().listNodes().find(n => n.getName() === "slides"); const skin = node.getSkin();
const srcSkin = src.getRoot().listSkins()[0];
const q = Array.from(skin.getInverseBindMatrices().getArray().slice(0, 16)), o = Array.from(srcSkin.getInverseBindMatrices().getArray().slice(0, 16));
const inv = m => { const a = m, r = new Array(16); // affine inverse (column-major)
  const [a00,a01,a02,a10,a11,a12,a20,a21,a22] = [a[0],a[1],a[2],a[4],a[5],a[6],a[8],a[9],a[10]];
  const det = a00*(a11*a22-a12*a21)-a01*(a10*a22-a12*a20)+a02*(a10*a21-a11*a20);
  const b = [(a11*a22-a12*a21)/det,-(a01*a22-a02*a21)/det,(a01*a12-a02*a11)/det,-(a10*a22-a12*a20)/det,(a00*a22-a02*a20)/det,-(a00*a12-a02*a10)/det,(a10*a21-a11*a20)/det,-(a00*a21-a01*a20)/det,(a00*a11-a01*a10)/det];
  r[0]=b[0];r[1]=b[1];r[2]=b[2];r[3]=0;r[4]=b[3];r[5]=b[4];r[6]=b[5];r[7]=0;r[8]=b[6];r[9]=b[7];r[10]=b[8];r[11]=0;
  const t=[a[12],a[13],a[14]]; r[12]=-(r[0]*t[0]+r[4]*t[1]+r[8]*t[2]); r[13]=-(r[1]*t[0]+r[5]*t[1]+r[9]*t[2]); r[14]=-(r[2]*t[0]+r[6]*t[1]+r[10]*t[2]); r[15]=1; return r; };
const mul = (a, b) => { const r = new Array(16).fill(0); for (let c=0;c<4;c++) for (let rr=0;rr<4;rr++) for (let k=0;k<4;k++) r[c*4+rr]+=a[k*4+rr]*b[c*4+k]; return r; };
const Q0 = mul(inv(o), q);
// metres: the build scales the Armature (not the mesh node), so store the geometry pre-scaled by that factor and take it
// back out of the inverse bind matrices; cloned with bindMatrix, the slides are then life-size
const arm = doc.getRoot().listScenes()[0].listChildren().find(c => Math.abs(c.getScale()[0] - 1) > 1e-3); const k = arm ? arm.getScale()[0] : 1;
const Sk = [k,0,0,0, 0,k,0,0, 0,0,k,0, 0,0,0,1], Sinv = [1/k,0,0,0, 0,1/k,0,0, 0,0,1/k,0, 0,0,0,1];
const Q = mul(Sk, Q0);                                   // IBM' = IBM * Q  ->  Q = IBM^-1 * IBM'
const prim = node.getMesh().listPrimitives()[0], pa = prim.getAttribute("POSITION");
const n = pa.getCount(), out = new Float32Array(n * 3), e = [0, 0, 0];
for (let i = 0; i < n; i++) { pa.getElement(i, e); for (let r = 0; r < 3; r++) out[i*3+r] = Q[r]*e[0] + Q[4+r]*e[1] + Q[8+r]*e[2] + Q[12+r]; }
prim.setAttribute("POSITION", doc.createAccessor().setType("VEC3").setArray(out).setBuffer(pa.getBuffer()));
{ const a = srcSkin.getInverseBindMatrices().getArray(), b = new Float32Array(a.length);
  for (let j = 0; j < a.length / 16; j++) b.set(mul(Array.from(a.slice(j*16, j*16+16)), Sinv), j*16);
  skin.setInverseBindMatrices(doc.createAccessor().setType("MAT4").setArray(b).setBuffer(pa.getBuffer())); }
console.log("armature scale", k);
// check: the source's slide positions, in the same order? report the bounding box in metres-to-be (Tripo units here)
let lo=[1e9,1e9,1e9], hi=[-1e9,-1e9,-1e9]; for (let i=0;i<n;i++) for (let r=0;r<3;r++){lo[r]=Math.min(lo[r],out[i*3+r]);hi[r]=Math.max(hi[r],out[i*3+r]);}
console.log("Q scale", Q[0].toFixed(5), Q[5].toFixed(5), Q[10].toFixed(5), "slides box", lo.map(v=>v.toFixed(3)), hi.map(v=>v.toFixed(3)));
await io.write(OUT, doc);
