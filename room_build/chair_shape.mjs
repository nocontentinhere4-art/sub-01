// The desk chair of the room upgrade (preview/room-upgrade) as signed distance fields, one per material part, in the frame
// of the room's chair node (web/room.html CHAIR: its pivot on the floor under the gas lift, y up, the sitter facing -z):
// a generic ergonomic office chair, no maker's design or logo. The seat cushion's top is 0.52 m over the floor where he
// sits (G2's seated clips sit on a 0.52 m seat), 0.50 m wide and 0.48 m deep, with a waterfall front and rolled sides;
// a mesh backrest in a plastic frame whose front follows the line of his back in the seated clips (measured: the furthest
// back his skin goes at each height, plus ~1 cm), so he leans on it without going into it; T-armrests, a five-star base
// on twin-wheel casters (0.33 m to the wheels: the page's CHAIR_FOOT), a gas lift with a chrome piston. build_chair.mjs
// meshes these; tests/visual/contacts.py checks his skin against the meshes in every seated clip.
import { sdRoundBox, sdRoundCone, smin, smax } from "./sdf_mesh.mjs";

export const SEAT_Y = 0.52;
const clamp01 = t => Math.max(0, Math.min(1, t)), sstep = t => { t = clamp01(t); return t * t * (3 - 2 * t); };
const sdRoundRect = (x, z, hx, hz, r) => { const qx = Math.abs(x) - hx + r, qz = Math.abs(z) - hz + r;
  return Math.hypot(Math.max(qx, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qz), 0) - r; };
const lerpPts = (pts, y) => { if (y <= pts[0][0]) return pts[0][1]; for (let i = 1; i < pts.length; i++) if (y <= pts[i][0]) {
  const [y0, z0] = pts[i - 1], [y1, z1] = pts[i], t = (y - y0) / (y1 - y0), s = t * t * (3 - 2 * t); return z0 + (z1 - z0) * s; } return pts[pts.length - 1][1]; };

// ---- the seat: a cushion on a plastic pan
const SEAT = {hx: 0.25, z0: -0.24, z1: 0.22, under: 0.447};
export function seatTop(x, z) {                          // the cushion's top: 0.52 where he sits, rolling off at the edges
  let y = SEAT_Y;
  y -= 0.009 * sstep((0.0 - z) / 0.09);                      // the thighs' part a touch lower than under him
  y -= 0.044 * Math.pow(sstep((-0.08 - z) / 0.16), 1.4);  // the waterfall front
  y -= 0.034 * Math.pow(clamp01((Math.abs(x) - 0.165) / 0.085), 2);   // the rolled sides
  y -= 0.03 * clamp01((Math.abs(x) - 0.14) / 0.10) * sstep((-0.09 - z) / 0.12);   // softer front corners (his calves, rising)
  y -= 0.012 * Math.pow(clamp01((z - 0.15) / 0.07), 2);   // and a little at the back, under the backrest
  return y;
}
const seatC = (z0, z1) => (z0 + z1) / 2, seatH = (z0, z1) => (z1 - z0) / 2;
export function cushion(x, y, z) {
  const d2 = sdRoundRect(x, z - seatC(SEAT.z0, SEAT.z1), SEAT.hx, seatH(SEAT.z0, SEAT.z1), 0.095);
  const under = SEAT.under + 0.03 * sstep((-0.14 - z) / 0.09);              // (its front's underside chamfered up: his calves)
  return smax(smax(d2, y - seatTop(x, z), 0.014), under - y, 0.006);
}
function pan(x, y, z) {                                    // the seat's plastic pan, and the mechanism under it with its lever
  let d = sdRoundBox(x, y - 0.433, z - 0.035, 0.225, 0.016, 0.18, 0.03);       // (set back from the front edge)
  d = Math.min(d, sdRoundBox(x, y - 0.398, z - 0.01, 0.105, 0.022, 0.13, 0.008));
  d = Math.min(d, sdRoundBox(x - 0.165, y - 0.392, z + 0.005, 0.06, 0.005, 0.012, 0.004));        // the tilt lever (right)
  d = Math.min(d, sdRoundBox(x - 0.222, y - 0.392, z + 0.005, 0.02, 0.011, 0.017, 0.008));        // its paddle
  return d;
}
// ---- the backrest: a plastic frame round a mesh panel; its front follows his back
const BACK_FRONT = [[0.585, 0.172], [0.66, 0.128], [0.76, 0.118], [0.84, 0.142], [0.88, 0.186], [0.92, 0.226], [0.96, 0.256],
  [1.00, 0.268], [1.06, 0.284], [1.10, 0.298], [1.14, 0.322], [1.17, 0.338]];   // (its top leans back: his head, stretching)
