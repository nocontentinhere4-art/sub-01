"""EP.1 soundtrack (stdlib synth): a driving pulse under the recording, typing clicks on the searches, a riser under the
fork and a hit on SCELTO, an error buzz, a boom on the reveal, a REM pad and a last hit on the logo."""
import math, random, struct, sys, wave
SR, DUR = 44100, 25.0
N = int(SR * DUR); buf = [0.0] * N; random.seed(5)
NZ = [random.uniform(-1, 1) for _ in range(SR)]
def add(t0, s, g=1.0):
    i0 = int(t0 * SR)
    for k, v in enumerate(s):
        if 0 <= i0 + k < N: buf[i0 + k] += v * g
def thump(f0, L, dec, drop=1.5): return [math.sin(2*math.pi*f0*(1+drop*math.exp(-k/SR*40))*k/SR)*math.exp(-k/SR*dec) for k in range(int(SR*L))]
def nb(L, dec, lp=.2):
    o, y = [], 0.0
    for k in range(int(SR*L)): y += lp*(NZ[k % SR]-y); o.append(y*math.exp(-k/SR*dec))
    return o
kick, hat, click, boom = thump(50, .3, 14), nb(.04, 90, .9), nb(.012, 300, .95), thump(38, 1.6, 2.5)
CUTS = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 10.8, 12.6, 17.0, 21.0]
# 120 bpm pulse while the recording plays (0-10.8 s, not under the fork's riser), half time after the reveal
t = 0.0
while t < 8.0: add(t, kick, .8); add(t + .25, hat, .3); t += .5
t = 12.6
while t < 21.0: add(t, kick, .55); add(t + .5, hat, .25); t += 1.0
for c in CUTS: add(c, nb(.25, 14, .5), .5)
for t0, q in ((3.05, 15), (10.0, 18)):                       # typing: the queries' letters
    for i in range(q): add(t0 + i / 22 + random.uniform(0, .01), click, .6)
riser = [NZ[k % SR] * (k / (SR * 1.15)) ** 2 * .5 for k in range(int(SR * 1.15))]; add(8.0, riser)
for k in range(int(SR * 1.15)):                               # a rising tone under the bars
    t = k / SR; add(8.0 + t, [0.08 * math.sin(2 * math.pi * (220 + 440 * t) * t)], 1)
add(9.15, boom, 1.0); add(9.15, nb(.4, 10, .6), .7)            # SCELTO
add(10.45, [0.35 * (1 if math.sin(2*math.pi*110*k/SR) > 0 else -1) * math.exp(-k/SR*4) for k in range(int(SR*.45))])   # error buzz
add(10.8, boom, 1.2)
for i in range(N):                                            # pad: A minor under the reveal, REM shimmer at the end
    t = i / SR
    if t >= 10.8:
        e = min(1, (t - 10.8) / .6)
        v = .06 * e * (math.sin(2*math.pi*55*t) + .5*math.sin(2*math.pi*82.4*t) + .3*math.sin(2*math.pi*110*t))
        if t >= 21.0:
            r = min(1, (t - 21) / .5) * (.6 + .4 * math.sin(2*math.pi*3*t))
            v += .04 * r * (math.sin(2*math.pi*880*t) + math.sin(2*math.pi*883.5*t) + .6*math.sin(2*math.pi*1318.5*t))
        buf[i] += v
add(22.8, thump(34, 2.2, 1.8, .8), 1.2)
for i in range(N):
    t = i / SR
    if t > DUR - 1.0: buf[i] *= max(0, (DUR - t) / 1.0)
pk = max(abs(x) for x in buf) or 1
with wave.open(sys.argv[1], 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(30000 * math.tanh(1.4 * x / pk))) for x in buf))
