"""Directive 006: the figure of the three regimes, drawn from the JSON of ``ec.regimes``.

  python3 scripts/rd_figure.py IN.json OUT.pdf

Top: the rate in bits per event against the rms timing tolerance, on a logarithmic axis. Bottom:
the regime between the jitter and the regeneration threshold on a linear axis. Theorem 2 gives the
solid lines and the band between its bounds. The circles are the numerical rate-distortion
function (R1) and the squares the operating points of the simple coder (R2). Nothing is computed
here except Theorem 2 on a dense axis, through ``ec.regimes.theory``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ec import regimes  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#d6542a"       # the two categorical colors of Fig. 1 of the manuscript
INK, MUTED, BAND = "#0b0b0b", "#52514e", "#dcdbd5"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "mathtext.fontset": "cm"})


def draw(d, out_pdf):
    c = d["constants"]
    n, tau, s, DA = c["n"], c["tau"], c["sigma"], c["D_A"]
    per = 1.0 / (n * regimes.LN2)                          # nats per pixel -> bits per event
    x_s, x_a = s / tau, np.sqrt(DA) / tau

    def th(D):
        lo, up = zip(*(regimes.theory(float(v), c) for v in D))
        return np.array(lo) * per, np.array(up) * per

    ba = np.array([(np.sqrt(r["D"]) / tau, r["R_upper"] * per) for r in d["rd"]])
    cod = [(np.sqrt(p["D"]) / tau, p["R"] * per) for k in ("all", "mean") for p in d["coder"][k]]
    cod = np.array(cod + [(np.sqrt(d["coder"]["none"]["D"]) / tau, 0.0)])

    fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.45, 3.9), gridspec_kw={"height_ratios": [1.25, 1.0], "hspace": 0.42})

    # top: all three regimes
    x_lo, x_hi = 0.6 * ba[:, 0].min(), 0.62
    r_lo = np.geomspace(x_lo, x_s, 60)
    ax.plot(r_lo, th((r_lo * tau) ** 2)[1], color=INK, lw=1.1, zorder=3, label="Theorem 2")
    r_mid = np.linspace(x_s, x_a, 200)[1:-1]
    lo, up = th((r_mid * tau) ** 2)
    ax.fill_between(r_mid, lo, up, color=BAND, lw=0, zorder=1)
    ax.plot(r_mid, lo, color=INK, lw=0.6, zorder=2)
    ax.plot(r_mid, up, color=INK, lw=0.6, zorder=2)
    ax.plot([x_a, x_hi], [0, 0], color=INK, lw=1.1, zorder=3)
    ax.plot(ba[:, 0], ba[:, 1], "o", color=BLUE, ms=3.4, mec="white", mew=0.5, zorder=5, label="numerical $R(D)$")
    ax.plot(cod[:, 0], cod[:, 1], "s", color=ORANGE, ms=3.2, mec="white", mew=0.5, zorder=4, label="scalar quantizer")
    y_hi = 1.12 * max(ba[:, 1].max(), cod[:, 1].max())
    for xv in (x_s, x_a):
        ax.plot([xv, xv], [0, y_hi], color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    ax.set_xscale("log")
    ax.set_xlim(x_lo, x_hi)
    ticks = [v for v in (0.003, 0.01, 0.03, 0.1, 0.3) if x_lo <= v <= x_hi]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{v:g}" for v in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylim(-0.04 * y_hi, y_hi)
    ax.set_ylabel("bits per event", labelpad=2)
    ax.set_xlabel(r"rms timing tolerance $\sqrt{D}/\tau_i$", labelpad=1)
    top = ax.secondary_xaxis("top")
    top.set_xticks([x_s, x_a])
    top.set_xticklabels([r"$\sigma$", r"$\sqrt{D_{A,i}}$"])
    top.tick_params(length=2, width=0.5, pad=1)
    top.minorticks_off()
    ty = 0.93 * y_hi
    for xv, text in ((np.sqrt(x_lo * x_s) * 1.25, "every\nevent time"), (np.sqrt(x_s * x_a), "one number\nper pixel"),
                     (np.sqrt(x_a * x_hi), "nothing")):
        ax.text(xv, ty, text, ha="center", va="top", fontsize=7, color=INK, linespacing=1.05)
    ax.legend(loc="lower left", frameon=False, fontsize=7, handlelength=1.4, borderaxespad=0.3, labelspacing=0.3)

    # bottom: between the jitter and the threshold
    r_mid = np.linspace(x_s, x_a, 300)[1:]
    lo, up = th((r_mid * tau) ** 2)
    bx.fill_between(r_mid, lo, up, color=BAND, lw=0, zorder=1)
    bx.plot(r_mid, lo, color=INK, lw=0.6, zorder=2)
    bx.plot(r_mid, up, color=INK, lw=0.6, zorder=2)
    bx.plot([x_a, 1.12 * x_a], [0, 0], color=INK, lw=1.1, zorder=3)
    sel = ba[:, 0] >= 0.98 * x_s
    bx.plot(ba[sel, 0], ba[sel, 1], "o", color=BLUE, ms=3.4, mec="white", mew=0.5, zorder=5)
    sel = cod[:, 0] >= 0.98 * x_s
    bx.plot(cod[sel, 0], cod[sel, 1], "s", color=ORANGE, ms=3.2, mec="white", mew=0.5, zorder=4)
    y2 = 1.08 * max(up.max(), cod[sel, 1].max())
    bx.plot([x_a, x_a], [0, y2], color=MUTED, lw=0.5, ls=(0, (2, 2)), zorder=0)
    bx.set_xlim(0.9 * x_s, 1.12 * x_a)
    bx.set_ylim(-0.04 * y2, y2)
    bx.set_ylabel("bits per event", labelpad=2)
    bx.set_xlabel(r"rms timing tolerance $\sqrt{D}/\tau_i$", labelpad=1)
    k = int(np.argmin(np.abs(r_mid - 0.45 * (x_s + x_a))))
    bx.annotate("bounds of\nTheorem 2", xy=(r_mid[k], 0.5 * (lo[k] + up[k])), xytext=(r_mid[k] + 0.25 * (x_a - x_s), 0.62 * y2),
                fontsize=7, ha="left", va="center", color=INK,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=MUTED, shrinkA=1, shrinkB=1))
    for a in (ax, bx):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.tick_params(length=2, width=0.5)
        a.tick_params(which="minor", length=1.2, width=0.4)
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(str(out_pdf)[:-4] + ".png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    if len(sys.argv) != 3 or not sys.argv[2].endswith(".pdf"):
        sys.exit("usage: python3 scripts/rd_figure.py IN.json OUT.pdf")
    draw(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    print("wrote", sys.argv[2])
