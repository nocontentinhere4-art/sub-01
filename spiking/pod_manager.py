"""Schedules GPU sessions inside the Railway server process: start a pod, watch it, always delete it.

`SUB01_SESSIONS` = "daily 21:00-22:00 Asia/Tokyo" by default (several windows separated by ';'; the zone defaults
to Asia/Tokyo; a window may cross midnight); "off" disables. The manager also needs SUB01_POD_SECRET, a server URL
and RUNPOD_API_KEY (Railway env; never logged). Hard caps: SUB01_MAX_HOURS_PER_DAY (1.0), SUB01_MAX_SESSION_MIN
(60, counted from pod creation, boot included) and, in RunPodOps, SUB01_GPU_HOURS_CAP (8.0) over a rolling
SUB01_GPU_CAP_DAYS (7) window. Learned weights stay on the server's
/data volume (spiking/server.py), never on paid RunPod storage (pods have no volume).
Each session tests yesterday's items from half cues, stores today's chat messages and readings, sleeps (REM
replay) and tests again; Pong runs only with SUB01_PONG=1 (it has not learned so far), the K-armed choice task
(spiking/choice.py) only with SUB01_CHOICE=1.
A pod is deleted at session end, when the pod reports done, on any error, with no hello in 15 min, when the
stream is lost for more than 3 min, and at shutdown. Blocking RunPod calls run in a thread executor.
Never imports torch or spiking.net.
"""
import asyncio
import json
import secrets
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sleep import ROME, day_of
from spiking import podpack
from spiking.costs import CostLog
from spiking.runpod_ops import RunPodOps
from spiking.words import half_cue_ok
from state_io import load_json, save_json

DEFAULT_TZ = "Asia/Tokyo"
HELLO_TIMEOUT_S = 15 * 60
LOST_S = 3 * 60
STOP_LEAD_S = 90                    # ask the pod to wrap up (upload weights) this long before the deadline
MIN_MINUTES = 25                    # boot + build + one test cycle: a shorter session is not worth a pod
DEFAULT_SESSIONS = "daily 21:00-22:00 Asia/Tokyo"
OFF = ("off", "none", "0", "false", "disabled")
PHASES = ["recall_yesterday", "encode", "memory_test", "sleep", "memory_test", "free"]
PONG_PHASES = ["pong_train", "pong_exam"]                  # inserted after encode with SUB01_PONG=1
CHOICE_PHASES = ["choice_train", "choice_exam"]            # inserted after encode (and Pong) with SUB01_CHOICE=1
MAX_PER_SOURCE = 5
SOURCES = ("chat", "reading", "taught")
WINDOW = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")


