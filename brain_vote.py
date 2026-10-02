"""The brain model decides what he clicks: each proposed action is tried out on a copy of the brain first.

An AI (eyes.py) only lists options, each tagged with the networks it would mostly drive ({group: 0..1}). Here:
1. the live brain's state is cloned (history buffer, stimulus, slow layer, random stream: Brain.clone);
2. every option's networks become a stimulus (weight x STIM_AMP x the sleep engine's gain) and all clones, plus one
   without any stimulus, are simulated for VOTE_S (300 ms) at once, with the same noise (common random numbers, so the
   differences come from the stimulus alone);
3. value = d_reward + 0.6 d_attention + 0.3 d_visual (videos only) - 0.8 d_fear, where d_x is the mean amplitude of
   group x relative to the clone without stimulus;
4. the values (scaled to the best one), the learned taste for the option's topics (tastes.py) and a small novelty bonus
   go through a softmax whose temperature rises with boredom and sleep pressure. Leaving (#29) is boredom- and
   taste-driven: the leave option gets LEAVE_BORED x boredom + LEAVE_CHAIN x the chain's pull (0 on the first page,
   1 after 30 pages in a row), and its taste term is the opposite of the taste for the page he is on (its topics are
   the page's), so a page whose topics have paid off holds him and one that has not lets him go;
5. the live brain then receives the chosen option's stimulus.
It is a rule on simulated activity, not understanding or liking: the model does not know what the page says.
"""
import math
import time

import numpy as np

from brain_sim import SLOW_DRIVE

VOTE_S = 0.3                 # simulated look-ahead per option
STIM_AMP = 8.0               # drive per unit network weight (a chat message drives 6-8 per rule)
MAX_OPTIONS = 6
VALUE = {"reward": 1.0, "attention": 0.6, "fear": -0.8}
VIDEO_VISUAL = 0.3
TASTE_W = 0.5                # weight of the learned preference next to the brain response (both ~[-1, 1])
NOVELTY = 0.3                # bonus for a link or search he has not done recently
LEAVE_BORED = 0.5            # leave bonus per unit boredom (0..1)
LEAVE_CHAIN = 0.6            # leave bonus at the end of a long chain of pages (eyes.leave_pull, 0..1)
VIDEO_ACTIONS = ("open_video", "play_video")
T0 = 0.15                    # softmax temperature when rested and not bored
NAMES = {"reward": "reward", "attention": "attention", "visual": "visual", "fear": "threat", "language": "language",
         "memory": "memory", "default": "default-mode", "salience": "salience", "somatomotor": "body-movement",
         "control": "control", "limbic": "limbic", "relay": "thalamic relay"}


def temperature(boredom=0.0, pressure=0.0, tired=0.0):
    """Softmax temperature: rises with boredom and with sleep pressure / sleep debt (choices get less decisive)."""
    sleepy = min(1.0, max(0.0, pressure)) + min(1.0, max(0.0, tired))
    return T0 * (1.0 + 1.5 * min(1.0, max(0.0, boredom))) * (1.0 + 1.5 * sleepy)


def stimulus_vector(brain, networks, gain):
    """{group: weight} -> per-region drive, exactly what brain.stimulate(group, w * STIM_AMP * gain) would add."""
    v = np.zeros(brain.n)
    for g, w in networks.items():
        idx = brain.group_idx.get(g)
        if idx:
            v[idx] += float(w) * STIM_AMP * gain
    return v


def simulate(clone, stims, seconds=VOTE_S):
    """Run len(stims) copies of `clone` side by side (one sparse product per step for all of them) with the same noise
    and slow drive; return each copy's mean amplitude per region over the window, shape (K, n). `clone` is not
    modified (its random stream and slow layer are copied again here)."""
    import copy
    b = clone
    n, hist, K = b.n, b.hist, len(stims)
    M, Ws = b.lag_coupling(), b.W.sum(1)
    H = np.empty((hist, n, K), complex)                          # H[d] = z(t - d)
    for d in range(hist):
        H[d] = b.buf[(b.t - d) % hist][:, None]
    stim = b.stim[:, None] + np.array(stims, float).T            # (n, K): what is already decaying + the option
    rng, slow = copy.deepcopy(b.rng), copy.deepcopy(b.slow) if b.slow_on else None
    slow_x, t, dt = b.slow_x.copy(), b.t, b.dt
    decay = math.exp(-dt / 2.0)
    acc = np.zeros((n, K))
    steps = int(round(seconds / dt))
    for _ in range(steps):
        z = H[0]
        coup = b.g * ((M @ H.reshape(hist * n, K)) - Ws[:, None] * z)
        if slow is not None and t % 100 == 0:
            slow_x = SLOW_DRIVE * b.slow_gain * np.clip(slow.advance(100 * dt)[b._slow_idx], -2.0, 3.0)
        a_eff = b.a + stim + (b.drive + slow_x + getattr(b, "neuromod", 0.0))[:, None]   # same terms as Brain.step
        local = np.exp((a_eff + 1j * b.omega[:, None] - np.abs(z) ** 2) * dt)
        noise = b.noise * math.sqrt(dt) * (rng.normal(size=n) + 1j * rng.normal(size=n))
        new = z * local + dt * coup + noise[:, None]
        H[1:] = H[:-1]
        H[0] = new
        t += 1
        stim *= decay
        acc += np.abs(new)
    return (acc / steps).T


