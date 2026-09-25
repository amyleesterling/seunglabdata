#!/usr/bin/env python
"""
Build web meshes for MEC cells, in two tiers, from a cell list pinned to nuclei.

WHY IT IS PINNED TO NUCLEI AND NOT TO ROOT IDS
----------------------------------------------
MEC is actively proofread, so a root id changes the moment anyone edits the
cell. A gallery pinned to root ids rots silently: the mesh still loads, it is
just no longer that cell. So the input file stores a nucleus position, and this
script resolves the CURRENT root at build time by reading the segmentation at a
point near the soma and asking the chunked graph what root owns it.

Re-running this after a proofreading session refreshes the gallery.

WHY IT DOES NOT USE CLOUDVOLUME FOR MESHES
------------------------------------------
cv.mesh.get raises "There is no shard configuration in the mesh info file for
level 10" on this volume (the graph has 10 layers). So meshes come from the
meshing service manifest, range-fetched out of the public bucket and decoded
with DracoPy. The volume sets uniform_draco_grid_size, which means decoded
vertices are already in GLOBAL NANOMETRES and need no per-chunk offset. That is
checked against the segmentation's own bounds on every run rather than assumed.

USAGE
-----
    python tools/mec_meshes.py cells.json --out assets/mec/cells

cells.json is a list of objects. Minimum: {"id", "cell_type", "nucleus_um"}.
A "root_id" may be given as a hint; it is verified and replaced if stale.

Requires a CAVE token at ~/.cloudvolume/secrets/cave-secret.json.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np

CAVE = "https://hc.himc-cave.com"
TABLE = "pni_mec"
MESH_BASE = ("https://storage.googleapis.com/princeton-eric-mec-prod-east1"
             "/ws/seg_20260713164845/graphene_meshes/initial")

# Straight from the segmentation info file. Everything is checked against these.
VOXEL_OFFSET = np.array([76728, 65192, 8])
VOLUME_SIZE = np.array([126968, 83616, 9932])
RESOLUTION_NM = np.array([16, 16, 45])
UM_PER_VOXEL = RESOLUTION_NM / 1000.0
BOUNDS_LO_UM = VOXEL_OFFSET * UM_PER_VOXEL
BOUNDS_HI_UM = (VOXEL_OFFSET + VOLUME_SIZE) * UM_PER_VOXEL

# Face density per unit AREA, never a single global face count: density varies
# enormously by cell class, and one flat target cuts fibres to a few percent of
# their faces while bloating compact cells many times over. The cap is a guard
# against one 1.3 mm axon eating a page budget, not the target.
TIERS = {
    "card":   {"density": 1.4,  "max_faces": 60_000},
    # For cells the camera passes within a couple of hundred micrometres of in
    # a flythrough. Card density is fine at population scale and visibly
    # faceted at arm's length; full detail for 434 such cells would be 113M
    # faces, which will not fit. This sits between.
    "close":  {"density": 6.0,  "max_faces": 140_000},
    "detail": {"density": 10.25, "max_faces": 260_000},
}
MIN_COMPONENT_FACES = 25      # strip specks before decimating
PCTL = (0.5, 99.5)            # percentile bounds; stray vertices wreck framing

# Somata differ in size by cell class, so the probe shell does too. Glia get a
# wider spread because their cytoplasm is a thin shell around the nucleus.
PROBE_RADII_UM = {
    "stellate": (6, 8, 10), "pyramidal": (6, 8, 10),
    "inhibitory": (5, 7, 9), "bipolar": (5, 7, 9),
    "astrocyte": (4, 6, 8), "oligodendrocyte": (4, 6, 8), "microglia": (4, 6, 8),
}
PROBE_N_DIRS = 18
# A segment with only a handful of mesh fragments is a nucleus blob or a speck,
# not a cell. Measured: for glia the MOST agreed root is almost always a
# 1-fragment object sitting at the nucleus, and the actual cell is the runner
# up. Excluding these first, then ranking by agreement, gets the cell.
MIN_CELL_FRAGMENTS = 4

# Extent ceiling per type, in micrometres, for the LONGEST axis.
#
# This is the check that matters for glia, and it is not optional. Probe
# agreement alone picks the big NEURON whose processes surround the glial soma,
# because more probe points land on it than on the glial cytoplasm. Measured:
# the highest-agreement "astrocyte" spanned 483 um and the highest-agreement
# "oligodendrocyte" spanned 839 um. Real ones are tens of micrometres. The
# right cell was a LOW agreement candidate with a small extent.
#
# Principal neurons here genuinely run hundreds of micrometres, so they get a
# loose ceiling that only catches obvious mergers.
EXTENT_CEILING_UM = {
    "astrocyte": 90, "oligodendrocyte": 120, "microglia": 120, "bipolar": 400,
    "stellate": 1100, "pyramidal": 1100, "inhibitory": 1100,
}
EXTENT_SAMPLE_FRAGMENTS = 24     # enough to bound a mesh without fetching it all


def probe_dirs(n=PROBE_N_DIRS):
    """Evenly spread directions on a sphere. A 10 point axis cross leaves gaps
    wide enough for a thin glial process to fall through."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    theta = np.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(theta) * np.sin(phi),
                     np.sin(theta) * np.sin(phi),
                     np.cos(phi)], axis=1)


