# MEC — handoff

Everything needed to pick up work on the medial entorhinal cortex dataset page at
**https://connectome.quest/mec/**. Read this before touching the renderer or the
mesh builder. The site-wide handoff is `../HANDOFF.md`; this file covers MEC only.

MEC is the first dataset EyeWire citizen scientists will test, so the page is
written for people who have never seen a connectome, and every number on it has
to be defensible.

---

## 1. Where things are

| What | Path |
|---|---|
| Page | `mec/index.html` (single file, inline `<style>` and `<script>`) |
| Interactive block viewer | `mec/volume/index.html` (three.js, own page, iframed) |
| Mesh builder | `tools/mec_meshes.py` |
| Population renderer | `tools/render_mec_population.py` |
| Single cell renderer | `tools/render_mec_cells.py` |
| Post compositor | `tools/cycle_frames.py` |
| Post labeller | `tools/label_frames.py` |
| Layer II analysis | `tools/layer2_modules.py` |
| Colour source of truth | `tools/mec_palette.json`, copied to `assets/mec/palette.json` |
| Built meshes + manifest | `assets/mec/cells/cells.json` and `*.glb` |
| Gallery meshes (web) | `assets/mec/gallery/` |
| Videos | `assets/mec/population/*.mp4`, posters in `.../web/` |

Deploy is `git push` to `main` on `amyleesterling/seunglabdata` (GitHub Pages).
A push is not a deploy: verify from the live URL.

## 2. The data

- CAVE datastack **`pni_mec`** on **`https://hc.himc-cave.com`**, not minnie.
  Its **annotation service returns 400 and materialize returns 503**. Both have
  been down the whole time. Anything needing synapses or annotation tables is
  blocked on Eric, who is the point of contact.
- **Two segmentations, and they are not interchangeable.**
  - Live chunkedgraph `seg_20260713164845` — what the mesh builder uses.
  - Flat `seg_20260708195730_stage2_ext` (`neuroglancer_multilod_draco`, sharded)
    in `gs://princeton-eric-medial-entorhinal-cortex-prod-central1/make_cv_happy/seg/`.
  Segment IDs from one **will return zero mesh fragments** in the other. They
  share voxel offset, size and resolution, so transfer by **position**, then
  verify by **voxel IoU** (see §6).
- Block: **2031 × 1338 × 447 µm** at 16 × 16 × 45 nm.
- 782 cells built. Types in the manifest: pyramidal 377, glia 250, stellate 81,
  inhibitory 44, astrocyte 11, oligodendrocyte 9, microglia 6, bipolar 4.
- Meshes come from the **meshing service manifest**, range-fetched from the
  public bucket and decoded with DracoPy. `cv.mesh.get` does not work on this
  volume ("no shard configuration ... for level 10").

## 3. Mesh tiers

Density is faces per µm² of surface area, with a hard face cap.

| Tier | Density | Cap | Who gets it | In git? |
|---|---|---|---|---|
| `card` | 1.4 | 60 k | all 782 | yes |
| `close` | 6.0 | 140 k | the **244** cells within 150 µm of the flythrough path | **no** |
| `detail` | 10.25 | 260 k | gallery cells | yes |
| `web` | — | 110 k | derived from detail by `tools/web_tier.py` | yes |

**The close tier is 485 MB and is deliberately gitignored.** It is a render
input, never served. The manifest still lists it, so a fresh clone has entries
without files; the renderer **falls back to another tier and prints a loud
WARNING naming the missing cells** rather than silently rendering a smaller
population. Rebuild with:

```bash
python tools/mec_meshes.py tools/mec_path_cells.json --out <scratch>/closeout --tiers close
```

Split the input across **at most 8 parallel builders**. Mesh building is memory
bound, not CPU bound: 12 builders ran *slower* than 6 (free RAM 63.7 → 11.8 GB,
CPU down to 62%, 2.0 cells/min; 8 builders gave 6.6 cells/min). Low CPU with
many processes means paging. Each builder writes its **own** `cells.json`, so
merge them in one process or the last one wins.

Known unfixed bug: `fetch_mesh` assumes every fragment is `path:offset:length`.
A few cells (e.g. `720575947522615248`) have fragments in unsharded
`<segid>:0:<chunk-range>` form, which raises `ValueError` and skips the cell.
Four candidate URL forms were probed against `MESH_BASE`; all 404'd.

## 4. Renderer modes

All via `blender --background --factory-startup --python tools/render_mec_population.py -- ...`

