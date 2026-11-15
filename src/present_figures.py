"""Slide-ready figures on a light paper background (figures/slide_*.png, 300 dpi).

Reads pipeline/validation outputs only.
    python src/present_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy import stats  # noqa: E402

import harmonize as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, FIG = ROOT / "output", ROOT / "figures"
SOURCE = "Source: NASA FIRMS, MODIS C6.1 & VIIRS 375 m, 2001-2025"
PAPER, INK, INK2, MUTED, RULE = "#faf7f2", "#1a1816", "#4a4540", "#7a736b", "#d9d2c6"
ACCENT, MODIS, VIIRS = "#c2410c", "#00897b", "#7356bf"
RAMP = ["#efe9df", "#f5d9b5", "#eeb07a", "#e07b39", "#c2410c", "#7f1d0b"]
plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER, "axes.edgecolor": INK2,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.titlecolor": INK,
    "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 11, "axes.titlesize": 14,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e2d8", "grid.linewidth": 0.7, "legend.frameon": False,
})


def finish(fig, name, note=""):
    fig.text(0.01, -0.035, SOURCE + (". " + note if note else ""), fontsize=8.5, color=MUTED, family="monospace",
             ha="left", va="top")
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", FIG / name)


def fig_2021():
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    r = pd.DataFrame(cal["records"]["harmonized"]["TR"])
    r["day"], r["region"] = pd.to_datetime(r["day"]), "TR"
    wk = H.weekly_anomalies(r, "frp_mw", years=(2012, 2025), min_value=100)
    y0, y1, w0, w1 = 2014, 2025, 21, 41
    sub = wk[wk["year"].between(y0, y1) & wk["week"].between(w0, w1)]
    allv = wk[(wk["year"] >= 2012) & (wk["value"] > 0)]["value"].sort_values().to_numpy()
    qs = [allv[int(p * (len(allv) - 1))] for p in (0.40, 0.70, 0.88, 0.97)]
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.grid(False)
    for s in sub.itertuples():
        lv = 0 if s.value <= 0 else 1 + sum(s.value > q for q in qs)
        yy = y1 - s.year
        ax.add_patch(Rectangle((s.week - 0.42, yy - 0.42), 0.84, 0.84, fc=RAMP[lv], ec="none"))
        if s.unusual:
            strong = s.z >= 5
            ax.add_patch(Rectangle((s.week - 0.5, yy - 0.5), 1.0, 1.0, fc="none", ec="#8f1d07" if strong else ACCENT,
                                   lw=2.2 if strong else 1.0))
    for i, s in enumerate(sub[(sub["year"] == 2021) & (sub["z"] > 10)].sort_values("week").itertuples()):
        dx = -4.5 if i == 0 else 4.5
        ax.annotate(f"z = {s.z:.0f}\n{s.value / s.mean:.0f}× the usual\nfire energy", (s.week, y1 - 2021),
                    xytext=(s.week + dx, y1 - 2021 + 2.4), fontsize=10, color=INK, ha="center",
                    bbox=dict(boxstyle="square,pad=0.3", fc=PAPER, ec=INK2, lw=0.6),
                    arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    ax.set_xlim(w0 - 0.6, w1 + 0.6)
    ax.set_ylim(-0.6, y1 - y0 + 0.6)
    ax.set_yticks(range(0, y1 - y0 + 1), [str(y1 - i) for i in range(0, y1 - y0 + 1)])
    ticks = [H.week_index(pd.Series([pd.Timestamp(2021, m, 1)])).iloc[0] for m in range(6, 11)]
    ax.set_xticks(ticks, ["1 Jun", "1 Jul", "1 Aug", "1 Sep", "1 Oct"])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Summer 2021 stands out: weekly fire energy in Türkiye, June–October, 2014–2025", pad=12)
    ax.text(w1 + 0.6, -1.9, "thin red outline = unusual week (z > 1.5)   heavy dark outline = exceptional (z ≥ 5)",
            ha="right", fontsize=9, color=INK2, family="monospace")
    finish(fig, "slide_2021_unusual.png", "Harmonized MODIS + VIIRS, z-score vs 2012-2025 leave-one-out weekly mean")


def fig_before_after():
    st = json.loads((ROOT / "docs" / "data" / "story.json").read_text(encoding="utf-8"))
    det = np.array([[a, b, s] for a, b, s in st["detections"]])
    ev = st["events"]
    from shapely.geometry import shape
    gj = json.loads((ROOT / "data" / "boundaries" / "tur_adm1.geojson").read_text(encoding="utf-8"))
    lats = np.r_[det[:, 0], [e[0] for e in ev]]
    lons = np.r_[det[:, 1], [e[1] for e in ev]]
    pad = 0.06
    ext = (lons.min() - pad, lons.max() + pad, lats.min() - pad, lats.max() + pad)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.0))
    for ax in axes:
        for f in gj["features"]:
            g = shape(f["geometry"])
            for poly in getattr(g, "geoms", [g]):
                x, y = poly.exterior.xy
                ax.fill(x, y, fc="#f1ece3", ec="#b9b0a3", lw=0.6, zorder=0)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_aspect(1 / np.cos(np.radians(lats.mean())))
        ax.set_facecolor("#e3e8ec")
        ax.grid(False); ax.tick_params(labelsize=8.5, colors=MUTED)
    m = det[:, 2] == 0
    axes[0].scatter(det[~m, 1], det[~m, 0], s=6, color=VIIRS, alpha=0.7, lw=0, label=f"VIIRS 375 m pixels ({(~m).sum():,})")
    axes[0].scatter(det[m, 1], det[m, 0], s=22, color=MODIS, alpha=0.5, lw=0, label=f"MODIS 1 km pixels ({m.sum():,})")
    axes[0].set_title(f"Before: {len(det):,} raw detections")
    axes[0].legend(loc="lower left", fontsize=9.5)
    col = {"both": ACCENT, "modis_only": MODIS, "viirs_only": VIIRS}
    for la, lo, ag, frp, n, k, nd in sorted(ev, key=lambda e: -e[3]):
        axes[1].scatter([lo], [la], s=max(40, 40 * np.log1p(frp)), color=col[ag], alpha=0.8, edgecolor=PAPER, lw=1)
        axes[1].annotate(f"{nd:,} detections that day", (lo, la), xytext=(10, 8), textcoords="offset points",
                         fontsize=9.5, color=INK)
    axes[1].set_title(f"After: {len(ev)} fire events (all seen by both satellites)" if all(e[2] == "both" for e in ev)
                      else f"After: {len(ev)} fire events")
    fig.suptitle(f"Two satellites, one truth — {st['name']}, {pd.Timestamp(st['day']).day} {pd.Timestamp(st['day']):%B %Y}",
                 x=0.01, ha="left", fontsize=16, fontweight="bold", y=1.02)
    finish(fig, "slide_before_after.png", "Event circles sized by total fire radiative power")


def fig_frp():
    d = pd.read_csv(OUT / "detections_harmonized.csv", parse_dates=["time_utc"],
                    usecols=["time_utc", "satellite", "frp_mw", "event_id", "day_night"])
    a = d[d["satellite"] == "Aqua"].groupby(["event_id", "time_utc", "day_night"])["frp_mw"].sum().reset_index()
    v = d[d["satellite"].isin(["S-NPP", "NOAA-20"])].groupby(["event_id", "time_utc"])["frp_mw"].sum().reset_index()
    m = a.merge(v, on="event_id", suffixes=("_m", "_v"))
    m = m[(m["time_utc_v"] - m["time_utc_m"]).abs() <= pd.Timedelta(minutes=30)]
    m = m.assign(dt=(m["time_utc_v"] - m["time_utc_m"]).abs()).sort_values("dt").drop_duplicates(["event_id", "time_utc_m"])
    m = m[(m["frp_mw_m"] > 0) & (m["frp_mw_v"] > 0)]
    x, y = np.log10(m["frp_mw_m"]), np.log10(m["frp_mw_v"])
    r = stats.pearsonr(x, y)[0]
    rho = stats.spearmanr(m["frp_mw_m"], m["frp_mw_v"])[0]
    sl, ic = np.polyfit(x, y, 1)
    fig, ax = plt.subplots(figsize=(7.2, 6.8))
    ax.scatter(m["frp_mw_m"], m["frp_mw_v"], s=6, color=ACCENT, alpha=0.25, lw=0)
    lo, hi = 0.5, max(m["frp_mw_m"].max(), m["frp_mw_v"].max()) * 1.5
    ax.plot([lo, hi], [lo, hi], color=MUTED, ls="--", lw=1)
    ax.text(hi / 1.6, hi / 1.2, "1:1", color=MUTED, fontsize=9, ha="right")
    xx = np.logspace(np.log10(lo), np.log10(hi), 50)
    ax.plot(xx, 10 ** (ic + sl * np.log10(xx)), color=INK, lw=1.6)
    ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
           xlabel="MODIS (Aqua) fire radiative power per event pass, MW",
           ylabel="VIIRS (S-NPP / NOAA-20) FRP, same event, ≤ 30 min apart, MW")
    ax.set_title(f"Do the two satellites agree on fire intensity?\nr = {r:.2f} (log-log)  ·  ρ = {rho:.2f}  ·  n = {len(m):,} pass pairs",
                 fontsize=13)
    finish(fig, "slide_frp_scatter.png", f"Fit slope {sl:.2f} in log-log space")
    return r, rho, len(m)


def fig_match():
    v = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))["match_rates_by_sensor"]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels = ["MODIS detections\nconfirmed by VIIRS", "VIIRS detections\nconfirmed by MODIS"]
    keys = [("MODIS_D", "MODIS_N"), ("VIIRS_D", "VIIRS_N")]
    x = np.arange(2)
    bars = [("h12", "D", -0.3, ACCENT, "day, within 12 h"), ("h12", "N", -0.1, "#7f1d0b", "night, within 12 h"),
            ("h1", "D", 0.1, "#eeb07a", "day, within 1 h"), ("h1", "N", 0.3, "#b9b0a3", "night, within 1 h")]
    for win, dn, off, c, lab in bars:
        vals = [100 * v[k[0] if dn == "D" else k[1]][win] for k in keys]
        b = ax.bar(x + off, vals, 0.19, color=c, label=lab)
        for bb, val in zip(b, vals):
            ax.text(bb.get_x() + bb.get_width() / 2, val + 1.2, f"{val:.0f}%", ha="center", fontsize=10, color=INK)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 70)
    ax.set_ylabel("share of detections with a match from the other sensor (%)")
    ax.set_title("Half of MODIS fires are also seen by VIIRS — but most VIIRS fires are too small for MODIS", fontsize=13)
    ax.legend(ncol=2, fontsize=9.5, loc="upper right")
    finish(fig, "slide_match_rates.png", "2012-2025; match = same event rule (footprint distance + time window)")


if __name__ == "__main__":
    fig_2021()
    fig_before_after()
    print("frp", fig_frp())
    fig_match()
    fig_dedup()
    og_cover()


def fig_dedup():
    s = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))["dedup"]
    yr = pd.DataFrame(s["per_year"])
    fig, ax = plt.subplots(figsize=(12, 5.2))
    x = yr["year"].to_numpy()
    ax.bar(x - 0.2, yr["modis"], 0.4, color=MODIS, label="MODIS detections")
    ax.bar(x - 0.2, yr["viirs"], 0.4, bottom=yr["modis"], color=VIIRS, label="VIIRS detections")
    ax.bar(x + 0.2, yr["events"], 0.4, color=ACCENT, label="fire events after merging")
    ax.axvline(2011.5, color=MUTED, ls=":", lw=1)
    ax.text(2011.6, ax.get_ylim()[1] * 0.93, "VIIRS (S-NPP) joins", color=INK2, fontsize=9.5)
    ax.axvline(2017.5, color=MUTED, ls=":", lw=1)
    ax.text(2017.6, ax.get_ylim()[1] * 0.86, "NOAA-20 joins", color=INK2, fontsize=9.5)
    ax.set_ylabel("per year")
    ax.legend(loc="upper left", fontsize=10)
    ax.set_title(f"{s['detections']:,} detections become {s['events']:,} fire events ({s['ratio']:.1f} detections per fire)",
                 fontsize=13)
    finish(fig, "slide_dedup.png", "Detections: vegetation fires only (FIRMS type 0)")


def og_cover():
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    r = pd.DataFrame(cal["records"]["harmonized"]["TR"])
    r["day"], r["region"] = pd.to_datetime(r["day"]), "TR"
    wk = H.weekly_anomalies(r, "frp_mw", years=(2012, 2025), min_value=100)
    vals = wk[wk["value"] > 0]["value"].sort_values().to_numpy()
    qs = [vals[int(p * (len(vals) - 1))] for p in (0.40, 0.70, 0.88, 0.97)]
    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor(PAPER)
    fig.text(0.05, 0.86, "THE FIRE ALMANAC OF TÜRKIYE · 2001–2025", family="monospace", fontsize=13, color=MUTED)
    fig.text(0.05, 0.62, "When does\nTürkiye burn?", fontsize=46, fontweight="bold", color=INK, va="center", linespacing=1.0)
    fig.text(0.05, 0.36, "25 years of MODIS and VIIRS fire\ndetections in one weekly calendar.", fontsize=17, color=INK2, va="center")
    fig.text(0.05, 0.12, "NASA FIRMS · MODIS C6.1 & VIIRS 375 m · FireWatch TR", family="monospace", fontsize=11, color=MUTED)
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.80, 0.80], color=INK, lw=1.2, transform=fig.transFigure))
    ax = fig.add_axes([0.53, 0.10, 0.43, 0.66])
    ax.set_axis_off()
    for s in wk[wk["week"] < 53].itertuples():
        lv = 0 if s.value <= 0 else 1 + sum(s.value > q for q in qs)
        ax.add_patch(Rectangle((s.week, 2025 - s.year), 0.86, 0.86, fc=RAMP[lv], ec="none"))
        if s.unusual and s.year >= 2012 and s.z >= 5:
            ax.add_patch(Rectangle((s.week - 0.1, 2025 - s.year - 0.1), 1.06, 1.06, fc="none", ec="#8f1d07", lw=1.2))
    ax.set_xlim(-0.5, 53.5); ax.set_ylim(25.5, -0.5)
    fig.savefig(ROOT / "docs" / "og.png", dpi=100, facecolor=PAPER)
    plt.close(fig)
    fig = plt.figure(figsize=(1.8, 1.8), dpi=100)
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0.12, 0.12, 0.76, 0.76]); ax.set_axis_off()
    for i, (h, c) in enumerate(zip([0.3, 0.55, 0.85], RAMP[2:5])):
        ax.add_patch(Rectangle((i * 0.34, 0), 0.28, h, fc=c))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.savefig(ROOT / "docs" / "og-icon.png", dpi=100, facecolor=PAPER)
    plt.close(fig)
    print("wrote docs/og.png, docs/og-icon.png")
