# What is licensed how

The MIT licence in `LICENSE` grants the code and the documentation only. The data and the assets listed below keep their
own terms; some are not covered by any licence yet and are not granted by `LICENSE`.

The MIT licence in `LICENSE` covers the code (the Python, the JavaScript, the HTML and CSS) and the documentation.
Everything else in the repository comes from somewhere, and keeps its own terms. The full credits with every paper
and author are on the site at `/about.html` (section 05) and in `web/room/CREDITS.md`.

| What | Where | Licence |
|---|---|---|
| The MRI data the model is built from (wiring, cortex, resting state) | derived files in `out/`, `web/*.bin`, `web/anatomy/` | PDDL (public domain): the MyConnectome project, OpenNeuro ds000031, Poldrack RA et al. (2015) |
| Receptor densities | `twin/data/` | CC BY 4.0: Zilles K & Palomero-Gallagher N (2017) |
| Neuron shapes (the close ups and the whole brain neuron view) | `web/neurons_morph.json`, `web/column_morph.json` | CC BY 4.0: NeuroMorpho.Org (RRID:SCR_002145) and the papers listed on `/about.html` |
| Arteries, nerves, pituitary and the spinal cord stub in the specimen views | `web/anatomy/` | CC BY 4.0: BodyParts3D, The Database Center for Life Science |
| The map and the routes | `web/tokyo_area.json` | ODbL: © OpenStreetMap contributors |
| Articles shown on the site | fetched at run time | CC BY-SA: Wikipedia and its authors |
| The 3D room, its textures and props | `web/room/room_clean.glb`, `web/room/room_phone.glb`, `web/room/props_*.glb` | CC0: modelled for this project, with Poly Haven assets (CC0 1.0); see `web/room/CREDITS.md` |
| The fonts | `web/fonts/` | SIL Open Font License 1.1: Geist and Geist Mono (Vercel) |
| The 3D character and the hand | `web/room/boy*.glb`, `web/room/char_*.glb`, `web/room/hand_phone.glb` | **Not covered.** Made for this project with Higgsfield and Meshy; the terms are not confirmed yet. You may run the repository with them, but do not redistribute them on their own until this line changes. |
| Screenshots and renders in `docs/` | `docs/readme/`, `docs/design/` | MIT, as documentation, except where they show the character (see the line above) |

The scanned person is credited on `/about.html` only, by the project's rule, and is not named anywhere else. Nothing
in this repository identifies them beyond the public dataset's own documentation.
