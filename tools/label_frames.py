#!/usr/bin/env python
"""
Add labels to MEC population renders, in post.

Labels are NOT burned into the Blender render. Keeping them here means a typo
or a count change costs seconds instead of re-rendering, and the same frames can
carry different labels for different audiences.

Reads scene.json written by render_mec_population.py, so the legend counts come
from what was actually rendered rather than from what someone typed.

Run:
    python tools/label_frames.py renders/population            # still or frames
    python tools/label_frames.py renders/population --out labelled
"""

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# The palette lives in ONE file. It used to be duplicated here, drifted from
# the render scripts, and the legend swatches showed pale lilac while the cells
# rendered hot pink. A key that disagrees with its own figure is a correctness
# bug, not a style one.
_PAL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "mec_palette.json"), encoding="utf-8"))
TYPE_HEX = {k: v["hex"] for k, v in _PAL["types"].items()}
TYPE_LABEL = {k: v["label"] for k, v in _PAL["types"].items()}
TYPE_ORDER = _PAL["order"]

INK = (234, 246, 255)
DIM = (159, 180, 196)
FONT_DIR = r"C:\Windows\Fonts"


def font(name, size):
    for candidate in (name, "segoeui.ttf", "arial.ttf"):
        path = os.path.join(FONT_DIR, candidate)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# Layer boundaries for the depth scale, taken as the midpoints between the mean
# nucleus y of consecutive layers. The layers' own y ranges overlap heavily, so
# a scale drawn from raw ranges would show overlapping bands; midpoints give
# one clean boundary per pair and stay faithful to where the layers sit.
LAYER_MEAN_Y = {"I": 2265, "II": 2119, "III": 1972, "IV": 1844, "V": 1748, "VI": 1626}
LAYER_ORDER = ["I", "II", "III", "IV", "V", "VI"]
CORTEX_TOP_Y, CORTEX_BOTTOM_Y = 2383.0, 1536.0

# Nuclei marked per layer across the WHOLE block. The reconstructed sample is
# not proportional to these, so the scale shows both: a reader who saw only
# "3 cells" next to layer IV could reasonably conclude the cortex has almost
# nothing there, which is not what the count says.
LAYER_NUCLEI = {"I": 7871, "II": 10463, "III": 14203,
                "IV": 4200, "V": 16215, "VI": 9679}


def layer_bounds():
    """(layer, y_high, y_low) top down, in micrometres."""
    ys = [LAYER_MEAN_Y[L] for L in LAYER_ORDER]
    edges = [CORTEX_TOP_Y]
    for a, b in zip(ys, ys[1:]):
        edges.append((a + b) / 2.0)
    edges.append(CORTEX_BOTTOM_Y)
    return [(L, edges[i], edges[i + 1]) for i, L in enumerate(LAYER_ORDER)]


