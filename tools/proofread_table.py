#!/usr/bin/env python
"""Write the proofreading table for the MEC gallery, from the built meshes.

The table used to be typed by hand into mec/index.html and into a CSV, and it
drifted: it listed glia that were no longer the ones being shipped. So it is
generated from assets/mec/gallery/cells.json, which is written by the mesh
builder and is therefore the only record of what a visitor actually sees.

Provenance travels with each row. A cell a person named by eye and a cell an
automatic prediction guessed at are not the same kind of claim, and a table
that flattens them invites exactly the error this gallery already made once.

Run:
    python tools/proofread_table.py
"""

import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = os.path.join(HERE, "assets", "mec", "gallery")
RES_NM = np.array([16, 16, 45])
LIVE_SEG = "seg_20260713164845 (pni_mec chunkedgraph)"
FLAT_SEG = "seg_20260708195730_stage2_ext (flat, no chunkedgraph)"

FIELDS = ["id", "cell_type", "root_id", "segmentation", "chosen_by", "confidence",
          "soma_x_vx", "soma_y_vx", "soma_z_vx",
          "span_x_um", "span_y_um", "span_z_um", "layer", "mesh_fragments",
          "match_iou", "note"]


def main():
    manifest = json.load(open(os.path.join(GALLERY, "cells.json")))
    rows = []
    for c in manifest["cells"]:
        if c.get("hidden"):
            continue
        soma = c.get("nucleus_um") or [0, 0, 0]
        vx = (np.array(soma, dtype=float) * 1000.0 / RES_NM).round().astype(int)
        tier = c["tiers"].get("detail") or next(iter(c["tiers"].values()))
        # The builder records bounds, not a span. Reading a "span_um" key
        # that was never written is how this table shipped 0 x 0 x 0.
        # Percentile bounds, not the raw bounding box. A single stray
        # fragment left after speck removal adds a hundred micrometres to
        # the raw box and misreports how big the cell is.
        lo = np.array(tier["p_bbox_min_um"], dtype=float)
        hi = np.array(tier["p_bbox_max_um"], dtype=float)
        span = [int(round(v)) for v in (hi - lo)]
        rows.append({
            "id": c["id"],
            "cell_type": c["cell_type"],
            "root_id": c["root_id"],
            "segmentation": c.get("segmentation", LIVE_SEG),
            "chosen_by": c.get("verified_by") or "automatic, from a nucleus-size prediction",
            "confidence": c.get("confidence", "unconfirmed"),
            "soma_x_vx": int(vx[0]), "soma_y_vx": int(vx[1]), "soma_z_vx": int(vx[2]),
            "span_x_um": span[0], "span_y_um": span[1], "span_z_um": span[2],
            "layer": c.get("layer", ""),
            "mesh_fragments": c.get("mesh_fragments", ""),
            "match_iou": c.get("match_iou", ""),
            "note": c.get("note", ""),
        })
    rows.sort(key=lambda r: r["id"])

    with open(os.path.join(GALLERY, "proofread.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(os.path.join(GALLERY, "proofread.json"), "w"), indent=1)

    print(f"wrote {len(rows)} rows")
    for r in rows:
        print(f"  {r['cell_type']:<16} {r['root_id']:<20} {r['confidence']:<12} "
              f"{r['chosen_by']}")


if __name__ == "__main__":
    main()
