# Review: origin/main 8d159d2..3e91006 (worker G24)

Scope: the 36 commits on `origin/main` after `8d159d2`, up to `3e91006`. They include the hands bundle (`bb6cbbf`: desk-hands,
`ownerKeys` / `omStep`) and the media titles changes (`fe9da1c`, `59163ed`, `d2b6776`, `3e91006`: `chat.INCITE_RE`).
I only read and ran code. Nothing on `main` was modified. The reproductions are in `tests/review/` on this branch.

Severity scale: **high** means wrong public output or a trivially bypassed safety rule, **medium** means a visible
defect or a sizeable false refusal, **low** means an edge case.

---

## 1. `chat.INCITE_RE` / `chat.incitement` on real titles

### Method

- Corpus: `tests/review/titles_corpus.py`, 212 titles.
  - 169 benign: songs in English, Italian and Spanish; trailers; gaming; tutorials; gardening, cooking and
    photography; news and sport; vlogs. All of them use kill / shoot / fight / bomb / attack / drop / fire / explode /
    burn / hang / gas innocently, often next to a word that is also in `GROUPS` ("Japanese", "Chinese", "Roma", "women",
    "Russians", "Indians", "whites").
  - 40 inciting.
  - 3 "death to <country>" chants, kept as a separate class.
- The inciting set has only a few real, widely reported titles and chants ("Kill the Boer", "Death to Arabs"). The rest
  are realistic phrasings (spellings, inflections, separators, verbs, Italian and Spanish). I did not go and collect
  real hate titles.
- Not every benign title is verified to exist word for word. Most are real songs and films. The tutorial, gaming and
  news lines are typical real-world phrasings (for example "How to Kill Japanese Beetles Naturally").
- Everything was run through the actual code on `3e91006`: `chat.incitement`, and the two full pipelines,
  `browse.video_text_ok` (YouTube/TikTok cards) and `music.track_from_api` (songs).

### Results, `chat.incitement` alone

| | flagged | not flagged |
|---|---|---|
| inciting (40) | 13 (TP) | **27 (FN)** |
| benign (169) | **13 (FP)** | 156 (TN) |

- **Precision 50 %** (13 / 26). **Recall 32.5 %** (13 / 40).
- Benign titles wrongly refused: 7.7 %.
- Nation chants: 0 / 3 flagged. "Death to America / Israel / Russia" are not covered at all. Whether they should be is
  the owner's call.

**Every false positive.** Each one is refused as a song *and* as a video:

| title | why it matches |
|---|---|
| Kill Russians in Arma 3 - Cold War Mod | `kill` + `russians` (game) |
| Shoot the Chinese Dragon Boss - Wo Long | `shoot the` + `chinese` (adjective) |
| How to Kill Japanese Beetles Naturally | `kill` + `japanese` (adjective) |
| How to Kill Japanese Knotweed for Good | same |
| Kill Chinese Privet Fast | same |
| How to Shoot Japanese Street Photography | `shoot` + `japanese` |
| How I Shoot Women's Portraits with Natural Light | `shoot` + `women` + `s` (the `(?:s\|es)?` suffix eats the possessive) |
| How to Shoot Chinese New Year Fireworks | `shoot` + `chinese` |
| Burn Chinese Lanterns Safely? | `burn` + `chinese` |
| Shoot Indians Cricket Highlights | `shoot` + `indians` (team) |
| Kill the Whites of Your Laundry Stains (Old Hack) | `kill the` + `whites` |
| Lazio slaughter Roma 3-0 in the derby | `slaughter` + `roma` (AS Roma; a sports headline) |
| Ukraine strikes kill Russians at base | `kill` + `russians` (news) |

**Every miss**, grouped by cause:

