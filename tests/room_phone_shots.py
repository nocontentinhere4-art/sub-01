"""The camera's shots while he is on his phone, in every phone pose: does the frame show the phone and his face, or his back?

    python tests/room_phone_shots.py [--root CHECKOUT] [--out DIR]

Poses: on the edge of the bed (phone_sit at the bedside), on the desk chair (phone_sit at the desk), lying in bed
(phone_lie), standing in the middle of the room (phone_stand). For each pose, every shot the page cycles through on the
phone ("over", "face", "medium" where the page has them; main has one fixed phone shot) at 1280x800 and 390x844, the
camera placed where the shot puts it. Per frame (results.json):
  - dist: the camera's distance to his face (m);
  - face_clear / phone_clear: the line from the camera to his face / to the phone misses his own body (his skinned mesh;
    the head itself and the hand round the phone excepted) and both are inside the frame;
  - body: the share of the frame his body covers (his mesh drawn flat over a blue room, as tests/room_render_shots.py
    masks the cloth): a camera inside his back reads ~0.8.
A frame passes when the face and the phone are both clear, dist >= 0.8 and body < 0.45. --root renders another checkout (main, for
the before of a before/after); the sheet puts each frame's screenshot with its numbers.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import HUD_OFF, MASK_JS, Run   # noqa: E402

POSES = {                     # name -> JS that puts him there, on the phone
    "bed_edge": 'act("phone"); snap("bedside", "phone_sit");',
    "desk_chair": 'act("phone"); snap("desk", "phone_sit");',
    "in_bed": 'act("phone"); snap("bedlie", "phone_lie");',
    "standing": 'act("phone"); snap("middle", "phone_stand");',
}
SIZES = {"desktop": (1280, 800, False), "phone": (390, 844, True)}
SHOTS = ("over", "face", "medium")

MEASURE_JS = """() => {
  const hits = [], skinned = []; boy.traverse(o => { if (o.isMesh) skinned.push(o); });
  const head = new THREE.Vector3(); (bones.headfront || bones.Head || boy).getWorldPosition(head);
  const ph = new THREE.Vector3(); phone.getWorldPosition(ph);
  const cam = camera.position.clone(), ray = new THREE.Raycaster();
  const clear = (p, spare) => { const d = cam.distanceTo(p), dir = p.clone().sub(cam).normalize();
    ray.set(cam, dir); ray.near = 0.02; ray.far = Math.max(0.05, d - spare); return ray.intersectObjects(skinned, false).length === 0; };
  const inFrame = p => { const q = p.clone().project(camera); return Math.abs(q.x) < 0.95 && Math.abs(q.y) < 0.95 && q.z < 1; };
  return {dist: +cam.distanceTo(head).toFixed(3), face_clear: clear(head, 0.11) && inFrame(head),
          phone_clear: phone.visible && clear(ph, 0.07) && inFrame(ph), phone_visible: phone.visible,
          shot: window.CAM ? CAM.kind : "follow", ang: window.CAM ? CAM.ang : null};
}"""


def passes(m):
    # the phone and his face both in sight, the camera at least 0.8 m off his head, his body under 45 % of the frame
    return bool(m["face_clear"] and m["phone_clear"] and m["dist"] >= 0.8 and m["body"] < 0.45)


def body_share(pg):
    # his mesh flat over a blue room: the share of the frame that is not blue
    pg.evaluate(MASK_JS)
    shot = pg.screenshot(type="png", timeout=480000, animations="disabled")
    import io
    im = Image.open(io.BytesIO(shot)).convert("RGB").resize((160, 100))
    px = list(im.get_flattened_data()) if hasattr(im, 'get_flattened_data') else list(im.getdata())
    return round(sum(1 for r, g, b in px if not (b > 200 and r < 60 and g < 60)) / len(px), 3)


def frames(run, out, tag):
    res = {}
    for size, (w, h, mobile) in SIZES.items():
        ctx, pg, errors = run.page(w, h, 23, mobile)
        pg.add_style_tag(content=HUD_OFF)
        has_shots = pg.evaluate("() => !!window.setShot")
        for pose, js in POSES.items():
            for shot in (SHOTS if has_shots else ("follow",)):
                pg.evaluate(f"""() => {{ setHour(23); setStage("AWAKE"); setScreen("phone"); if (window.setShot) setShot({json.dumps(shot)});
                  {js} settle(); for (let i = 0; i < 20; i++) sim(0.05);
                  updateCameraGoal(); if (window.CAM) CAM.cut = false;
                  camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); controls.update(); sim(0.05); }}""")
                if has_shots and pg.evaluate("() => CAM.kind") != shot:
                    continue                                      # the page does not cycle this shot for this pose
                pg.wait_for_timeout(800)
                pg.evaluate("window.FREEZE = true; if (window.post) post.render(0.1); else renderer.render(scene, camera)")   # the loop stops: the screenshot takes this frame
                name = f"{tag}_{size}_{pose}_{shot}"
                pg.screenshot(path=str(out / f"{name}.png"), timeout=480000, animations="disabled")   # software GL: seconds a frame
                m = pg.evaluate(MEASURE_JS)
                m["body"] = body_share(pg)
                m["pass"] = passes(m)
                pg.evaluate("window.FREEZE = false")
                res[name] = m
                print(name, m, flush=True)
        if errors:
            res[f"{tag}_{size}_errors"] = errors[:5]
        ctx.close()
    return res


def sheet(out, res, tag, path):
    names = [k for k in res if k.startswith(tag + "_") and not k.endswith("_errors")]
    W, H, cols = 400, 250, 4
    rows = (len(names) + cols - 1) // cols
    im = Image.new("RGB", (cols * W, rows * (H + 40)), (24, 24, 26))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, n in enumerate(names):
        x, y = (i % cols) * W, (i // cols) * (H + 40)
        fr = Image.open(out / f"{n}.png").convert("RGB"); fr.thumbnail((W - 6, H - 6))
        im.paste(fr, (x + 3, y + 3))
        m = res[n]; m["pass"] = passes(m)
        col = (120, 220, 120) if m["pass"] else (240, 120, 100)
        d.text((x + 4, y + H + 2), n[len(tag) + 1:], fill=(220, 220, 220), font=font)
        d.text((x + 4, y + H + 19), f"{'PASS' if m['pass'] else 'FAIL'}  dist {m['dist']} m  face {'ok' if m['face_clear'] else 'hidden'}  "
               f"phone {'ok' if m['phone_clear'] else 'hidden'}  body {m['body']:.0%}", fill=col, font=font)
    im.save(path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="another checkout to render (main, for the before)")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--out", default="/tmp/room_phone_shots")
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--sheet-only", action="store_true", help="redraw the sheet from <tag>.json (no rendering)")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.sheet_only:
        res = json.loads((out / f"{args.tag}.json").read_text())
    else:
        with Run(port=args.port, root=args.root) as run:
            res = frames(run, out, args.tag)
    (out / f"{args.tag}.json").write_text(json.dumps(res, indent=1))
    for m in res.values():
        if isinstance(m, dict):
            m["pass"] = passes(m)
    sheet(out, res, args.tag, out / f"{args.tag}_sheet.jpg")
    bad = [k for k, m in res.items() if isinstance(m, dict) and not m["pass"]]
    print(json.dumps({"frames": len([k for k in res if not k.endswith('_errors')]), "fail": bad}))


if __name__ == "__main__":
    main()
