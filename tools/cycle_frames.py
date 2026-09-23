#!/usr/bin/env python
"""Build the MEC cycle animation from rendered per-type layers.

The animation steps through each cell type on its own, then fades every type
in together at the end.

WHY THIS IS A POST PASS AND NOT A BLENDER ANIMATION
---------------------------------------------------
Animating alpha in EEVEE would mean rendering every frame: several hundred
renders for a sequence whose only change is how visible each type is. Instead
render_mec_population.py --cycle renders ONE alpha layer per type over a single
shared plate, and this composites them. Eight renders instead of four hundred,
and the timing can be changed in seconds without touching the GPU.

The camera is identical across layers because the renderer keeps every cell
loaded and only hides them from the render, so the layers stack exactly.

Run:
    python tools/render_mec_population.py --cells ... --out DIR --type-cycle
    python tools/cycle_frames.py DIR
    python tools/label_frames.py DIR/frames --out DIR/labelled
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

FADE_IN = 12        # frames to bring a type up
HOLD = 26           # frames it stays up alone
FADE_OUT = 12       # frames to take it back down
ALL_IN = 40         # frames to bring every type in at the end
ALL_HOLD = 70       # frames the full population holds


def ease(t):
    """Smoothstep. A linear fade reads as a hard start and a hard stop."""
    t = float(np.clip(t, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def build_timeline(types, accumulate=False, hold=HOLD, fade=FADE_IN):
    """(weights per group, highlighted group) for every frame.

    accumulate=False cycles: each group comes up alone and goes back down.
    accumulate=True builds: each group comes up and STAYS, so the picture is
    assembled piece by piece. That is what makes a descent through cortical
    layers read as anatomy accumulating rather than as a slideshow.
    """
    tl = []
    if accumulate:
        standing = {}
        for t in types:
            for i in range(fade):
                tl.append((dict(standing, **{t: ease((i + 1) / fade)}), t))
            standing[t] = 1.0
            for _ in range(hold):
                tl.append((dict(standing), t))
        for _ in range(ALL_HOLD):
            tl.append((dict(standing), None))
        return tl

    for t in types:
        for i in range(fade):
            tl.append(({t: ease((i + 1) / fade)}, t))
        for _ in range(hold):
            tl.append(({t: 1.0}, t))
        for i in range(FADE_OUT):
            tl.append(({t: ease(1.0 - (i + 1) / FADE_OUT)}, t))
    for i in range(ALL_IN):
        w = ease((i + 1) / ALL_IN)
        tl.append(({t: w for t in types}, None))
    for _ in range(ALL_HOLD):
        tl.append(({t: 1.0 for t in types}, None))
    return tl


def build_sweep(groups, frames, base, window):
    """A lit window travelling across the groups, everything else held faint.

    Used for the depth sweep. The groups outside the window are NOT hidden: the
    point of the shot is where the lit slab sits INSIDE the whole block, and a
    window moving through blackness shows position against nothing.
    """
    tl = []
    n = len(groups)
    for f in range(frames):
        centre = -0.5 + (n) * (f / max(1, frames - 1))
        w = {}
        for i, g in enumerate(groups):
            d = abs(i - centre) / window
            w[g] = base + (1.0 - base) * max(0.0, 1.0 - d * d)
        near = min(range(n), key=lambda i: abs(i - centre))
        tl.append((w, groups[near]))
    return tl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="folder holding plate.png and layer_*.png")
    ap.add_argument("--out", default=None)
    ap.add_argument("--accumulate", action="store_true",
                    help="keep each group on screen once it has appeared, "
                         "instead of fading it back out")
    ap.add_argument("--hold", type=int, default=HOLD)
    ap.add_argument("--fade", type=int, default=FADE_IN)
    ap.add_argument("--sweep", type=int, default=0, metavar="FRAMES",
                    help="move a lit window across the groups over FRAMES "
                         "frames, with everything else held at --base")
    ap.add_argument("--base", type=float, default=0.16,
                    help="how visible the groups outside the window are")
    ap.add_argument("--window", type=float, default=1.6,
                    help="width of the lit window, in groups")
    args = ap.parse_args()

    meta_path = os.path.join(args.folder, "scene.json")
    if not os.path.exists(meta_path):
        sys.exit(f"no scene.json in {args.folder}; render with --type-cycle first")
    meta = json.load(open(meta_path))
    types = meta.get("cycle_types")
    if not types:
        sys.exit("scene.json has no cycle_types; render with --type-cycle first")

    plate_path = os.path.join(args.folder, "plate.png")
    if not os.path.exists(plate_path):
        sys.exit(f"missing {plate_path}")
    plate = np.asarray(Image.open(plate_path).convert("RGB"), dtype=np.float32)

    layers = {}
    for t in types:
        p = os.path.join(args.folder, f"layer_{t}.png")
        if not os.path.exists(p):
            sys.exit(f"missing {p}")
        a = np.asarray(Image.open(p).convert("RGBA"), dtype=np.float32)
        if a.shape[:2] != plate.shape[:2]:
            sys.exit(f"{p} is {a.shape[:2]}, plate is {plate.shape[:2]}")
        layers[t] = (a[..., :3], a[..., 3:4] / 255.0)
        cover = float((a[..., 3] > 8).mean())
        print(f"  layer {t:<16} covers {cover * 100:5.2f}% of the frame")
        if cover == 0.0:
            print(f"     WARNING: {t} layer is empty, it will never appear")

    out_dir = args.out or os.path.join(args.folder, "frames")
    os.makedirs(out_dir, exist_ok=True)

    if args.sweep:
        timeline = build_sweep(types, args.sweep, args.base, args.window)
    else:
        timeline = build_timeline(types, args.accumulate, args.hold, args.fade)
    highlights = []
    for i, (weights, note) in enumerate(timeline):
        img = plate.copy()
        for t in types:                       # fixed order, so overlaps are stable
            w = weights.get(t, 0.0)
            if w <= 0.001:
                continue
            rgb, alpha = layers[t]
            a = alpha * w
            img = img * (1.0 - a) + rgb * a
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(
            os.path.join(out_dir, f"frame_{i:04d}.png"))
        highlights.append(note)
        if i % 50 == 0:
            print(f"  frame {i}/{len(timeline)}")

    # The labeller needs to know which type each frame is showing. Without this
    # it falls back to cycling the list one type per FRAME, which flickers the
    # legend instead of tracking the animation.
    meta["highlight_by_frame"] = highlights
    meta["cycle_frames"] = len(timeline)
    json.dump(meta, open(os.path.join(out_dir, "scene.json"), "w"), indent=1)
    json.dump(meta, open(meta_path, "w"), indent=1)
    print(f"\nwrote {len(timeline)} frames to {out_dir}")
    print(f"at 30 fps that is {len(timeline) / 30.0:.1f} s")


if __name__ == "__main__":
    main()
