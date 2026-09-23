#!/usr/bin/env python
"""Are layer II stellate cells in patches, or spread evenly? Test, then figure.

THE CONTROL IS THE ARGUMENT.
Comparing stellate positions against points scattered uniformly in a box would
"find" clustering in any dataset, because layer II is a curved sheet inside a
block and not a box. So the null is: draw the same NUMBER of nuclei at random
FROM LAYER II ITSELF, 400 times. That holds the sheet's shape and its density
fixed, and anything left over is about stellate cells specifically.

Patches in cortex are defined in the tangential plane. Depth here is y, so the
tangential plane is x by z, and that is the test that matters. The 3D result is
reported alongside as a check.

"Stellate" means nucleus-size cluster 7, which is 84% pure against Amy's
labelled set and sits almost entirely in layer II, where stellate cells belong
in MEC. Contamination WEAKENS a clustering signal rather than manufacturing
one, so the direction of the result is safe even though the label is not exact.

Writes assets/mec/figures/stellate-patches.png and a JSON of the numbers.

Run:  python tools/stellate_patches.py
"""

import json
import os
import re

import numpy as np
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = r"C:\Users\amyle\AppData\Local\Temp\claude\state_nuclei_by_layer.json"
RES = np.array([16, 16, 45]) / 1000.0
N_NULL = 400
RADII = np.array([10, 20, 30, 40, 60, 80, 120, 160])
SEED = 5

INK, DIM, LINE = "#eaf6ff", "#9fb4c4", "#22303c"
GROUND, MINT = "#04060b", "#67f5cb"


def load_layer2():
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
    return np.array(pts), np.array(clus)


def nn_mean(p):
    d, _ = cKDTree(p).query(p, k=2)
    return float(d[:, 1].mean())


def k_counts(p, radii):
    t = cKDTree(p)
    return np.array([np.mean([len(x) - 1 for x in t.query_ball_point(p, r)])
                     for r in radii])


def main():
    lay2, clus = load_layer2()
    stel = lay2[clus == 7]
    rng = np.random.default_rng(SEED)
    print(f"layer II nuclei {len(lay2)}, cluster 7 {len(stel)}")

    out = {"n_layer2": int(len(lay2)), "n_stellate": int(len(stel)),
           "n_null_draws": N_NULL}

    for label, cols, key in (("tangential", [0, 2], "tangential"),
                             ("3D", [0, 1, 2], "three_d")):
        obs_p, pool = stel[:, cols], lay2[:, cols]
        obs_nn, obs_k = nn_mean(obs_p), k_counts(obs_p, RADII)
        null_nn = np.empty(N_NULL)
        null_k = np.empty((N_NULL, len(RADII)))
        for i in range(N_NULL):
            s = pool[rng.choice(len(pool), size=len(obs_p), replace=False)]
            null_nn[i], null_k[i] = nn_mean(s), k_counts(s, RADII)
        z = float((obs_nn - null_nn.mean()) / null_nn.std())
        out[key] = {
            "nn_observed_um": round(obs_nn, 3),
            "nn_null_mean_um": round(float(null_nn.mean()), 3),
            "nn_null_ci95_um": [round(float(v), 3)
                                for v in np.percentile(null_nn, [2.5, 97.5])],
            "nn_z": round(z, 2),
            "null_draws_at_least_as_clustered": int((null_nn <= obs_nn).sum()),
            "radii_um": RADII.tolist(),
            "k_observed": [round(float(v), 3) for v in obs_k],
            "k_null_mean": [round(float(v), 3) for v in null_k.mean(0)],
            "k_z": [round(float((obs_k[j] - null_k[:, j].mean())
                                / null_k[:, j].std()), 1)
                    for j in range(len(RADII))],
        }
        print(f"{label}: NN {obs_nn:.2f} vs null {null_nn.mean():.2f}, z={z:+.1f}, "
              f"{int((null_nn <= obs_nn).sum())}/{N_NULL} null draws as clustered")
        if key == "tangential":
            null_example = pool[rng.choice(len(pool), size=len(obs_p), replace=False)]
            fig_data = (obs_p, null_example, obs_k, null_k)

    obs_p, null_example, obs_k, null_k = fig_data
    cmap = LinearSegmentedColormap.from_list("mint", [GROUND, "#12303a", MINT])
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.4), facecolor=GROUND,
                             gridspec_kw={"width_ratios": [1, 1, 1.05]})
    for ax in axes:
        ax.set_facecolor(GROUND)
        for sp in ax.spines.values():
            sp.set_color(LINE)
        ax.tick_params(colors=DIM, labelsize=9)

    # The two maps MUST share bins and axis limits. Letting each set its own
    # made the null panel a different size and shape, which is a visual
    # advantage handed to whichever panel happened to be tighter, and the
    # entire point of the figure is that the two are comparable.
    both = np.vstack([obs_p, null_example])
    bins = [np.linspace(both[:, 0].min(), both[:, 0].max(), 68),
            np.linspace(both[:, 1].min(), both[:, 1].max(), 26)]
    for ax, pts, title in ((axes[0], obs_p, "Stellate cells, where they actually are"),
                           (axes[1], null_example,
                            "The same number, drawn at random from layer II")):
        h, xe, ye = np.histogram2d(pts[:, 0], pts[:, 1], bins=bins)
        from scipy.ndimage import gaussian_filter
        ax.imshow(gaussian_filter(h.T, 1.1), origin="lower", cmap=cmap,
                  extent=[xe[0], xe[-1], ye[0], ye[-1]], aspect="auto",
                  interpolation="bilinear")
        ax.scatter(pts[:, 0], pts[:, 1], s=1.4, c="#dffaf1", alpha=.55, lw=0)
        ax.set_xlim(bins[0][0], bins[0][-1])
        ax.set_ylim(bins[1][0], bins[1][-1])
        ax.set_title(title, color=INK, fontsize=11.5, pad=9)
        ax.set_xlabel("micrometres across the block", color=DIM, fontsize=9.5)
    axes[0].set_ylabel("micrometres through the block", color=DIM, fontsize=9.5)

    ax = axes[2]
    lo = np.percentile(null_k, 2.5, axis=0)
    hi = np.percentile(null_k, 97.5, axis=0)
    ax.fill_between(RADII, lo, hi, color=DIM, alpha=.22,
                    label="chance, 95% of 400 draws")
    ax.plot(RADII, null_k.mean(0), color=DIM, lw=1.4, ls="--", label="chance, mean")
    ax.plot(RADII, obs_k, color=MINT, lw=2.4, marker="o", ms=4.5, label="observed")
    ax.set_xlabel("radius, micrometres", color=DIM, fontsize=9.5)
    ax.set_ylabel("neighbouring stellate cells within that radius",
                  color=DIM, fontsize=9.5)
    ax.set_title("More neighbours than chance, at every distance",
                 color=INK, fontsize=11.5, pad=9)
    leg = ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    for t in leg.get_texts():
        t.set_color(DIM)

    fig.tight_layout()
    d = os.path.join(HERE, "assets", "mec", "figures")
    os.makedirs(d, exist_ok=True)
    png = os.path.join(d, "stellate-patches.png")
    fig.savefig(png, dpi=150, facecolor=GROUND)
    json.dump(out, open(os.path.join(d, "stellate-patches.json"), "w"), indent=1)
    print("wrote", png)


if __name__ == "__main__":
    main()