def cave_token():
    path = os.path.expanduser("~/.cloudvolume/secrets/cave-secret.json")
    with open(path) as fh:
        data = json.load(fh)
    return data.get("token") or next(iter(data.values()))


def get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def resolve_root(cv, token, nucleus_um, cell_type):
    """Current root id for the cell whose nucleus sits at nucleus_um.

    Reading at the nucleus centre returns the NUCLEUS segment, not the cell, so
    this probes shells out in the soma cytoplasm, drops candidates too small to
    be a cell, and takes the one the most probe points agree on.
    Returns (root_id, mesh_fragments, probe_hits) or None.
    """
    radii = PROBE_RADII_UM.get(cell_type, (5, 7, 9))
    points = []
    for r in radii:
        for direction in probe_dirs():
            p = (np.array(nucleus_um) + direction * r) / UM_PER_VOXEL
            points.append([int(round(v)) for v in p])

    def one(p):
        try:
            sv = int(np.asarray(cv[p[0]:p[0] + 1, p[1]:p[1] + 1, p[2]:p[2] + 1]).ravel()[0])
            if not sv:
                return None
            return int(get_json(f"{CAVE}/segmentation/api/v1/table/{TABLE}/node/{sv}/root", token)["root_id"])
        except Exception:
            return None

    hits = Counter()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for root in ex.map(one, points):
            if root:
                hits[root] += 1
    # Two filters, then rank. Ranking by mesh SIZE selects mergers (it once
    # returned a 1,448 fragment object spanning 1.36 mm as an 'astrocyte').
    # Ranking by AGREEMENT alone selects the neighbouring neuron for glia.
    # So: drop nucleus blobs by fragment count, drop anything too big to be
    # this cell type, then take the most agreed of what is left.
    ceiling = EXTENT_CEILING_UM.get(cell_type)
    scored = []
    for root, n in hits.most_common(8):
        try:
            frags = len(manifest(root, token))
        except Exception:
            continue
        if frags < MIN_CELL_FRAGMENTS:
            continue
        span = None
        if ceiling:
            try:
                span = float(sampled_extent_um(root, token).max())
            except Exception:
                span = None
            if span is not None and span > ceiling:
                continue
        scored.append((n, frags, root, span))
    if not scored:
        return None
    scored.sort(reverse=True)
    n, frags, root, span = scored[0]
    return (root, frags, n)