def responses(brain, options, gain, seconds=VOTE_S):
    """Per option: {group: change in mean amplitude vs the clone without stimulus}."""
    stims = [np.zeros(brain.n)] + [stimulus_vector(brain, o["networks"], gain) for o in options]
    amp = simulate(brain, stims, seconds)
    groups = {g: i for g, i in brain.group_idx.items() if i}
    base = {g: float(amp[0, i].mean()) for g, i in groups.items()}
    return [{g: float(amp[k, i].mean()) - base[g] for g, i in groups.items()} for k in range(1, len(stims))]


def value(delta, video=False):
    v = sum(w * delta.get(g, 0.0) for g, w in VALUE.items())
    return v + (VIDEO_VISUAL * delta.get("visual", 0.0) if video else 0.0)


def vote(clone, options, gain=1.0, mood=None, tastes=None, novel=None, rng=None, seconds=VOTE_S):
    """Pick one option. `clone` = brain.clone() taken on the event loop; options = validated eyes.py options;
    mood = {boredom, pressure, tired}; tastes = [prediction in -1..1] per option; novel = [bool] per option.
    Returns the decision record (also what the page shows)."""
    t0 = time.perf_counter()
    options = list(options)[:MAX_OPTIONS]
    if not options:
        return None
    mood = mood or {}
    rng = rng or np.random.default_rng()
    tastes = list(tastes) if tastes is not None else [0.0] * len(options)
    novel = list(novel) if novel is not None else [False] * len(options)
    deltas = responses(clone, options, gain, seconds)
    vals = [value(d, o.get("action") in VIDEO_ACTIONS) for d, o in zip(deltas, options)]
    scale = max(abs(v) for v in vals)
    vn = [v / scale if scale > 1e-9 else 0.0 for v in vals]
    tastes = [-ts if o.get("action") == "leave" else ts for o, ts in zip(options, tastes)]
    leave = [leave_bonus(o, mood) for o in options]
    total = [v + TASTE_W * ts + (NOVELTY if nv else 0.0) + lv for v, ts, nv, lv in zip(vn, tastes, novel, leave)]
    T = temperature(mood.get("boredom", 0.0), mood.get("pressure", 0.0), mood.get("tired", 0.0))
    top = max(total)
    w = np.array([math.exp((x - top) / T) for x in total])
    p = w / w.sum()
    k = int(rng.choice(len(options), p=p))
    rows = [{"action": o["action"], "label": o["label"], "target": o.get("target"), "networks": o["networks"],
             "response": round(v, 5), "value": round(n_, 3), "taste": round(ts, 3), "novel": bool(nv),
             "p": round(float(pk), 3), "chosen": i == k}
            for i, (o, v, n_, ts, nv, pk) in enumerate(zip(options, vals, vn, tastes, novel, p))]
    for row, lv in zip(rows, leave):
        if row["action"] == "leave":
            row["leave_bonus"] = round(lv, 3)
    return {"options": rows, "chosen": k, "temperature": round(T, 3), "gain": round(gain, 3),
            "reason": reason(options, deltas, vals, total, k, mood, tastes),
            "ms": round((time.perf_counter() - t0) * 1000), "clones": len(options) + 1, "seconds": seconds}


def leave_bonus(option, mood):
    """Extra pull of the leave option: boredom, and the length of the chain of pages (eyes.leave_pull)."""
    if option.get("action") != "leave":
        return 0.0
    try:
        pull = float(option.get("pull") or 0.0)
    except (TypeError, ValueError):
        pull = 0.0
    pull = min(1.0, max(0.0, pull)) if pull == pull else 0.0
    return LEAVE_BORED * min(1.0, max(0.0, mood.get("boredom", 0.0))) + LEAVE_CHAIN * pull


def reason(options, deltas, vals, total, k, mood, tastes):
    if options[k].get("action") == "leave":
        bits = []
        if mood.get("boredom", 0.0) >= 0.5:
            bits.append("bored")
        if float(options[k].get("pull") or 0.0) >= 0.5:
            bits.append("a long chain of pages")
        if tastes[k] > 0.2:
            bits.append("this page's topics have not paid off")
        if bits:
            return "moved on: " + ", ".join(bits)
    d = deltas[k]
    up = sorted((g for g in ("reward", "attention", "visual") if d.get(g, 0.0) > 0), key=lambda g: -d[g])[:2]
    if up and vals[k] > 0:
        why = f"chose it: {' and '.join(NAMES[g] for g in up)} areas responded most"
    elif vals[k] >= max(vals):
        why = "chose it: it moved the threat area least"
    else:
        why = "chose it: no option stood out in the brain response"
    best = int(np.argmax(total))
    intensity = [sum(o["networks"].values()) for o in options]
    sleepy = mood.get("pressure", 0.0) >= 0.8 or mood.get("tired", 0.0) >= 0.5
    if k != best:
        if sleepy and intensity[k] < max(intensity):
            why += "; tired, so he picked the lighter option"
        elif sleepy or mood.get("boredom", 0.0) >= 0.6:
            why += f"; {'tired' if sleepy else 'bored'}, so a weaker option won"
        else:
            why += "; by chance, not the top-scoring option"
    elif tastes[k] > 0.3 and tastes[k] * TASTE_W > abs(vals[k] / (max(abs(v) for v in vals) or 1)):
        why += "; its topics have paid off before"
    return why


def apply(brain, option, gain):
    """The live brain receives the chosen option's stimulus (same scaling as the vote)."""
    for g, w in option["networks"].items():
        if brain.group_idx.get(g):
            brain.stimulate(g, float(w) * STIM_AMP * gain)
