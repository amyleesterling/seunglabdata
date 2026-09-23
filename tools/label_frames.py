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

    # Legend, bottom left, only the types actually present.
    counts = meta.get("counts", {})
    present = [t for t in TYPE_ORDER if counts.get(t)]
    row = int(30 * s)
    y = H - pad - row * len(present)
    sw = int(14 * s)
    for t in present:
        colour = tuple(int(TYPE_HEX[t][i:i + 2], 16) for i in (1, 3, 5))
        active = note == t
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
