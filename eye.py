"""The Eye: what SUB-01 "sees" — a persistent world built from chat, rendered through the brain's state.

- World: things people mention become objects in SUB-01's world. Each mention strengthens an object; objects
  fade with time (half-life WORLD_HALF_LIFE_H of simulated time) and are forgotten below a floor.
- Every frame, a small local language model turns (sleep stage, network activity, market mood, world, recent
  messages, REM replays) into a first-person scene description + one short "thought". A local image model
  renders the scene. Awake = clear and realistic, REM = surreal dream remix, NREM = near-dark.
- Everything is logged with its inputs ("why"), so each frame can be traced back to messages and state.

Images and thoughts are AI-generated from the model's state. They are not what the real person saw or thought.
"""
import json
import math
import re
import time
from pathlib import Path

WORLD_HALF_LIFE_H = 6.0            # simulated hours for an object's strength to halve
FORGET_BELOW = 0.15
MAX_OBJECTS = 40
LLM_ID = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
HOME = "a quiet dark laboratory room at night with one large window over a sleeping city"

SYSTEM = """You write the inner view of SUB-01, a simulated brain built from public MRI scans.
You receive its current state as JSON. Reply with JSON only:
{"new_objects": [...], "scene": "...", "thought": "..."}
- new_objects: up to 3 concrete, drawable things (nouns, 1-3 words, English) mentioned in recent_messages that are
  not already in world. Skip abstract words, people, brands, tickers, coins, money.
- new_objects must be words the messages actually used (translate to English), never things you invent.
- scene: one first-person view (max 45 words, English). Awake, it is always inside "home" (its persistent place)
  and contains the strongest world objects; in dreams, home melts into the replayed messages.
  Follow the style: awake = coherent, realistic, lighting from mood; rem = surreal dream mixing the replayed
  messages, impossible geometry; nrem = almost black, slow blurred shapes. Never draw people's faces, text,
  logos, violence, nudity or real persons.
- thought: one short inner line (max 16 words) in the language of the most recent message (Italian or English),
  reacting to what it sees. Never ask for money, never tell anyone to buy or sell, never claim to be human,
  conscious, or the real person the scans came from."""

STYLE = {
    "AWAKE": "first-person view, photoreal, cinematic, natural perspective, 35mm",
    "REM": "first-person dream, surreal, dreamlike, soft glow, impossible architecture, film grain",
    "NREM": "almost completely dark, slow blurred abstract shapes, deep blue and black, very low light",
}
BAD = re.compile(r"https?://|www\.|\$[a-z]{2,10}\b|[1-9A-HJ-NP-Za-km-z]{32,44}|0x[0-9a-f]{40}", re.I)


class World:
    def __init__(self, d=None):
        d = d or {}
        self.objects = d.get("objects", {})             # name -> {w, first, last, text}

    def strength(self, o, t):
        return o["w"] * 0.5 ** (max(0.0, t - o["last"]) / 3600 / WORLD_HALF_LIFE_H)

    def add(self, names, t, source_text):
        for n in names[:3]:
            n = re.sub(r"[^a-zA-ZÀ-ſ \-]", "", str(n)).strip().lower()[:30]
            if not n or BAD.search(n):
                continue
            o = self.objects.get(n)
            if o:
                o["w"] = self.strength(o, t) + 1.0
                o["last"] = t
            else:
                self.objects[n] = {"w": 1.0, "first": t, "last": t, "text": source_text[:120]}
        self.forget(t)

    def forget(self, t):
        live = {k: v for k, v in self.objects.items() if self.strength(v, t) >= FORGET_BELOW}
        keep = sorted(live, key=lambda k: -self.strength(live[k], t))[:MAX_OBJECTS]
        self.objects = {k: live[k] for k in keep}

    def top(self, t, k=6):
        items = sorted(self.objects.items(), key=lambda kv: -self.strength(kv[1], t))[:k]
        return [{"name": n, "strength": round(self.strength(o, t), 2)} for n, o in items]

    def to_dict(self):
        return {"objects": self.objects}


def mood(groups, stage, market):
    """Readable summary of the brain state that the language model conditions on."""
    g = groups or {}
    base = sum(g.values()) / max(1, len(g))

    def rel(k):
        return round(g.get(k, base) / max(base, 1e-6), 2)

    return {"stage": stage.lower(), "reward": rel("reward"), "fear": rel("fear"), "salience": rel("salience"),
            "attention": rel("attention"), "self": rel("default"), "language": rel("language"),
            "market": market}