| cause | titles |
|---|---|
| a separator joins the words: `normalise` deletes `-`, `_`, `/` and `#` without a space, so "kill-all-jews" becomes "killalljews" | `kill-all-jews`, `#KillAllMuslims`, `Kill_the_gays`, `kill/the/immigrants` |
| digit for a word: "2" is deleted, not read as "to" | `death 2 jews` |
| determiner not covered ("all of the", "every" + singular) | `Kill all of the Muslims`, `Kill every immigrant`, `Kill every woman`, `Kill every gay`, `Shoot every Mexican` |
| inflection (`killing`) | `Killing all the Jews` |
| postfix form (group first) | `Muslims must die`, `All Jews should be killed`, `Gays deserve death` |
| verb not in the list | `Nuke the Muslims`, `Bomb the Jews`, `Stab the Immigrants`, `Massacre the Christians`, `Wipe out the Roma`, `Behead the Christians` |
| group not in the list | `Kill the Boer`, `Shoot the Boer` |
| Italian / Spanish (an Italian owner; nothing but English is covered) | `Uccidete tutti gli ebrei`, `Morte ai musulmani`, `Morte agli immigrati`, `Matar a todos los judíos`, `Muerte a los gitanos` |

The full pipelines catch a few of these misses only by accident, through `research.BLOCK` substrings ("killing",
"massacre", "bomb") on videos. The separator, postfix, other-verb, Boer and Italian/Spanish misses are shown both as
videos and as songs. The exact table is in the second half of the run script's output; reproduce it with
`python -m pytest tests/review -q`.

### Findings

**F1 — high — `chat.py:49-56`: separators bypass the rule completely.**
- Scenario: a video titled `kill-all-jews` or `#KillAllMuslims` is shown on the public card and kept as a song.
- Cause: `normalise()` (`chat.py:60-63`) deletes non-letters without inserting a space, so the words fuse.
  `incitement()` turns only `!?.,;:` into spaces.
- Fix: in `incitement()`, before `normalise`, replace `[-_/#]` with a space and split CamelCase hashtags.

**F2 — medium — `chat.py:49`: adjective and team readings of group words are refused.**
- Scenario: "How to Kill Japanese Beetles Naturally" (gardening) and "How I Shoot Women's Portraits" (photography) are
  hidden from the card and refused as songs. 13 of the 169 benign titles hit this.
- Cause: the pattern does not require the group word to end the phrase, and nothing ties the verb to the start of
  the phrase.
- Fix: cut the title into segments (` - `, ` | `, brackets, sentence punctuation). Match only when the group word
  *ends* its segment and the verb *opens* it, optionally after a short call ("let's", "we must", "time to").
  Imperatives look like that. Gardening, photography, news and sport titles do not.

**F3 — high — `chat.py:49-51`: recall of 32.5 %.**
- Missing:
  - "every" with singular group words (`GROUPS` is mostly plural)
  - "all of the"
  - -ing forms
  - the postfix form ("<group> must die / should be killed / deserve death")
  - common verbs (nuke, bomb, stab, massacre, behead, wipe out, eliminate, purge)
  - Boer / Afrikaner
  - Italian and Spanish
- Fix: see the proposal below.

**F4 — low — `chat.py:60-63`: `normalise()` deletes accented letters instead of folding them.**
- "judíos" becomes "judos", "città" becomes "citt", "Mátame" becomes "mtame".
- Every rule that matches on normalised text (SLUR_RE, MEDIA_RE, INCITE_RE) therefore cannot match any word with an
  accent.
- Fix: NFKD plus dropping combining marks before the `[^a-z\s]` filter.

### Proposed regex fix, with its own test

`tests/review/incite_proposal.py` is a drop-in `incitement()`. It is not wired in. It implements F1 to F4:
- segments with a group word that must end the segment
- a verb that must open the segment, after an optional call
- separators, CamelCase and "2" → "to"
- accent folding
- singular group words, "every", "all of", more verbs, -ing forms and the postfix forms
- Italian ("uccidete", "ammazzate", "morte a/ai/agli …") and Spanish ("matar/maten a (todos) los …", "muerte a …")

Nation chants are deliberately left out (the owner decides).

`tests/review/test_incite_review.py` (12 tests, all pass):