export const backFront = (x, y) => lerpPts(BACK_FRONT, y) - 0.022 * (x / 0.22) ** 2;   // (its sides come round him a little)
const BACK = {y0: 0.585, y1: 1.115, t: 0.026};
const backHalfW = y => 0.205 + 0.025 * Math.sin(Math.PI * clamp01((y - BACK.y0) / (BACK.y1 - BACK.y0)) * 0.9 + 0.15);
function backOutline(x, y, inset) {                       // 2D (x, y) rounded outline of the backrest, inset inwards
  const hw = backHalfW(y) - inset, cy = (BACK.y0 + BACK.y1) / 2, hh = (BACK.y1 - BACK.y0) / 2 - inset;
  const qx = Math.abs(x) - hw + 0.06, qy = Math.abs(y - cy) - hh + 0.06;
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - 0.06;
}
function backFrame(x, y, z) {
  const zf = backFront(x, y), slab = Math.max(zf - z, z - (zf + BACK.t));
  const ring = smax(backOutline(x, y, 0), -backOutline(x, y, 0.028), 0.004);
  return smax(slab, ring, 0.006);
}
function backMesh(x, y, z) {                              // the mesh panel, 5 mm behind the frame's front
  const zf = backFront(x, y) + 0.005, slab = Math.max(zf - z, z - (zf + 0.010));
  return Math.max(slab, backOutline(x, y, 0.022));
}
function spine(x, y, z) {                                  // the bar from the mechanism up behind the backrest
  const top = [0, 0.70, backFront(0, 0.70) + BACK.t + 0.012];
  const pts = [[0, 0.405, 0.11], [0, 0.42, 0.235], [0, 0.52, 0.275], top];
  let d = 9;
  for (let i = 0; i + 1 < pts.length; i++) for (const s of [-1, 1]) {
    const a = [pts[i][0] + s * 0.011, pts[i][1], pts[i][2]], b = [pts[i + 1][0] + s * 0.011, pts[i + 1][1], pts[i + 1][2]];
    d = smin(d, sdRoundCone([x, y, z], a, b, 0.015, 0.015), 0.02); }
  d = Math.min(d, sdRoundBox(x, y - top[1] - 0.02, z - top[2] + 0.004, 0.07, 0.045, 0.006, 0.006));   // its plate on the back
  return d;
}
// ---- the armrests: a bracket under the seat, a post, a pad
export const ARM = {x: 0.296, pad_y: 0.700, pad_z0: -0.055, pad_z1: 0.150, post_z: 0.045};
function arms(x, y, z) {
  const s = Math.sign(x) || 1, ax = Math.abs(x);
  let d = sdRoundBox(ax - 0.205, y - 0.410, z - ARM.post_z, 0.095, 0.009, 0.026, 0.006);                    // bracket
  d = smin(d, sdRoundBox(ax - ARM.x, y - 0.545, z - ARM.post_z, 0.014, 0.135, 0.024, 0.009), 0.01);          // post
  const pc = (ARM.pad_z0 + ARM.pad_z1) / 2, ph = (ARM.pad_z1 - ARM.pad_z0) / 2;
  d = smin(d, sdRoundBox(ax - ARM.x, y - (ARM.pad_y - 0.012), z - pc, 0.034, 0.012, ph, 0.011), 0.008);      // pad
  return d + 0 * s;
}
// ---- the gas lift, the base, the casters
function lift(x, y, z) {
  const r = Math.hypot(x, z);
  const shroud = Math.max(r - 0.031, Math.max(0.10 - y, y - 0.305));
  return smin(shroud, Math.max(r - 0.033, Math.abs(y - 0.30) - 0.006), 0.004);    // (a lip at its top)
}
function piston(x, y, z) { return Math.max(Math.hypot(x, z) - 0.0145, Math.max(0.29 - y, y - 0.385)); }
export const LEGS = 5, LEG_R = +(process.env.LEG_R || 0.280), WHEEL_R = 0.024, LEG_OFF = +(process.env.LEG_OFF || 0.20);
const legAngle = k => -Math.PI / 2 + LEG_OFF + k * 2 * Math.PI / LEGS;      // (turned 11.5 deg off straight forward: his feet,
                                                                                   // getting up, sweep the front; this leaves them most room)
