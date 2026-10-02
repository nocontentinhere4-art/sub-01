# NeuronRender: the close-up API (#88, part A ↔ part B)

`web/neuron_render/neuron_render.js` draws one region's neurons at microscopy scale: tapered tubes from the SWC
radii, a soma with a nucleus, spines, myelin with nodes of Ranvier, boutons, an out-of-focus tissue background,
bloom and a mild depth of field, in a **fluorescence** or a **3D render** style. It is a classic script
(`window.NeuronRender`, no modules, no bundler) and takes the page's `THREE` (r128 global on `/brain`, r169 module
in the room: both work; it uses nothing newer than r128).

Part B (`web/neurons3d.js`, the whole-brain forest) hands over to it when the viewer zooms into a region or presses a
close-up button, and takes back when it closes. The module owns **its own canvas**, overlaid on the container it is
given, with its own render loop, camera and orbit (drag to turn, wheel / pinch to zoom): the page's brain scene is
not drawn while a close-up is open (the page's loop should `return` while `nr` exists, as it does today).

```html
<script src="/neuron_render/neuron_render.js"></script>   <!-- after three.js; loads /neuron_render/cells.json itself -->
```

## Open / close

```js
const nr = NeuronRender.open(container, {
  THREE,                       // the page's three.js
  region: 12,                  // brain.json region index (0-213): the region whose spikes this close-up shows
  kind: "cortex",              // "cortex" | "striatum" | "thalamus" | "hippocampus" | "amygdala"
                               //   (NeuronRender.kindOf(node) gives it from a brain.json node; null = no close-up)
  label: "left Vis 13",        // the region's label for the caption
  style: "fluorescence",       // "fluorescence" (GFP green / tdTomato orange on black) | "render" (soft 3D)
  lod: "auto",                 // "auto" (by screen width and devicePixelRatio) | "phone" | "desktop"
  live: false,                 // is a spiking network live now? (updated by onFrame / setLive; see Activity)
  onClose(reason) {},          // the viewer zoomed out past the block ("zoomout") or pressed ✕ ("button")
  onInfo(info) {},             // counts changed (first build, LOD or style change): same object as nr.info()
  groupRate(msg) {},           // optional: Hz of this region's network group from a frame without n3.rq (a pod built
                               //   before #62's per-region rates); the module quantises it like quantise_rates
});
nr.close();                    // removes the canvas, frees every GPU resource, stops the loop (no onClose call)
```

`container` is a positioned element (the brain's host `div`): the module appends `<canvas class="nr">` with
`position:absolute; inset:0` and a small HUD (style toggle, ✕) in the container's corner; `nr.close()` removes
both. Nothing else on the page is touched.

## Activity (never faked)

```js
nr.onFrame(msg)                // every {"type":"spiking"} websocket frame, as received (spiking/frames.py: n3.rq, n3.sq, n3.span)
                               //   the module keeps only this region's sampled spikes (frame slot 0-255 -> a drawn cell)
                               //   and its rate byte; it goes offline by itself 10 s after the last frame
nr.spike(slot, delayMs = 0)    // alternative to onFrame: one recorded spike of this region (slot 0-255), to play after delayMs
nr.rates(rq)                   // alternative to onFrame: Uint8Array(214) of rate bytes (quantise_rates) or a number for this region
nr.setLive(false)              // force offline (e.g. the socket closed): static cells, caption "no live network"
nr.debugTime(s | null)         // test hook: freeze the clock s seconds after the last spike() (screenshots under software GL)
```

What a spike does: the cell's soma flashes; an action potential runs from the soma along the axon at the real
conduction speed divided by `NeuronRender.SLOWDOWN` (stated in the caption), hopping node to node where the type is
myelinated (saltatory: an internode lights at once, the next after its delay); the axon's boutons glow when it
arrives. The region's rate byte sets a faint dendritic glow. With no frames for 10 s nothing moves and the caption
says so. No frames → no activity, ever: there is no demo mode.

## Look, LOD, measure

```js
nr.setStyle("render"); nr.style()         // toggle; the HUD does the same
nr.setLod("phone"); nr.lod()              // "phone" | "desktop"; "auto" picks by screen width / DPR
nr.focus(i)                               // put the depth-of-field focus and the hero detail on drawn cell i
nr.resize()                               // the container changed size (the module also listens to window resize)
nr.info()                                 // {kind, region, label, style, lod, cells, heroCells, triangles, triangleCap,
                                          //  spines, boutons, nodesOfRanvier, drawCalls, live, spikes, fps, jsMs, offScreen}
nr.caption()                              // the honest caption, plain text (see below)
```

Rendering stops while the container is off screen (IntersectionObserver) or the tab is hidden; `info().fps` and
`info().jsMs` are measured over the last second. `triangles` is the count drawn at the current LOD; `triangleCap`
is the LOD's cap (the planner drops far cells, then spines, then tube sides until it fits).

## Statics

```js
NeuronRender.kindOf(node)        // brain.json node -> kind or null (same rules as Neurons3D.kindOf)
NeuronRender.KINDS               // kind -> {types: [[type, share]], cells: {phone, desktop}}
NeuronRender.SLOWDOWN            // the stated slowdown of the pulses (number)
NeuronRender.CAPTION             // the fixed sentence (word for word from #88):
                                 //   "Shapes are real reconstructed neurons (public databases); thickness, spines and
                                 //    myelin are drawn from published typical values. The simulated network uses point
                                 //    neurons (no dendrites are simulated); cells are enlarged and pulses slowed to be
                                 //    visible. A model, not a mind."
NeuronRender.CELLS               // once loaded: the asset (cells.json) with per-type credits (NeuroMorpho.Org ids, papers)
NeuronRender.load()              // Promise of the asset (open() calls it; B may call it early to prefetch)
```

## What B keeps doing (today's call site, `web/index.html` `closeupOpen` / `closeupExit`)

- pick the region (most active of its kind, or nearest the camera) and call `open` with `region`, `kind`, `label`;
- pass every spiking frame to `nr.onFrame(msg)` next to `n3d.onFrame(msg)`;
- on `onClose`, drop `nr`, restore the brain camera and the layer buttons;
- the caption line (`nr.caption()` + credits) in the panel, as `closeupLine()` does today. The module never writes
  into the panel.

A: `web/neuron_render/*`, `docs/spiking/neuron_render.md`, this file, and the close-up call site only.
B: everything else in `web/neurons3d.js`, the panel HTML/CSS.
