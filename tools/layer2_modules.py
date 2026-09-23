#!/usr/bin/env python
"""Islands and ocean: the modular layout of MEC layer II, from nucleus positions.

WHAT THIS REPLACED, AND WHY
A first pass asked only whether stellate cells were clustered, found that they
were, and called the section "stellate cells sit in patches". That was a wrong
conclusion drawn from a real measurement. The published organisation of layer
II runs the other way: calbindin positive PYRAMIDAL cells form the patches, and
reelin positive STELLATE cells occupy the space between them.

  Ray et al., Science 2014, 343:891   doi:10.1126/science.1243028
  Naumann et al., J Neurophysiol 2018, 119:2129   doi:10.1152/jn.00574.2017

Two things made the first answer look complete when it was not. It tested only
ONE cell class, so it could not separate "these cluster" from "these are
excluded from somewhere else". And it stopped at 160 um, which is inside a
single patch, so a finite patch size could not appear at all: you have to look
far enough out to watch the excess die away.

The statistic that separates the explanations is the CROSS one: how many
stellate cells sit near a pyramidal cell, against chance.

The null is unchanged, and it is the point: draw the same number of nuclei from
layer II itself, which holds the curved sheet's shape and its density fixed.

Cluster 6 is the pyramidal size cluster and cluster 7 the stellate one. Neither
is a cell anyone has looked at; the page copy says what that does and does not
allow.

Run:  python tools/layer2_modules.py
"""

import json
import os
import re

import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = r"C:\Users\amyle\AppData\Local\Temp\claude\state_nuclei_by_layer.json"
RES = np.array([16, 16, 45]) / 1000.0
TAN = [0, 2]                 # tangential plane; depth is y
N_NULL = 200
RADII = np.array([20, 40, 60, 90, 120, 160, 200, 250, 300, 380, 460, 560])
PYR_CLUSTER, STEL_CLUSTER = 6, 7

INK, DIM, LINE = "#eaf6ff", "#9fb4c4", "#22303c"
GROUND, MINT, BLUE = "#04060b", "#67f5cb", "#3E96F0"


def load():
    st = json.load(open(STATE, encoding="utf8"))
    pts, clus = [], []
    for L in st["layers"]:
        if L.get("type") != "annotation":
            continue
        if L["name"].replace("_nuclei_points", "").replace("layer_", "") != "II":
            continue
        for a in L.get("annotations", []):
            m = re.search(r"cluster\s+(\d+)", a.get("description", "") or "")
            if not m:
                continue
            pts.append(np.array(a["point"], dtype=float) * RES)
            clus.append(int(m.group(1)))
    return np.array(pts)[:, TAN], np.array(clus)


def kcurve(a, b, radii, same):
    tb = cKDTree(b)
    return np.array([np.mean([len(x) - (1 if same else 0)
                              for x in tb.query_ball_point(a, r)])
                     for r in radii])


