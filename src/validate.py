"""Validation figures and trend insight (writes figures/*.png and output/validation.json).

    python src/validate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy import stats  # noqa: E402

import harmonize as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, FIG = ROOT / "output", ROOT / "figures"
FIG.mkdir(exist_ok=True)

BG, PANEL, INK, INK2, MUTED, LINE = "#120f0e", "#1a1614", "#f3ece7", "#c9bcb3", "#8f8179", "#2f2724"
BOTH, MODIS, VIIRS, ACCENT, RED = "#e8590c", "#2aa198", "#8c72e8", "#f97316", "#e5392f"
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG, "axes.edgecolor": LINE,
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.titlecolor": INK, "axes.grid": True, "grid.color": LINE, "grid.linewidth": 0.6,
    "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "legend.frameon": False, "axes.spines.top": False, "axes.spines.right": False,
})


def save(fig, name):
    fig.savefig(FIG / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / name)


def load():
    d = pd.read_csv(OUT / "detections_harmonized.csv", parse_dates=["time_utc"], low_memory=False)
    return d.sort_values("time_utc").reset_index(drop=True)


# ------------------------------------------------------------------ 1. match rates
def match_rates(d: pd.DataFrame, res: dict):
    v = d[d["time_utc"] >= H.VIIRS_START].reset_index(drop=True)
    pairs = H.candidate_pairs(v)
    sen = v["sensor"].to_numpy()
    cross = pairs[sen[pairs[:, 0]] != sen[pairs[:, 1]]]
    t = v["time_utc"].to_numpy("datetime64[m]").astype(np.int64)
    dt = np.abs(t[cross[:, 0]] - t[cross[:, 1]])
    out = {}
    for label, sel in (("≤ 12 h (event rule)", np.ones(len(cross), bool)), ("≤ 1 h (near-simultaneous)", dt <= 60)):
        hit = np.zeros(len(v), bool)
        hit[cross[sel].ravel()] = True
        out[label] = hit
    rows = []
    for label, hit in out.items():
        for (sensor, sat, dn), g in v.assign(hit=hit).groupby(["sensor", "satellite", "day_night"]):
            rows.append({"window": label, "sensor": sensor, "satellite": sat, "day_night": dn,
                         "n": len(g), "matched": float(g["hit"].mean())})
    tab = pd.DataFrame(rows)
    res["match_rates"] = tab.round(4).to_dict("records")
    summ = (v.assign(h12=out["≤ 12 h (event rule)"], h1=out["≤ 1 h (near-simultaneous)"])
            .groupby(["sensor", "day_night"])[["h12", "h1"]].mean().round(4))
    res["match_rates_by_sensor"] = {f"{s}_{dn}": r.to_dict() for (s, dn), r in summ.iterrows()}

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, (label, _) in zip(axes, out.items()):
        sub = tab[tab["window"] == label]
        cats = [(s, sat) for s, sat in [("MODIS", "Terra"), ("MODIS", "Aqua"), ("VIIRS", "S-NPP"),
                                        ("VIIRS", "NOAA-20"), ("VIIRS", "NOAA-21")]
                if ((sub["sensor"] == s) & (sub["satellite"] == sat)).any()]
        x = np.arange(len(cats))
        for k, (dn, col, off) in enumerate([("D", ACCENT, -0.2), ("N", "#5b6fd6", 0.2)]):
            vals = [sub[(sub["satellite"] == sat) & (sub["day_night"] == dn)]["matched"].sum() * 100 for _, sat in cats]
            bars = ax.bar(x + off, vals, 0.38, color=col, label={"D": "day", "N": "night"}[dn])
            for b, val in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, val + 1, f"{val:.0f}%", ha="center", fontsize=8, color=INK2)
        ax.set_xticks(x, [f"{sat}\n({s}→{'VIIRS' if s == 'MODIS' else 'MODIS'})" for s, sat in cats])
        ax.set_title(f"Cross-sensor match, {label}")
        ax.set_ylim(0, 105)
    axes[0].set_ylabel("detections with a match from the other sensor (%)")
    axes[0].legend(loc="upper right")
    fig.suptitle("MODIS–VIIRS agreement at detection level (2012+)", color=INK, fontweight="bold")
    save(fig, "match_rates.png")


# ------------------------------------------------------------------ 2. FRP scatter
def frp_scatter(d: pd.DataFrame, res: dict):
    """Per event: Aqua pass vs the nearest S-NPP/NOAA-20 pass within 30 min (same overpass window)."""
    a = d[(d["satellite"] == "Aqua")].groupby(["event_id", "time_utc", "day_night"])["frp_mw"].sum().reset_index()
    v = d[d["satellite"].isin(["S-NPP", "NOAA-20"])].groupby(["event_id", "satellite", "time_utc"])["frp_mw"].sum().reset_index()
    m = a.merge(v, on="event_id", suffixes=("_m", "_v"))
    m["dt"] = (m["time_utc_v"] - m["time_utc_m"]).abs().dt.total_seconds() / 60
    m = m[m["dt"] <= 30].sort_values("dt").drop_duplicates(["event_id", "time_utc_m"])
    m = m[(m["frp_mw_m"] > 0) & (m["frp_mw_v"] > 0)]
    x, y = np.log10(m["frp_mw_m"]), np.log10(m["frp_mw_v"])
    r, p = stats.pearsonr(x, y)
    rho, _ = stats.spearmanr(m["frp_mw_m"], m["frp_mw_v"])
    slope, icpt = np.polyfit(x, y, 1)
    ratio = float(np.median(m["frp_mw_v"] / m["frp_mw_m"]))
    res["frp"] = {"n_pairs": int(len(m)), "pearson_r_log10": round(float(r), 3), "spearman_rho": round(float(rho), 3),
                  "loglog_slope": round(float(slope), 3), "loglog_intercept": round(float(icpt), 3),
                  "median_ratio_viirs_over_modis": round(ratio, 3),
                  "by_daynight": {dn: {"n": int(len(g)), "pearson_r_log10":
                                       round(float(stats.pearsonr(np.log10(g["frp_mw_m"]), np.log10(g["frp_mw_v"]))[0]), 3)}
                                  for dn, g in m.groupby("day_night") if len(g) > 10}}
    fig, ax = plt.subplots(figsize=(6.4, 6))
    for dn, col in (("D", ACCENT), ("N", "#5b6fd6")):
        g = m[m["day_night"] == dn]
        ax.scatter(g["frp_mw_m"], g["frp_mw_v"], s=7, alpha=0.35, color=col, lw=0, label=f"{'day' if dn == 'D' else 'night'} (n={len(g):,})")
    lo, hi = 0.5, max(m["frp_mw_m"].max(), m["frp_mw_v"].max()) * 1.5
    ax.plot([lo, hi], [lo, hi], color=MUTED, ls="--", lw=1, label="1:1")
    xx = np.logspace(np.log10(lo), np.log10(hi), 50)
    ax.plot(xx, 10 ** (icpt + slope * np.log10(xx)), color=INK, lw=1.6, label=f"fit: slope {slope:.2f}")
    ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
           xlabel="MODIS Aqua FRP per event-pass (MW)", ylabel="VIIRS FRP per event-pass (MW, S-NPP / NOAA-20)")
    ax.set_title(f"FRP agreement, |Δt| ≤ 30 min\nPearson r(log) = {r:.2f} · Spearman ρ = {rho:.2f} · n = {len(m):,}")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "frp_scatter.png")


# ------------------------------------------------------------------ 3. dedup
def dedup(d: pd.DataFrame, res: dict):
    meta = json.loads((ROOT / "docs" / "data" / "meta.json").read_text(encoding="utf-8"))
    d = d.assign(year=d["time_utc"].dt.year)
    ev_first = d.groupby("event_id")["time_utc"].min().dt.year
    yr = pd.DataFrame({"modis": d[d.sensor == "MODIS"].groupby("year").size(),
                       "viirs": d[d.sensor == "VIIRS"].groupby("year").size(),
                       "events": ev_first.value_counts()}).fillna(0).sort_index()
    yr["ratio"] = (yr["modis"] + yr["viirs"]) / yr["events"]
    res["dedup"] = {"detections": int(len(d)), "events": int(d["event_id"].nunique()),
                    "ratio": round(len(d) / d["event_id"].nunique(), 2),
                    "per_year": yr.astype(float).round(2).reset_index(names="year").to_dict("records"),
                    "mode_counts": meta["counts"]}
    fig, ax = plt.subplots(figsize=(12, 4.6))
    x = yr.index.to_numpy()
    ax.bar(x - 0.2, yr["modis"], 0.4, color=MODIS, label="MODIS detections")
    ax.bar(x - 0.2, yr["viirs"], 0.4, bottom=yr["modis"], color=VIIRS, label="VIIRS detections")
    ax.bar(x + 0.2, yr["events"], 0.4, color=BOTH, label="harmonized events")
    for xi, (t, e, r) in zip(x, zip(yr["modis"] + yr["viirs"], yr["events"], yr["ratio"])):
        ax.text(xi, t * 1.02, f"{r:.1f}×", ha="center", fontsize=7.5, color=INK2)
    ax.axvline(2011.5, color=MUTED, ls=":", lw=1)
    ax.text(2011.6, ax.get_ylim()[1] * 0.92, "VIIRS S-NPP →", color=MUTED, fontsize=8)
    ax.axvline(2017.5, color=MUTED, ls=":", lw=1)
    ax.text(2017.6, ax.get_ylim()[1] * 0.85, "+ NOAA-20 →", color=MUTED, fontsize=8)
    ax.set_title(f"Raw detections vs harmonized fire events: {len(d):,} → {d['event_id'].nunique():,} "
                 f"({len(d) / d['event_id'].nunique():.1f}× reduction; label = detections per event)")
    ax.set_ylabel("count per year")
    ax.legend(loc="upper left")
    save(fig, "dedup.png")


# ------------------------------------------------------------------ 4. small fire
def small_fire(d: pd.DataFrame, res: dict):
    ev = d.groupby("event_id").agg(agree=("agreement", "first"), n=("frp_mw", "size"),
                                   frp=("frp_mw", "max"), passes=("time_utc", "nunique"),
                                   sats=("satellite", lambda s: len(set(s))), lat=("lat", "mean"),
                                   lon=("lon", "mean"), t0=("time_utc", "min"), prov=("province", "first"),
                                   conf=("confidence_score", "mean"))
    vo = ev[(ev["agree"] == "viirs_only") & ev["prov"].notna()]
    both = ev[ev["agree"] == "both"]
    res["small_fire"] = {"viirs_only_share": round(float((ev["agree"] == "viirs_only").mean()), 4),
                         "median_max_frp_viirs_only": round(float(vo["frp"].median()), 2),
                         "median_max_frp_both": round(float(both["frp"].median()), 2)}
    # example: VIIRS-only, small FRP, short-lived (<= 14 h, 2-4 passes, >= 2 VIIRS satellites), fire season,
    # and NOT a recurring spot (persistent unflagged industrial sources would repeat all year)
    dur = d.groupby("event_id")["time_utc"].agg(lambda t: (t.max() - t.min()).total_seconds() / 3600)
    vo = vo.assign(dur=dur.reindex(vo.index).to_numpy())
    cand = vo[(vo["frp"] < 5) & vo["passes"].between(2, 4) & (vo["sats"] >= 2) & (vo["dur"] <= 14)
              & (vo["conf"] >= 0.5) & pd.to_datetime(vo["t0"]).dt.month.between(6, 10)]
    yr_ev = ev.assign(year=pd.to_datetime(ev["t0"]).dt.year)
    def recurring(r):
        o = yr_ev[(yr_ev["year"] == pd.Timestamp(r["t0"]).year)]
        o = o[(o["lat"] - r["lat"]).abs().lt(0.02) & (o["lon"] - r["lon"]).abs().lt(0.02)]
        return (H.haversine_km(r["lat"], r["lon"], o["lat"], o["lon"]) < 1.5).sum() - 1
    cand = cand.sort_values(["passes", "conf"], ascending=False).head(400)
    cand = cand[[recurring(r) == 0 for _, r in cand.iterrows()]]
    ex = cand.sort_values(["passes", "conf", "frp"], ascending=[False, False, True]).iloc[0]
    det = d[d["event_id"] == ex.name]
    day0, day1 = det["time_utc"].min() - pd.Timedelta(hours=12), det["time_utc"].max() + pd.Timedelta(hours=12)
    near = d[(d["sensor"] == "MODIS") & (d["time_utc"].between(day0, day1))
             & (H.haversine_km(ex["lat"], ex["lon"], d["lat"], d["lon"]) < 15)]
    res["small_fire"]["example"] = {"event_id": ex.name, "province": ex["prov"], "lat": round(ex["lat"], 4),
                                    "lon": round(ex["lon"], 4), "first_seen_utc": str(ex["t0"]),
                                    "viirs_detections": int(ex["n"]), "passes": int(ex["passes"]),
                                    "max_frp_mw": round(float(ex["frp"]), 2),
                                    "modis_detections_within_15km_same_window": int(len(near))}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5), gridspec_kw={"width_ratios": [1, 1.15]})
    bins = np.logspace(-1, 4, 50)
    a1.hist(vo["frp"], bins=bins, color=VIIRS, alpha=0.8, label=f"VIIRS-only events (n={len(vo):,})")
    a1.hist(both["frp"], bins=bins, color=BOTH, alpha=0.7, label=f"MODIS+VIIRS events (n={len(both):,})")
    a1.set(xscale="log", xlabel="max FRP of event (MW)", ylabel="events")
    a1.set_title("VIIRS-only events are small fires")
    a1.legend(fontsize=8)
    kx = 111.32 * np.cos(np.radians(ex["lat"]))
    for r in det.itertuples():
        w, h = r.scan_km / kx, r.track_km / 110.574
        a2.add_patch(Rectangle((r.lon - w / 2, r.lat - h / 2), w, h, fc=VIIRS, ec=INK, alpha=0.35, lw=0.8))
    for r in near.itertuples():
        w, h = r.scan_km / kx, r.track_km / 110.574
        a2.add_patch(Rectangle((r.lon - w / 2, r.lat - h / 2), w, h, fc="none", ec=MODIS, lw=1.2))
    for s, mk in (("S-NPP", "o"), ("NOAA-20", "^"), ("NOAA-21", "s")):
        g = det[det["satellite"] == s]
        if len(g):
            a2.scatter(g["lon"], g["lat"], marker=mk, s=28, color=INK, zorder=3,
                       label=f"{s}: {len(g)} det, FRP {g['frp_mw'].min():.1f}–{g['frp_mw'].max():.1f} MW")
    pad = 0.03
    a2.set_xlim(det["lon"].min() - pad, det["lon"].max() + pad)
    a2.set_ylim(det["lat"].min() - pad, det["lat"].max() + pad)
    a2.set_aspect(1 / np.cos(np.radians(ex["lat"])))
    a2.set_title(f"Example {ex.name} · {ex['prov']} · {pd.Timestamp(ex['t0']).date()}\n"
                 f"{int(ex['n'])} VIIRS 375 m detections on {int(ex['passes'])} passes; "
                 f"MODIS detections within 15 km: {len(near)}", fontsize=10)
    a2.set(xlabel="longitude", ylabel="latitude")
    a2.legend(fontsize=8, loc="lower left")
    save(fig, "small_fire_example.png")


# ------------------------------------------------------------------ 5. trend insight + 2021 check
def season_stats(days: pd.Series, frp: pd.Series, years) -> pd.DataFrame:
    df = pd.DataFrame({"day": pd.to_datetime(days), "frp": frp})
    df["year"], df["doy"] = df["day"].dt.year, df["day"].dt.dayofyear
    rows = []
    for y in years:
        g = df[df["year"] == y].sort_values("doy")
        if len(g) < 20:
            continue
        c = np.arange(1, len(g) + 1) / len(g)
        rows.append({"year": y, "events": len(g), "frp": g["frp"].sum(),
                     "start": int(g["doy"].to_numpy()[np.searchsorted(c, 0.10)]),
                     "end": int(g["doy"].to_numpy()[np.searchsorted(c, 0.90)])})
    out = pd.DataFrame(rows)
    out["length"] = out["end"] - out["start"]
    return out


def trend(s: pd.DataFrame, col: str):
    sl, ic, lo, hi = stats.theilslopes(s[col], s["year"])
    tau, p = stats.kendalltau(s["year"], s[col])
    return {"theil_sen_slope_per_year": round(float(sl), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "kendall_tau": round(float(tau), 3), "p_value": round(float(p), 4)}


def insight(d: pd.DataFrame, res: dict):
    # Consistent sensor record: MODIS (Terra+Aqua) only, events re-linked from MODIS detections alone,
    # restricted to the vegetation-fire season window used by the calendar (all year, by event first day).
    m = d[(d["sensor"] == "MODIS") & d["province"].notna()].reset_index(drop=True)
    lab = H.link_events(m)
    ev = H.build_events(m, lab)
    ev["day"] = H.local_day(ev["first_seen"]).to_numpy()
    years = range(2001, 2026)
    s = season_stats(ev["day"], ev["sum_frp"], years)
    # VIIRS S-NPP only (2012-2025), as an independent check
    v = d[(d["satellite"] == "S-NPP") & d["province"].notna()].reset_index(drop=True)
    labv = H.link_events(v)
    evv = H.build_events(v, labv)
    evv["day"] = H.local_day(evv["first_seen"]).to_numpy()
    sv = season_stats(evv["day"], evv["sum_frp"], range(2012, 2026))
    tr = {"modis": {k: trend(s, k) for k in ("events", "frp", "start", "end", "length")},
          "snpp": {k: trend(sv, k) for k in ("events", "frp", "start", "end", "length")}}
    res["trend"] = tr
    sig = [(src, k) for src in tr for k in tr[src] if tr[src][k]["p_value"] < 0.05]
    res["trend_significant"] = sig

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    for ax, k, lab_ in zip(axes, ("frp", "start", "length"),
                           ("total FRP per year (GW)", "season start (day of year, 10% of events)",
                            "season length (days, 10%→90% of events)")):
        for ss, col, name in ((s, MODIS, "MODIS Terra+Aqua"), (sv, VIIRS, "VIIRS S-NPP")):
            yv = ss[k] / (1000 if k == "frp" else 1)
            ax.plot(ss["year"], yv, "-o", color=col, ms=3.5, lw=1.8, label=name)
            t = tr["modis" if name.startswith("MODIS") else "snpp"][k]
            sl = t["theil_sen_slope_per_year"] / (1000 if k == "frp" else 1)
            ax.plot(ss["year"], np.median(yv) + sl * (ss["year"] - ss["year"].median()), "--", color=col, lw=1,
                    alpha=0.8)
            ax.text(0.02, 0.95 if name.startswith("MODIS") else 0.87,
                    f"{name}: {sl:+.2f}/yr, Kendall p = {t['p_value']:.2f}", transform=ax.transAxes, fontsize=8, color=col)
        ax.set_title(lab_, fontsize=10.5)
    axes[0].legend(loc="lower right", fontsize=8)
    if ("modis", "length") in sig and ("snpp", "length") in sig:
        txt = (f"The fire season (10-90% of events) lengthened in both independent records: "
               f"MODIS {tr['modis']['length']['theil_sen_slope_per_year']:+.1f} d/yr (p={tr['modis']['length']['p_value']:.3f}), "
               f"VIIRS S-NPP {tr['snpp']['length']['theil_sen_slope_per_year']:+.1f} d/yr (p={tr['snpp']['length']['p_value']:.3f}); "
               f"no significant trend in total FRP.")
    elif sig:
        txt = "Significant (p<0.05): " + ", ".join(f"{a.upper()} {b}" for a, b in sig)
    else:
        txt = "No statistically significant trend (Kendall p ≥ 0.05) in total FRP, season start or season length."
    fig.suptitle("Türkiye fire-season trends from consistent single-sensor records\n" + txt, fontsize=11.5, color=INK,
                 fontweight="bold", y=1.04)
    save(fig, "insight.png")
    res["insight_sentence"] = txt
    res["season_table_modis"] = s.to_dict("records")

    # 2021 check: national weekly z-scores, harmonized active events and FRP
    cal = json.loads((OUT / "calendar_daily.json").read_text(encoding="utf-8"))
    rec = pd.DataFrame(cal["records"]["harmonized"]["TR"])
    rec["day"] = pd.to_datetime(rec["day"])
    rec["region"] = "TR"
    fig, axes = plt.subplots(2, 1, figsize=(13, 5.6), sharex=True)
    for ax, metric, lab_ in zip(axes, ("events", "frp_mw"), ("active events", "FRP (MW)")):
        wk = H.weekly_anomalies(rec, metric, years=(2012, 2025), min_value=3 if metric == "events" else 100)
        w = wk[wk["year"] == 2021]
        cols = [RED if u else (ACCENT if a else "#4a3d37") for u, a in zip(w["unusual"], w["above_mean"])]
        ax.bar(w["week"], w["value"], color=cols)
        ax.plot(w["week"], w["mean"], color=INK2, lw=1.5, ls="--", label="2012–2025 mean (leave-one-out)")
        ax.set_ylabel(lab_)
        ax.legend(loc="upper left", fontsize=8)
        top = w.sort_values("z", ascending=False).head(3)
        res.setdefault("check_2021", {})[metric] = top[["week", "value", "mean", "z"]].round(2).to_dict("records")
    axes[0].set_title("Türkiye 2021, weekly burn activity (harmonized). Red = unusual week (z > 1.5), orange = above mean")
    ticks = [H.week_index(pd.Series([pd.Timestamp(2021, mo, 1)])).iloc[0] for mo in range(1, 13)]
    axes[1].set_xticks(ticks, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    save(fig, "calendar_2021_check.png")


def main():
    d = load()
    res = {}
    for f in (dedup, match_rates, frp_scatter, small_fire, insight):
        f(d, res)
    (OUT / "validation.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("match_rates", "season_table_modis")},
                     indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
