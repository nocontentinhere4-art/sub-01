# SUB-01 (local build): jury score, round 2

Estimate, not affiliated with Awwwards. Independent critic (a fresh agent, never the first one, that saw only the crawl
screenshots and the audit, never the code, the brief or JURY-1), from 6 pages plus the 404 on 2026-11-02 (evening), crawled
from the demo server at http://localhost:8799 with the /jury skill with the intro flag preset (`--init`), so the critic
scored the dashboard this time (desktop 1440, a phone at 390 throttled to 4× CPU and slow 4G, reduced motion, keyboard
focus, hover pairs, page transitions). Scored after the jury fix round, the owner's removals and the v3 controls (commits
7220a8e … 105aeff).

**The idea, as the critic read it:** a round-the-clock live stream of an invented man in a small Tokyo room, whose sleep,
reading, diary and chat replies are driven by a brain model built from one real person's open MRI data, with "a model,
not a mind" on every page. (Matches the brief.)

**Critic overall: 7.3** (0.4 Design + 0.3 Usability + 0.2 Creativity + 0.1 Content, on the critic's strict scale); round 1 was 6.4
**Jury estimate: about 8.4** (critic + 1.1, the offset measured on two recent Sites of the Day); round 1 about 7.5
**Band, from the estimate:** Site of the Day range (7.2 and up), now above the two measured winners (7.24 and 7.28)

| Criterion | Round 1 | Round 2 | Evidence (round 2) |
|---|---|---|---|
| Design (40%) | 7 | 7.5 | brain/d-01: the fibre brain with the axis ticks, the mono rail, the display headline: works as a poster. room/d-01 composed; about d-01..d-07 an editorial system; the 404 in voice; the readout strip a signature on every page. Against: room m-01..m-06 text over the busy scene with no scrim and the loader pill in every frame; diary/sees a sentence in a full viewport; the active nav pill and the active "wires" toggle give no hover; the home title dims on a page that does not scroll. |
| Usability (30%) | 5 | 6.5 | Desktop LCP 60–536 ms, 119–120 fps; skip link first and a visible ring on every page; axe 0; no overflow; home and about composed for the phone. Against: the 3D room never arrives on the throttled phone (room loadMs 51.5 s, home 59.1 s, the loader pill in every m- frame); brain phone LCP 2.8 s; small targets (the 1m/5m/15m buttons 35×17, inline links 19–20 px); the active nav link answers nothing on hover. |
| Creativity (20%) | 7 | 8 | One idea carried through every page: the live readouts, the neuromodulator rail, the room cam with "camera: follows him" and the vote bar, the dream diary after REM, "what it sees", messages as stimuli. The brain page a true signature moment. Held: the home is a conventional stream-dashboard grid; two concept pages still empty frames in the capture. |
| Content (10%) | 7 | 7.5 | about: real substance with voice, negative results shown and labelled, sources as file paths, licences marked not stated; specific microcopy on home; the 404 in voice. Against: diary and sees 53 and 52 words (empty states); a sentence repeated twice on about; em dashes; the contract address block after the scientific credits breaks the register (it stays: the owner's rule is the address line on /about.html and nowhere else). |

| Developer | Round 1 | Round 2 | Evidence (round 2) |
|---|---|---|---|
| Semantics/SEO | 4 | 6 | Unique titles, one h1 per page, descriptions and canonicals. Against: 2 FAIL, the two template-literal links in served HTML; descriptions of 173 characters on diary and about; the 404's h1 only after JS. |
| Animations/Transitions | 5 | 6 | Real treatments now: the send button's transform, pill fills, the draw-in underline, the emoji brightness, a tooltip on the camera button; idle motion on four pages; 120 fps. Against: the transition frames show a hard navigation with blank panels (the crossfade is cross-document and the captures catch the fill); the active nav pill and the active toggle give no hover; "1m" colour only. |
| Accessibility | 4 | 7.5 | axe 0 on all 9 captures; skip link first on the 6 pages; clear focus rings; nothing moving under reduced motion. Against: one text hidden under reduced motion on brain (a `.ui-in` entrance); dim secondary labels flagged for review; the 404 without the skip link first. |
| WPO | 4 | 6 | Brain 356 KB, JS 214 KB gzipped, CSS 8 KB; CLS ≤ 0.035 everywhere (home 0.007, was 0.607); phone LCP home 1.7 s, room 0.8 s, about 0.6 s. Against: brain phone LCP 2.8 s on the poster; the room scene 51–59 s on the throttled phone with the loader pill on screen. |
| Responsive | 5 | 7 | No overflow on any page; the phone header in two clean rows with LIVE top right; home, brain, about, diary, sees composed at 390. Against: room's text over the scene; small targets on home, room and about. |
| Markup/Meta-data | 3 | 6 | OG, Twitter, favicon, viewport and alt all pass; per-page titles and descriptions. Against: the two template-literal hrefs; two home images without width/height. |

## Fixes, most score first (the critic's list, 2 November evening)
1. [Usability · WPO · Responsive] The 3D room on a throttled phone: ship the still (now the poster) and keep it when the GLB has not arrived by 2.6 s; a Draco or meshopt room GLB under 2 MB on tap under 768 px (still open: no asset tooling here).
2. [Animations · Design] Hard navigation in the transition frames: keep the shell persistent and crossfade only the main panel, and seed the NOW, UP NEXT and readouts from the last known state so nothing blanks (the last-seen values already exist on the live page; extend them to brain and room).
3. [Animations · Design] Hover on the active nav pill and the active toggle: a 1 px lift and a brighter pill; a sliding thumb behind the live page's 1m/5m/15m control (it is a page-own control, not `.ui-seg`) and behind the multi-choice wires/surface/areas control.
4. [SEO · Markup] The two template-literal links: move the templates out of the served HTML (a `<template>` or a script block).
5. [WPO] The brain poster on phones: preload with fetchpriority high, a 780 px AVIF, width/height (the width/height is set; the preload and the small variant are not).
6. [Design · Responsive] The room on phones: a top scrim under the text block or the text stacked below the scene under 480 px; a sleeping-state poster while the GLB loads.
7. [Responsive] Targets under 24 px: the live page's time buttons to 28 px, the footer about link padded, the credits' inline links a larger line-height.
8. [Content · Design] Diary and sees empty states: keep the last entry or frame visible when stale, the countdown (now there, from the Tokyo clock), a strip of past entries.
9. [Accessibility] Secondary grey labels flagged for contrast review on brain, home and room: raise toward 4.5:1 on the ground they sit on.
10. [SEO · Markup] Descriptions under 155 characters on diary and about; the 404 markup with its h1 server-side; width/height on the two home images.
11. [Accessibility] The one `.ui-in` text hidden under reduced motion on brain: resolve the entrance to opacity 1 there.
12. [Content] One of the two identical "It is a model, not a mind." sentences on about; the em dashes rewritten. (The contract address stays where it is: owner's rule.)
13. [Design] The home title's scroll fade guarded behind scrollY > 40 so it does not dim on a non-scrolling page.

## Measured (from shots/summary.json and the audit)
Desktop FPS 89–120; phone FPS 120. Phone LCP: home 1.7 s, brain 2.8 s, room 0.8 s, diary 1.5 s, sees 1.6 s, about 0.6 s.
Phone CLS: home 0.007, brain 0.008, room 0.035, others 0. Page errors 0 on every real page. axe serious 0 everywhere.
Overflow none. Skip link first on all six pages. noHoverChange 1 per page (the active nav link); colorOnly 2–4.
Idle motion on live, brain, room, about. Audit: 2 FAIL (the template-literal links), 11 WARN (was 8 FAIL, 55 WARN at round 1).

Not scored: how the brain fibres, the room camera and the readout strip move, sound, the chat flow. The v3 controls
(the light round a hovered pill, the sliding thumb and nav pill, the panel light, the magnetic primary, tooltips, the
toast, the send state) were verified headlessly after this crawl's hover pairs were taken; only the pairs the crawler
happened to pick show them.

## Re-scoring
Run the /jury skill again with a NEW critic after fixes 1–4, with the intro flag preset; rename this file to JURY-2.md
(it already is) and write JURY-3.md with the change per category.
