#!/usr/bin/env python
"""Where one cell's surface touches every other reconstructed cell's surface.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This finds APPOSITIONS: places where two reconstructed surfaces come within a
threshold of each other. It does not find synapses. A synaptic cleft is about
20 nm and these meshes are decimated to roughly a micrometre between vertices,
so the measurement cannot see a cleft even in principle. Membranes in neuropil
touch constantly without a synapse between them.

The reason it is being done this way at all is that the CAVE synapse table for
pni_mec is unavailable: materialize returns 503 and annotation returns 404. When
it comes back, the honest version of this figure is a join against that table,
and this file becomes the fallback.

So the claim the output supports is "this is everything this cell touches", and
every caption built from it has to say so.

THE CONTROL
-----------
Contact count on its own is uninterpretable, because a cell that simply shares
more space with the target will touch it more. So every candidate is also
measured after being displaced by a small random offset, keeping its shape and
its rough neighbourhood but destroying the actual registration between the two
surfaces. A partner whose real contact count is no higher than its displaced
count is explained by co-location alone.

Run:
    python tools/mec_contacts.py 720575947522615248
"""

import argparse
import json
import os
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(HERE, "assets", "mec", "cells")
TOUCH_UM = 1.5          # about the vertex spacing of the coarsest partner mesh
SITE_UM = 4.0           # contacts nearer than this are one site
N_SHUFFLE = 3
SHIFT_UM = 12.0         # displacement for the control: a few cell radii


def load_target(root_id, scratch):
    v = os.path.join(scratch, "syn_v.npy")
    if os.path.exists(v):
        return np.load(v).astype(np.float64)
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import mec_meshes as M
    tok = json.load(open(os.path.expanduser("~/.cloudvolume/secrets/cave-secret.json")))
    pts, _ = M.fetch_mesh(root_id, tok.get("token"))
    np.save(v, pts.astype(np.float32))
    return pts.astype(np.float64)


def cluster(pts, radius):
    """Greedy single pass clustering. Enough for counting distinct sites."""
    if not len(pts):
        return []
    left = list(range(len(pts)))
    tree = cKDTree(pts)
    seen, sites = set(), []
    for i in left:
        if i in seen:
            continue
        grp = tree.query_ball_point(pts[i], radius)
        grp = [g for g in grp if g not in seen]
        if not grp:
            continue
        seen.update(grp)
        sites.append(pts[grp].mean(axis=0))
    return sites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root_id")
    ap.add_argument("--touch", type=float, default=TOUCH_UM)
    ap.add_argument("--out", default=os.path.join(CELLS, "contacts.json"))
    ap.add_argument("--scratch", default=os.environ.get("TEMP", "."))
    args = ap.parse_args()

    tgt = load_target(args.root_id, args.scratch)
    print("target %s: %d vertices, bbox %s to %s um"
          % (args.root_id, len(tgt), np.round(tgt.min(0), 1), np.round(tgt.max(0), 1)))
    tree = cKDTree(tgt)
    tlo, thi = tgt.min(0) - args.touch, tgt.max(0) + args.touch

    man = json.load(open(os.path.join(CELLS, "cells.json")))
    rng = np.random.default_rng(3)
    rows, skipped = [], 0

    for c in man["cells"]:
        if str(c.get("root_id")) == str(args.root_id):
            continue
        tier = c["tiers"].get("close") or c["tiers"].get("detail") or c["tiers"].get("card")
        lo = np.array(tier["bbox_min_um"])
        hi = np.array(tier["bbox_max_um"])
        # Cheap rejection first. Most of the 782 are nowhere near this cell and
        # loading their meshes to find that out would dominate the runtime.
        if np.any(hi < tlo) or np.any(lo > thi):
            continue
        path = os.path.join(CELLS, tier["file"])
        if not os.path.exists(path):
            skipped += 1
            continue
        v = np.asarray(trimesh.load(path, force="mesh").vertices, dtype=np.float64)
        d, _ = tree.query(v, distance_upper_bound=args.touch)
        hit = np.isfinite(d)
        n_hit = int(hit.sum())
        if n_hit == 0:
            continue

        # The control: same mesh, same neighbourhood, wrong registration.
        ctrl = []
        for _ in range(N_SHUFFLE):
            off = rng.normal(0, SHIFT_UM, 3)
            dd, _ = tree.query(v + off, distance_upper_bound=args.touch)
            ctrl.append(int(np.isfinite(dd).sum()))
        sites = cluster(v[hit], SITE_UM)
        rows.append({
            "id": c["id"],
            "cell_type": c["cell_type"],
            "layer": c.get("layer"),
            "root_id": c.get("root_id"),
            "contact_points": n_hit,
            "contact_sites": len(sites),
            "control_mean": float(np.mean(ctrl)),
            "enrichment": float(n_hit / max(1.0, np.mean(ctrl))),
            "sites_um": [[round(float(x), 2) for x in p] for p in sites[:60]],
        })
        print("  %-22s %-12s points %5d  sites %3d  control %6.1f  x%.1f"
              % (c["id"], c["cell_type"], n_hit, len(sites),
                 np.mean(ctrl), rows[-1]["enrichment"]))

    rows.sort(key=lambda r: -r["contact_sites"])
    real = [r for r in rows if r["enrichment"] >= 2.0]
    out = {
        "target_root_id": args.root_id,
        "touch_um": args.touch,
        "site_um": SITE_UM,
        "control": {"n_shuffle": N_SHUFFLE, "shift_um": SHIFT_UM},
        "caveat": ("Appositions at mesh resolution, NOT detected synapses. The "
                   "CAVE synapse table for pni_mec is unavailable (materialize "
                   "503, annotation 404). A synaptic cleft is about 20 nm and "
                   "these meshes have roughly a micrometre between vertices."),
        "n_candidates_touching": len(rows),
        "n_above_control": len(real),
        "cells_missing_mesh": skipped,
        "partners": rows,
    }
    json.dump(out, open(args.out, "w"), indent=1)
    print("\n%d cells touch it, %d of them above the displaced control"
          % (len(rows), len(real)))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
