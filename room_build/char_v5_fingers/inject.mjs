// node inject.mjs in.glb workdir out.glb [pose.json] : add the finger joints (fingers.json) to the skin, with the new body
// weights (nf_j.bin, nf_w.bin). Each joint's local transform = inverse(parent bind) * own bind, so at rest it rides its
// parent exactly. pose.json (optional, tests only): {jointName: [x,y,z,w] extra local rotation}.
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, IN, WD, OUT, POSE] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(IN); const root = doc.getRoot(); const skin = root.listSkins()[0]; const buf = root.listBuffers()[0];
const F = JSON.parse(fs.readFileSync(`${WD}/fingers.json`)); const pose = POSE ? JSON.parse(fs.readFileSync(POSE)) : {};
const joints = skin.listJoints(); const ibmA = skin.getInverseBindMatrices().getArray();
const inv = m => { // 4x4 column-major inverse (rigid + uniform scale safe, general)
  const a = m, o = new Array(16); const s0=a[0]*a[5]-a[4]*a[1], s1=a[0]*a[6]-a[4]*a[2], s2=a[0]*a[7]-a[4]*a[3], s3=a[1]*a[6]-a[5]*a[2], s4=a[1]*a[7]-a[5]*a[3], s5=a[2]*a[7]-a[6]*a[3];
  const c5=a[10]*a[15]-a[14]*a[11], c4=a[9]*a[15]-a[13]*a[11], c3=a[9]*a[14]-a[13]*a[10], c2=a[8]*a[15]-a[12]*a[11], c1=a[8]*a[14]-a[12]*a[10], c0=a[8]*a[13]-a[12]*a[9];
  const d = 1/(s0*c5-s1*c4+s2*c3+s3*c2-s4*c1+s5*c0);
  o[0]=(a[5]*c5-a[6]*c4+a[7]*c3)*d; o[1]=(-a[1]*c5+a[2]*c4-a[3]*c3)*d; o[2]=(a[13]*s5-a[14]*s4+a[15]*s3)*d; o[3]=(-a[9]*s5+a[10]*s4-a[11]*s3)*d;
  o[4]=(-a[4]*c5+a[6]*c2-a[7]*c1)*d; o[5]=(a[0]*c5-a[2]*c2+a[3]*c1)*d; o[6]=(-a[12]*s5+a[14]*s2-a[15]*s1)*d; o[7]=(a[8]*s5-a[10]*s2+a[11]*s1)*d;
  o[8]=(a[4]*c4-a[5]*c2+a[7]*c0)*d; o[9]=(-a[0]*c4+a[1]*c2-a[3]*c0)*d; o[10]=(a[12]*s4-a[13]*s2+a[15]*s0)*d; o[11]=(-a[8]*s4+a[9]*s2-a[11]*s0)*d;
  o[12]=(-a[4]*c3+a[5]*c1-a[6]*c0)*d; o[13]=(a[0]*c3-a[1]*c1+a[2]*c0)*d; o[14]=(-a[12]*s3+a[13]*s1-a[14]*s0)*d; o[15]=(a[8]*s3-a[9]*s1+a[10]*s0)*d; return o; };
const mul = (a, b) => { const o = new Array(16).fill(0); for (let c=0;c<4;c++) for (let r=0;r<4;r++) for (let k=0;k<4;k++) o[c*4+r]+=a[k*4+r]*b[c*4+k]; return o; };
const colMajor = M => [0,1,2,3].flatMap(c => [0,1,2,3].map(r => M[r][c]));
const quatFromMat = m => { const t=m[0]+m[5]+m[10]; let x,y,z,w;
  if (t>0){const s=Math.sqrt(t+1)*2; w=s/4; x=(m[6]-m[9])/s; y=(m[8]-m[2])/s; z=(m[1]-m[4])/s;}
  else if (m[0]>m[5]&&m[0]>m[10]){const s=Math.sqrt(1+m[0]-m[5]-m[10])*2; w=(m[6]-m[9])/s; x=s/4; y=(m[4]+m[1])/s; z=(m[8]+m[2])/s;}
  else if (m[5]>m[10]){const s=Math.sqrt(1+m[5]-m[0]-m[10])*2; w=(m[8]-m[2])/s; x=(m[4]+m[1])/s; y=s/4; z=(m[9]+m[6])/s;}
  else {const s=Math.sqrt(1+m[10]-m[0]-m[5])*2; w=(m[1]-m[4])/s; x=(m[8]+m[2])/s; y=(m[9]+m[6])/s; z=s/4;}
  const n=Math.hypot(x,y,z,w); return [x/n,y/n,z/n,w/n]; };
const qmul = (a,b) => [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1], a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0], a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3], a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
const byName = Object.fromEntries(joints.map((j, i) => [j.getName(), {node: j, bind: inv(Array.from(ibmA.slice(i*16, i*16+16)))}]));
const ibm = Array.from(ibmA);
for (const q of F.joints) {
  const bind = colMajor(q.bind); const p = byName[q.parent];
  const local = mul(inv(p.bind), bind);
  let r = quatFromMat(local); if (pose[q.name]) r = qmul(r, pose[q.name]);
  const n = doc.createNode(q.name).setTranslation([local[12], local[13], local[14]]).setRotation(r);
  p.node.addChild(n); skin.addJoint(n); byName[q.name] = {node: n, bind}; ibm.push(...inv(bind));
}
skin.setInverseBindMatrices(doc.createAccessor().setType("MAT4").setArray(new Float32Array(ibm)).setBuffer(buf));
const rd = (f, T) => { const b = fs.readFileSync(`${WD}/${f}`); return new T(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
const body = root.listMeshes()[0].listPrimitives()[0];
body.setAttribute("JOINTS_0", doc.createAccessor().setType("VEC4").setArray(rd("nf_j.bin", Uint16Array)).setBuffer(buf));
body.setAttribute("WEIGHTS_0", doc.createAccessor().setType("VEC4").setArray(rd("nf_w.bin", Float32Array)).setBuffer(buf));
await io.write(OUT, doc); console.log(OUT, skin.listJoints().length, "joints");