class Schedule:
    """Daily windows [(start_min, end_min, tz)]; end <= start means the window ends the next day."""

    def __init__(self, windows=()):
        self.windows = list(windows)

    @classmethod
    def parse(cls, spec):
        out = []
        for part in (spec or "").split(";"):
            tz, span = DEFAULT_TZ, None
            for tok in part.split():
                m = WINDOW.match(tok)
                if m:
                    h1, m1, h2, m2 = map(int, m.groups())
                    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
                        raise ValueError(f"bad time in SUB01_SESSIONS: {tok}")
                    span = (h1 * 60 + m1, h2 * 60 + m2)
                elif tok.lower() != "daily":
                    try:
                        ZoneInfo(tok)
                    except (KeyError, ValueError, OSError):
                        raise ValueError(f"unknown token in SUB01_SESSIONS: {tok!r}") from None
                    tz = tok
            if span:
                out.append((span[0], span[1], tz))
            elif part.strip():
                raise ValueError(f"cannot parse session window: {part.strip()!r}")
        return cls(out)

    @property
    def enabled(self):
        return bool(self.windows)

    def next_session(self, now, skip=()):
        """(start, end) of the first window that has not ended yet (it may be running now), skipping `skip` starts."""
        best = None
        for a, b, tzname in self.windows:
            tz = ZoneInfo(tzname)
            today = now.astimezone(tz).date()
            for off in (-1, 0, 1):
                day = today + timedelta(days=off)
                start = datetime(day.year, day.month, day.day, a // 60, a % 60, tzinfo=tz)
                end = start + timedelta(minutes=(b - a) % 1440 or 1440)
                if end > now and start not in skip and (best is None or start < best[0]):
                    best = (start, end)
        return best


def next_session(now, spec):
    return Schedule.parse(spec).next_session(now)


def _today(memory, t, source):
    today = day_of(t)
    cand = [m for m in memory.items if m["t"] <= t and day_of(m["t"]) == today
            and m.get("source", "chat") == source]
    cand.sort(key=lambda m: memory.weight(m, t, None), reverse=True)
    return cand


def top_messages(memory, t, n=5):
    """Today's accepted chat messages (not readings) with the highest Memory.weight, as [{"text", "emotion"}]."""
    return [{"text": m["text"], "emotion": m["emotion"]} for m in _today(memory, t, "chat")[:n]]


def top_items(memory, t, n=MAX_PER_SOURCE):
    """The day's items for the GPU session: top n chat messages, top n readings (title + keywords, hashed like
    chat) and up to n words viewers taught it (those with two or more content words first, then the most replayed), as [{"text", "source", "item", "emotion"}]."""
    out = [{"text": m["text"], "source": "chat", "item": m["text"], "emotion": m["emotion"]}
           for m in _today(memory, t, "chat")[:n]]
    for m in _today(memory, t, "reading")[:n]:
        title = m.get("title") or m["text"]
        out.append({"text": " ".join([title] + list(m.get("keywords") or [])), "source": "reading", "item": title,
                    "emotion": m["emotion"]})
    taught = sorted(_today(memory, t, "taught"), key=lambda m: (half_cue_ok(m["text"]), m.get("replays", 0)),
                    reverse=True)           # testable from a half cue, then the most replayed; ties: Memory.weight
    out += [{"text": m["text"], "source": "taught", "item": m["text"], "emotion": m["emotion"]} for m in taught[:n]]
    return out


def item_source(src):
    return src if src in SOURCES else "chat"


def _utcnow():
    return datetime.now(timezone.utc)


class PodManager:
    def __init__(self, data_dir, server_url, secret, api=None, clock=None, get_messages=None, schedule=None,
                 ops=None, sleep=None, env=None, tick=5.0, get_items=None):
        env = os.environ if env is None else env
        self.dir = Path(data_dir) / "spiking"
        self.server_url, self.secret = (server_url or "").rstrip("/"), secret
        self.clock = clock or _utcnow
        self._sleep = sleep or asyncio.sleep
        self.tick = tick
        self.get_messages = get_messages or (lambda: [])
        self.get_items = get_items
        spec = env.get("SUB01_SESSIONS")
        spec = DEFAULT_SESSIONS if spec is None or not spec.strip() else spec
        self.schedule = schedule if schedule is not None else Schedule.parse("" if spec.strip().lower() in OFF else spec)
        self.max_hours_day = float(env.get("SUB01_MAX_HOURS_PER_DAY") or 1.0)
        self.max_session_min = float(env.get("SUB01_MAX_SESSION_MIN") or 60)
        self.pong = env.get("SUB01_PONG") == "1"
        self.choice = env.get("SUB01_CHOICE") == "1"
        # RunPod credentials: the Railway env var, or a proxy that injects them (sandbox), or an injected client
        self.has_key = bool(env.get("RUNPOD_API_KEY") or env.get("SUB01_RUNPOD_PROXY_AUTH") == "1"
                            or api is not None or ops is not None)
        self.log = CostLog(self.dir / "costs.jsonl")
        self.ops = ops or RunPodOps(api=api, log=self.log, hours_cap=float(env.get("SUB01_GPU_HOURS_CAP") or 8.0),
                                    cap_days=float(env.get("SUB01_GPU_CAP_DAYS") or 7))
        self.send_stop = None                  # async callable set by the server: forwards {"type":"stop"} to the pod
        self.current = None                    # state of the running session
        self.done_windows = set()
        self.last_result = None
        self._warned = False
        self._pack = None                      # injectable for tests: callable -> env dict

    # --- enablement ------------------------------------------------------------------
    def enabled(self):
        why = None
        if not self.schedule.enabled:
            why = "SUB01_SESSIONS is not set"
        elif not self.secret:
            why = "SUB01_POD_SECRET is not set"
        elif not self.server_url:
            why = "no server URL (SUB01_SERVER_URL)"
        elif not self.has_key:
            why = "RUNPOD_API_KEY is not set"
        if why and not self._warned:
            self._warned = True
            print(f"spiking pod manager disabled: {why}", flush=True)
        return why is None

    # --- callbacks from the websocket (server.py) -------------------------------------
    def on_hello(self, info=None):
        c = self.current
        if c:
            c["hello"], c["disconnected_at"], c["last_seen"] = True, None, self.clock()

    def on_state(self, state=None):
        c = self.current
        if c:
            c["last_seen"] = self.clock()
            if isinstance(state, dict):
                c["phase"] = state.get("phase", c.get("phase"))
                c["t_sim"] = state.get("t_sim", c.get("t_sim"))

    def on_done(self, msg=None):
        c = self.current
        if c:
            c["done"] = msg if isinstance(msg, dict) else {"ok": True}

    def on_disconnect(self):
        c = self.current
        if c and c.get("hello") and not c.get("disconnected_at"):
            c["disconnected_at"] = self.clock()

    # --- status ----------------------------------------------------------------------
    def status(self):
        c = self.current
        nxt = self.schedule.next_session(self.clock(), self.done_windows) if self.schedule.enabled else None
        live = bool(c and c.get("hello") and not c.get("disconnected_at"))
        sess = None
        if c:
            sess = {"session_id": c["session_id"], "started": c["started"].isoformat(),
                    "ends": c["deadline"].isoformat(), "phase": c.get("phase"), "t_sim": c.get("t_sim")}
        return {"live": live, "session": sess, "next_session": nxt[0].isoformat() if nxt else None,
                "spend": self.log.summary()}

    # --- the loop --------------------------------------------------------------------
    async def run(self):
        if not self.enabled():
            return
        loop = asyncio.get_running_loop()
        try:
            try:
                await loop.run_in_executor(None, self.ops.cleanup_ours, "startup recovery")
            except Exception as e:
                print(f"spiking startup recovery failed: {type(e).__name__}", flush=True)
            self._load_done()
            while True:
                nxt = self.schedule.next_session(self.clock(), self.done_windows)
                if nxt is None:
                    return
                start, end = nxt
                while self.clock() < start:
                    await self._sleep(min(30.0, max(1.0, (start - self.clock()).total_seconds())))
                self.done_windows.add(start)
                self._save()
                try:
                    self.last_result = await self.run_session(start, end)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_result = f"error: {type(e).__name__}"
                    if type(e).__name__ == "CapExceeded":
                        print(f"spiking: GPU-hour cap reached, sessions paused ({e})", flush=True)
                    else:
                        print("spiking session failed:", self.last_result, flush=True)   # no API bodies in logs
        finally:
            self.shutdown()

    def shutdown(self):
        """Blocking last resort: no pod of ours survives the manager."""
        try:
            self.ops.cleanup_ours("shutdown")
        except Exception as e:
            print(f"spiking shutdown cleanup failed: {type(e).__name__}", file=sys.stderr, flush=True)

    # --- one session -----------------------------------------------------------------
    def session_config(self, start, minutes, now):
        day = now.astimezone(ROME).date()
        try:
            if self.get_items is not None:
                raw = list(self.get_items() or [])
            else:
                raw = [dict(m, source="chat") for m in (self.get_messages() or [])]
        except Exception:
            raw = []
        items, n = [], {}
        for m in raw:
            src = item_source(m.get("source"))
            if m.get("text") and n.get(src, 0) < MAX_PER_SOURCE:
                n[src] = n.get(src, 0) + 1
                items.append({"text": str(m["text"]), "source": src, "item": str(m.get("item") or m["text"]),
                              "emotion": m.get("emotion", "neutral")})
        msgs = [{"text": it["text"], "emotion": it["emotion"]} for it in items if it["source"] == "chat"]
        max_min = max(5, int(minutes) - 15)                     # pod-side budget: boot (~5-10 min) is billed too
        phases = list(PHASES)
        if self.pong:
            phases[phases.index("encode") + 1:phases.index("encode") + 1] = PONG_PHASES
        if self.choice:
            at = phases.index("pong_exam") + 1 if self.pong else phases.index("encode") + 1
            phases[at:at] = CHOICE_PHASES
        return {"session_id": "s-" + start.astimezone(ROME).strftime("%Y%m%d-%H%M"), "day": day.isoformat(),
                "n_neurons": 1_000_000, "seed": 1, "max_minutes": max_min,      # fixed: same synapses every day
                "phases": phases, "pong_train_minutes": 20 if max_min >= 60 else max(3, max_min // 4),
                "messages": msgs, "items": items, "elapsed_days": self.elapsed_days(now), "validate": False}

    def elapsed_days(self, now):
        state = self.dir / "manager.json"
        try:
            last = datetime.fromisoformat(json.loads(state.read_text())["last_session_end"])
        except Exception:
            w = self.dir / "weights.npz"
            last = datetime.fromtimestamp(w.stat().st_mtime, timezone.utc) if w.exists() else None
        if last is None:
            return 1.0
        return round(max(0.0, (now - last).total_seconds() / 86400), 3)

    def _load_done(self):
        """Windows already used (kept across restarts so a crash loop cannot start a second pod in one window)."""
        try:
            for s in load_json(self.dir / "manager.json", {}).get("windows_done", []):
                self.done_windows.add(datetime.fromisoformat(s))
        except Exception:
            pass

    def _save(self, **updates):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            path = self.dir / "manager.json"
            state = load_json(path, {})
            state.update(updates, windows_done=[d.isoformat() for d in sorted(self.done_windows)[-10:]])
            save_json(path, state)                          # atomic: a torn file would forget windows_done
        except OSError:
            pass

    async def run_session(self, start, end):
        loop = asyncio.get_running_loop()
        now = self.clock()
        day_left = self.max_hours_day - self.log.hours_on(now.astimezone(ROME).date())
        minutes = min(self.max_session_min, (end - now).total_seconds() / 60, day_left * 60)
        if minutes < MIN_MINUTES:
            return f"skipped: only {minutes:.0f} min allowed (daily cap / window)"
        cfg = self.session_config(start, minutes, now)
        data = await loop.run_in_executor(None, self._pack or podpack.pack_bytes)
        token = secrets.token_hex(24)
        env = dict(podpack.boot_env(token), SUB01_SESSION=json.dumps(cfg), SUB01_SERVER_URL=self.server_url,
                   SUB01_POD_SECRET=self.secret, SUB01_SESSION_ID=cfg["session_id"])
        t_create = self.clock()                                  # billed from here: boot counts against the hour
        pod = await loop.run_in_executor(None, self.ops.create, env, "session", "spiking.session", minutes)
        pod_id = pod["id"]
        try:                                                     # code + data go up after boot (create body < 100 KB)
            await loop.run_in_executor(None, self.ops.upload, pod_id, data, token)
        except BaseException:
            await self._delete(pod_id, "pack upload failed")
            raise
        t0 = self.clock()
        self.current = {"session_id": cfg["session_id"], "pod_id": pod_id, "started": t0, "hello": False,
                        "last_seen": t0, "disconnected_at": None, "done": None,
                        "deadline": t_create + timedelta(minutes=minutes)}
        print(f"spiking session {cfg['session_id']} started ({minutes:.0f} min max)", flush=True)
        reason = "error"
        try:
            reason = await self._watch(t0, self.current)
        finally:
            await self._delete(pod_id, reason)
            self._save(last_session_end=self.clock().isoformat())
            self.current = None
        return reason

    async def _watch(self, t0, c):
        """Poll until a stop condition; returns the reason the pod is deleted."""
        stop_sent = False
        while True:
            now = self.clock()
            if c["done"] is not None:
                ok = c["done"].get("ok", True)
                return "done" if ok else f"done with error: {str(c['done'].get('error'))[:120]}"
            if now >= c["deadline"]:
                return "session end"
            if not c["hello"] and (now - t0).total_seconds() > HELLO_TIMEOUT_S:
                return "no hello within 15 min"
            if c["hello"]:
                gap = now - (c["disconnected_at"] or c["last_seen"])
                if gap.total_seconds() > LOST_S:
                    return "stream lost"
            if not stop_sent and c["hello"] and (c["deadline"] - now).total_seconds() <= STOP_LEAD_S:
                stop_sent = True
                if self.send_stop:
                    try:
                        await self.send_stop()
                    except Exception:
                        pass
            await self._sleep(self.tick)

    async def _delete(self, pod_id, reason):
        """Delete in the executor; if that is cancelled or fails, retry blocking so the pod never survives."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self.ops.delete, pod_id, reason)
            return
        except BaseException as e:
            err = e
        try:
            self.ops.delete(pod_id, reason)
        except Exception as e2:
            print(f"spiking: could not delete pod {pod_id}: {type(e2).__name__}", file=sys.stderr, flush=True)
        if isinstance(err, asyncio.CancelledError):
            raise err


def from_env(data_dir, get_messages=None, get_items=None):
    """Manager configured from the Railway environment (server URL from SUB01_SERVER_URL or the Railway domain)."""
    url = os.environ.get("SUB01_SERVER_URL", "")
    if not url and os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        url = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"]
    return PodManager(data_dir, url, os.environ.get("SUB01_POD_SECRET", ""), get_messages=get_messages,
                      get_items=get_items)
