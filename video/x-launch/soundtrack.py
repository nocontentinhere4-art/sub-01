"""Heartbeat + drone soundtrack, synced to the storyboard's 0.6 s beat grid. Pure stdlib.
usage: python3 soundtrack.py <duration_s>"""
import math, random, struct, sys, wave
from pathlib import Path

SR = 44100
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 31.2
N = int(SR * DUR)
buf = [0.0] * N
CUTS = [3.0, 5.4, 8.4, 11.4, 14.4, 17.4, 22.8, 26.4]
SILENT = (22.8, 26.4)            # "It's a model. Not a mind." plays over near silence

def add(i0, samples):
    for k, s in enumerate(samples):
        if 0 <= i0 + k < N:
            buf[i0 + k] += s

def thump(f0, amp, length=0.22):
    out = []
    for k in range(int(SR * length)):
        t = k / SR
        f = f0 * (1 + 1.5 * math.exp(-t * 40))        # pitch drop
        out.append(amp * math.sin(2 * math.pi * f * t) * math.exp(-t * 18))
    return out

lub, dub = thump(58, 0.9), thump(70, 0.6, 0.16)
random.seed(1)
noise = [random.uniform(-1, 1) for _ in range(int(SR * 0.6))]

# heartbeat on every beat (0.6 s), denser + louder through the zoom scene, absent in the silent stretch
t = 0.0
while t < DUR:
    if not (SILENT[0] - 0.05 <= t < SILENT[1] - 0.05):
        boost = 1.25 if 17.4 <= t < 22.8 else 1.0
        add(int(t * SR), [s * boost for s in lub])
        add(int((t + 0.16) * SR), [s * boost for s in dub])
    t += 0.6
# one lonely beat in the silence, then a big hit on the end card
add(int(24.6 * SR), lub)

# riser (filtered noise swell) into each cut
for c in CUTS:
    L = int(SR * 0.45)
    i0 = int(c * SR) - L
    lp = 0.0
    seg = []
    for k in range(L):
        x = k / L
        lp += 0.08 * (noise[k % len(noise)] - lp)
        seg.append(lp * 0.5 * x * x)
    add(i0, seg)

# drone: A1 + E2 with slow tremolo, swelling through the zoom, ducked in the silence, final chord on the end card
for i in range(N):
    t = i / SR
    env = min(1, t / 1.5)
    if 17.4 <= t < 22.8:
        env *= 1 + 0.8 * (t - 17.4) / 5.4
    if SILENT[0] <= t < SILENT[1]:
        env *= 0.08
    if t >= SILENT[1]:
        env = 1.6 * math.exp(-(t - SILENT[1]) * 0.45) + 0.25
    trem = 0.75 + 0.25 * math.sin(2 * math.pi * 0.5 * t)
    d = (math.sin(2 * math.pi * 55 * t) + 0.6 * math.sin(2 * math.pi * 82.41 * t)
         + 0.25 * math.sin(2 * math.pi * 110 * t) + 0.12 * math.sin(2 * math.pi * 164.8 * t))
    if t >= SILENT[1]:
        d += 0.35 * math.sin(2 * math.pi * 220 * t) + 0.2 * math.sin(2 * math.pi * 329.6 * t)
    buf[i] += 0.11 * env * trem * d

# end-card impact
add(int(SILENT[1] * SR), thump(45, 1.0, 0.9))

# fade out last 1.2 s, normalise, soft clip
for i in range(N):
    t = i / SR
    if t > DUR - 1.2:
        buf[i] *= max(0, (DUR - t) / 1.2)
peak = max(abs(x) for x in buf) or 1
with wave.open(str(Path(__file__).with_name('soundtrack.wav')), 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(32000 * math.tanh(1.3 * x / peak))) for x in buf))
print('soundtrack.wav', DUR, 's')
