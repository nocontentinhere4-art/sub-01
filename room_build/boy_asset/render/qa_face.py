"""The visual QA suite's face close-up (tests/visual, #98 G8: scene "walking", 14:00, the "face" camera recipe) and the
walking scene itself at 1280, for the character PR's sheet:  python render/qa_face.py <outdir> <tag>
Runs G8's harness with its scene list cut down to that one scene and close-up, on whatever web/room/boy.glb is installed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.visual import harness as H, scenes as S   # noqa: E402

out, tag = Path(sys.argv[1]), sys.argv[2]
S.CORE_SHOTS = [("walking", 14, "1280")]
S.CLOSEUPS = {"face": S.CLOSEUPS["face"]}


class One(H.Harness):
    def flicker(self, *a, **k): pass
    def perf(self): pass


res = One(out / tag, full=False, cdn_cache=H.HERE / ".cdn_cache").run()
print("hard failures:", res["hard_failures"])