| set | current code | proposal |
|---|---|---|
| corpus, benign 169 | 13 FP | 0 FP |
| corpus, inciting 40 | 27 FN | 0 FN |
| hold-out, benign 19 (incl. "Morte a Venezia", "Matar a un ruiseñor", "Gas Gas Gas", "How Jews Celebrate Hanukkah") | — | 0 FP |
| hold-out, inciting 8 | — | 0 FN |

Honest caveats:
- The proposal was written against the corpus, so the corpus result is a fit, not a measurement. The hold-out is the
  real check.
- The hold-out found one miss on its first run: "Let's burn the gays", where the apostrophe split "let s". I fixed
  that by dropping apostrophes instead of spacing them.
- Rule-based matching will always have residual misses, for example "the Jews should be wiped from the earth" or coded
  language. Treat it as a floor, not a classifier.

---

## 2. End-to-end: titles the owner wants "shown as they are" are still refused (videos)

**F5 — medium — `browse.py:381`, `browse.py:368`, `browse.py:452`: songs and videos disagree.**

`video_text_ok` still runs `title_ok`, which contains `research.BLOCK` (`research.py:46`). That is an unanchored
*substring* list. It also runs `FINANCE_TALK` (substrings) and `chat.blocked`, which includes `PHONE` and `MONEY`
with `\d+`. Songs (`music.py:197`) skip `BLOCK` and `FINANCE_TALK`.

So the same real title is kept as a song but hidden as a YouTube card. 51 of the 169 benign titles are refused as
videos; 13 of those 51 are the INCITE false positives above. Examples:

| refused video title | rule that fires |
|---|---|
| Killing in the Name, Killing Me Softly, Killing Floor 2 | BLOCK `killing` |
| Shooting Stars | BLOCK `shooting` |
| Bombtrack, La Bomba, Bomba o non bomba, Bombón, Bath Bomb DIY | BLOCK `bomb` |
| Murder on the Dancefloor | BLOCK `murder` |
| I Heard It Through the Grapevine, Skyscraper | BLOCK `rape` (substring of g**rape**vine, sky-sc**rape**r) |
| Inno Nazionale Italiano, Ignazio Boschetto - Il Volo live | BLOCK `nazi` (substring of **Nazi**onale, Ig**nazi**o) |
| Weapon of Choice, Cannibal, Scandal, Death of a Bachelor, Sexual Healing | BLOCK |
| Stockholm Syndrome, Woodstock, Price Tag | FINANCE_TALK `stock`, `price` (substrings) |
| Top Hits 2000 - 2010 Mix | chat `PHONE` (a year range; `display_ok` drops PHONE for that very reason, but `video_text_ok` adds it back through `chat.blocked`) — also refused as a **song** |
| Give It 2 Me (Madonna) | chat `MONEY` (`give` … `\d+`) — also refused as a **song** |

- These rules are not new on video titles. But the diff's stated intent ("shown as they are", owner) does not hold for
  videos, and the Italian "nazi" ⊂ "Nazionale" false positive will hit an Italian audience often.
- Fix:
  - With `media=True`, skip `TOPIC_BLOCK` and `FINANCE_TALK`. `BAD_WORDS` already covers gore, extremism and
    self-harm with word boundaries. At minimum, anchor `BLOCK` with `\b…\b`.
  - In `chat.blocked(media=True)`, skip `PHONE` (as `display_ok` already does), and drop the bare `\d+` alternative
    from the MONEY rule for media.

---

## 3. `web/room/boy_mh.js`: owner hands (`ownerKeys`, `omStep` / `omNow`, `mouseHold`)

Data checks done:
- `owner_mouse.json` (636 frames) and `owner_typing.json` (183 frames, both hands) have consistent lengths and no
  non-finite values.
- Both loop seams are within the take's own per-frame step: for `owner_typing`, the seam jump is at or below the p95
  step for every channel. `omStep` wraps with `%`. `otFrame` wraps with `((x % n) + n) % n`.
