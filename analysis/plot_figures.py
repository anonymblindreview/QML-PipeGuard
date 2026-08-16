"""
paper-ready figures for the experiment json outputs.

  fig_detection_bars : weak vs local observable deviations,
                       horizontal lollipops with tolerance line
  fig_sample_curve   : tpr and fpr vs shot budget, vertical
                       lollipops on a log-x axis
  fig_drift_panel    : fingerprint per timepoint (jittered markers
                       with three distinct line styles) and a
                       horizontal lollipop pairwise drift panel

palette: deep teal (primary), amber (weak family), and a
royal blue / royal purple / forest green trio for the three drift
timepoints. bordeaux is reserved for threshold lines and false
positives so it never collides with a timepoint marker color.

no titles or in-figure descriptive text are written here; figure
text belongs in the latex caption.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.lines import Line2D


# --- visual constants ---

TEAL    = "#1f5f6b"   # primary, also tpr in sample curve
AMBER   = "#c08a1c"   # weak family
BORDX   = "#9a3a3a"   # thresholds and fpr
SLATE   = "#3a3a44"   # text
MIST    = "#d8d8d2"   # grid

# drift timepoint palette (matches the layer-stack figure in the paper)
T0 = "#1565C0"   # royal blue
T1 = "#5B2C91"   # royal purple
T2 = "#1B5E20"   # forest green

DPI = 220


def apply_style():
    """house style for all figures."""
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10.5,
        "axes.labelsize": 10.5,
        "axes.edgecolor": SLATE,
        "axes.linewidth": 0.8,
        "axes.labelcolor": SLATE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
        "grid.color": MIST,
        "grid.linestyle": (0, (2, 2)),
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
    })


def load(p):
    with open(p) as f:
        return json.load(f)


def fig_detection_bars(d, out_path):
    """horizontal lollipops, weak family in amber, local family
    in teal, tolerance line in bordeaux."""
    weak_set = set(d.get("weak_family", []))
    family = d["complete_family"]
    if weak_set and not (weak_set <= set(family)):
        family = list(weak_set) + family

    fp_h = d["fingerprint_honest"]
    fp_s = d["fingerprint_sneaky"]
    devs = [abs(fp_h[p] - fp_s[p]) for p in family]
    colors = [AMBER if p in weak_set else TEAL for p in family]
    eps = d["eps"]

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.set_axisbelow(True)
    ax.xaxis.grid(True)

    y = np.arange(len(family))
    xmax = max(max(devs), eps) * 1.20

    for yi, v, c in zip(y, devs, colors):
        ax.plot([0, v], [yi, yi], color=c, linewidth=1.8,
                alpha=0.85, zorder=2)
        ax.scatter([v], [yi], s=130, color=c,
                   edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(v + xmax * 0.018, yi, f"{v:.3f}",
                va="center", fontsize=9.2, color=SLATE)

    ax.axvline(eps, color=BORDX, linewidth=1.4, zorder=1)

    proxy_weak = Line2D([0], [0], marker="o", color="w",
                        markerfacecolor=AMBER, markersize=10,
                        label="weak family")
    proxy_local = Line2D([0], [0], marker="o", color="w",
                            markerfacecolor=TEAL, markersize=10,
                            label="local family")
    proxy_tol = Line2D([0], [0], color=BORDX, linewidth=1.4,
                       label=fr"tolerance $\varepsilon = {eps}$")
    ax.legend(handles=[proxy_weak, proxy_local, proxy_tol],
              loc="lower right")

    ax.set_yticks(y)
    ax.set_yticklabels(family)
    ax.set_ylim(-0.7, len(family) - 0.3)
    ax.invert_yaxis()
    ax.set_xlim(-xmax * 0.01, xmax)
    ax.set_xlabel(
        r"$|\langle P \rangle_{\mathrm{honest}}"
        r" - \langle P \rangle_{\mathrm{sneaky}}|$"
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI)
    print(f"saved {out_path}")
    plt.close(fig)


def fig_sample_curve(d, out_path):
    """vertical lollipops on a log-x axis showing tpr (true
    positive rate, teal) and fpr (false positive rate, bordeaux)
    for each shot budget. dashed lines at the target tpr (1-eta)
    and target fpr (eta) provide reference."""
    labels = list(d["results"].keys())
    shots = [d["results"][k]["shots_per_obs"] for k in labels]
    # support both new (tpr/fpr) and old (detection_rate) format
    if "tpr" in d["results"][labels[0]]:
        tprs = [d["results"][k]["tpr"] for k in labels]
        fprs = [d["results"][k]["fpr"] for k in labels]
    else:
        tprs = [d["results"][k]["detection_rate"] for k in labels]
        fprs = None
    target_tpr = 1 - d["eta"]
    target_fpr = d["eta"]

    order = np.argsort(shots)
    shots = [shots[i] for i in order]
    tprs = [tprs[i] for i in order]
    if fprs is not None:
        fprs = [fprs[i] for i in order]
    labels = [labels[i] for i in order]

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.set_axisbelow(True)
    ax.xaxis.grid(True)
    ax.yaxis.grid(True)

    # tpr lollipops in teal, slightly offset to the left
    offset = 1.08
    for s, t in zip(shots, tprs):
        ax.plot([s / offset, s / offset], [0, t],
                color=TEAL, linewidth=1.8, alpha=0.55, zorder=2)
    ax.scatter([s / offset for s in shots], tprs, s=140,
               marker="D", color=TEAL, edgecolor="white",
               linewidth=1.2, zorder=3, label="TPR (sneaky)")

    # fpr lollipops in bordeaux, slightly offset to the right
    if fprs is not None:
        for s, f in zip(shots, fprs):
            ax.plot([s * offset, s * offset], [0, f],
                    color=BORDX, linewidth=1.8, alpha=0.55, zorder=2)
        ax.scatter([s * offset for s in shots], fprs, s=140,
                   marker="X", color=BORDX, edgecolor="white",
                   linewidth=1.2, zorder=3, label="FPR (honest)")

    # budget labels above the markers
    for s, t, lab in zip(shots, tprs, labels):
        ax.annotate(lab, (s, max(t, 1.0)),
                    textcoords="offset points",
                    xytext=(0, 12), ha="center",
                    fontsize=9, color=SLATE)

    # reference lines
    ax.axhline(target_tpr, color=TEAL, linestyle=(0, (4, 3)),
               linewidth=1.0, alpha=0.7,
               label=fr"target TPR = $1-\eta = {target_tpr}$")
    ax.axhline(target_fpr, color=BORDX, linestyle=(0, (4, 3)),
               linewidth=1.0, alpha=0.7,
               label=fr"target FPR = $\eta = {target_fpr}$")
    ax.set_xscale("log")
    ax.set_xlim(min(shots) * 0.55, max(shots) * 1.8)
    ax.set_xlabel("shots per observable")
    ax.set_ylabel("rate")
    ax.set_ylim(-0.04, 1.20)
    ax.legend(loc="center right", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI)
    print(f"saved {out_path}")
    plt.close(fig)


def fig_drift_panel(d, out_path):
    """two panels:
      top - jittered markers with three line styles per timepoint
      bottom - horizontal lollipop pairwise drift with d_drift line
    no titles; the caption in latex carries the description."""
    fps = d["fingerprints"]
    family = list(fps[0].keys())
    n_t = len(fps)
    vals = np.array([[fps[t][p] for p in family] for t in range(n_t)])

    d_drift = d.get("d_drift_typ", None)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.2, 5.6),
        gridspec_kw={"height_ratios": [2, 1.2]},
    )

    # top: jittered markers + connecting lines with distinct styles
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(True)
    x = np.arange(len(family))

    tp_colors = [T0, T1, T2, BORDX][:n_t]
    tp_markers = ["h", "D", "P", "X"][:n_t]
    tp_lstyles = ["-", (0, (5, 2)), (0, (1, 2)), (0, (3, 1, 1, 1))][:n_t]
    if n_t == 1:
        offsets = [0.0]
    else:
        span = 0.20
        offsets = np.linspace(-span / 2, span / 2, n_t)

    # faint vertical guides for each observable
    for xi in x:
        ax1.axvline(xi, color=MIST, linewidth=0.6, zorder=1)

    for t in range(n_t):
        xj = x + offsets[t]
        ax1.plot(xj, vals[t], color=tp_colors[t],
                 linewidth=1.6, linestyle=tp_lstyles[t],
                 alpha=0.85, zorder=2)
        ax1.scatter(xj, vals[t], s=150, marker=tp_markers[t],
                    color=tp_colors[t], edgecolor="white",
                    linewidth=1.4, zorder=3,
                    label=f"timepoint $t_{{{t+1}}}$")
    ax1.set_xticks(x)
    ax1.set_xticklabels(family)
    ax1.set_ylabel(r"$\langle P \rangle$")
    ax1.legend(loc="lower right", ncol=min(n_t, 3))

    # bottom: pairwise lollipop
    pairwise = d.get("pairwise_deviations", {})
    if pairwise:
        ax2.set_axisbelow(True)
        ax2.xaxis.grid(True)
        labels = list(pairwise.keys())
        # archived keys are 0-based (t0_t1); display 1-based to match the paper table
        disp = [l.replace("t0","tA").replace("t1","tB").replace("t2","tC")
                  .replace("tA","t1").replace("tB","t2").replace("tC","t3")
                  .replace("_", " -> ") for l in labels]
        pvals = [pairwise[k] for k in labels]
        yb = np.arange(len(labels))
        xmax = max(pvals + [d_drift if d_drift is not None else 0]) * 1.35
        for yi, v in zip(yb, pvals):
            ax2.plot([0, v], [yi, yi], color=TEAL, linewidth=1.8,
                     alpha=0.85, zorder=2)
            ax2.scatter([v], [yi], s=130, color=TEAL,
                        edgecolor="white", linewidth=1.2, zorder=3)
            ax2.text(v + xmax * 0.015, yi, f"{v:.3f}",
                     va="center", fontsize=9.2, color=SLATE)
        if d_drift is not None:
            ax2.axvline(
                d_drift, color=BORDX, linewidth=1.4,
                label=(
                    fr"$d_{{\mathrm{{drift}}}}^{{\mathrm{{typ}}}}"
                    fr" = {d_drift:.3f}$"
                ),
            )
            ax2.legend(loc="lower right")
        ax2.set_yticks(yb)
        ax2.set_yticklabels(disp)
        ax2.set_xlim(0, xmax)
        ax2.invert_yaxis()
        ax2.set_xlabel("pairwise max deviation")

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI)
    print(f"saved {out_path}")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="json files")
    ap.add_argument("--outdir", default="results/figures")
    args = ap.parse_args()

    apply_style()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for p in args.paths:
        d = load(p)
        exp = d.get("experiment", "")
        stem = Path(p).stem
        if exp == "detection":
            fig_detection_bars(d, outdir / f"{stem}_bars.png")
        elif exp == "sample_complexity_validation":
            fig_sample_curve(d, outdir / f"{stem}_curve.png")
        elif exp == "drift_observation":
            fig_drift_panel(d, outdir / f"{stem}_panel.png")
        else:
            print(f"skipping {p}: unknown experiment type")


if __name__ == "__main__":
    main()