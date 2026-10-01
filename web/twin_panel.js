/* "Twin" panel shared by the brain page (index.html) and the life page (life.html).
   Fed with the `twin` object of every tick message of live_server.py. No external requests. Texts that come from
   chat (memory messages) are only ever set with textContent. Wording: plain words for a non-expert, no overstatement. */
(function () {
  const WHAT = "a digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the person";
  const CSS = `
  .twin { font-size:12px; }
  .twin .tw-what { color:var(--fg); opacity:.85; font-size:11px; line-height:1.35; margin-bottom:8px; }
  .twin .tw-score { border:1px solid #2a2a36; border-radius:3px; padding:6px 8px; margin-bottom:8px; line-height:1.4; }
  .twin .tw-score b { font-weight:normal; color:var(--fg); }
  .twin .tw-label { color:var(--dim); font-size:11px; margin-top:4px; line-height:1.35; }
  .twin .tw-row { display:flex; align-items:center; gap:8px; margin:3px 0; }
  .twin .tw-row > span:first-child { width:92px; color:var(--dim); flex:none; }
  .twin .tw-track { position:relative; flex:1; height:6px; background:#15151d; border-radius:3px; overflow:hidden; }
  .twin .tw-fill { height:100%; width:0; background:linear-gradient(90deg,#3a4a9a,#4cc9f0); transition:width .4s; }
  .twin .tw-fill.p { background:linear-gradient(90deg,#4cc9f0,#ff4d6d); }
  .twin .tw-mark { position:absolute; left:50%; top:0; bottom:0; width:1px; background:#55556a; }
  .twin .tw-val { width:34px; text-align:right; color:var(--fg); flex:none; }
  .twin .tw-vit { color:var(--dim); margin:6px 0 2px; line-height:1.5; }
  .twin .tw-vit b { font-weight:normal; color:var(--fg); }
  .twin .tw-sub { color:var(--dim); font-size:11px; margin:10px 0 2px; letter-spacing:.08em; text-transform:uppercase; }
  .twin .tw-hint { color:#55556a; font-size:10px; line-height:1.35; margin:0 0 4px; }
  .twin .tw-mem { padding:3px 0; border-bottom:1px solid #111118; color:var(--fg); word-wrap:break-word; }
  .twin .tw-mem small { display:block; color:var(--dim); font-size:10px; }
  .twin .tw-none { color:#55556a; }
  .twin .tw-drift { color:var(--dim); margin-top:8px; line-height:1.4; }
  .twin .tw-drift b { font-weight:normal; color:var(--fg); }
  `;
  const LEVELS = [["DA", "dopamine", "reward and drive; rises with trades and messages"],
                  ["5HT", "serotonin", "mood and calm; low in dream (REM) sleep"],
                  ["NE", "noradrenaline", "alertness and stress; falls in sleep"],
                  ["ACh", "acetylcholine", "attention; high awake and in dream (REM) sleep"]];
  const LEVEL_HINT = "Simulated levels, not measured in anyone. The tick = 1.0, the resting-wake level; 0 to 2 on the bar. " +
    "They follow the sleep model and the stimuli, and change how strongly each region reacts.";

  function el(tag, cls, text) {
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text !== undefined) x.textContent = text;
    return x;
  }
  function row(label, track, cls) {
    const r = el("div", "tw-row"), t = el("div", "tw-track"), f = el("div", "tw-fill" + (cls ? " " + cls : "")), v = el("span", "tw-val", "–");
    t.append(f);
    if (track === "mark") t.append(el("div", "tw-mark"));
    r.append(el("span", "", label), t, v);
    return {row: r, fill: f, val: v};
  }
  function sub(text, title) {
    const s = el("div", "tw-sub", text);
    if (title) s.title = title;
    return s;
  }

  function mount(host) {
    const st = document.createElement("style");
    st.textContent = CSS;
    document.head.append(st);
    const box = el("div", "twin");
    const what = el("div", "tw-what", WHAT);
    what.title = "Built from one person's public MRI scans (structure) and fMRI recordings (activity). It simulates; it does not think or feel, and it is not the person.";
    box.append(what);
    // held-out similarity score and its honest label (web/twin_score.json via the tick message)
    const score = el("div", "tw-score"), scoreTop = el("div", "", "How close to the real recordings? –"), label = el("div", "tw-label");
    score.append(scoreTop, label);
    box.append(score);
    // neuromodulators (1.0 = resting wake, the tick on each bar)
    box.append(sub("Neuromodulators · simulated, tick = resting wake", LEVEL_HINT));
    const lv = {};
    for (const [k, name, what] of LEVELS) {
      lv[k] = row(name, "mark");
      lv[k].row.title = `${name} (${k}): ${what}. Simulated level, 1.0 = resting wake; not a measurement.`;
      box.append(lv[k].row);
    }
    // vitals
    box.append(sub("Body · simulated, not the person's", "A small textbook body model (heart, breathing, blood sugar, hunger) that reacts to the brain model and feeds back into it. Nothing here is measured on a person."));
    const vit = el("div", "tw-vit");
    vit.title = "heart rate in beats per minute · breaths per minute · blood glucose in mg/dl · hunger on a 0 (full) to 1 (very hungry) scale";
    box.append(vit);
    const sleep = row("sleep pressure", null, "p");
    sleep.row.title = "Simulated need for sleep, 0 to 1: builds up while awake, is paid off while asleep. It decides when the model falls asleep and wakes.";
    box.append(sleep.row);
    const sleepNote = el("div", "tw-vit");
    sleepNote.title = "H: the sleep need built up so far (model units). C: the body-clock drive, 0 to 1, highest in the late afternoon.";
    box.append(sleepNote);
    // memories
    box.append(sub("Memories · at most one per night", "A memory here is a small change of the model's wiring, made once per night during dream (REM) sleep. It is not a recollection and nothing is stored in words."));
    box.append(el("div", "tw-hint", "A memory = a small strengthening (1 % at most), during dream (REM) sleep, of the connections among the regions that reacted most to the day's strongest message. Not a recollection."));
    const memHead = el("div", "tw-vit", "memories so far: 0"), memList = el("div");
    box.append(memHead, memList);
    const drift = el("div", "tw-drift");
    drift.title = "How far the simulated connection weights have moved from the connectome traced from the MRI scan (relative Frobenius norm of the difference). Changes are capped at 5 % per connection and 2 % overall.";
    box.append(drift);
    host.append(box);

    let memKey = "", scoreKey = "";
    function update(tw) {
      if (!tw) return;
      const sc = tw.score || {}, k1 = JSON.stringify(sc);
      if (k1 !== scoreKey) {
        scoreKey = k1;
        const fc = typeof sc.fc_r === "number" ? sc.fc_r.toFixed(2) : "–", ks = typeof sc.fcd_ks === "number" ? sc.fcd_ks.toFixed(2) : "–";
        const ceil = typeof sc.ceiling_r === "number" ? sc.ceiling_r.toFixed(2) : null;
        const how = typeof sc.fc_r === "number" && sc.fc_r < 0.05 ? "no match" : "a weak match";
        scoreTop.replaceChildren(
          document.createTextNode("How close to the real recordings? "),
          el("b", "", `r = ${fc}`),
          document.createTextNode(` on ${sc.n_runs || "?"} fMRI runs the model never saw (0 = no match, 1 = identical).` +
            (ceil ? ` The two halves of the person's own recordings agree at r = ${ceil}, so this is ${how}.` : ` ${how[0].toUpperCase()}${how.slice(1)}.`) +
            (typeof sc.fcd_ks === "number" && sc.fcd_ks >= 0.3
              ? ` How the pattern changes over time does not match either: distance ${ks} (0 same, 1 unrelated).`
              : ` How the pattern changes over time matches better: distance ${ks} (0 same, 1 unrelated).`)));
        scoreTop.title = "r is the correlation between which regions rise and fall together in the model and in the recordings. Static match (correlation of functional connectivity, FC) and dynamics match (Kolmogorov-Smirnov distance between FC-dynamics distributions, FCD), both on held-out recordings: sessions the fit never saw. Measured with all neuromodulator levels at 1.0 and the original weights, without the recorded-session replay.";
        label.textContent = "source: " + (sc.label || "") + (sc.label && !/weak|no static/i.test(sc.label) ? " (weak static match)" : "");
      }
      for (const [k] of LEVELS) {
        const v = (tw.levels || {})[k];
        if (typeof v !== "number") continue;
        lv[k].fill.style.width = Math.max(0, Math.min(100, v / 2 * 100)) + "%";
        lv[k].val.textContent = v.toFixed(2);
      }
      const v = tw.vitals || {};
      vit.replaceChildren(document.createTextNode("heart "), el("b", "", `${Math.round(v.hr_bpm)} bpm`),
        document.createTextNode(" · breathing "), el("b", "", `${(+v.resp_per_min).toFixed(1)} /min`),
        document.createTextNode(" · blood sugar "), el("b", "", `${Math.round(v.glucose_mg_dl)} mg/dl`),
        document.createTextNode(" · hunger "), el("b", "", (+v.hunger).toFixed(2)));
      const s = tw.sleep || {};
      sleep.fill.style.width = Math.max(0, Math.min(100, (s.pressure || 0) * 100)) + "%";
      sleep.val.textContent = (s.pressure || 0).toFixed(2);
      sleepNote.textContent = `sleep need built up (H) ${s.H} · body-clock drive (C) ${s.C}`;
      const m = tw.memories || {count: 0, last: []}, key = m.count + ":" + (m.last.length ? m.last[m.last.length - 1].sha256 : "");
      if (key !== memKey) {
        memKey = key;
        memHead.textContent = `memories so far: ${m.count}`;
        memList.replaceChildren();
        if (!m.last.length) memList.append(el("div", "tw-none", "none yet: the first night after at least one chat message makes one"));
        for (const x of m.last.slice().reverse()) {
          const d = el("div", "tw-mem", `#${x.n} · strongest message of the day: “${x.message}”`);
          d.append(el("small", "", `night of ${x.day} · fingerprint of the wiring after the change (sha256): ${x.sha256}…`));
          d.title = "The quoted text is the chat message the model reacted to most that day. The fingerprint is a hash of all connection weights after the change, so anyone can check the weights were not edited afterwards.";
          memList.append(d);
        }
      }
      const dr = tw.drift || {};
      drift.replaceChildren(document.createTextNode("wiring drift from the scanned original: "),
        el("b", "", `${((dr.rel_frobenius || 0) * 100).toPrecision(2)} %`),
        document.createTextNode(` of the connection weights, ${dr.edges_changed || 0} connections touched (no new ones)`));
    }
    return {update};
  }
  window.TwinPanel = {mount, WHAT};
})();
