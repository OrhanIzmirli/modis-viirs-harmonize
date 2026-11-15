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
        ax.grid(False); ax.tick_params(labelsize=10, colors=MUTED)
        ax.title.set_fontsize(15)
    m = det[:, 2] == 0
    axes[0].scatter(det[~m, 1], det[~m, 0], s=6, color=VIIRS, alpha=0.7, lw=0, label=f"VIIRS 375 m pixels ({(~m).sum():,})")
    axes[0].scatter(det[m, 1], det[m, 0], s=22, color=MODIS, alpha=0.5, lw=0, label=f"MODIS 1 km pixels ({m.sum():,})")
    axes[0].set_title(f"Before: {len(det):,} raw detections")
    axes[0].legend(loc="lower left", fontsize=12, markerscale=1.6)
    col = {"both": ACCENT, "modis_only": MODIS, "viirs_only": VIIRS}
    for la, lo, ag, frp, n, k, nd in sorted(ev, key=lambda e: -e[3]):
        axes[1].scatter([lo], [la], s=max(40, 40 * np.log1p(frp)), color=col[ag], alpha=0.8, edgecolor=PAPER, lw=1)
        axes[1].annotate(f"{nd:,} detections that day", (lo, la), xytext=(10, 8), textcoords="offset points",
                         fontsize=12, color=INK)
    axes[1].set_title(f"After: {len(ev)} fire events (all seen by both satellites)" if all(e[2] == "both" for e in ev)
                      else f"After: {len(ev)} fire events")
    fig.suptitle(f"What two satellites saw — {st['name']}, {pd.Timestamp(st['day']).day} {pd.Timestamp(st['day']):%B %Y}",
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
    fig.text(0.05, 0.40, "25 years of MODIS and VIIRS fire\ndetections in one weekly calendar.", fontsize=17, color=INK2, va="center")
    n_det, n_ev = int(r["det_modis"].sum() + r["det_viirs"].sum()), int(r["new_events"].sum())
    fig.text(0.05, 0.255, f"{n_det:,} detections", fontsize=19, fontweight="bold", color=INK, va="center")
    fig.text(0.05, 0.195, f"→ {n_ev:,} fire events", fontsize=19, fontweight="bold", color=ACCENT, va="center")
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


def fig_climate():
    """Global temperature anomaly (NASA GISTEMP v4, J-D) vs Türkiye's yearly fire energy, 2001-2025.

    Fire energy is the MODIS-only record (Terra+Aqua, inside the 81 provinces): it is the only
    sensor-consistent series for the whole period. The harmonized/VIIRS totals rise when new VIIRS
    satellites join (2012, 2018, 2023), which would correlate with any upward trend, so their r is
    reported for comparison only. Correlation, not causation.
    """
    g = pd.read_csv(ROOT / "data" / "gistemp" / "GLB.Ts+dSST.csv", skiprows=1, na_values="***")
    g = g[g["Year"].between(2001, 2025)].set_index("Year")["J-D"].astype(float)
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    tot = {}
    for mode in ("modis", "harmonized"):
        r = pd.DataFrame(cal["records"][mode]["TR"])
        tot[mode] = r.groupby(pd.to_datetime(r["day"]).dt.year)["frp_mw"].sum().reindex(g.index).fillna(0)
    y = tot["modis"] / 1000  # GW
    pr, sr = stats.pearsonr(g, y), stats.spearmanr(g, y)
    yrs = g.index.to_numpy()
    detr = lambda v: v - np.polyval(np.polyfit(yrs, v, 1), yrs)
    pd_ = stats.pearsonr(detr(g.to_numpy()), detr(y.to_numpy()))
    ph = stats.pearsonr(g, tot["harmonized"])
    res = {"years": [int(yrs[0]), int(yrs[-1])], "n": int(len(yrs)),
           "gistemp_series": "GISTEMP v4 global land-ocean, annual (J-D), anomaly vs 1951-1980 (deg C)",
           "frp_series": "MODIS Terra+Aqua, yearly sum of daily FRP inside Türkiye (MW)",
           "modis": {"pearson_r": round(float(pr[0]), 3), "p": round(float(pr[1]), 3),
                     "spearman_rho": round(float(sr[0]), 3), "spearman_p": round(float(sr[1]), 3),
                     "detrended_pearson_r": round(float(pd_[0]), 3), "detrended_p": round(float(pd_[1]), 3)},
           "harmonized_for_comparison": {"pearson_r": round(float(ph[0]), 3), "p": round(float(ph[1]), 4),
                                         "note": "inflated by VIIRS satellites joining in 2012, 2018, 2023"}}
    (OUT / "climate.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    fig = plt.figure(figsize=(13, 5.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.75, 1], height_ratios=[1, 1.35], hspace=0.12, wspace=0.22)
    a1 = fig.add_subplot(gs[0, 0])
    a2 = fig.add_subplot(gs[1, 0], sharex=a1)
    a3 = fig.add_subplot(gs[:, 1])
    a1.plot(yrs, g, "-o", color=INK, ms=3.5, lw=1.6)
    a1.set_ylabel("global temp.\nanomaly (°C)")
    a1.tick_params(labelbottom=False)
    a1.set_title("Global temperature and Türkiye's fire energy, 2001–2025", fontsize=13.5)
    cols = [ACCENT if yy == 2021 else MODIS for yy in yrs]
    a2.bar(yrs, y, 0.72, color=cols)
    a2.set_ylabel("fire energy (GW,\nMODIS, yearly sum)")
    a2.text(2021, y.loc[2021], "2021", ha="center", va="bottom", fontsize=9, color=ACCENT)
    a3.scatter(g, y, s=34, color=MODIS, edgecolor=PAPER, lw=0.6, zorder=3)
    a3.scatter([g.loc[2021]], [y.loc[2021]], s=46, color=ACCENT, zorder=4)
    for yy in (2001, 2009, 2021, 2025):
        a3.annotate(str(yy), (g.loc[yy], y.loc[yy]), xytext=(5, 3), textcoords="offset points", fontsize=8.5,
                    color=ACCENT if yy == 2021 else INK2)
    a3.set_xlabel("global temperature anomaly (°C)")
    a3.set_ylabel("fire energy (GW)")
    m = res["modis"]
    a3.set_title(f"Pearson r = {m['pearson_r']:.2f} (p = {m['p']:.2f})", fontsize=12)
    a3.text(0.98, 0.97, f"Spearman ρ = {m['spearman_rho']:.2f} (p = {m['spearman_p']:.2f})\n"
                        f"detrended r = {m['detrended_pearson_r']:.2f}\nn = {res['n']} years",
            transform=a3.transAxes, fontsize=9, color=INK2, va="top", ha="right", family="monospace")
    fig.text(0.01, -0.035,
             "Sources: NASA FIRMS; NASA GISTEMP. Fire energy: MODIS Terra+Aqua only (Aqua from Jul 2002), the "
             "sensor-consistent record.\nThe merged MODIS+VIIRS total gives r = "
             f"{res['harmonized_for_comparison']['pearson_r']:.2f}, mostly because VIIRS satellites joined in "
             "2012, 2018 and 2023. Correlation, not causation.",
             fontsize=8.5, color=MUTED, family="monospace", ha="left", va="top")
    fig.savefig(FIG / "slide_climate.png", dpi=300, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", FIG / "slide_climate.png", res["modis"])


def fig_ogm():
    """Our yearly series vs OGM official forest-fire statistics (table 2.11), 2001-2024.

    OGM counts forest fires only, nationally; satellites also see agricultural and other vegetation
    fires. Two scopes are compared and all results go to output/ogm_comparison.json:
      * national: all of Türkiye, all months;
      * forest scope: the 14 Mediterranean/Aegean provinces of docs/data/education.json, June-October.
    Harmonized and MODIS-only records are both reported; detrended r guards against shared trends.
    """
    o = pd.read_csv(ROOT / "data" / "ogm" / "ogm_forest_fires_2001_2024.csv").set_index("year")
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    med = json.loads((ROOT / "docs" / "data" / "education.json").read_text(encoding="utf-8"))["mediterranean_provinces"]
    yrs = o.index.to_numpy()

    def series(mode, regions, months=None):
        tot = None
        for reg in regions:
            r = pd.DataFrame(cal["records"][mode].get(reg, []))
            if r.empty:
                continue
            d = pd.to_datetime(r["day"])
            if months:
                r, d = r[d.dt.month.isin(months)], d[d.dt.month.isin(months)]
            g = r.groupby(d.dt.year)[["new_events", "frp_mw"]].sum()
            tot = g if tot is None else tot.add(g, fill_value=0)
        return tot.reindex(o.index).fillna(0)

    detr = lambda v: v - np.polyval(np.polyfit(yrs, v, 1), yrs)

    def corr(a, b, log=False):
        a, b = np.asarray(a, float), np.asarray(b, float)
        if log:
            a, b = np.log10(a), np.log10(b)
        pr, sr, dr = stats.pearsonr(a, b), stats.spearmanr(a, b), stats.pearsonr(detr(a), detr(b))
        return {"pearson_r": round(float(pr[0]), 3), "pearson_p": round(float(pr[1]), 4),
                "spearman_rho": round(float(sr[0]), 3), "spearman_p": round(float(sr[1]), 4),
                "detrended_r": round(float(dr[0]), 3), "detrended_p": round(float(dr[1]), 4)}

    scopes = {"national": (["TR"], None), "forest_scope": (med, [6, 7, 8, 9, 10])}
    res = {"years": [int(yrs[0]), int(yrs[-1])], "n": int(len(yrs)),
           "ogm_source": "OGM Ormancılık İstatistikleri 2024, table 2.11 (data/ogm/SOURCE.md); national forest fires",
           "forest_scope": "14 Mediterranean/Aegean provinces (docs/data/education.json), June-October"}
    S = {}
    for sc, (regs, mo) in scopes.items():
        for mode in ("harmonized", "modis"):
            s = S[(sc, mode)] = series(mode, regs, mo)
            res[f"{sc}_{mode}"] = {"events_vs_ogm_fires": corr(s["new_events"], o["fires"]),
                                   "log_frp_vs_log_burnt_area": corr(s["frp_mw"], o["burnt_area_ha"], log=True)}
    (OUT / "ogm_comparison.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    hn, hf = S[("national", "harmonized")], S[("forest_scope", "harmonized")]
    cn, af = res["national_harmonized"]["events_vs_ogm_fires"], res["forest_scope_harmonized"]["log_frp_vs_log_burnt_area"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.25})
    a1.plot(yrs, o["fires"] / o["fires"].mean(), "-o", color=INK, ms=3.5, lw=1.7, label="OGM: forest fires (count)")
    a1.plot(yrs, hn["new_events"] / hn["new_events"].mean(), "-o", color=ACCENT, ms=3.5, lw=1.7,
            label="Satellite: fire events, all Türkiye (merged)")
    a1.axhline(1, color=MUTED, lw=0.8, ls=":")
    for x0, lab in ((2012, "VIIRS joins"), (2018, "NOAA-20")):
        a1.axvline(x0 - 0.5, color=MUTED, lw=0.8, ls=":")
        a1.text(x0 - 0.4, a1.get_ylim()[1] * 0.97, lab, fontsize=8.5, color=MUTED, va="top")
    a1.set_ylabel("ratio to own 2001–2024 mean")
    a1.legend(loc="lower right", fontsize=9.5)
    a1.set_title(f"Counts: r = {cn['pearson_r']:.2f}, detrended r = {cn['detrended_r']:.2f}", fontsize=12.5)
    a2.scatter(o["burnt_area_ha"], hf["frp_mw"] / 1000, s=34, color=ACCENT, edgecolor=PAPER, lw=0.6, zorder=3)
    for yy in (2008, 2021, 2014, 2024):
        a2.annotate(str(yy), (o.loc[yy, "burnt_area_ha"], hf.loc[yy, "frp_mw"] / 1000), xytext=(5, 3),
                    textcoords="offset points", fontsize=8.5, color=INK2)
    a2.set_xscale("log"); a2.set_yscale("log")
    a2.set_xlabel("OGM burnt forest area, Türkiye (ha, log)")
    a2.set_ylabel("fire energy, Med./Aegean Jun–Oct (GW, log)")
    a2.set_title(f"Area vs energy: r(log) = {af['pearson_r']:.2f}, \u03c1 = {af['spearman_rho']:.2f}", fontsize=12.5)
    mn, mf = res["national_modis"], res["forest_scope_modis"]
    fig.text(0.01, -0.035,
             "Sources: NASA FIRMS; OGM Forestry Statistics 2024, table 2.11. 2001–2024 (OGM 2025 not yet published).\n"
             "Different scopes: OGM counts forest fires only; satellites also see agricultural, pasture and other vegetation "
             "fires.\nRight panel: satellite energy from 14 Mediterranean/Aegean provinces, June–October, vs national OGM area. "
             f"MODIS only: counts r = {mn['events_vs_ogm_fires']['pearson_r']:.2f},\n"
             f"area vs energy r(log) = {mf['log_frp_vs_log_burnt_area']['pearson_r']:.2f}. Merged record r is partly a shared "
             "upward trend (more satellites, more reported fires). Correlation, not calibration.",
             fontsize=8.5, color=MUTED, family="monospace", ha="left", va="top")
    fig.savefig(FIG / "slide_ogm.png", dpi=300, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", FIG / "slide_ogm.png", json.dumps(res, ensure_ascii=False))



def fig_calendar_slide():
    """Readable crop of the almanac calendar for slides: weekly fire energy, all weeks, 2012-2025."""
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    r = pd.DataFrame(cal["records"]["harmonized"]["TR"])
    r["day"], r["region"] = pd.to_datetime(r["day"]), "TR"
    wk = H.weekly_anomalies(r, "frp_mw", years=(2012, 2025), min_value=100)
    y0, y1 = 2012, 2025
    sub = wk[wk["year"].between(y0, y1)]
    allv = wk[(wk["year"] >= 2012) & (wk["value"] > 0)]["value"].sort_values().to_numpy()
    qs = [allv[int(p * (len(allv) - 1))] for p in (0.40, 0.70, 0.88, 0.97)]
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.grid(False)
    for s in sub.itertuples():
        lv = 0 if s.value <= 0 else 1 + sum(s.value > q for q in qs)
        ax.add_patch(Rectangle((s.week - 0.45, y1 - s.year - 0.42), 0.9, 0.84, fc=RAMP[lv], ec="none"))
        if s.unusual and s.z >= 5:
            ax.add_patch(Rectangle((s.week - 0.5, y1 - s.year - 0.5), 1.0, 1.0, fc="none", ec="#3b0d03", lw=1.8))
    wmax = int(sub["week"].max())
    ax.set_xlim(sub["week"].min() - 0.6, wmax + 0.6)
    ax.set_ylim(y1 - y0 + 0.6, -0.6)
    ax.set_yticks(range(0, y1 - y0 + 1, 1), [str(y1 - i) if (y1 - i) % 2 else "" for i in range(0, y1 - y0 + 1)],
                  fontsize=13)
    ticks = [H.week_index(pd.Series([pd.Timestamp(2021, m, 1)])).iloc[0] for m in (1, 3, 5, 7, 9, 11)]
    ax.set_xticks(ticks, ["Jan", "Mar", "May", "Jul", "Sep", "Nov"], fontsize=13)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("Weekly fire energy, Türkiye, 2012–2025", fontsize=16, pad=10)
    for i, (lab, c) in enumerate([("low", RAMP[1]), ("", RAMP[2]), ("", RAMP[3]), ("", RAMP[4]), ("high", RAMP[5])]):
        fig.patches.append(Rectangle((0.14 + i * 0.05, 0.015), 0.045, 0.03, transform=fig.transFigure, fc=c, ec="none"))
    fig.text(0.13, 0.03, "less", ha="right", va="center", fontsize=12, color=INK2)
    fig.text(0.395, 0.03, "more energy     dark box = exceptional week (z ≥ 5)", ha="left", va="center",
             fontsize=12, color=INK2)
    fig.subplots_adjust(bottom=0.14)
    finish(fig, "slide_calendar.png", "Harmonized MODIS + VIIRS")


if __name__ == "__main__":
    fig_2021()
    fig_calendar_slide()
    fig_before_after()
    print("frp", fig_frp())
    fig_match()
    fig_dedup()
    og_cover()
    fig_climate()
    fig_ogm()
