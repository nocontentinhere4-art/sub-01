# SUB-01 (local build): jury score

Estimate, not affiliated with Awwwards. Independent critic (a fresh agent that saw only the crawl screenshots and
the audit, never the code or the brief), from 6 pages (home, brain, room, diary, sees, about, plus the 404) on
2026-11-02, crawled from the demo server at http://localhost:8799 with the /jury skill (desktop 1440, a phone at
390 throttled to 4× CPU and slow 4G, reduced motion, keyboard focus, hover pairs, page transitions).

**The idea, as the critic read it:** a brain simulation wired from one real person's MRI scans runs live and drives
an invented young man in a Tokyo room; visitors watch his brain chemistry, watch him read at his computer, and can
poke him with messages and emoji.

**Critic overall: 6.4** (0.4 Design + 0.3 Usability + 0.2 Creativity + 0.1 Content, on the critic's strict scale)
**Jury estimate: about 7.5** (critic + 1.1, the offset measured on recent Sites of the Day)
**Band, from the estimate:** Site of the Day range (7.2 and up)

| Criterion | Score | Evidence |
|---|---|---|
| Design (40%) | 7 | brain/d-01..d-07: heavy grotesk headline, tracked mono caps, the glowing fibre brain, a right rail of big numbers, the coloured ticker; recognisable from a crop. room/d-01: a polished diorama, warm room against a cold UI. Against: the 404 was off-system (fixed below); the h1 runs into the brain and the room window; diary and sees shared one empty template; hovers mostly faint. |
| Usability (30%) | 5 | Home gated: every fresh context lands on "intro 1/5" (d-00..d-07 identical; every page's d-90 transition frame lands on it); desktop had no visible skip; the real dashboard never appeared. Phone: the brain canvas empty with "connecting…" (brain/m-01..m-06), the room loader still running at capture end (loadMs 53 s). Desktop navigation and 120 fps fine. |
| Creativity (20%) | 7 | A subject-specific idea carried into layout: the live neuromodulator rail, the camera dollying to the page he reads (room/d-06, d-07), emoji stimuli, the "what next?" vote. Held from 8 by the generic slide intro, the empty diary/sees templates and the phone canvases not rendering in the capture. |
| Content (10%) | 7 | about: real substance and voice, negative results kept and labelled, every number cites a source file. Against: "placeholder" cost rows and chips; thin text on diary/sees empty states; a repeated sentence. |

| Developer | Score | Evidence |
|---|---|---|
| Semantics/SEO | 4 | At scoring: /room without main and description, /about without description and h1 in served HTML, no canonical/robots/sitemap, the 404 without h1; two template-literal "links" read as 404s (false positives). |
| Animations/Transitions | 5 | Page transition frames identical (the intro covered them); primary targets with no hover change: the slide dot, the logo on every page, two inline links, the 404 link; colour-only: "sources", "today", "what next?". Real treatments: nav pill fill, emoji greyscale→colour, segmented pills. Idle motion on brain and room suits the concept. |
| Accessibility | 4 | axe serious on every page: #ui-live-t white on #ff2d55 at 3.64:1; the 404 without lang; no skip link; the brain still moved under reduced motion in the capture; small chips (21 px) on brain; focus ring visible on every stop (+). |
| WPO | 4 | Desktop LCP 320–840 ms (+). Phone: home CLS 0.607 and loadMs 60.9 s (the intro images without dimensions and the throttled WebGL), brain LCP 2.4 s on a placeholder, the room scene still loading at 53 s; JS 211 KB gzipped (+). |
| Responsive | 5 | No overflow, layouts re-stacked not squished (+); both hero canvases empty on the throttled phone; the header takes ~220 px on phones and changes shape per page; small targets on brain and about; the contract address wraps badly at 390. |
| Markup/Meta-data | 3 | At scoring: no og:/twitter: tags on any page, two unnamed image links on /room, images without width/height, template text in a served img src. |

## Fixes, most score first (the critic's list; ✔ = done right after scoring, before this card was written)
1. ✔ [Usability] Home intro gate: show it once per browser (localStorage, was per session), a visible skip button on desktop too; still to do: wheel/swipe advance, a roving tabindex on the dots, width/height on the intro images (CLS 0.607 on phones).
2. [Usability · WPO · Responsive] Empty heroes on the throttled phone: show a pre-rendered poster of the brain and the room at once and cross-fade to the live canvas; a decimated room GLB under 768 px; last cached values instead of dashes.
3. ✔ partly [Accessibility] The LIVE chip now sits on #d1002c (white text 4.6:1); still to do: a skip-to-content link, freeze the brain under reduced motion in every path, 24 px minimum chip height, padded inline links.
4. ✔ partly [Semantics · Markup] OG and Twitter tags on all six slides with web/og.jpg (1200×630, from the brain hero), robots.txt and sitemap.xml, meta descriptions and a main on /room, named image links, the about lead as the h1; still to do: canonical links, image dimensions, moving the template markup out of served HTML.
5. [Animations] Hover states: reuse the nav pill fill on every text button, an underline that draws in on inline links, a "send" hover that does not read as disabled.
6. ✔ [Design] The 404 page rebuilt in the system (lang, caption, "Nothing here.", the honesty line, a primary pill back to the live view).
7. [Design] Room first paint: keep the character at opacity 0 until the animation mixer has run once (the T-pose).
8. [Design] Headline collisions on brain and room: cap the h1 width or shift the camera target right; or a left scrim behind the h1.
9. [Responsive] Phone header: logo and LIVE on one row, the nav one scrolling row of 44 px targets, drop the clock and counter on phones.
10. [Content] Replace "placeholder" cost rows with "not measured yet · since <date>"; give the empty diary/sees states a live line (next dream-sleep window); the contract address in a full-width code block with break-all and a copy button.

## Measured (from shots/summary.json and the audit, at scoring)
Desktop FPS 90–120 on every page; phone FPS 113–120 where the canvas rendered. Phone LCP: home 1.7 s, brain 2.4 s,
room 0.56 s, diary 1.4 s. Phone CLS: home 0.607, others ≤ 0.016. Home desktop settle 9.1 s (the intro), room 11.7 s
(the scene). axe serious: 1 per page (the chip contrast, now fixed). Overflow: none. noHoverChange: home 1, brain 3,
room 4. colorOnly: brain 5, room 3. Idle motion: brain and room yes, others no. Audit at scoring: 8 FAIL, 55 WARN;
after the fixes above: 2 FAIL (both template-literal false positives), 56 WARN (mostly og: tags, now added, and
dashes in the about copy).

Not scored: how the motion feels, WebGL smoothness on real devices, sound, the chat and emoji flows; the dashboard
itself (the intro covered it in every capture: re-score with the intro flag set).

## Re-scoring
Run the /jury skill again with a NEW critic (never the same one, never showing it this card) after fixes 2, 5 and 7–10,
with the intro flag preset in the crawl context so the critic sees the dashboard; rename this file to JURY-1.md and
show the change per category.