def sampled_extent_um(root_id, token):
    """Bounding extent of a root from a SAMPLE of its mesh fragments.

    Fetching every fragment to find out a cell is the wrong one is wasteful,
    and a couple of dozen fragments spread through the list bound it well
    enough to tell 50 micrometres from 500.
    """
    import DracoPy
    frags = manifest(root_id, token)
    if len(frags) > EXTENT_SAMPLE_FRAGMENTS:
        idx = np.linspace(0, len(frags) - 1, EXTENT_SAMPLE_FRAGMENTS).astype(int)
        frags = [frags[i] for i in idx]

    def one(frag):
        path, offset, length = frag.lstrip("~").rsplit(":", 2)
        offset, length = int(offset), int(length)
        req = urllib.request.Request(
            f"{MESH_BASE}/{path}",
            headers={"Range": f"bytes={offset}-{offset + length - 1}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        v = np.asarray(DracoPy.decode(raw).points, dtype=np.float64)
        return v.min(0), v.max(0)

    with ThreadPoolExecutor(max_workers=12) as ex:
        parts = list(ex.map(one, frags))
    lo = np.min([a for a, _ in parts], axis=0) / 1000.0
    hi = np.max([b for _, b in parts], axis=0) / 1000.0
    return hi - lo


def manifest(root_id, token):
    url = f"{CAVE}/meshing/api/v1/table/{TABLE}/manifest/{root_id}:0?verify=1"
    return get_json(url, token)["fragments"]


def fetch_mesh(root_id, token):
    """Assemble a root's mesh. Returns (vertices_um, faces)."""
    import DracoPy
    frags = manifest(root_id, token)

    def one(frag):
        path, offset, length = frag.lstrip("~").rsplit(":", 2)
        offset, length = int(offset), int(length)
        req = urllib.request.Request(
            f"{MESH_BASE}/{path}",
            headers={"Range": f"bytes={offset}-{offset + length - 1}"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        mesh = DracoPy.decode(raw)
        return (np.asarray(mesh.points, dtype=np.float32),
                np.asarray(mesh.faces, dtype=np.uint32))

    with ThreadPoolExecutor(max_workers=16) as ex:
        parts = list(ex.map(one, frags))

    verts, faces, n = [], [], 0
    for v, f in parts:
        if len(v) == 0:
            continue
        verts.append(v)
        faces.append(f + n)
        n += len(v)
    if not verts:
        raise RuntimeError(f"root {root_id} produced no geometry")
    V = np.vstack(verts).astype(np.float64)
    F = np.vstack(faces)

    # CONTROL, every run. Decoded coordinates are claimed to be global
    # nanometres. If that ever stops being true the meshes would silently land
    # in the wrong place, so check before anything is built on them.
    lo_nm, hi_nm = BOUNDS_LO_UM * 1000.0, BOUNDS_HI_UM * 1000.0
    if not ((V.min(0) >= lo_nm - 1).all() and (V.max(0) <= hi_nm + 1).all()):
        raise RuntimeError(
            f"root {root_id}: decoded vertices fall outside the imaged block "
            f"({V.min(0)} .. {V.max(0)} nm vs {lo_nm} .. {hi_nm}). "
            "uniform_draco_grid_size may have changed; do not trust these meshes.")
    return V / 1000.0, F


def percentile_bounds(vertices):
    """Extent ignoring strays. These meshes routinely carry a handful of
    vertices thousands of micrometres from everything else, and a raw min/max
    box collapses any auto-scale computed from it."""
    lo = np.percentile(vertices, PCTL[0], axis=0)
    hi = np.percentile(vertices, PCTL[1], axis=0)
    return lo, hi


def clean(mesh):
    """Drop tiny disconnected specks before decimating."""
    import trimesh
    try:
        labels = trimesh.graph.connected_component_labels(
            mesh.face_adjacency, node_count=len(mesh.faces))
    except Exception:
        return mesh, 0
    counts = np.bincount(labels)
    keep = np.isin(labels, np.where(counts >= MIN_COMPONENT_FACES)[0])
    dropped = int((~keep).sum())
    if dropped and keep.any():
        mesh.update_faces(keep)
        mesh.remove_unreferenced_vertices()
    return mesh, dropped


def write_tier(verts_um, faces, out_path, tier):
    import trimesh
    import fast_simplification
    mesh = trimesh.Trimesh(vertices=verts_um, faces=faces, process=False)
    mesh.merge_vertices()
    mesh, dropped = clean(mesh)
    before = mesh.bounds.copy()
    faces_in = len(mesh.faces)
    area = float(mesh.area)

    spec = TIERS[tier]
    # No 'keep at least x% of the original faces' floor. That guard silently
    # wins on every cell and has pushed a render from 6 s/frame to 128.
    target = min(int(area * spec["density"]), spec["max_faces"])
    target = max(target, 200)

    if len(mesh.faces) > target:
        frac = max(min(target / len(mesh.faces), 1.0), 0.002)
        v, f = fast_simplification.simplify(
            np.asarray(mesh.vertices, dtype=np.float32),
            np.asarray(mesh.faces, dtype=np.uint32),
            target_reduction=1.0 - frac)
        mesh = trimesh.Trimesh(vertices=v.astype(np.float64), faces=f, process=False)

    shift = float(np.abs(mesh.bounds - before).max())
    mesh.export(out_path)
    lo, hi = percentile_bounds(np.asarray(mesh.vertices))
    return {
        "faces": int(len(mesh.faces)),
        "faces_in": int(faces_in),
        "specks_dropped": int(dropped),
        "density_per_um2": round(len(mesh.faces) / area, 2) if area else None,
        "vertices": int(len(mesh.vertices)),
        "bytes": os.path.getsize(out_path),
        "bbox_min_um": mesh.bounds[0].round(2).tolist(),
        "bbox_max_um": mesh.bounds[1].round(2).tolist(),
        "p_bbox_min_um": lo.round(2).tolist(),
        "p_bbox_max_um": hi.round(2).tolist(),
        "decimation_bbox_shift_um": round(shift, 4),
        "surface_area_um2": round(area, 1),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cells", help="JSON list of cells to build")
    ap.add_argument("--out", default="assets/mec/cells", help="output directory")
    ap.add_argument("--tiers", default="card,detail")
    ap.add_argument("--limit", type=int, default=0, help="build only the first N cells")
    args = ap.parse_args()

    from cloudvolume import CloudVolume
    token = cave_token()
    cv = CloudVolume(f"graphene://{CAVE}/segmentation/table/{TABLE}",
                     use_https=True, progress=False, agglomerate=False)
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    for t in tiers:
        if t not in TIERS:
            sys.exit(f"unknown tier {t!r}; known: {', '.join(TIERS)}")

    with open(args.cells) as fh:
        cells = json.load(fh)
    if args.limit:
        cells = cells[:args.limit]
    os.makedirs(args.out, exist_ok=True)

    print(f"block {(BOUNDS_HI_UM - BOUNDS_LO_UM).round(2)} um, "
          f"{len(cells)} cells, tiers {tiers}")

    built = []
    for i, cell in enumerate(cells, 1):
        cid = cell["id"]
        print(f"\n[{i}/{len(cells)}] {cid} ({cell.get('cell_type','?')})")
        try:
            # A PINNED root skips resolution. Resolving from the soma reads the
            # live segmentation around a point, and for a small glial cell most
            # of those points land in the neighbour pressed against it: the
            # microglia Amy picked resolved to a spongiform astrocyte of
            # plausible size. Where a cell has been matched to a known mesh by
            # overlap, that answer is better than anything a probe can do, so
            # it is used directly and says so.
            if cell.get("pin_root") and cell.get("root_id"):
                root = str(cell["root_id"])
                frags = len(manifest(root, token))
                hits = None
                print(f"   root {root} PINNED ({cell.get('pin_reason','no reason given')})")
                print(f"   fragments {frags}")
            else:
                found = resolve_root(cv, token, cell["nucleus_um"],
                                     cell.get("cell_type", ""))
                if not found:
                    print("   no root resolved at that nucleus, skipping")
                    continue
                root, frags, hits = found
                hint = cell.get("root_id")
                if hint and str(hint) != str(root):
                    print(f"   root moved since the list was written: {hint} -> {root}")
                print(f"   root {root}  fragments {frags}  probe hits {hits}")

            verts, faces = fetch_mesh(root, token)
            print(f"   assembled {len(verts)} verts, {len(faces)} faces, "
                  f"span {np.round(verts.max(0)-verts.min(0),1)} um")

            record = dict(cell)
            record["root_id"] = str(root)
            record["mesh_fragments"] = frags
            record["tiers"] = {}
            for tier in tiers:
                path = os.path.join(args.out, f"{cid}.{tier}.glb")
                stats = write_tier(verts, faces, path, tier)
                record["tiers"][tier] = dict(stats, file=os.path.basename(path))
                print(f"   {tier:<7} {stats['faces']:>7} faces  "
                      f"{stats['bytes']/1e6:>6.2f} MB  "
                      f"{stats['density_per_um2']}/um2  "
                      f"specks -{stats['specks_dropped']}  "
                      f"bbox shift {stats['decimation_bbox_shift_um']} um")
            built.append(record)
        except Exception as exc:
            print(f"   FAILED: {type(exc).__name__}: {exc}")

    # MERGE into any existing manifest instead of overwriting it. Rebuilding
    # three glia used to wipe the four neurons out of cells.json, leaving GLBs
    # on disk that nothing referenced.
    out_manifest = os.path.join(args.out, "cells.json")
    merged = {}
    if os.path.exists(out_manifest):
        try:
            with open(out_manifest) as fh:
                for c in json.load(fh).get("cells", []):
                    if all(os.path.exists(os.path.join(args.out, t["file"]))
                           for t in c.get("tiers", {}).values()):
                        merged[c["id"]] = c
        except Exception as exc:
            print(f"could not read the existing manifest ({exc}), writing a fresh one")
    for c in built:
        merged[c["id"]] = c
    built = [merged[k] for k in sorted(merged)]

    with open(out_manifest, "w") as fh:
        json.dump({
            "block": {
                "extent_um": (BOUNDS_HI_UM - BOUNDS_LO_UM).round(3).tolist(),
                "min_um": BOUNDS_LO_UM.round(3).tolist(),
                "max_um": BOUNDS_HI_UM.round(3).tolist(),
                "resolution_nm": RESOLUTION_NM.tolist(),
            },
            "built_cells": len(built),
            "cells": built,
        }, fh, indent=1)
    print(f"\nwrote {out_manifest}: {len(built)} of {len(cells)} cells built")


if __name__ == "__main__":
    main()
