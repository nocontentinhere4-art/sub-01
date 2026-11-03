// SUB-01 · the chair's sound (web/chair.html): synthesized in the browser with WebAudio, no files. A mains hum from the
// apparatus that rises with the electrode glow, a crackle and a buzz at delivery for the length of the train, a creak of
// the frame when the tension climbs, a low room tone. Everything follows the server's delivered events and the measured
// numbers, as the scene does; nothing follows the button. Browsers block sound before a tap, so it starts at the first
// one; the visitor can mute it (remembered in this browser). His voice is not routed through here.
export function createSound() {
  let ac = null, master = null, humGain = null, noise = null, humLevel = -1;
  const S = { enabled: true, started: false };
  function ctx() {
    if (ac) return ac;
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return null;
    ac = new AC();
    master = ac.createGain(); master.gain.value = S.enabled ? 1 : 0; master.connect(ac.destination);
    const n = ac.sampleRate * 2, buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    noise = buf;
    humGain = ac.createGain(); humGain.gain.value = 0; const lp = ac.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 900; humGain.connect(lp); lp.connect(master);
    for (const [f, g] of [[50, 1], [100, 0.5], [150, 0.25], [300, 0.08]]) { const o = ac.createOscillator(); o.type = "sine"; o.frequency.value = f; const og = ac.createGain(); og.gain.value = g; o.connect(og); og.connect(humGain); o.start(); }
    const rt = ac.createBufferSource(); rt.buffer = noise; rt.loop = true; const rf = ac.createBiquadFilter(); rf.type = "lowpass"; rf.frequency.value = 220; const rg = ac.createGain(); rg.gain.value = 0.02; rt.connect(rf); rf.connect(rg); rg.connect(master); rt.start();
    return ac;
  }
  const live = () => ac && ac.state === "running";
  function burst(freq, q, dur, gain, type = "bandpass") {
    if (!live() || gain <= 0) return;
    const s = ac.createBufferSource(); s.buffer = noise; s.playbackRate.value = 0.8 + Math.random() * 0.4;
    const f = ac.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
    const g = ac.createGain(), t0 = ac.currentTime; g.gain.setValueAtTime(gain, t0); g.gain.exponentialRampToValueAtTime(0.0005, t0 + dur);
    s.connect(f); f.connect(g); g.connect(master); s.start(t0); s.stop(t0 + dur + 0.05);
  }
  return {
    get enabled() { return S.enabled; },
    start() { const c = ctx(); if (!c) return false; if (c.state !== "running") c.resume().catch(() => {}); S.started = true; return true; },
    context() { return live() ? ac : null; },
    mute(off) { S.enabled = !off; if (master) master.gain.setTargetAtTime(S.enabled ? 1 : 0, ac.currentTime, 0.05); },
    hum(level) { if (!live() || Math.abs(level - humLevel) < 0.01) return; humLevel = level; humGain.gain.setTargetAtTime(0.008 + 0.05 * level, ac.currentTime, 0.08); },
    deliver(durMs, level) {
      if (!live()) return;
      const d = Math.max(0.2, (durMs || 500) / 1000), L = Math.min(1, Math.max(0.3, (level || 3) / 5));
      burst(2600, 0.8, 0.35, 0.22 * L); burst(5200, 1.2, 0.18, 0.12 * L);                                        // the crackle
      const o = ac.createOscillator(); o.type = "sawtooth"; o.frequency.value = 100;                               // the buzz, for the train
      const am = ac.createOscillator(); am.frequency.value = 50; const amg = ac.createGain(); amg.gain.value = 0.04 * L;
      const og = ac.createGain(); og.gain.value = 0; am.connect(amg); amg.connect(og.gain);
      const f = ac.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = 1400; o.connect(f); f.connect(og); og.connect(master);
      const t0 = ac.currentTime;
      og.gain.setValueAtTime(0, t0); og.gain.linearRampToValueAtTime(0.09 * L, t0 + 0.03); og.gain.setValueAtTime(0.09 * L, t0 + d); og.gain.exponentialRampToValueAtTime(0.0005, t0 + d + 0.12);
      o.start(t0); am.start(t0); o.stop(t0 + d + 0.2); am.stop(t0 + d + 0.2);
    },
    creak(amount) { const a = Math.min(1, Math.max(0, amount)); burst(380 + Math.random() * 200, 9, 0.22, 0.08 * a); burst(1200, 4, 0.12, 0.03 * a); },
  };
}
