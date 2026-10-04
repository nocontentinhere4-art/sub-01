"""Fit and score the encoding models (docs/encoding/REPORT.md) and write the runtime weights for sensory.py.

Two models, each from public fMRI with commercially usable stimuli:
  vision: Emo-FilM (ds004892), 3 Blender films (CC BY), up to 30 participants, TR 1.3 s;
          features = CLIP image embedding (512) + luminance, contrast, change (3), 2 frames/s averaged per TR.
  text:   Alice (ds002322), one public-domain story, 23 participants with preprocessed data, TR 2 s;
          features = MiniLM embedding of the last 8 s of words (384) + nuisance: word rate, audio envelope (2).
Model: ridge regression from the features at HRF delays (vision 1.3-7.8 s, text 2-10 s) to each region's BOLD,
one penalty per region chosen by inner cross-validation on the training data only.

Cross-validation, by stimulus AND by participant: the participants are split in two halves (A = even, B = odd in
sorted order); each fold trains on one half's average response to the training stimuli and is scored on the OTHER
half's average response to the held-out stimulus (vision: leave one film out; text: leave one of 4 contiguous
quarters of the story out, with 5 TRs dropped on each side of it from training). 6 + 8 folds.
Noise ceiling: the split-half correlation of the two halves' averages on the same stimulus, sqrt'ed (the r a perfect
stimulus model could reach against one half's average).
Controls: (1) shuffled features (blocks of 10 TRs permuted, train and test); (2) time-shifted stimulus (the held-out
stimulus' features rolled by half its length). Significance: the held-out r against the held-out r of 10 models
fitted and tested on block-shuffled features (pooled over regions), Benjamini-Hochberg q < 0.05 over the 214 regions.

Runtime weights (out/encoding/{vision,text}.npz): refit on all stimuli x all participants with the median of the
folds' penalties; the delays are summed (the response to a sustained picture), and each region is weighted by its
held-out r (0 when not significant). The text model's runtime part is the semantic one (nuisance held at its mean),
so its weights come from that part's held-out score.

Run:   python analysis/encoding/fit.py            (needs out/encoding_work/ from extract_*.py and features_*.py)
Check: python analysis/encoding/fit.py --check    (re-scores from the committed out/encoding/cv_data.npz and compares
       with out/encoding/scores.json; tests/test_sensory.py runs it)
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, WORK, names214  # noqa: E402

ALPHAS = np.logspace(0, 6, 13)
N_SHUFFLES = 10
FEATURE_CLIP = 3.0        # = sensory.FEATURE_CLIP: inputs past 3 SD of the training stimuli are held there
SEED = 0
CFG = {
    "vision": {"tr": 1.3, "lags": list(range(1, 7)), "skip": 8, "runtime_zero": []},
    "text": {"tr": 2.0, "lags": list(range(1, 6)), "skip": 4, "runtime_zero": ["words", "envelope"]},
}


# --- data -> cv_data.npz -------------------------------------------------------------------------------------------
def zs(x):
    x = np.asarray(x, np.float64)
    s = x.std(0)
    return (x - x.mean(0)) / np.where(s > 0, s, 1.0)


def halves(subs):
    subs = sorted(subs)
    return subs[0::2], subs[1::2]


def build_vision():
    """Per film: features on the film's TR grid and the BOLD of each participant interpolated onto it (z-scored)."""
    films = ["BigBuckBunny", "Sintel", "TearsOfSteel"]
    tr = CFG["vision"]["tr"]
    out = {"stimuli": films}
    subj = {}
    for f in films:
        fz = np.load(WORK / "features" / f"{f}.npz")
        n = int(fz["t"][-1] // tr)
        g = (np.arange(n) + 0.5) * tr                               # TR-bin centres in film time
        X = np.zeros((n, 515))
        for j in range(n):
            m = (fz["t"] >= j * tr) & (fz["t"] < (j + 1) * tr)
            X[j] = np.concatenate([fz["emb"][m].mean(0), fz["ll"][m].mean(0)])
        out[f"X_{f}"] = X
        for p in sorted(glob.glob(str(WORK / "emofilm" / f"*_{f}.npz"))):
            z = np.load(p)
            ts = z["ts"].astype(np.float64)
            if np.isnan(ts).any():
                continue
            t_bold = (np.arange(len(ts)) + 0.5) * float(z["tr"]) - float(z["onset_s"])   # film time of each volume
            if t_bold[-1] < g[-1]:
                continue
            Y = np.stack([np.interp(g, t_bold, ts[:, r]) for r in range(214)], 1)
            subj.setdefault(Path(p).name.split("_")[0], {})[f] = zs(Y)
    subs = sorted(s for s, d in subj.items() if all(f in d for f in films))   # only those who saw all three
    return out, subj, subs


ALICE_DROPPED = 2      # preprocessed volumes missing at the start (see build_text); not the README's 10
ALICE_HEAD = 4         # the first preprocessed volumes are a filter-edge transient (z ~ 18): not used


def build_text(dropped=None):
    """The preprocessed runs have 372 volumes, the raw ones 374 (748 s = the audio): the README's "first 10 volumes
    discarded" does not fit them. The offset was chosen once by the held-out score of the full model over 0, 1, 2, 3
    and 10 dropped volumes (REPORT.md); 2 also fits the speech-onset response of the temporal cortex (volume ~12)."""
    dropped = ALICE_DROPPED if dropped is None else dropped
    fz = np.load(WORK / "features" / "alice.npz")
    g = fz["g"]
    n = len(g)
    X = np.concatenate([fz["emb"], fz["nuis"]], 1)
    subj = {}
    for p in sorted(glob.glob(str(WORK / "alice" / "*.npz"))):
        z = np.load(p)
        ts = z["ts"].astype(np.float64)
        if np.isnan(ts).any():
            continue
        onset = 10 * float(z["tr"]) - float(z["t0_s"])                                  # the audio's onset in the scan
        t_bold = dropped * float(z["tr"]) - onset + float(z["tr"]) * (np.arange(len(ts)) + 0.5)   # audio time
        ts, t_bold = ts[ALICE_HEAD:], t_bold[ALICE_HEAD:]
        Y = np.stack([np.interp(g + 1.0, t_bold, ts[:, r]) for r in range(214)], 1)
        subj[Path(p).stem] = {"alice": zs(Y)}
    # the one story is cut into 4 contiguous quarters: they are the held-out "stimuli"
    q = np.array_split(np.arange(n), 4)
    out = {"stimuli": [f"alice_q{i + 1}" for i in range(4)], "X_alice": X,
           "quarters": np.concatenate([[i] * len(x) for i, x in enumerate(q)])}
    return out, subj, sorted(subj)


def group(subj, subs, key):
    return zs(np.mean([subj[s][key] for s in subs], 0))


def build(kind, **kw):
    data, subj, subs = build_vision() if kind == "vision" else build_text(**kw)
    a, b = halves(subs)
    keys = data["stimuli"] if kind == "vision" else ["alice"]
    for k in keys:
        # float16 storage: the check (and this fit) use exactly the stored values
        data[f"A_{k}"] = group(subj, a, k).astype(np.float16)
        data[f"B_{k}"] = group(subj, b, k).astype(np.float16)
        data[f"all_{k}"] = group(subj, subs, k).astype(np.float16)
    data["n_subjects"] = len(subs)
    return data, subj, subs


# --- ridge -----------------------------------------------------------------------------------------------------------
def lagged(X, lags):
    T = len(X)
    out = np.zeros((T, X.shape[1] * len(lags)))
    for i, l in enumerate(lags):
        out[l:, i * X.shape[1]:(i + 1) * X.shape[1]] = X[:T - l]
    return out


def corr(a, b):
    a = a - a.mean(0)
    b = b - b.mean(0)
    return (a * b).sum(0) / np.sqrt((a * a).sum(0) * (b * b).sum(0) + 1e-12)


def ridge_path(X, Y, alphas):
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    UtY = U.T @ Y
    return [(Vt.T * (S / (S ** 2 + a))) @ UtY for a in alphas]


def fit_ridge(X, Y, chunks, alphas=ALPHAS):
    """Per-region penalty by leave-one-chunk-out inside the training rows (`chunks`: chunk id per row), then the fit
    on all training rows. Returns (W, log10 alpha per region)."""
    score = np.zeros((len(alphas), Y.shape[1]))
    for c in np.unique(chunks):
        tr, va = chunks != c, chunks == c
        for i, W in enumerate(ridge_path(X[tr], Y[tr], alphas)):
            score[i] += corr(X[va] @ W, Y[va])
    best = score.argmax(0)
    path = ridge_path(X, Y, alphas)
    W = np.stack([path[best[r]][:, r] for r in range(Y.shape[1])], 1)
    return W, np.log10(alphas[best])


def block_shuffle(X, rng, block=10):
    idx = np.arange(len(X))
    blocks = [idx[i:i + block] for i in range(0, len(X), block)]
    rng.shuffle(blocks)
    return X[np.concatenate(blocks)]




# --- folds -----------------------------------------------------------------------------------------------------------
def segments(kind, data):
    """[(held-out stimulus id, its feature matrix, its target key, its rows)]."""
    if kind == "vision":
        return [(f, data[f"X_{f}"], f, np.arange(len(data[f"X_{f}"]))) for f in data["stimuli"]]
    q = data["quarters"]
    return [(f"alice_q{i + 1}", data["X_alice"], "alice", np.where(q == i)[0]) for i in range(4)]


def design(kind, X, mu, sd, zero=None):
    f = (X - mu) / sd
    if zero is not None and zero.any():
        f = f.copy()
        f[:, zero] = 0.0
    return lagged(f, CFG[kind]["lags"])


def usable(kind, rows):
    """Rows scored / fitted: the first `skip` TRs of each film (onset transient) or of the story are left out."""
    skip = CFG[kind]["skip"]
    return rows[skip:] if kind == "vision" else rows[rows >= skip]


def run_folds(kind, data, mode="real", rng=None, fit_mask=None, test_mask=None):
    """Held-out predictions, one per (held-out stimulus, training half). mode: real | shuffled (blocks of 10 TRs
    permuted in the training and the test features) | shifted (the held-out stimulus' features rolled by half its
    length). fit_mask: the features the model may use (others zeroed in training and test); test_mask: the features
    kept at test time (others at their training mean): the text model's runtime (semantic) part."""
    segs = segments(kind, data)
    D_ = None if fit_mask is None else ~fit_mask
    out = []
    for ti, (sid, Xs, key, rows) in enumerate(segs):
        train = []
        for si, (_, X2, key2, rows2) in enumerate(segs):
            if si == ti:
                continue
            if kind == "text":                     # 5 TRs on each side of the held-out quarter stay out (HRF overlap)
                rows2 = rows2[(rows2 < rows.min() - 5) | (rows2 > rows.max() + 5)]
            train.append((X2, key2, rows2, si))
        Xall = np.concatenate([X2[r2] for X2, _, r2, _ in train])
        mu, sd = Xall.mean(0), Xall.std(0) + 1e-8
        Xtrain = [block_shuffle(X2, rng) if mode == "shuffled" else X2 for X2, _, _, _ in train]
        Xt = Xs
        if mode == "shuffled":
            Xt = block_shuffle(Xs, rng)
        elif mode == "shifted":
            Xt = Xs.copy()
            Xt[rows] = np.roll(Xs[rows], len(rows) // 2, axis=0)
        test_rows = usable(kind, rows)
        Lt = design(kind, Xt, mu, sd, D_)
        if test_mask is not None:
            Lt = design(kind, Xt, mu, sd, (~test_mask) | (D_ if D_ is not None else False))
        for train_half, test_half in (("A", "B"), ("B", "A")):
            D, Y, C = [], [], []
            for X2, (_, key2, rows2, si) in zip(Xtrain, train):
                v = usable(kind, rows2)
                D.append(design(kind, X2, mu, sd, D_)[v])
                Y.append(data[f"{train_half}_{key2}"].astype(np.float64)[v])
                C.append(np.full(len(v), si))
            W, la = fit_ridge(np.concatenate(D), np.concatenate(Y), np.concatenate(C))
            out.append({"stim": sid, "train": train_half, "log_alpha": la, "pred": Lt[test_rows] @ W,
                        "y": data[f"{test_half}_{key}"].astype(np.float64)[test_rows],
                        "other": data[f"{train_half}_{key}"].astype(np.float64)[test_rows]})
    return out


def bh(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = p[o] * len(p) / (np.arange(len(p)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty_like(q)
    out[o] = np.minimum(q, 1)
    return out


def summarise(res, null=None):
    """Held-out r per region (mean over folds), the split-half ceiling and, with `null` (pooled held-out r of models
    fitted on shuffled features), one-sided p and Benjamini-Hochberg q per region."""
    r = np.mean([corr(f["pred"], f["y"]) for f in res], 0)
    split = np.mean([corr(f["other"], f["y"]) for f in res], 0)       # split-half reliability of a half's average
    out = {"r": r, "split_half": split, "ceiling": np.sqrt(np.clip(split, 0, None))}
    if null is not None:
        null = np.sort(np.asarray(null).ravel())
        p = (1 + len(null) - np.searchsorted(null, r, side="left")) / (1 + len(null))
        out.update(p=p, q=bh(p), null95=float(np.quantile(null, 0.95)))
    return out


def score(kind, data, n_shuffles=N_SHUFFLES, controls=True):
    """The model, its partial models and the controls. Significance: against the held-out r of N_SHUFFLES models
    fitted and tested on block-shuffled features (pooled over the 214 regions: a null that includes everything a
    model can pick up by chance -- the circular-shift null alone proved too lenient, REPORT.md)."""
    D = (data[f"X_{data['stimuli'][0]}"] if kind == "vision" else data["X_alice"]).shape[1]
    shuffled = [summarise(run_folds(kind, data, "shuffled", np.random.default_rng(SEED + 1 + k)))
                for k in range(n_shuffles)]
    null = np.stack([x["r"] for x in shuffled])
    real = run_folds(kind, data)
    s = {"real": summarise(real, null), "log_alpha": np.median([f["log_alpha"] for f in real], 0)}
    if kind == "text":
        sem = np.arange(D) < 384
        s["semantic"] = summarise(run_folds(kind, data, test_mask=sem), null)     # = the runtime part
        s["nuisance_only"] = summarise(run_folds(kind, data, fit_mask=~sem), null)
    else:
        s["low_level_only"] = summarise(run_folds(kind, data, fit_mask=np.arange(D) >= 512), null)
    if controls:
        # the shuffled control: the mean of the N_SHUFFLES runs (one run alone scatters by ~0.06 per region)
        s["shuffled"] = dict(shuffled[0], r=null.mean(0), r_runs_sd=null.std(0))
        s["shuffled"].update({k: v for k, v in summarise(run_folds(kind, data, "shuffled", np.random.default_rng(
            SEED + 999)), null).items() if k in ("p", "q")})              # one more, unseen run, tested like the model
        s["shifted"] = summarise(run_folds(kind, data, "shifted"), null)
    return s


# --- final runtime model -------------------------------------------------------------------------------------------
def runtime_model(kind, data, s, names):
    """Refit on everything (all stimuli, all participants' average) with each region's median fold penalty; sum the
    delays (the response to a sustained input) and weight regions by their held-out score."""
    segs = segments(kind, data)
    key_rows = {}
    for sid, X, key, rows in segs:
        key_rows.setdefault(key, (X, []))[1].append(rows)
    X_all = np.concatenate([X[np.concatenate(r)] for X, r in key_rows.values()])
    mu, sd = X_all.mean(0), X_all.std(0) + 1e-8
    D, Y = [], []
    for key, (X, rr) in key_rows.items():
        v = usable(kind, np.concatenate(rr)) if kind == "text" else np.concatenate([usable(kind, r) for r in rr])
        D.append(design(kind, X, mu, sd)[v])
        Y.append(data[f"all_{key}"].astype(np.float64)[v])
    D, Y = np.concatenate(D), np.concatenate(Y)
    U, S, Vt = np.linalg.svd(D, full_matrices=False)
    UtY = U.T @ Y
    alpha = 10 ** s["log_alpha"]
    W = np.stack([(Vt.T * (S / (S ** 2 + alpha[r]))) @ UtY[:, r] for r in range(Y.shape[1])], 1)
    nf = X_all.shape[1]
    W_ss = W.reshape(len(CFG[kind]["lags"]), nf, -1).sum(0)          # (features, regions)
    fnames = ([f"clip{i}" for i in range(512)] + ["luminance", "contrast", "change"] if kind == "vision"
              else [f"minilm{i}" for i in range(384)] + ["words", "envelope"])
    zero = np.array([n in CFG[kind]["runtime_zero"] for n in fnames])
    F = np.clip((X_all - mu) / sd, -FEATURE_CLIP, FEATURE_CLIP)      # as sensory.Encoding.predict
    F[:, zero] = 0.0
    P = F @ W_ss
    sc = s["semantic"] if kind == "text" else s["real"]
    sig = (sc["q"] < 0.05) & (sc["r"] > 0) & (sc["r"] > s["shuffled"]["r"]) & (sc["r"] > s["shifted"]["r"])
    weight = np.where(sig, sc["r"] / max(sc["r"][sig].max(), 1e-6) if sig.any() else 0.0, 0.0)
    extra = {}
    if kind == "vision":
        # familiarity: how close a picture is to what the model learned from (the films' TR-averaged CLIP embeddings,
        # every 3rd); the floor is the 5th percentile of a film's TRs' nearest neighbour among the OTHER films
        E = X_all[:, :512] / np.linalg.norm(X_all[:, :512], axis=1, keepdims=True)
        film = np.concatenate([[i] * len(np.concatenate(rr)) for i, (_, rr) in enumerate(key_rows.values())])
        ref = np.arange(0, len(E), 3)
        near = np.array([(E[ref][film[ref] != film[t]] @ E[t]).max() for t in range(len(E))])
        extra = {"ref": E[ref].astype(np.float16), "ref_floor": float(np.percentile(near, 5))}
    np.savez_compressed(OUT / f"{kind}.npz", W=W_ss.astype(np.float32), mu=mu, sd=sd, pred_mu=P.mean(0),
                        pred_sd=P.std(0) + 1e-8, weight=weight, r=sc["r"], ceiling=sc["ceiling"],
                        runtime_zero=zero, names=np.array(fnames), regions=np.array(names),
                        clipped_share=float((np.abs((X_all - mu) / sd) > FEATURE_CLIP).mean()), **extra)
    return weight


def runtime_only(kinds, names):
    """Rewrite the runtime weights from the committed cv_data.npz + scores.json (no re-scoring)."""
    sc = json.load(open(OUT / "scores.json"))
    for kind in kinds:
        def arr(d):
            return {k: (arr(v) if isinstance(v, dict) else np.array(v) if isinstance(v, list) else v)
                    for k, v in d.items()}
        w = runtime_model(kind, load_cv(kind), arr(sc[kind]), names)
        print(kind, "regions driven:", int((w > 0).sum()))


# --- report ------------------------------------------------------------------------------------------------------
def jsonable(s, names):
    out = {}
    for k, v in s.items():
        if isinstance(v, dict):
            out[k] = jsonable(v, names)
        elif isinstance(v, np.ndarray):
            out[k] = [round(float(x), 5) for x in v]
        else:
            out[k] = v
    return out


def headline(s):
    def h(x):
        r = np.asarray(x["r"])
        d = {"median_r": round(float(np.median(r)), 4), "max_r": round(float(r.max()), 4),
             "mean_r": round(float(r.mean()), 4)}
        if "q" in x:
            d["significant_regions"] = int((np.asarray(x["q"]) < 0.05).sum())
        return d
    return {k: h(v) for k, v in s.items() if isinstance(v, dict) and "r" in v}


def per_subject(kind, data, subj, subs):
    """Mean over held-out participants of r(prediction, that participant's own response)."""
    a, b = halves(subs)
    res = run_folds(kind, data)
    rs = []
    for f in res:
        test = b if f["train"] == "A" else a
        key = f["stim"] if kind == "vision" else "alice"
        rows = None
        for sid, X, k, r in segments(kind, data):
            if sid == f["stim"]:
                rows = usable(kind, r)
        for s_ in test:
            rs.append(corr(f["pred"], subj[s_][key][rows]))
    return np.mean(rs, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--kinds", default="vision,text")
    ap.add_argument("--runtime-only", action="store_true")
    a = ap.parse_args()
    names = names214()
    if a.check:
        return check(a.kinds.split(","))
    if a.runtime_only:
        return runtime_only(a.kinds.split(","), names)
    OUT.mkdir(parents=True, exist_ok=True)
    cv_data, scores = {}, {}
    old = OUT / "scores.json"
    if old.exists():
        scores = json.load(open(old))
    for kind in a.kinds.split(","):
        data, subj, subs = build(kind)
        print(kind, "participants:", len(subs), flush=True)
        s = score(kind, data)
        s["per_subject"] = {"r": per_subject(kind, data, subj, subs)}
        w = runtime_model(kind, data, s, names)
        scores[kind] = {"n_subjects": len(subs), "subjects": subs, "stimuli": list(data["stimuli"]),
                        "headline": headline(s), "regions_driven": int((w > 0).sum()), **jsonable(s, names)}
        for k, v in data.items():
            cv_data[f"{kind}/{k}"] = v
        print(json.dumps(scores[kind]["headline"], indent=1), flush=True)
    scores["regions"] = names
    json.dump(scores, open(OUT / "scores.json", "w"), indent=0)
    prev = dict(np.load(OUT / "cv_data.npz", allow_pickle=False)) if (OUT / "cv_data.npz").exists() else {}
    prev.update({k: np.asarray(v) for k, v in cv_data.items()})
    np.savez_compressed(OUT / "cv_data.npz", **prev)


def load_cv(kind):
    z = np.load(OUT / "cv_data.npz", allow_pickle=False)
    pre = f"{kind}/"
    return {k[len(pre):]: (z[k].tolist() if k.endswith("stimuli") else z[k]) for k in z.files if k.startswith(pre)}


def check(kinds, tol=1e-4):
    """Re-score the main held-out r from the committed cv_data.npz; compare with scores.json."""
    ref = json.load(open(OUT / "scores.json"))
    bad = []
    for kind in kinds:
        data = load_cv(kind)
        r = summarise(run_folds(kind, data))["r"]
        d = float(np.max(np.abs(r - np.array(ref[kind]["real"]["r"]))))
        print(f"{kind}: max |r - reported| = {d:.2e}")
        if d > tol:
            bad.append(kind)
    if bad:
        raise SystemExit(f"scores differ: {bad}")
    return True


if __name__ == "__main__":
    main()
