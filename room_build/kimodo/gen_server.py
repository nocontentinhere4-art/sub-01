"""Kimodo generation server for the room clips: loads Kimodo-SOMA-RP-v1.1 once, then processes spec files dropped in
/workspace/queue (one JSON per clip, see specs/*.json) into /workspace/out/<name>/<seed>_<i>.npz.

Spec fields: name, prompts (list: sequential segments), durations (s, one per prompt), seeds (list), num_samples,
steps, cfg ([text, constraint]), heading (first heading angle, rad; 0 faces +Z), post (Kimodo's post-process),
constraints (Kimodo's constraints-JSON dicts: root2d, ...), ee (end-effector pins: each {frames, joints, targets
{joint: [[x,y,z] per frame]}, pose: "<name>/<file>.npz" (the take whose pose at those frames supplies the rest of the
chain and the rotations) or omitted (the targets alone, with the rotations of the closest frame of the same take)})."""
import glob, json, os, time, traceback
import numpy as np, torch
from kimodo import load_model
from kimodo.constraints import load_constraints_lst, EndEffectorConstraintSet
from kimodo.exports.motion_io import save_kimodo_npz
from kimodo.tools import seed_everything

Q, OUT = "/workspace/queue", "/workspace/out"
os.makedirs(Q, exist_ok=True); os.makedirs(OUT, exist_ok=True)
dev = "cuda:0"
t0 = time.time()
model = load_model("Kimodo-SOMA-RP-v1.1", device=dev, default_family="Kimodo")
sk30 = model.skeleton; sk77 = sk30.somaskel77; sl = sk30.get_skel_slice(sk77)
print(f"model loaded in {time.time() - t0:.0f} s, fps {model.fps}", flush=True)

def ee_constraints(spec):
    out = []
    for e in spec.get("ee", []):
        src = np.load(os.path.join(OUT, e["pose"]))
        fr = e["frames"]; sf = e.get("src_frames", fr)
        P = torch.tensor(src["posed_joints"][sf], dtype=torch.float32)        # [T,77,3]
        R = torch.tensor(src["global_rot_mats"][sf], dtype=torch.float32)     # [T,77,3,3]
        pl = e.get("place")
        if pl:                                                                   # the whole pose turned to heading `face` and moved to `root`
            li, ri = sk77.bone_index["LeftLeg"], sk77.bone_index["RightLeg"]
            for k in range(len(fr)):
                d = P[k, ri] - P[k, li]; h = torch.atan2(d[2], -d[0]); yaw = float(pl["face"][k] if isinstance(pl["face"], list) else pl["face"]) - float(h)
                cy_, sy_ = np.cos(yaw), np.sin(yaw); Ry = torch.tensor([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]], dtype=torch.float32)
                r0 = P[k, 0].clone(); P[k] = (P[k] - r0) @ Ry.T + torch.tensor(pl["root"][k] if isinstance(pl["root"][0], list) else pl["root"], dtype=torch.float32)
                R[k] = Ry @ R[k]
        for j, tg in e.get("targets", {}).items():                              # move the joint's chain (hand: the hand + fingers)
            ji = sk77.bone_index[j]; tg = torch.tensor(tg, dtype=torch.float32)
            d = tg - P[:, ji]
            kids = [k for k, n in enumerate(sk77.bone_order_names) if n.startswith(j)]   # LeftHand* / LeftFoot (+ toes below)
            if j.endswith("Foot"): kids += [sk77.bone_index[j.replace("Foot", "ToeBase")], sk77.bone_index[j.replace("Foot", "ToeEnd")]]
            for k in set(kids): P[:, k] += d
        for j, tg in e.get("rots", {}).items():                                 # optional global rotation override (3x3 per frame)
            R[:, sk77.bone_index[j]] = torch.tensor(tg, dtype=torch.float32)
        root = e.get("root")
        if root is not None:                                                     # optional hips position (moves only the hips joint)
            P[:, 0] = torch.tensor(root, dtype=torch.float32)
        c = EndEffectorConstraintSet(sk30, frame_indices=torch.tensor(fr), global_joints_positions=P[:, sl].to(dev),
                                     global_joints_rots=R[:, sl].to(dev), smooth_root_2d=None, joint_names=e["joints"])
        out.append(c)
    return out

def run(spec):
    name = spec["name"]; d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    texts = spec["prompts"]; nf = [int(round(s * model.fps)) for s in spec["durations"]]
    cons = load_constraints_lst(spec.get("constraints", []), sk30) if spec.get("constraints") else []
    cons += ee_constraints(spec)
    res = []
    for seed in spec.get("seeds", [0]):
        seed_everything(seed)
        kw = dict(num_denoising_steps=spec.get("steps", 100), num_samples=spec.get("num_samples", 1), multi_prompt=True,
                  constraint_lst=cons, post_processing=spec.get("post", True), return_numpy=True, num_transition_frames=spec.get("transition", 5))
        if spec.get("cfg"): kw.update(cfg_type="separated", cfg_weight=spec["cfg"])
        if spec.get("heading") == "ee0":                                         # the heading of the first pinned pose
            P0 = cons[-len(spec["ee"])].global_joints_positions[0]; hv = P0[sk30.bone_index["RightLeg"]] - P0[sk30.bone_index["LeftLeg"]]
            kw["first_heading_angle"] = torch.full((spec.get("num_samples", 1),), float(torch.atan2(hv[2], -hv[0])), device=dev)
        elif spec.get("heading") is not None: kw["first_heading_angle"] = torch.full((spec.get("num_samples", 1),), float(spec["heading"]), device=dev)
        t = time.time(); o = model(texts, nf, **kw)
        n = int(o["posed_joints"].shape[0])
        for i in range(n):
            single = {k: (v[i] if hasattr(v, "shape") and len(v.shape) > 0 and v.shape[0] == n else v) for k, v in o.items()}
            f = os.path.join(d, f"s{seed}_{i}.npz"); save_kimodo_npz(f, single); res.append(os.path.basename(f))
        print(f"{name} seed {seed}: {n} samples in {time.time() - t:.1f} s", flush=True)
    json.dump({"spec": spec, "files": res, "fps": model.fps}, open(os.path.join(d, "done.json"), "w"))

while True:
    for f in sorted(glob.glob(Q + "/*.json")):
        try:
            spec = json.load(open(f)); os.rename(f, f + ".running"); run(spec); os.rename(f + ".running", f + ".ok")
        except Exception:
            traceback.print_exc(); os.rename(f + ".running", f + ".err") if os.path.exists(f + ".running") else None
            open(f + ".errlog", "w").write(traceback.format_exc())
    time.sleep(1)