class Eye:
    def __init__(self, out_dir, world_path, width=768, height=432, steps=8, quantize=4):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.world_path = Path(world_path)
        self.world = World(json.loads(self.world_path.read_text()) if self.world_path.exists() else None)
        self.size, self.steps, self.quantize = (width, height), steps, quantize
        self.heard = []                                  # recent accepted messages (text, t)
        self.absorbed = set()                            # messages already turned into world objects
        self.llm = self.tok = self.img = None
        self.log = self.out / "frames.jsonl"

    # called from the server whenever a chat message is accepted
    def hear(self, text, t):
        self.heard.append((text, t))
        self.heard = self.heard[-12:]

    def _load(self):
        if self.llm is None:
            from mlx_lm import load
            self.llm, self.tok = load(LLM_ID)
        if self.img is None:
            from mflux.models.common.resolution.config_resolution import ConfigResolution
            from mflux.models.z_image.variants.z_image import ZImage
            self.img = ZImage(model_config=ConfigResolution.resolve_restricted("z-image-turbo", "z-image-turbo",
                                                                               model_path=None),
                              quantize=self.quantize, model_path=None)

    def _ask(self, state):
        from mlx_lm import generate
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(state)}]
        prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        raw = generate(self.llm, self.tok, prompt=prompt, max_tokens=220)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            out = json.loads(m.group(0)) if m else {}
        except ValueError:
            out = {}
        scene = str(out.get("scene", ""))[:400]
        thought = str(out.get("thought", ""))[:140]
        if BAD.search(thought):
            thought = ""
        return out.get("new_objects") or [], scene, thought

    def step(self, t, stage, groups, market, replays, sim_hhmm):
        """One frame. Blocking (runs in a worker thread): returns the frame record."""
        self._load()
        recent = [x for x, ts in self.heard if t - ts < 3 * 3600][-5:]
        state = {"time": sim_hhmm, "home": HOME, **mood(groups, stage, market), "world": self.world.top(t),
                 "recent_messages": recent, "replayed_messages": replays[-4:]}
        new, scene, thought = self._ask(state)
        fresh = [x for x, ts in self.heard if t - ts < 3 * 3600 and x not in self.absorbed]
        if fresh:                                        # a message shapes the world once; objects must come from it
            words = set(re.findall(r"[a-z\u00C0-\u017F]{3,}", " ".join(fresh).lower()))
            keep = [n for n in new if set(re.findall(r"[a-z\u00C0-\u017F]{3,}", str(n).lower())) & words]
            self.world.add(keep, t, fresh[-1])
            self.absorbed.update(fresh)
        style = STYLE.get(stage, STYLE["AWAKE"])
        prompt = f"{scene or 'an empty quiet room'}. {style}. no text, no people"
        name = f"{int(time.time() * 1000)}.jpg"
        t0 = time.time()
        image = self.img.generate_image(seed=int(t) % 100000, prompt=prompt, width=self.size[0], height=self.size[1],
                                        num_inference_steps=self.steps, guidance=0.0)
        pil = getattr(image, "image", None) or image
        if stage == "NREM":                               # deep sleep: keep only a faint trace of the scene
            from PIL import ImageEnhance
            pil = ImageEnhance.Brightness(pil).enhance(0.25)
        pil.convert("RGB").save(self.out / name, quality=88)
        rec = {"t": sim_hhmm, "stage": stage, "img": f"/eye/{name}", "thought": thought, "scene": scene,
               "why": {"messages": recent, "replayed": replays[-4:], "world": self.world.top(t, 5),
                       "mood": {k: v for k, v in state.items() if k in ("reward", "fear", "salience", "market")}},
               "render_s": round(time.time() - t0, 1)}
        with self.log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        self.world_path.write_text(json.dumps(self.world.to_dict()))
        return rec


def market_mood(trades, window_s=120):
    """'pumping' / 'dumping' / 'calm' from the last few minutes of trades [(t, kind, usd)]."""
    now = time.time()
    recent = [(k, u) for ts, k, u in trades if now - ts < window_s]
    buy = sum(u for k, u in recent if k == "buy")
    sell = sum(u for k, u in recent if k == "sell")
    if buy + sell < 50:
        return "calm"
    r = (buy - sell) / (buy + sell)
    return "pumping" if r > 0.25 else "dumping" if r < -0.25 else "choppy"