function base(x, y, z) {
  const r = Math.hypot(x, z);
  let d = Math.max(r - 0.046, Math.max(0.072 - y, y - 0.128)) ;                                 // the hub
  d = smax(d, Math.hypot(r, y - 0.13) - 0.06, 0.01);
  for (let k = 0; k < LEGS; k++) {
    const a = legAngle(k), u = x * Math.cos(a) + z * Math.sin(a), t = -x * Math.sin(a) + z * Math.cos(a);
    const f = clamp01(u / LEG_R), hw = 0.024 - 0.008 * f, top = 0.122 - 0.032 * f, bot = 0.082 - 0.016 * f;
    const leg = Math.max(Math.abs(t) - hw, Math.max(y - top, bot - y), Math.max(-u, u - LEG_R - 0.012));
    d = smin(d, leg, 0.012);
    d = smin(d, Math.max(Math.hypot(u - LEG_R, t) - 0.017, Math.max(0.052 - y, y - (bot + 0.012))), 0.006);   // the caster's socket
  }
  return d;
}
function casters(x, y, z) {
  let d = 9;
  for (let k = 0; k < LEGS; k++) {
    const a = legAngle(k), u = x * Math.cos(a) + z * Math.sin(a), t = -x * Math.sin(a) + z * Math.cos(a);
    const uc = LEG_R + 0.016;                                                                   // (the wheels trail outwards)
    const hood = smax(Math.hypot(u - uc, y - WHEEL_R) - WHEEL_R - 0.006, Math.max(Math.abs(t) - 0.02, WHEEL_R - 0.003 - y), 0.004);
    d = Math.min(d, hood);
    d = Math.min(d, sdRoundBox(u - (LEG_R + 0.004), y - 0.052, t, 0.012, 0.008, 0.012, 0.005));          // the swivel
    for (const s of [-1, 1]) d = Math.min(d, Math.max(Math.hypot(u - uc, y - WHEEL_R) - WHEEL_R, Math.abs(t - s * 0.0125) - 0.0085));
  }
  return d;
}
// the parts, with their material and the box to mesh them in (step: the surface nets' cell)
export const PARTS = {
  cushion: {f: cushion, mat: "chair_fabric", lo: [-0.27, 0.43, -0.26], hi: [0.27, 0.54, 0.24], step: 0.004},
  pan: {f: pan, mat: "chair_plastic", lo: [-0.27, 0.36, -0.25], hi: [0.27, 0.46, 0.25], step: 0.004},
  back_frame: {f: backFrame, mat: "chair_plastic", lo: [-0.25, 0.57, 0.08], hi: [0.25, 1.18, 0.38], step: 0.004},
  back_mesh: {f: backMesh, mat: "chair_mesh", lo: [-0.24, 0.59, 0.09], hi: [0.24, 1.16, 0.37], step: 0.003},
  spine: {f: spine, mat: "chair_plastic", lo: [-0.09, 0.38, 0.08], hi: [0.09, 0.78, 0.36], step: 0.004},
  arms: {f: arms, mat: "chair_plastic", lo: [-0.34, 0.39, -0.08], hi: [0.34, 0.72, 0.18], step: 0.004},
  lift: {f: lift, mat: "chair_plastic", lo: [-0.04, 0.09, -0.04], hi: [0.04, 0.32, 0.04], step: 0.003},
  piston: {f: piston, mat: "chair_chrome", lo: [-0.02, 0.28, -0.02], hi: [0.02, 0.39, 0.02], step: 0.002},
  base: {f: base, mat: "chair_plastic", lo: [-0.33, 0.04, -0.33], hi: [0.33, 0.20, 0.33], step: 0.004},
  casters: {f: casters, mat: "chair_rubber", lo: [-0.36, -0.002, -0.36], hi: [0.36, 0.07, 0.36], step: 0.0025},
};
export const chairSDF = (x, y, z) => Math.min(...Object.values(PARTS).map(p => p.f(x, y, z)));
