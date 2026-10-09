# Room page, simplified (G24, on preview/interactive)

- **Header:** "SUB-01" + nav, one status line (dot · pill · Tokyo time · where), one "is …" line (18 px desktop / 15 px phone). The why-line and the day plan sit behind a "today ▾" toggle, a popover that doesn't change the header's height, so `hudBand()` stays correct.
- **Panel:** one glass panel (340 px, right) with tabs Vote (default, time left in its tab) · Chat (a dot for new lines) · Teach · More. More holds the screen/chess card, music, reading, the memory test, body, map and the footnote, each collapsible by tapping its label. The tab is remembered per viewer (localStorage).
- **Reactions and brain:** a pill at the bottom centre of the room (6 emoji + "N watching", 44 px taps). The brain is a round 72 px thumbnail, bottom-left, linking to /brain; it's hidden on phones.
- **Phones (≤ 900 px):** the room at 56 vh with the header on a gradient; the pill on the room's bottom edge; the tabs as a sticky segmented control with their content below. The chat input is fixed at the bottom only on the Chat tab. No horizontal scroll at 390 px.
- **Choices made here:** every element id and all JS are kept (cards moved, not renamed), with one card style and one 12 px radius. Checks before the first push: no console errors (desktop, 390 px); test_interactive, test_desk_states, test_char_mixamo: 24 passed; smoke OK. tests/visual/test_phone_camera: **6 passed** with the new header (`hudBand()` reads `#top`; the today popover is absolutely positioned and doesn't change its height). No console errors on any tab at 1280×800 or 390×844, and no horizontal scroll.

- **360 px:** checked on the Vote, Chat and More tabs: no horizontal scroll, no console errors. The reactions pill fits with its viewer count (34 px emoji below 380 px). More draws a divider only between sections that are shown.
- **Polish (after e79f243):**
  - Phones: the reactions pill is fixed at the bottom of the screen on every tab, above the chat input on Chat. It used to sit at the room's edge and scrolled away with the page. The panes leave room under it.
  - The vote explainer is one line, "The winner nudges what he does next · how it works ▾", with the full rule behind the fold.
  - Checked at 390 and 360 px on Vote, Teach and Chat, at the top and scrolled: no horizontal scroll, no errors.

## v2 (owner's feedback: nothing over the room, much less below)
- A slim solid bar **above** the room: SUB-01 + nav + "today ▾" on one line, the status line, then "is …" on one line with an ellipsis. The empty-room note is a small line in the bar. The camera chip and the room's vignette are gone. The room canvas starts under the bar (`--barh`, measured), so `hudBand()` reads 1.
- `frameHim()` keeps a 10% margin round him (`FRAME_PAD`). The old header over the room used to add it; without it, the get-up from bed was 0.79 in frame (min 0.8).
- Phones: the bar, the room (55vh), the reactions pill, one compact vote card ("What next?", time left, 3 short rows, "one vote each"), and a fixed bottom chat bar. Its ••• opens a sheet with Chat history · Teach · More. No tab row.
- Desktop keeps the tabbed panel under the bar; the vote explainer is gone there too.
- Checked at 1280, 430, 390 and 360: no horizontal scroll, no console errors. test_interactive, test_desk_states, test_char_mixamo: 24 passed; smoke OK; test_phone_camera: 6 passed.