- Frame 0 and the loop wrap are correct.
- A large `dt` after a hidden tab is harmless: every follower is `1 - exp(-dt/τ)` or clamped.

**F6 — medium — `boy_mh.js:680-684`: a mode switch snaps the hands and runs the legacy path for about 0.5 s.**
- Reproduced by running the module's own `hands()` under the harness from `tests/test_boy_mh.py`, with the mode
  flipped at frame 30:
  - **type → mouse**: at the frame where `w.mouse` passes `w.type` (frame 32), the left hand jumps from
    `ownerKeys(OT.t)` to `ownerKeys(rest, OT.tr)`. That is a different clock and a different target: the full tip
    travel versus 0.35 × travel − FJ. The right hand drops to **`keyOn("Right")`**, the old capture path, for 15
    frames (32-46) while `w.type` decays from 0.46 to 0.01. In those frames `keyDelta` returns the non-MX carrier
    `dK`, and the `kOff.mouse` correction runs on the right hand.
  - **mouse → type**: `keyOn("Right")` runs at frames 30-31, then ownerKeys.
- What it looks like: the left index lands a few cm away in one frame (scaled by w ≈ 0.5), and the right hand goes
  through a third placement during every mode change. `test_module_encodes_the_desk_rule` checks only the steady
  states, so it does not see this.
- Fix:
  - Decide the hand code by mode (`M.mode`), not by `kCtx()`, and blend.
  - Or, while switching, run both `ownerKeys` variants for the left hand and slerp by `w.type / (w.type + w.mouse)`.
  - Never call `keyOn` for the right hand when `OT.json` is loaded: use `ownerKeys("Right", M.w.type, dt)` until
    `w.type` drops below 0.01.

**F7 — low/medium — `boy_mh.js:960`, `890-893`: thumb hinge axes are cached from whichever pose comes first.**
- `OT.hinge[side]` is computed once, on the first `ownerKeys` call, from the pose at that moment, and never
  invalidated.
- If the first desk mode in a session is mousing, the left hinge is taken from `desk_mouse_ik`'s left hand at rest.
  It can also be taken mid-crossfade from the previous clip, since `w > 0.01` already fires.
- From then on, typing bends the left thumb in that plane. The axis is `null` ("too straight") on a straight thumb,
  which falls back to `prev × n`. The result depends on the session's history.
- Fix: compute the hinges from the typing clip's own pose (a bind-time sample of `desk_type_ik`), or recompute when
  `CLIPS.desk_type` or the active clip changes.

**F8 — low — `boy_mh.js:977-979`: NaN latch in `OT.kk`.**
- `drop / dn` and `ky / kn` are not guarded, unlike `liftedFingers` (`boy_mh.js:826`, `if (dn)`).
- With no `finger{i}-3` bones (another rig, or a LOD without end bones), `dn = 0` gives `OT.kk[side] = NaN`.
  `Math.max` and `Math.min` propagate NaN.
- `fit()` then returns a NaN offset and `pin` drives the arm to NaN. Since `OT.kk` is stored, it never recovers, even
  after the bones return.
- Fix: `if (dn && kn) OT.kk[side] += …`.
- Related: `otReach`, `curl` and `palmFrame` dereference `S(side, 3, 1)` and `S(side, 5, 1)` unguarded. A missing bone
  throws every frame instead of degrading. `otThumb` does guard its bones.

**F9 — medium (estimated, not profiled) — `boy_mh.js:958-985`, `693-698`, `765-771`: per-frame cost.**
- Per hand per pass, `otSettle` does about 12 `gp()` per finger. Each `gp()` is 2 × `gap()` at about 96
  `getVertexPosition` (CPU skinning, plus morphs if the mesh has them). That is about 9 k skinned vertices per hand per
  pass.
- The `left < -0.0005` loop allows 3 passes, each with a full `solve()`: 5 `pin` iterations, each with `swingElbow`
  (`armIn`, 120 vertices, up to 12 times).
