/* "Twin" panel shared by the brain page (index.html) and the life page (life.html).
   Fed with the `twin` object of every tick message of live_server.py. No external requests. Texts that come from
   chat (memory messages) are only ever set with textContent. */
(function () {
  const WHAT = "a digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the person";
  const CSS = `
  .twin { font-size:12px; }
  .twin .tw-what { color:var(--fg); opacity:.85; font-size:11px; line-height:1.35; margin-bottom:8px; }
  .twin .tw-score { border:1px solid #2a2a36; border-radius:3px; padding:6px 8px; margin-bottom:8px; }
  .twin .tw-score b { font-weight:normal; color:var(--fg); }
  .twin .tw-label { color:var(--dim); font-size:11px; margin-top:3px; line-height:1.35; }
  .twin .tw-row { display:flex; align-items:center; gap:8px; margin:3px 0; }
  .twin .tw-row > span:first-child { width:92px; color:var(--dim); flex:none; }
  .twin .tw-track { position:relative; flex:1; height:6px; background:#15151d; border-radius:3px; overflow:hidden; }
  .twin .tw-fill { height:100%; width:0; background:linear-gradient(90deg,#3a4a9a,#4cc9f0); transition:width .4s; }
  .twin .tw-fill.p { background:linear-gradient(90deg,#4cc9f0,#ff4d6d); }
  .twin .tw-mark { position:absolute; left:50%; top:0; bottom:0; width:1px; background:#55556a; }
  .twin .tw-val { width:34px; text-align:right; color:var(--fg); flex:none; }
  .twin .tw-vit { color:var(--dim); margin:6px 0 2px; line-height:1.5; }
  .twin .tw-vit b { font-weight:normal; color:var(--fg); }
  .twin .tw-sub { color:var(--dim); font-size:11px; margin:8px 0 2px; letter-spacing:.08em; text-transform:uppercase; }
  .twin .tw-mem { padding:3px 0; border-bottom:1px solid #111118; color:var(--fg); word-wrap:break-word; }
  .twin .tw-mem small { display:block; color:var(--dim); font-size:10px; }
  .twin .tw-none { color:#55556a; }
  .twin .tw-drift { color:var(--dim); margin-top:6px; }
  .twin .tw-drift b { font-weight:normal; color:var(--fg); }
  `;
  const LEVELS = [["DA", "dopamine"], ["5HT", "serotonin"], ["NE", "noradrenaline"], ["ACh", "acetylcholine"]];

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

  function mount(host) {
    const st = document.createElement("style");
    st.textContent = CSS;
    document.head.append(st);
    const box = el("div", "twin");
    box.append(el("div", "tw-what", WHAT));
    // held-out similarity score and its honest label (web/twin_score.json via the tick message)
    const score = el("div", "tw-score"), scoreTop = el("div", "", "held-out similarity: –"), label = el("div", "tw-label");
    score.append(scoreTop, label);
    box.append(score);
    // neuromodulators (1.0 = resting wake, the tick on each bar)
    box.append(el("div", "tw-sub", "Neuromodulators (model levels)"));
    const lv = {};
    for (const [k, name] of LEVELS) { lv[k] = row(name, "mark"); lv[k].row.title = `${name}: 1.0 is the resting-wake level`; box.append(lv[k].row); }
    // vitals
    box.append(el("div", "tw-sub", "Body model"));
    const vit = el("div", "tw-vit");
    box.append(vit);
    const sleep = row("sleep pressure", null, "p");
    box.append(sleep.row);
    const sleepNote = el("div", "tw-vit");
    box.append(sleepNote);
    // memories
    box.append(el("div", "tw-sub", "Memories (one per night, REM)"));
    const memHead = el("div", "tw-vit", "memories: 0"), memList = el("div");
    box.append(memHead, memList);
    const drift = el("div", "tw-drift");
    box.append(drift);
    host.append(box);

    let memKey = "", scoreKey = "";
    function update(tw) {
      if (!tw) return;
      const sc = tw.score || {}, k1 = JSON.stringify(sc);
      if (k1 !== scoreKey) {
        scoreKey = k1;
        const fc = typeof sc.fc_r === "number" ? sc.fc_r.toFixed(2) : "–", ks = typeof sc.fcd_ks === "number" ? sc.fcd_ks.toFixed(2) : "–";
        scoreTop.replaceChildren(document.createTextNode("held-out similarity to recorded fMRI: "), el("b", "", `r = ${fc}`),
          document.createTextNode(` (static functional connectivity, ${sc.n_runs || "?"} runs the model never saw) · dynamics distance ${ks}`));
        scoreTop.title = typeof sc.ceiling_r === "number" ? `recorded runs of the same person agree with each other at r = ${sc.ceiling_r}` : "";
        label.textContent = (sc.label || "") + (sc.label && !/weak/i.test(sc.label) ? " (weak static match)" : "");
      }
      for (const [k] of LEVELS) {
        const v = (tw.levels || {})[k];
        if (typeof v !== "number") continue;
        lv[k].fill.style.width = Math.max(0, Math.min(100, v / 2 * 100)) + "%";
        lv[k].val.textContent = v.toFixed(2);
      }
      const v = tw.vitals || {};
      vit.replaceChildren(document.createTextNode("heart "), el("b", "", `${Math.round(v.hr_bpm)} bpm`),
        document.createTextNode(" · breathing "), el("b", "", `${(+v.resp_per_min).toFixed(1)}/min`),
        document.createTextNode(" · glucose "), el("b", "", `${Math.round(v.glucose_mg_dl)} mg/dl`),
        document.createTextNode(" · hunger "), el("b", "", (+v.hunger).toFixed(2)));
      const s = tw.sleep || {};
      sleep.fill.style.width = Math.max(0, Math.min(100, (s.pressure || 0) * 100)) + "%";
      sleep.val.textContent = (s.pressure || 0).toFixed(2);
      sleepNote.textContent = `homeostatic H ${s.H}, circadian C ${s.C}`;
      const m = tw.memories || {count: 0, last: []}, key = m.count + ":" + (m.last.length ? m.last[m.last.length - 1].sha256 : "");
      if (key !== memKey) {
        memKey = key;
        memHead.textContent = `memories: ${m.count}`;
        memList.replaceChildren();
        if (!m.last.length) memList.append(el("div", "tw-none", "none yet: a night with at least one chat message makes one"));
        for (const x of m.last.slice().reverse()) {
          const d = el("div", "tw-mem", `memory #${x.n} “${x.message}”`);
          d.append(el("small", "", `night of ${x.day} · weights sha256 ${x.sha256}…`));
          memList.append(d);
        }
      }
      const dr = tw.drift || {};
      drift.replaceChildren(document.createTextNode("drift from the original connectome: "),
        el("b", "", `${((dr.rel_frobenius || 0) * 100).toPrecision(2)} %`), document.createTextNode(` (${dr.edges_changed || 0} edges changed)`));
    }
    return {update};
  }
  window.TwinPanel = {mount, WHAT};
})();
