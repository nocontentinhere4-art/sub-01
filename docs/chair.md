# The chair (/chair): simulated shocks, measured activity, his body and his lines

Visitors pick an intensity and send a shock. The shock is a pulse train into his simulated network; what moves his
body is the activity the network measures afterwards, never the button. A model, not a mind; the character is
fiction; no living neurons and no hardware are connected. The page says "Simulated neural activity".

## The chain

| step | where | what |
|---|---|---|
| request | `web/chair.html` → `/ws/chair` | `{"type":"shock","level":1..5}` |
| validation, limits | `chair.Hub.submit` | level 1-5 only; one every 4 s per visitor (burst 2); 6 waiting at most; one delivery every 2 s; 20 a minute for everyone; the sender gets `queued / throttled / full / unavailable / stopped` |
| delivery | `chair.Hub.pump_once` → `spiking/alif.py` child | the one process that advances the network injects the pulse train; the request becomes `delivered` with the simulation time, the amplitude, the duration and how many neurons were recruited |
| measurement | `spiking.alif.Measure` | 20 ms bins: population rate (all, excitatory, inhibitory, per group, per region), the mean adaptation current; a quiet-time baseline; per stimulus a response card (peak against baseline, onset, burst, recruitment, undershoot, time back in the band) → `measured` |
| the body | `spiking.alif.drive_from` → `web/chair_scene.js` | three numbers read off each bin: tension (rate above baseline, log scale, 1 at 8x), slack (the undershoot), heavy (adaptation above its baseline); springs for inertia; bounded by the restraints |
| the rest of him | `live_server.Live.chair_shock` | the same delivery stimulates the rate model's motor, salience and relay networks and the sleep circuit, so the brain page and the room feel it too |
| his lines | `speech.py` | reactions from the response class as the bins come in; a comment at most every 45 s and every 4 shocks, written by the mind's metered model call from the measured numbers, or a rule line; one line at a time, reactions interrupt comments, stale lines dropped |

## The network (`spiking/alif.py`)

The day network's wiring (`spiking/wiring.py`, the same seed as `spiking/live.py`: 20,000 neurons, 80 % excitatory,
one population per region of the connectome, fixed in-degree, long-range delays from fibre length at 6 m/s), with two
mechanisms the plain LIF does not have, both in the equations:

- exponential current synapses, tau_e 5 ms, tau_i 10 ms (Brunel & Wang 2001 ranges), scaled so the PSP integral
  equals the day network's instantaneous jump;
- an adaptation current, tau_w dw/dt = a v − w, w += b at a spike (the w of Brette & Gerstner 2005, in voltage
  units; a = 0.1, b = 1 mV, tau_w = 1 s, the slow after-hyperpolarisation end of the range Benda & Herz 2003
  review, so that shocks seconds apart meet a network still adapted).

Kept from the day network: membrane dynamics and a fixed threshold, a 2 ms refractory period, excitatory and
inhibitory populations, conduction delays, a noisy background drive (raised from 15 to 20 mV to keep the baseline
near 4 Hz with adaptation on). No plasticity: nothing in the chair is called learning. Integration: Euler at 1 ms
for v and w (dt/tau 0.05 and 0.001), exact decay for the synaptic variables. Measured on this laptop: 0.17 s of
wall time per simulated second at 20k neurons, about a third of a core while running; paused when nobody watches.

The stimulus (`Pulse`): a 50 Hz train of 2 ms pulses, amplitude 3-16 mV per step, 300-1000 ms long, on a random
subset of the neurons under the clamp (10-60 % of a montage that weights the parcels under the crown and temples:
somatomotor 1.0, attention and salience 0.7, language 0.6, control and default 0.5, visual and limbic 0.3, thalamus
0.2, amygdala 0.1, striatum and hippocampus 0). The montage is an engineering assumption, not a model of current flow
through a head. The subset is drawn once per stimulus (modelled chance); nothing else is random on the page.

## What was measured (20k neurons, `tune_alif.py` runs and `tests/test_chair.py`)

- baseline 3.9 Hz (sd 0.28 Hz per 20 ms bin), excitatory and inhibitory alike, mean w 5 mV;
- levels 1→5: peak 5.2, 7.7, 11, 15, 19 Hz (1.3x to 4.9x baseline); onset at the first bin for level 2 and up;
  bursts (3 bins over 3x) from level 4; regions recruited 0 %, 2 %, 37 %, 86 %, 93 %; undershoot to 0.5-0.8x after
  the train; back inside the baseline band after 0.7-3 s; level 1 is sometimes not distinguishable, and the card
  says so;
