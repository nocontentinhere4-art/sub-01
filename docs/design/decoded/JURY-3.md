# SUB-01 (local build): jury score, round 3

Estimate, not affiliated with Awwwards. Independent critic (a fresh agent, never the earlier ones, that saw only the crawl
screenshots and the audit, never the code, the brief or the earlier cards), from 6 pages plus the 404 on 2026-11-03 (early),
crawled from the demo server at http://localhost:8799 with the /jury skill, the intro flag preset (desktop 1440, a phone at
390 throttled to 4× CPU and slow 4G, reduced motion, keyboard focus, hover pairs, page transitions). Scored after the two
look passes (Geist, sentence case, the design skill's values) and the live-page removals.

**The idea, as the critic read it:** a round-the-clock stream of a fictional man in a small Tokyo room whose behaviour is
driven by a brain-activity model built from one person's MRI data; you watch his room and his glowing brain, read the
readouts, and send him messages that move them. (Matches the brief.)

**Critic overall: 6.9** (0.4 Design + 0.3 Usability + 0.2 Creativity + 0.1 Content, on the critic's strict scale); round 2 was 7.3, round 1 6.4
**Jury estimate: about 8.0** (critic + 1.1, the offset measured on two recent Sites of the Day)
**Band, from the estimate:** Site of the Day range (7.2 and up)

Different critics differ by a few tenths; the three rounds agree on the shape: Creativity and Content high, Usability held
down by the phone, Design by the two empty pages and the phone compositions.

| Criterion | Round 1 | Round 2 | Round 3 | Evidence (round 3) |
|---|---|---|---|---|
| Design (40%) | 7 | 7.5 | 7 | brain/d-01 one composed frame; room/d-01 memorable; about an editorial system; the 404 in voice. Against: diary and sees are near-black screens with a ghost brain and two lines; brain/m-01 floats the brain in 1100 px of black with the headline below; room/m-01 a cropped poster under a loading pill; the 1m control text-colour only; the copy button no visible hover. |
| Usability (30%) | 5 | 6.5 | 6 | Nav pill, skip link first, focus rings, no overflow, the 404's way back. Against: the room never finishes on the throttled phone (loadMs 52.6 s), the home room card loads for the whole capture (61.6 s), brain phone LCP 3.5 s, small targets, diary and sees dead ends. |
| Creativity (20%) | 7 | 8 | 8 | The concept drives every populated page: the readout rail, the view toggles, the vote bar and reactions, "Send him a message" into a reaction card. "A live fictional person run by a brain model with falsifiable numbers is not something reviewers saw this month." Short of 9 for the empty pages. |
| Content (10%) | 7 | 7.5 | 7 | about specific and honest, negative results kept; every live headline a model state. Against: the empty states; the contract address with no sentence of context; the repeated sentence, the long descriptions, the em dashes. |

| Developer | R1 | R2 | R3 | Evidence (round 3) |
|---|---|---|---|---|
| Semantics/SEO | 4 | 6 | 7 | 0 FAIL; unique titles; against: the 404's h1 only after JS, descriptions of 173 characters, thin diary and sees. |
| Animations/Transitions | 5 | 6 | 6 | Pill-fill nav hovers and the send lift are real; against: each return to home restarts the scene (the captures catch the fill), the copy button without a visible hover, the 1m control colour only. |
| Accessibility | 4 | 7.5 | 7 | axe 0 on all pages, skip link first, focus visible; against: one invisible focus on about (a link in the credits), one hidden text under reduced motion on brain, the live chart still redrawing under reduced motion, the 404 without the shell. |
| WPO | 4 | 6 | 6 | CLS ≤ 0.044, brain 495 KB; against: brain phone LCP 3.5 s on the poster, the two scene pages past a minute on the throttled phone. |
| Responsive | 5 | 7 | 6 | No overflow, home and about stack cleanly; against: the room's phone crop, the brain's empty first screen, small targets. |
| Markup/Meta-data | 3 | 6 | 7 | 0 FAIL; against: two home images without dimensions, grey captions flagged for contrast review. |

## Fixes, most score first (the critic's list, 3 November)
1. [Usability · Responsive · WPO] The room on a throttled phone: make the poster the phone view (fitted to 390 px, not the
   desktop crop), drop the loading pill after 3 s, swap in GL only when ready.
2. [Usability · WPO] The home room card on phones: the room poster from HTML until the embed is ready, so the card and
   the LCP are the same thing.
3. [Content · Design] Diary and sees: show the last entry or frame with its time and the countdown, or take them out of
   the nav until they have content. (On the live site both have content; the demo server has none, which is what the
   critic saw.)
4. [Animations] Each return to home restarts the scene: keep the shell and seed the panels from the last known state.
5. [Animations · Design] The copy button's hover and the 1m/5m/15m control as a segmented control with the sliding thumb.
6. [WPO] The brain poster on phones: preload, a 390 px variant.
7. [Responsive] brain/m-01: the headline and the readout row above the brain, the canvas capped at about 60 vw.
8. [Responsive · Accessibility] Targets under 24 px on about, home and room; the focus ring on the credits link.
9. [Content] One sentence of context on the contract address section; the repeated sentence; the descriptions; the dashes.
10. [Semantics · Accessibility] The 404 with its h1 server-side and the nav shell.
11. [Accessibility] Reduced motion: the live chart per tick, the headline swap without its animation.
12. [Accessibility] The grey mono captions lifted toward 4.5:1.

## Measured (from shots/summary.json and the audit)
Desktop FPS 74–121 (brain 74). Phone LCP: home 2.3 s, brain 3.5 s, room 1.0 s, diary 2.4 s, sees 2.5 s, about 0.7 s.
Phone CLS ≤ 0.044. Phone load: home 61.6 s, room 52.6 s (software GL, 4× CPU, slow 4G; the 1.85 MB phone model alone
takes about 37 s on slow 4G). axe serious 0 everywhere. Overflow none. noHoverChange 0 on every page but about (1).
Audit: 0 FAIL, 11 WARN. One page error counted on brain in a context the crawler does not keep.

Not scored: how the brain fibres, the room camera and the readout strip move, sound, the chat flow, the real-phone feel.
