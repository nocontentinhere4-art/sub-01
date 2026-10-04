"""The X film's soundtrack, synthesised (stdlib only) to the edit in compose.js: a low impact on every cut, a heartbeat
under the day, a slowing heartbeat into sleep, clock ticks under the time-lapse, a REM shimmer and a last hit on the logo.
usage: python3 soundtrack2.py out.wav"""
import math, random, struct, sys, wave
SR, DUR = 44100, 29.6
N = int(SR * DUR)
buf = [0.0] * N
random.seed(3)
NOISE = [random.uniform(-1, 1) for _ in range(SR)]
CUTS = [2.4, 5.0, 7.4, 10.0, 12.2, 14.6, 17.0, 20.0, 24.4]
SPLIT_SLEEP, REM_AT, TL0, END, LOGO = 17.0, 18.7, 20.0, 24.4, 27.0

def add(t0, smp, g=1.0):
    i0 = int(t0 * SR)
    for k, v in enumerate(smp):
        if 0 <= i0 + k < N:
            buf[i0 + k] += v * g

def thump(f0, length, decay, drop=1.5):
    return [math.sin(2 * math.pi * f0 * (1 + drop * math.exp(-k / SR * 40)) * k / SR) * math.exp(-k / SR * decay) for k in range(int(SR * length))]

def noise_burst(length, decay, lp=0.15):
    out, y = [], 0.0
    for k in range(int(SR * length)):
        y += lp * (NOISE[k % SR] - y)
        out.append(y * math.exp(-k / SR * decay))
    return out

boom, lub, dub, tick = thump(42, 1.2, 4), thump(58, 0.22, 18), thump(70, 0.16, 22), noise_burst(0.03, 120, 0.9)
# riser into the first cut and the hit on it, impacts on every cut
riser = [NOISE[k % SR] * (k / (SR * 2.3)) ** 3 * 0.35 for k in range(int(SR * 2.3))]
add(0.1, riser)
for c in CUTS:
    add(c, boom, 0.9); add(c, noise_burst(0.5, 9, 0.3), 0.5)
# heartbeat: 100 bpm through the day, slowing to 55 bpm into sleep, none in the time-lapse
t = 2.4
while t < TL0:
    bpm = 100 if t < SPLIT_SLEEP else 100 - 45 * min(1, (t - SPLIT_SLEEP) / 1.6)
    add(t, lub, 0.8); add(t + 0.16, dub, 0.5)
    t += 60 / bpm
# clock ticks, accelerating, through the time-lapse
t, step = TL0, 0.25
while t < END - 0.05:
    add(t, tick, 0.6); t += step; step = max(0.07, step * 0.93)
# drone (A minor-ish), and a REM shimmer: detuned high partials with a slow tremolo
for i in range(N):
    t = i / SR
    env = min(1, t / 2.0)
    d = math.sin(2 * math.pi * 55 * t) + 0.5 * math.sin(2 * math.pi * 82.4 * t) + 0.2 * math.sin(2 * math.pi * 110 * t)
    lvl = 0.09 * env
    if TL0 <= t < END:
        lvl *= 1 + 0.8 * (t - TL0) / (END - TL0)
    v = lvl * d
    if t >= REM_AT and not (TL0 <= t < END):
        r = min(1, (t - REM_AT) / 1.0) * (0.5 if t < TL0 else 1.0)
        trem = 0.6 + 0.4 * math.sin(2 * math.pi * 3.0 * t)
        v += 0.05 * r * trem * (math.sin(2 * math.pi * 880 * t) + math.sin(2 * math.pi * 883.5 * t) + 0.7 * math.sin(2 * math.pi * 1318.5 * t) + 0.5 * math.sin(2 * math.pi * 659.3 * t))
    buf[i] += v
add(LOGO, thump(36, 2.5, 1.6, 0.8), 1.2)
for i in range(N):
    t = i / SR
    if t > DUR - 1.5:
        buf[i] *= max(0, (DUR - t) / 1.5)
peak = max(abs(x) for x in buf) or 1
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'soundtrack2.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(30000 * math.tanh(1.4 * x / peak))) for x in buf))
print('ok')
