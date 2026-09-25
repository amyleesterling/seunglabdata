#!/usr/bin/env python
"""Second pass on the contact candidates, at full mesh resolution.

The first pass (mec_contacts.py) measures against DECIMATED partner meshes,
roughly a micrometre between vertices, so it can only ask "are these two cells
in the same place". Its own control says that is mostly all it is measuring:
median enrichment over a randomly displaced copy of the same cell was 1.20.

This pass re-measures the shortlist against the partners' FULL meshes, straight
from the meshing service, at a threshold ten times tighter. That is still not a
synapse detector, and it still is not evidence of a synapse. What it can do is
separate two surfaces that genuinely run together from two surfaces that merely
pass through the same cubic micrometre.

Run:  python tools/mec_contacts_hires.py --top 40
"""

import argparse
import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(HERE, "assets", "mec", "cells")
sys.path.insert(0, os.path.join(HERE, "tools"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--touch", type=float, default=0.15, help="micrometres")
    ap.add_argument("--site", type=float, default=2.0)
    ap.add_argument("--shift", type=float, default=12.0)
    ap.add_argument("--scratch", default=os.environ.get("TEMP", "."))
    ap.add_argument("--inp", default=os.path.join(CELLS, "contacts.json"))
    ap.add_argument("--out", default=os.path.join(CELLS, "contacts_hires.json"))
    args = ap.parse_args()

    import mec_meshes as M
    tok = json.load(open(os.path.expanduser("~/.cloudvolume/secrets/cave-secret.json")))
    token = tok.get("token")

    d = json.load(open(args.inp))
    tgt = np.load(os.path.join(args.scratch, "syn_v.npy")).astype(np.float64)
    tree = cKDTree(tgt)
    print("target %s: %d vertices" % (d["target_root_id"], len(tgt)))

    # Shortlist: anything that stood out on the coarse pass, plus anything with
    # a lot of distinct sites, because a partner running alongside for a long
    # way is interesting even if its enrichment is unremarkable.
    pool = sorted(d["partners"],
                  key=lambda r: -(r["enrichment"] * 2 + r["contact_sites"]))
    pool = pool[:args.top]
    rng = np.random.default_rng(5)
    rows = []

    for k, r in enumerate(pool):
        if not r.get("root_id"):
            continue
        try:
            v, _ = M.fetch_mesh(str(r["root_id"]), token)
        except Exception as e:
            print("  %-22s FETCH FAILED %s" % (r["id"], str(e)[:70]))
            continue
        v = np.asarray(v, dtype=np.float64)
        dd, _ = tree.query(v, distance_upper_bound=args.touch)
        hit = np.isfinite(dd)
        n_hit = int(hit.sum())
        ctrl = []
        for _ in range(3):
            off = rng.normal(0, args.shift, 3)
            c, _ = tree.query(v + off, distance_upper_bound=args.touch)
            ctrl.append(int(np.isfinite(c).sum()))
        cm = float(np.mean(ctrl))

        sites = 0
        if n_hit:
            hp = v[hit]
            t2 = cKDTree(hp)
            seen = set()
            for i in range(len(hp)):
                if i in seen:
                    continue
                grp = [g for g in t2.query_ball_point(hp[i], args.site) if g not in seen]
                if grp:
                    seen.update(grp)
                    sites += 1

        rows.append({
            "id": r["id"], "cell_type": r["cell_type"], "layer": r.get("layer"),
            "root_id": r["root_id"], "vertices": int(len(v)),
            "contact_points": n_hit, "contact_sites": sites,
            "control_mean": cm,
            "enrichment": float(n_hit / max(1.0, cm)),
            "coarse_enrichment": r["enrichment"],
        })
        print("  [%2d/%2d] %-22s %-11s verts %8d  points %5d  sites %3d  "
              "control %6.1f  x%.1f  (coarse x%.1f)"
              % (k + 1, len(pool), r["id"], r["cell_type"], len(v), n_hit,
                 sites, cm, rows[-1]["enrichment"], r["enrichment"]))

    rows.sort(key=lambda r: -r["enrichment"])
    e = np.array([r["enrichment"] for r in rows]) if rows else np.array([0.0])
    out = {
        "target_root_id": d["target_root_id"],
        "touch_um": args.touch,
        "site_um": args.site,
        "control": {"n_shuffle": 3, "shift_um": args.shift},
        "caveat": ("Appositions between full resolution meshes, NOT detected "
                   "synapses. The CAVE synapse table for pni_mec is "
                   "unavailable (materialize 503, annotation 404)."),
        "median_enrichment": float(np.median(e)),
        "n_above_4x": int((e >= 4).sum()),
        "partners": rows,
    }
    json.dump(out, open(args.out, "w"), indent=1)
    print("\nmedian enrichment %.2f, %d of %d above 4x"
          % (np.median(e), int((e >= 4).sum()), len(rows)))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