| Flag | What it makes |
|---|---|
| *(none)* | one still |
| `--frames N` | turntable, full revolution, loops |
| `--type-cycle` | one class at a time, composited in post by `cycle_frames.py` |
| `--group-by layer\|depth` | same machinery, grouped by layer or depth bin |
| `--buildup N` | cells arrive one by one, then hold |
| `--flythrough N` | camera weaves through the block lighting cells as it passes |
| `--soma-tour N` | slow drift soma to soma with the focus racking |

Common: `--group-glia` (glia subtypes are unreliable, draw them as one class),
`--no-cage`, `--fill`, `--aspect`, `--random-colours SEED` (decorative only,
never for a figure with a legend), `--headlamp`, `--near-fade`.

**Not `--cycle`.** Blender's own parser rejects it as ambiguous with
`--cycles-device` before the script ever runs.

The exact commands used for the shipped videos are in
`<scratchpad>/evening.sh` and `<scratchpad>/rerender_all.sh`; copy them rather
than reconstructing the flags.

## 5. What the two cinematic modes actually needed

Both took several failed runs. The reasons are specific to this tissue and will
recur on any dense volume.

**Flythrough.** A world HDRI lights every surface identically wherever it sits,
so the interior had no distance cue at all and read as a flat wall: measured
coverage was 96–99 % of frame filled, with no black in it. Fixes, in order of
how much they mattered:
1. A light **carried by the camera**, mounted **off the lens axis**. On-axis it
   lights everything head on and flattens exactly what it was added to model.
2. A **near fade** so cells at the lens neither occlude nor crowd. Band is
   0.12 × TARGET_SIZE ≈ 244 µm. The first value tried, 0.55, was 1100 µm, half
   the block, and dimmed the whole scene.
3. The near cull measures **sampled surface points** (~111 200 of them), not
   bounding radius. In dense tissue the camera is inside nearly every cell's
   bounding sphere at once, and culling on that blanked whole frames.
4. The **close tier**, because card density is visibly faceted at arm's length.
5. The opening is **primed**: cells already in front of the camera at u = −1 are
   dated FADE frames in the past, so frame 0 is standing rather than black.

Path bugs already fixed and easy to reintroduce: overshooting the block by 55 %
put the camera outside looking at nothing (634 cells visible, zero culled,
frame black); easing the travel made it loiter at the empty ends and race
through the middle.

**Soma tour.** The lesson here is the general one:

> **There is no distance at which reconstructed layer II becomes see-through.**
> The frame is ~250 µm across at the far edge of any sensible cull band, and
> 250 µm of this neuropil is opaque. Culling by distance only changes *which*
> wall you are looking at.

Four runs were spent tuning the fade before that was clear. The control that
works is **how many cells are drawn**: the tour draws the cell in focus and its
`--tour-cast` nearest neighbours (6), and nothing else, easing cells in and out
as the cast changes. Second thing that mattered: the camera stands **386 µm**
off the soma (`VIEW = TARGET_SIZE * 0.19`), framing ~270 µm. At 173 µm it framed
114 µm, which is *inside* the arbor rather than in front of a cell.

Focus distance is **measured to the soma every frame**, so the rack follows the
geometry instead of being keyframed alongside it. Soma positions go through the
importer's axis map and the root matrix, and the code **asserts** each mapped
soma lands on its own cell's surface (median 3.2 µm, worst 12 µm). Do not remove
that assert; a silent axis error aims the camera at empty space.

The stops walk **neighbour to neighbour**, hops of 50–235 µm. Farthest point
sampling is right for covering a volume and wrong for planning a camera move:
stops a millimetre apart have to be crossed inside one leg, which is a whip pan.

## 6. Rules that were learned the hard way

- **Match cells across segmentations by voxel IoU, never by size.** Size
  matching transferred a microglia onto an astrocyte at a ratio of 0.78 and it
  passed. IoU gave 0.96–0.97 for correct pairs and under 0.05 for the impostor.
  Caught only by rendering it and looking.
- **Glia subtypes are unreliable.** The nucleus-size prediction mislabels them
  and size cannot separate the classes. Draw them as one "glia" class.
- **One test frame cannot detect a static sequence.** Seven spin videos shipped
  as byte-identical frames because the glTF importer leaves `rotation_mode` on
  QUATERNION and an object in quaternion mode ignores `rotation_euler` silently.
  Set `obj.rotation_mode = "XYZ"`. Every animation now hashes two frames and
  prints `frames differ: True`.
