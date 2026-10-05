"""The new face in the room at 1:1: preview/room-mh's own page and locked shots, BEFORE | AFTER, 1280x800 each.

    python preview/face_g2/render_room.py [--branch origin/preview/room-mh] [--out preview/face_g2/room_sheet.jpg]

A scratch worktree of `--branch` is served by its own live_server.py (tests/room_render_shots.py's Run); this folder's
face.js and ../skin_eyes/{body,skin_eyes}.js and G2's face delta (preview/mh-motion 9612b7b) are copied into the
worktree's web/g6/ (scratch only: nothing is committed there). Each shot is room-mh's (tools/shots/room_mh.json: its
scene, its camera): rendered as the branch draws him today, then again after dressFace (applied once, in his rest pose)
with the blink held open. The frames are full size: what the page shows at 1280x800.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import HUD_OFF, Run   # noqa: E402

SHOTS = (0, 2)            # room_mh.json's shots: at the desk searching (keyboard and mouse), reading a book at the desk

DRESS_JS = """async () => {
  let skin = null; boy.traverse(o => { if (o.isSkinnedMesh && o.material && o.material.name === "skin") skin = o; });
  skin.skeleton.pose(); boy.updateMatrixWorld(true);                     // his rest pose: the face fitted upright
  const {dressFace} = await import("/g6/face_g2/face.js");
  const delta = (await (await fetch("/g6/face_g2/g2_face_delta.json")).json()).delta_gltf;
  const info = dressFace(THREE, boy, {delta});
  info.cornea.envMap = scene.environment; info.blink.set(0);
  window.__face = info; return {moved: info.shape.moved, brows: info.brows, lids: info.lidEdges};
}"""


def shot_js(s):
    c = s["cam"]
    return f"""() => {{ setHour({s.get('hour', 14)}); setStage("AWAKE");
      ({s['scene']})(); settle(); for (let i = 0; i < {int(20 * s.get('settle', 1.0)) + 20}; i++) sim(0.05);
      follow = false; camera.fov = {c['fov']}; camera.position.set(...{json.dumps(c['pos'])}); controls.target.set(...{json.dumps(c['target'])});
      camera.updateProjectionMatrix(); controls.update(); sim(0.05);
      window.FREEZE = true; if (window.post) post.render(0.1); else renderer.render(scene, camera); }}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="origin/preview/room-mh")
    ap.add_argument("--out", default=str(HERE / "room_sheet.jpg"))
    ap.add_argument("--port", type=int, default=8798)
    args = ap.parse_args()
    wt = Path(tempfile.mkdtemp(prefix="room-mh-")) / "wt"
    subprocess.run(["git", "worktree", "add", "-f", "--detach", str(wt), args.branch], cwd=ROOT, check=True, capture_output=True)
    try:
        g6 = wt / "web" / "g6"
        (g6 / "face_g2").mkdir(parents=True); (g6 / "skin_eyes").mkdir(parents=True)
        shutil.copy(HERE / "face.js", g6 / "face_g2")
        for f in ("body.js", "skin_eyes.js"):
            shutil.copy(HERE.parent / "skin_eyes" / f, g6 / "skin_eyes")
        (g6 / "face_g2" / "g2_face_delta.json").write_bytes(subprocess.run(
            ["git", "show", "9612b7b:room_build/mh/glb/boy_g2_face_delta.json"], cwd=ROOT, check=True, capture_output=True).stdout)
        shots = json.loads((wt / "tools/shots/room_mh.json").read_text())["shots"]
        frames = {}
        with Run(port=args.port, root=wt) as run:
            ctx, pg, errors = run.page(1280, 800, 14, False)
            pg.add_style_tag(content=HUD_OFF)
            pg.wait_for_function("() => !!(window.mh && window.boy)", timeout=240000, polling=1000)
            for side in ("before", "after"):
                if side == "after":
                    print("dressed", pg.evaluate(DRESS_JS), flush=True)
                for k in SHOTS:
                    pg.evaluate("window.FREEZE = false")
                    pg.evaluate(shot_js(shots[k]))
                    p = HERE.parent.parent / "tmp_room_frame.png"
                    pg.screenshot(path=str(p), timeout=480000, animations="disabled")
                    frames[(side, k)] = Image.open(p).convert("RGB"); p.unlink()
                    print(side, k, flush=True)
            print("errors", errors[:5], flush=True)
            ctx.close()
        W, H, PAD = 1280, 800, 12
        sheet = Image.new("RGB", (2 * W + 3 * PAD, len(SHOTS) * (H + 40 + PAD) + 40), (22, 22, 24))
        d = ImageDraw.Draw(sheet)
        try:
            fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
            f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except OSError:
            fb = f = ImageFont.load_default()
        d.text((PAD, 8), "BEFORE (room-mh today)", fill=(240, 140, 120), font=fb)
        d.text((2 * PAD + W, 8), "AFTER (the new face)", fill=(130, 220, 130), font=fb)
        for r, k in enumerate(SHOTS):
            y = 44 + r * (H + 40 + PAD)
            sheet.paste(frames[("before", k)], (PAD, y)); sheet.paste(frames[("after", k)], (2 * PAD + W, y))
            d.text((PAD + 4, y + H + 6), shots[k]["label"] + " (1280x800, 1:1)", fill=(220, 220, 220), font=f)
        sheet.save(args.out, quality=90)
        print(json.dumps({"out": args.out}))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)


if __name__ == "__main__":
    main()