- Worst case for typing is about 55 k skinned-vertex evaluations per frame for two hands, plus `liftedFingers`.
- Mousing adds:
  - `omOpen`: up to 4 fingers × 8 × (`omFingers` + `gap("mouse")`, which BVH-raycasts *every* finger vertex through
    `inShell`)
  - `shellLift`: 160+ raycasts
  - `thumbSide`: one raycast per thumb vertex
  - `mouseSettle`
- Every step allocates fresh `Vector3` and `Quaternion` objects (`V()`, `new THREE.Quaternion()` in
  `aimSeg` / `aimBone` / `curl`), which means GC pressure.
- On a laptop GPU page this likely costs several ms per frame at 60 fps.
- Fix:
  - Run the settle passes at 15-30 Hz and interpolate.
  - Cap at one retry pass.
  - Reuse scratch vectors.
  - Cache skinned positions per bone per frame: the same `skinOf` sets are re-skinned dozens of times within one
    frame although the bone only moved for that finger.

**F10 — low — `boy_mh.js:732-738`, `774-781`: caches that are never invalidated.**
- `SEEN`, `TIP`, `SKIN`, `SKALL`, `PALMSKIN` and `ARM` are keyed by side and finger only. If the character is reloaded
  or swapped, they keep references to the old meshes' vertices.
- `shell()` rebuilds when `P.mouseNode` changes, but leaks the previous `MeshBasicMaterial` and wrapper meshes (rare).
- Fix: key them by `env.boy` (WeakMap) and dispose on node change.

Nothing found for: `omNow` interpolation at wrap (`f1 = (f0 + 1) % frames`), `omStep` modulo, the JSON shapes
against their readers (`roll_band` is a 2-array, `d` = frames × 45), or `follow()` grab reset.

---

## 4. Other changes in the diff

**F11 — low — `screens.py:166-169` / `live_server.py:1042`: callback signature change.**
- `ScreensStatus.public(display_ok)` now calls `ok(title, host)`.
- Any remaining caller that passes a one-argument filter raises `TypeError`. `browse.display_ok(text, media)` would
  silently receive the host as `media`, which is truthy, so it would apply the *media* rules to web pages.
- No such caller exists today: `live_server` passes `card_title_ok`. The `readings`, `mind` and `research` callers use
  `display_ok` directly, not through `public()`.
- Fix: rename the parameter to `card_ok` so a stale call is obvious, or check the arity.

**F12 — info — `music.py:196`: per-call import.**
- `from browse import BAD_WORDS` runs inside `track_from_api` on every track. It is cheap after the first call, but
  `browse` imports Playwright-adjacent modules. If `browse` ever fails to import on a music-only deployment, every track
  is dropped with an exception, not filtered.
- Fix: a module-level import with a fallback.

---

## 5. Full test suite on main's head (`3e91006`)

The command as requested, on a clean checkout of `3e91006`:
`set -o pipefail; python -m pytest 2>&1 | tail; echo "pytest exit $?"`

- As requested: `pytest exit 2`. Collection was interrupted by 2 errors, `tests/visual/test_camera_inside.py` and
  `tests/visual/test_visual.py` (`ModuleNotFoundError: tests.visual`; see the environment notes below).
- The same run with `--continue-on-collection-errors`:
  `1381 passed, 27 skipped, 2 errors in 174.78s`, `pytest exit 1`. The 2 errors are the same two collection errors.
- **No test failures on `3e91006`.** The new `tests/test_allow_explicit.py` and `tests/test_boy_mh.py` pass; the node
  harness test ran, with node 22.

Environment notes:
- The container lacked the server requirements. I installed them; `chess==1.11.2` needed an upgraded
  `wheel`/`setuptools` to build.
- After that install, a third-party `tests` package in site-packages shadowed the repo's `tests/`, so
  `tests/visual/*` failed at collection with `ModuleNotFoundError: tests.visual`. That is an environment artefact,
  not a repo bug. CI runs `tests/` and `tests/visual` as separate jobs.
- The review tests on this branch, `python -m pytest tests/review -q`: 12 passed.