- **Fit a camera to the box's 8 real corners, not its bounding sphere.** A
  sphere over-pads a flat slab. This mistake was made in Blender, written into
  the guidebook, and then repeated in JavaScript in the volume viewer.
- **Panels that share an axis must share the colour scale too.** `imshow`
  autoscales per panel, so two maps look equally structured whatever the data
  says. Compute `vmin`/`vmax` jointly.
- **A measurement that can return nothing needs a control.** "Stellate cells sit
  in patches" was a wrong conclusion from a real measurement: it tested only one
  class, so it could not separate "these cluster" from "these are excluded", and
  it stopped at 160 µm, inside a single patch. The published organisation runs
  the other way (pyramidal cells form the patches, stellate occupy the space
  between). Ray et al., Science 2014 · Naumann et al., J Neurophysiol 2018.
- **Blender writes relative `--out` against the process cwd.** Always absolute.
- **EEVEE motion blur off, always.** Neurons never glossy: IOR 1.04, subsurface.
- Fade with **brightness, not alpha**. Alpha makes EEVEE sort hundreds of
  overlapping transparent meshes. Hide at level 0, because a black mesh still
  writes depth and punches holes in what is behind it.
- Python **block-buffers stdout when redirected**, so progress prints sit in the
  buffer and the log looks dead. `python -u`, or `PYTHONUNBUFFERED=1`. Blender's
  embedded Python resists both; trust the frame count on disk instead.

## 7. Page conventions

- No em-dashes or en-dashes anywhere in copy.
- Colours come from `assets/mec/palette.json`, fetched at run time. Blender
  colour sockets are **linear**; convert with `srgb_to_linear` or lose half the
  saturation on every type.
- Amy's hue preference: blues, purples, yellows and pinks dominant. No
  yellow-greens or olives.
- Prose ≥ 16 px, labels ≥ 13 px. The inline `<style>` in `index.html` beats
  `styles.css`, and `.mec__figure figcaption` (0,1,1) beats `.mec__caption`
  (0,1,0). A caption that is the wrong size is almost always that rule.
- `min-height` with `aspect-ratio` forces a minimum **width**. That is what made
  the page 504 px wide on a 375 px phone.
- Videos in `.mec__figure--wide` get a play badge automatically from the script
  at the bottom of the page. A poster frame is indistinguishable from a still.
- Every figure caption says what was measured and what it does not show. The
  sample is not proportional, so the depth scale prints denominators.

## 8. The gate

`/mec/` is behind the word `citizenscience`, as a salted SHA-256 checked with
`crypto.subtle`, set before first paint so the page never flashes its contents.

**This is not access control and must not be described as such.** The repo is
public, so anything on the page can be fetched directly from
`raw.githubusercontent.com`. It stops someone who lands on the page from reading
it. Real options, none chosen yet: Cloudflare Access, Cloudflare Pages with a
private repo, or client-side encryption of the payload.

## 9. State as of 2026-09-24

Done and live: 782-cell population, corrected gallery cells with IoU provenance,
type cycle / laminar descent / depth sweep / turntable, islands-and-ocean
analysis with an in-sample null, layer diagram, hero banner, homepage card,
mobile type scale, 6400 × 3600 print render, the gate.

In flight tonight: soma tour (600 frames), flythrough re-render on close-tier
meshes (460), slow banner turn (480). Gallery markup for flythrough, soma tour
and buildup is already in `index.html` and expects
`mec_flythrough.mp4`, `mec_soma_tour.mp4`, `mec_buildup.mp4` plus posters at
`assets/mec/population/web/{flythrough,soma_tour,buildup}-poster.jpg`.

Open:
- Synapse partner animation along the axon of `720575947522615248`. **Blocked**:
  needs partner IDs, and Amy's neuroglancer state is on
  `global.brain-wire-test.org`, a different auth realm. Materialize is 503.
- Portrait 4:5 cuts exist in `p_still/p_cycle/p_layers/p_depth/p_turn` and are
  **not wired up**; no mobile source switching yet.
- MEC-in-mouse-brain context diagram. The whatisabrain MEC cube is on branch
  `claude/mouse-cleft` and was never deployed.
- Early-access subscribe link: dedicated page, or a tagged preset on the
  existing form. Not decided.
- Unsharded mesh fragment parser (§3).
- The guidebook repo `C:\Users\amyle\neuron-render-guidebook` has no remote.
- **Amy has a `stash@{0}` in this repo. Do not drop it.**