def main():
    pool, clus = load()
    pyr, stel = pool[clus == PYR_CLUSTER], pool[clus == STEL_CLUSTER]
    rng = np.random.default_rng(11)
    print("layer II %d, pyramidal %d, stellate %d" % (len(pool), len(pyr), len(stel)))

    tests, results = {}, {}
    for name, a, b, same in (
            ("pyramidal_around_pyramidal", pyr, pyr, True),
            ("stellate_around_stellate", stel, stel, True),
            ("stellate_around_pyramidal", pyr, stel, False)):
        obs = kcurve(a, b, RADII, same)
        null = np.empty((N_NULL, len(RADII)))
        for i in range(N_NULL):
            aa = pool[rng.choice(len(pool), len(a), replace=False)]
            bb = aa if same else pool[rng.choice(len(pool), len(b), replace=False)]
            null[i] = kcurve(aa, bb, RADII, same)
        z = (obs - null.mean(0)) / null.std(0)
        tests[name] = (obs, null, z)
        results[name] = {"radii_um": RADII.tolist(),
                         "observed": [round(float(v), 3) for v in obs],
                         "chance_mean": [round(float(v), 3) for v in null.mean(0)],
                         "z": [round(float(v), 1) for v in z]}
        print("%s: z at 40 um %+.1f, at 560 um %+.1f" % (name, z[1], z[-1]))

    # Where the cross curve crosses zero is the scale at which stellate cells
    # stop being excluded, which is a patch radius read straight off the data.
    zc = tests["stellate_around_pyramidal"][2]
    cross = None
    for j in range(len(RADII) - 1):
        if zc[j] < 0 <= zc[j + 1]:
            t = -zc[j] / (zc[j + 1] - zc[j])
            cross = float(RADII[j] + t * (RADII[j + 1] - RADII[j]))
            break
    results["exclusion_radius_um"] = None if cross is None else round(cross, 1)
    print("stellate exclusion extends to about %s um" % (round(cross) if cross else "n/a"))

    warm = LinearSegmentedColormap.from_list("isl", [GROUND, "#123049", BLUE])
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), facecolor=GROUND,
                             gridspec_kw={"width_ratios": [1, 1, 1.06]})
    for ax in axes:
        ax.set_facecolor(GROUND)
        for sp in ax.spines.values():
            sp.set_color(LINE)
        ax.tick_params(colors=DIM, labelsize=9)

    both = np.vstack([pyr, stel])
    bins = [np.linspace(both[:, 0].min(), both[:, 0].max(), 74),
            np.linspace(both[:, 1].min(), both[:, 1].max(), 28)]
    null_pyr = pool[rng.choice(len(pool), len(pyr), replace=False)]
    null_stel = pool[rng.choice(len(pool), len(stel), replace=False)]

    # BOTH panels must share the colour scale as well as the axes. imshow
    # autoscales per panel by default, so each map gets stretched to its own
    # range and the two look equally structured no matter what the data says.
    # That is the same bug as letting each panel pick its own axis limits, and
    # it defeats the only thing the figure is for.
    SMOOTH = 2.2                      # ~35 um, the scale patches live at
    fields = []
    for p in (pyr, null_pyr):
        h, xe, ye = np.histogram2d(p[:, 0], p[:, 1], bins=bins)
        fields.append(gaussian_filter(h.T, SMOOTH))
    vmin = float(min(f.min() for f in fields))
    vmax = float(max(np.percentile(f, 99.5) for f in fields))

    for ax, field, s, title in (
            (axes[0], fields[0], stel, "Where they actually are"),
            (axes[1], fields[1], null_stel,
             "The same numbers, drawn at random from layer II")):
        ax.imshow(field, origin="lower", cmap=warm, vmin=vmin, vmax=vmax,
                  extent=[bins[0][0], bins[0][-1], bins[1][0], bins[1][-1]],
                  aspect="auto", interpolation="bilinear")
        ax.scatter(s[:, 0], s[:, 1], s=2.6, c=MINT, alpha=.85, lw=0)
        ax.set_xlim(bins[0][0], bins[0][-1])
        ax.set_ylim(bins[1][0], bins[1][-1])
        ax.set_title(title, color=INK, fontsize=11.5, pad=9)
        ax.set_xlabel("micrometres across the block", color=DIM, fontsize=9.5)
    axes[0].set_ylabel("micrometres through the block", color=DIM, fontsize=9.5)

    ax = axes[2]
    ax.axhline(0, color=DIM, lw=1, ls=":")
    ax.axhspan(-2, 2, color=DIM, alpha=.16)
    ax.plot(RADII, tests["pyramidal_around_pyramidal"][2], color=BLUE, lw=2.4,
            marker="o", ms=4.5, label="pyramidal near pyramidal")
    ax.plot(RADII, tests["stellate_around_pyramidal"][2], color=MINT, lw=2.4,
            marker="o", ms=4.5, label="stellate near pyramidal")
    if cross:
        ax.axvline(cross, color=MINT, lw=1, ls="--", alpha=.55)
        ax.annotate("%d \u00b5m" % round(cross), (cross, 0),
                    textcoords="offset points", xytext=(8, -26),
                    color=MINT, fontsize=9.5)
    ax.set_xlabel("radius, micrometres", color=DIM, fontsize=9.5)
    ax.set_ylabel("standard deviations from chance", color=DIM, fontsize=9.5)
    ax.set_title("Islands, and the water around them", color=INK,
                 fontsize=11.5, pad=9)
    leg = ax.legend(frameon=False, fontsize=9.5, loc="upper right")
    for t in leg.get_texts():
        t.set_color(DIM)

    fig.tight_layout()
    d = os.path.join(HERE, "assets", "mec", "figures")
    os.makedirs(d, exist_ok=True)
    fig.savefig(os.path.join(d, "layer2-modules.png"), dpi=150, facecolor=GROUND)
    json.dump({"n_layer2": int(len(pool)), "n_pyramidal": int(len(pyr)),
               "n_stellate": int(len(stel)), "n_null_draws": N_NULL,
               "tests": results,
               "references": [
                   "Ray et al., Science 2014, 343:891, doi:10.1126/science.1243028",
                   "Naumann et al., J Neurophysiol 2018, 119:2129, doi:10.1152/jn.00574.2017"]},
              open(os.path.join(d, "layer2-modules.json"), "w"), indent=1)
    print("wrote %s" % os.path.join(d, "layer2-modules.png"))


if __name__ == "__main__":
    main()
