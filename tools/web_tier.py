#!/usr/bin/env python
"""Build a 'web' mesh tier for the interactive gallery.

WHY THIS TIER EXISTS
The gallery was loading the CARD tier, which is sized for the population
figure, where a cell is a few pixels across and 1.4 faces per square micrometre
is plenty. On a gallery card the same cell fills a 340 px box, and a compact
glial cell has so little surface area that the card budget leaves it with
almost nothing: the oligodendrocyte came out at 3,350 faces against 24,546 at
detail, and its processes simply vanished.

The detail tier looks right but costs 21 MB for seven cells, which is not "a
few MB". So: cells already under the cap are copied straight across, and only
the large ones are reduced. That matters, because decimating an already
decimated mesh compounds its error, and the cells that looked broken are
exactly the ones that must not be touched again.

Works from the detail GLBs on disk, so it needs no network and no CAVE token.

Run:  python tools/web_tier.py
"""

import json
import os
import shutil

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = os.path.join(HERE, "assets", "mec", "gallery")
MAX_FACES = 110_000


def main():
    import trimesh
    import fast_simplification

    manifest_path = os.path.join(GALLERY, "cells.json")
    d = json.load(open(manifest_path))
    total = 0
    for c in sorted(d["cells"], key=lambda x: x["id"]):
        src_t = c["tiers"].get("detail")
        if not src_t:
            print(f"{c['id']}: no detail tier, skipping")
            continue
        src = os.path.join(GALLERY, src_t["file"])
        dst_name = f"{c['id']}.web.glb"
        dst = os.path.join(GALLERY, dst_name)
        faces_in = src_t["faces"]

        if faces_in <= MAX_FACES:
            shutil.copy2(src, dst)
            faces_out = faces_in
            how = "copied from detail, already small enough"
        else:
            mesh = trimesh.load(src, force="mesh", process=False)
            v, f = fast_simplification.simplify(
                np.asarray(mesh.vertices, dtype=np.float32),
                np.asarray(mesh.faces, dtype=np.uint32),
                target_reduction=1.0 - MAX_FACES / faces_in)
            out = trimesh.Trimesh(vertices=v.astype(np.float64), faces=f,
                                  process=False)
            out.export(dst)
            faces_out = len(out.faces)
            how = f"reduced from {faces_in:,}"

        size = os.path.getsize(dst)
        total += size
        c["tiers"]["web"] = dict(src_t, file=dst_name, faces=int(faces_out),
                                 bytes=int(size), derived_from="detail")
        print(f"  {c['id']:<20} {faces_out:>8,} faces  {size/1e6:>5.2f} MB   {how}")

    json.dump(d, open(manifest_path, "w"), indent=1)
    print(f"\nweb tier total: {total/1e6:.1f} MB for {len(d['cells'])} cells")


if __name__ == "__main__":
    main()
