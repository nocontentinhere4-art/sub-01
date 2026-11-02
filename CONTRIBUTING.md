# Contributing to SUB-01

SUB-01 is a model of brain activity built from one person's public MRI scans, running around the clock and driving an
invented character. It is open so that people who know more than we do about brains, simulation, rendering or writing
can make it better. Thank you for reading this far.

## Run it

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-server.txt
BROWSE=0 python live_server.py --demo --port 8765
python -m pytest -q tests/
```

The demo mode needs no keys and no GPU. The spiking tests skip without torch, the browser tests without Chromium. Five
tests fail on a clean checkout today (`test_boy_mh`, `test_reading`, `test_spiking_live`, `test_spiking_ops`,
`test_tastes_faster`); one more (`test_server_round_end_applies_when_awake`) fails around Tokyo midnight. Fixing any of
them is a good first pull request.

## Where the model lives

| Part | Files |
|---|---|
| The whole-brain model (regions, wiring, the slow layer, neuromodulators) | `brain_sim.py`, `twin/` |
| Sleep and wake (Phillips & Robinson 2007) | `sleep.py` |
| Spiking neurons (CPU fallback and the rented GPU runs) | `spiking/`, `docs/spiking/` |
| The character's day, his room, what he reads | `life.py`, `browse.py`, `research.py`, `eye.py`, `diary.py` |
| The server, the socket, the pages | `live_server.py`, `web/` |
| The design system the pages follow | `docs/design/decoded/SYSTEM.md` |

## The rules of the house

These are not negotiable; a pull request that breaks one will not be merged, however good the rest is.

- **A model, not a mind.** Nothing on the site or in the docs claims that it feels, thinks, understands or is conscious.
- **The character is fiction.** He is not the scanned person. The scanned person is credited on `/about.html` only and
  is never named anywhere else.
- **No "AI" wording on the pages.** The site says what the model did in plain words. Where a language model writes
  something (notes, plans, replies), `/about.html` says so once.
- **Honest numbers.** Negative results stay in the README and on the site, labelled. No invented statistics.
- **No coin promotion.** The contract address appears once, on `/about.html`, and nowhere else. No prices, no tickers.
- **Plain sentences.** Sentence case, no uppercase tracked labels, no hyphens inside running copy, no exclamation marks.
- **No third-party scripts.** The pages load three.js and leaflet from the CDNs already used, the fonts from the repo,
  and nothing else.

## How to contribute

1. Open an issue first for anything bigger than a fix, with the question you want to answer or the thing you want to
   change. The open problems below are a good place to start.
2. Keep pull requests small and on one subject. Run the tests. Say what you measured.
3. Write commit messages as one plain sentence saying what changed and why. No tool or model names in them.
4. Pages follow `docs/design/decoded/SYSTEM.md`. Run the local demo and look at the page at 1440 and 390 px wide.

## Open problems

Scientific, in rough order of how much they would change:

- **The model explains little of the real resting state.** r ≈ 0.21 on held out sessions (`docs/`). A better fit of
  the slow layer, the delays or the neuromodulator maps would be a real result.
- **PCI stays below the clinical cutoff in every state** (0.18 awake, 0.07 NREM, 0.17 REM). Why, and what would change it?
- **The spiking network does not learn Pong** (17.5 % against 25 % for the no-plasticity control) but does learn to
  choose. What separates the two tasks?
- **The sleep circuit is one published model with its constants.** A fit to the scanned person's own actigraphy or
  resting-state sessions would be new.

Engineering:

- The room on phones: the 1.85 MB model loads, but a real phone has not been measured.
- The brain glow and the room cost on a real GPU: only software rendering has been measured here.
- The two tests that fail on a clean checkout, and the midnight one.

## Licence

Code and docs are MIT (`LICENSE`). Data and assets keep their own terms (`LICENSES.md`); the character models are not
covered yet, so do not build anything that redistributes them on their own.