- repeated level 4 every 1.5 s: the peak rate is the same (the train drives the recruited neurons regardless) but
  the adaptation current before each shock rises from 5.1 to 7.0 mV and the undershoot deepens: the state carries;
- numerically: v never above threshold, w bounded, no NaN over minutes of repeated stimulation; the refractory period
  caps every neuron's rate.

## The flatline and the revival (a rule of the piece, owner 11-03)

`Measure.load` is the mean adaptation current averaged over 15 s. When it stays above 1.6x its quiet level
(`FLAT_LOAD_RATIO` 1.45; about ten level 5 shocks in a row from one visitor, never from level 3, measured at 20k), `ALIFNet.arrest()` sets
the background drive to zero and the spontaneous activity stops: the trace is flat, the bins carry `flat`, nothing is
measured against the baseline, the body hangs (`limp`), the lamp sinks, he is silent and the chat answers "flat". A
shock of level `REVIVE_LEVEL` (3) or more calls `restart()` before its train: a `revived` event with the seconds flat
and the level, a jolt in the body, a "back" line at once and then a longer line from the model about how it was
(`SYSTEM_BACK`), or a rule line. No neuron has such a rule; it is written as the piece's and said so on the page.

## The chat

`speech.ChairChat`: messages from the chair page (typed, or spoken through the browser's own speech recognition; no
audio leaves the device), one per visitor every 15 s, one answer at a time every 20 s at most, answered by the mind's
metered model call (`SYSTEM_CHAT`) with the measured shocks as context and said in his voice where one answers. By
the owner's rule there is no content filter on what visitors write and no gate on what he answers: the only bounds
are length and rate. The room chat keeps its own filter.

## What is art

The movements (head into the clamp, torso against the strap, shoulders, forearms and fingers on the armrests, feet,
a 9 Hz tremor under tension, breathing from 13 to 46 a minute, the slump when the rate undershoots and the
adaptation is high), the springs (fast up, slow down), the lamp dip at delivery, the electrode glow, the camera and
every line he says. Under reduced motion: no tremor, no lamp dip. The character has no face rig: no jaw, no lip sync.

## Voice

`speech.VoiceStudio` talks to the owner's local VoiceStudio app (github.com/debpalash/VoiceStudio, AGPL-3.0, the
OmniVoice engine) through its local HTTP API: `POST /generate` (text, instruct tags, seed, steps) answers WAV bytes
with `X-Audio-Duration`; `GET /health` says whether it is up. The server passes `--voice-url http://localhost:3900`
(or `VOICE_STUDIO_URL`); without it `NoVoice` reports unavailable and the lines are captions. The voice is the app's saved
profile named by `--voice-profile` / `VOICE_STUDIO_PROFILE` (the owner chose "BREZ", a profile of his own app), else a
designed one from tags ("male, young adult, moderate pitch", fixed seed). OmniVoice has no emotion tags,
so the only expressive delivery is its whisper tag on the settling lines; nothing else is pretended. Renders are
cached and the reaction vocabulary is rendered ahead, so a reaction plays at once; a comment renders on demand
(0.4-0.8 s per line on this Mac's GPU, measured). The hub renders off the event loop with a time limit; a line whose
audio is late goes out as a caption. The page plays the audio from `/api/chair/voice/<key>.wav`, stops it on
cancellation, and says when the browser blocks sound before a tap. Production cannot reach the app, so it plays the
bank: every reaction line and every rule comment without a number in it, rendered ahead with the BREZ profile by
`tools/chair_voice_bank.py` into `web/chair_voice/` (29 files, 1.7 MB, served as static files; `speech.BankVoice`).
A line that is not in the bank (a model-written comment, a rule comment with numbers) is a caption there. No lip sync: the character has no face rig.

## Operator

`POST /api/chair/stop`, `/api/chair/resume`, `/api/chair/reset` with the admin token (`X-Admin-Token` or the gate's
cookie); `GET /api/chair/status` (public). `SUB01_CHAIR=0` turns the chair off; `SUB01_CHAIR_NEURONS` sets the size.

## Future source

`chair.Source` is the interface: `stimulate(rid, level)`, `resume/pause/reset`, `status()` with `kind`, and the
callbacks `on_trace`, `on_event`, `on_state`. Only `SimSource` exists. A provider of another kind must report it in
`status()["kind"]`; the page shows the kind it is told and shows "unavailable" when a source is down. Never relabel.