def depth_scale(d, W, H, s, active, counts):
    """A cortical depth scale down the right hand side, with the layer the
    animation is currently revealing picked out."""
    pad = int(44 * s)
    x = W - pad - int(150 * s)
    top, bot = int(H * 0.20), int(H * 0.78)
    span = CORTEX_TOP_Y - CORTEX_BOTTOM_Y
    f_lay = font("segoeuib.ttf", int(19 * s))
    f_n = font("segoeui.ttf", int(15 * s))

    d.text((x, top - int(34 * s)), "CORTICAL DEPTH", font=f_n, fill=DIM)
    for L, hi, lo in layer_bounds():
        y0 = top + int((CORTEX_TOP_Y - hi) / span * (bot - top))
        y1 = top + int((CORTEX_TOP_Y - lo) / span * (bot - top))
        on = (L == active)
        d.rectangle([x, y0, x + int(7 * s), y1],
                    fill=(90, 210, 236, 255) if on else (90, 210, 236, 46))
        n = counts.get(L, 0)
        d.text((x + int(18 * s), (y0 + y1) // 2 - int(13 * s)),
               f"Layer {L}", font=f_lay, fill=INK if on else DIM)
        marked = LAYER_NUCLEI.get(L)
        line = (f"{n} of {marked:,} marked" if marked
                else (f"{n} cells" if n else "none reconstructed"))
        d.text((x + int(18 * s), (y0 + y1) // 2 + int(5 * s)),
               line, font=f_n, fill=INK if on else DIM)


def label(img, meta, note=None):
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    s = W / 1600.0                      # every size is relative to the frame
    pad = int(44 * s)

    f_title = font("segoeuib.ttf", int(38 * s))
    f_sub = font("segoeui.ttf", int(21 * s))
    f_key = font("segoeui.ttf", int(20 * s))
    f_small = font("segoeui.ttf", int(17 * s))

    d.text((pad, pad), "Medial entorhinal cortex", font=f_title, fill=INK)
    block = meta.get("block_um") or [0, 0, 0]
    n = len(meta.get("cells", []))
    d.text((pad, pad + int(48 * s)),
           f"{n} reconstructed cells in a "
           f"{block[0]:.0f} \u00d7 {block[1]:.0f} \u00d7 {block[2]:.0f} \u00b5m imaged block",
           font=f_sub, fill=DIM)

    by_layer = meta.get("cycle_group_by") == "layer"
    if by_layer:
        depth_scale(d, W, H, s, note, meta.get("cycle_counts", {}))

    # Legend, bottom left, only the types actually present.
    counts = meta.get("counts", {})
    present = [t for t in TYPE_ORDER if counts.get(t)]
    row = int(30 * s)
    y = H - pad - row * len(present)
    sw = int(14 * s)
    for t in present:
        colour = tuple(int(TYPE_HEX[t][i:i + 2], 16) for i in (1, 3, 5))
        active = (note == t) and not by_layer
        d.rounded_rectangle([pad, y + int(4 * s), pad + sw, y + int(4 * s) + sw],
                            radius=int(3 * s), fill=colour + (255 if active else 190,))
        d.text((pad + sw + int(12 * s), y),
               f"{TYPE_LABEL[t]}   {counts[t]}", font=f_key,
               fill=INK if active else DIM)
        y += row

    d.text((W - pad, H - pad), "connectome.quest/mec",
           font=f_small, fill=DIM, anchor="rs")
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=None)
    ap.add_argument("--highlight", default=None,
                    help="cell type to emphasise in the legend")
    args = ap.parse_args()

    meta_path = os.path.join(args.folder, "scene.json")
    if not os.path.exists(meta_path):
        sys.exit(f"no scene.json in {args.folder}; render first")
    with open(meta_path) as fh:
        meta = json.load(fh)

    out_dir = args.out or os.path.join(args.folder, "labelled")
    os.makedirs(out_dir, exist_ok=True)

    names = sorted(f for f in os.listdir(args.folder)
                   if f.lower().endswith(".png"))
    if not names:
        sys.exit(f"no PNGs in {args.folder}")

    # A cycle animation holds one type for many frames, so the highlight has to
    # come from the timeline the compositor actually built. Falling back to
    # "one type per frame" made the legend strobe instead of tracking the
    # animation, which is why the per-frame list is preferred.
    by_frame = meta.get("highlight_by_frame") or []
    cycle = meta.get("cycle_types") or []
    if by_frame and len(by_frame) != len(names):
        print(f"warning: {len(by_frame)} highlights for {len(names)} frames; "
              "labelling by frame index anyway")
    for i, name in enumerate(names):
        img = Image.open(os.path.join(args.folder, name)).convert("RGB")
        note = args.highlight
        if not note and by_frame:
            note = by_frame[i] if i < len(by_frame) else None
        elif not note and cycle:
            note = cycle[i % len(cycle)]
        label(img, meta, note)
        img.save(os.path.join(out_dir, name))
    print(f"labelled {len(names)} image(s) -> {out_dir}")


if __name__ == "__main__":
    main()
