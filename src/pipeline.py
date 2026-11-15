"""End-to-end pipeline: cached FIRMS CSVs -> harmonized events -> calendars -> web data.

    python src/pipeline.py                 # uses data/raw
    python src/pipeline.py --raw other/dir
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

import harmonize as H

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WEB = ROOT / "docs" / "data"
BOUNDS = ROOT / "data" / "boundaries" / "tur_adm1.geojson"

MODES = {"harmonized": None, "modis": "MODIS", "viirs": "VIIRS"}
AGREE_CODE = {"both": 0, "modis_only": 1, "viirs_only": 2}
SAT_CODE = {"Terra": 0, "Aqua": 1, "S-NPP": 2, "NOAA-20": 3, "NOAA-21": 4}


def day_idx(days) -> np.ndarray:
    return ((pd.to_datetime(pd.Series(days)) - H.EPOCH).dt.days).to_numpy()


def province_table():
    gj = json.loads(BOUNDS.read_text(encoding="utf-8"))
    return {f["properties"]["shapeISO"]: f["properties"]["shapeName"] for f in gj["features"]}


def write_json(path: Path, obj, compact=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":") if compact else None,
                  indent=None if compact else 2)


def run_mode(det: pd.DataFrame, mode: str, sensor: str | None):
    d = det if sensor is None else det[det["sensor"] == sensor].reset_index(drop=True)
    t = time.time()
    labels = H.link_events(d)
    ev = H.build_events(d, labels, prefix={"harmonized": "H", "modis": "M", "viirs": "V"}[mode])
    ev["region"] = H.assign_regions(ev["lat"], ev["lon"], BOUNDS)
    ed = H.event_days(d, labels, ev["region"])
    cal = H.daily_calendar(ed, ev["agreement"] if mode == "harmonized" else None)
    print(f"[{mode}] {len(d):,} detections -> {len(ev):,} events "
          f"({ev['region'].notna().sum():,} inside Turkey) in {time.time() - t:.1f}s")
    return d, labels, ev, ed, cal


def simplify_provinces(dst: Path):
    from shapely.geometry import shape, mapping
    gj = json.loads(BOUNDS.read_text(encoding="utf-8"))
    feats = []
    for f in gj["features"]:
        g = shape(f["geometry"]).simplify(0.01, preserve_topology=True)
        m = mapping(g)

        def rnd(c):
            return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 3), round(c[1], 3)]
        m = {"type": m["type"], "coordinates": rnd(m["coordinates"])}
        feats.append({"type": "Feature", "properties": {"id": f["properties"]["shapeISO"],
                                                        "name": f["properties"]["shapeName"]},
                      "geometry": m})
    write_json(dst, {"type": "FeatureCollection", "features": feats})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw"))
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)

    raw = H.load_raw_dir(Path(args.raw))
    det = H.clean(raw)
    print(f"raw rows {len(raw):,} -> clean detections {len(det):,}")
    names = province_table()

    results = {m: run_mode(det, m, s) for m, s in MODES.items()}
    dH, labH, evH, edH, calH = results["harmonized"]

    # ---------------- output/ ----------------
    dets = dH.copy()
    dets["event_id"] = evH["event_id"].to_numpy()[labH]
    dets["agreement"] = evH["agreement"].to_numpy()[labH]
    dets["province"] = evH["region"].to_numpy()[labH]
    cols = ["lat", "lon", "time_utc", "sensor", "satellite", "frp_mw", "footprint_km2", "frp_mw_per_km2",
            "day_night", "confidence_raw", "confidence_class", "confidence_score", "scan_km", "track_km",
            "event_id", "agreement", "province", "source"]
    csv_path = OUT / "detections_harmonized.csv"
    dets[cols].to_csv(csv_path, index=False, float_format="%.5g")
    with open(csv_path, "rb") as fi, gzip.open(str(csv_path) + ".gz", "wb") as fo:
        shutil.copyfileobj(fi, fo)

    feats = []
    for r in evH.itertuples(index=False):
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [round(r.lon, 4), round(r.lat, 4)]},
                      "properties": {
                          "event_id": r.event_id, "first_seen": r.first_seen.isoformat(),
                          "last_seen": r.last_seen.isoformat(), "sensors": r.sensors,
                          "satellites": r.satellites, "n_modis": r.n_modis, "n_viirs": r.n_viirs,
                          "max_frp": round(float(r.max_frp), 2), "sum_frp": round(float(r.sum_frp), 1),
                          "harmonized_confidence": round(float(r.harmonized_confidence), 3),
                          "agreement": r.agreement, "province": r.region,
                          "province_name": names.get(r.region)}})
    write_json(OUT / "events.geojson", {"type": "FeatureCollection", "features": feats})
    # GitHub rejects files > 100 MB: the repository ships gzip copies of the two large outputs
    with open(OUT / "events.geojson", "rb") as fi, gzip.open(str(OUT / "events.geojson") + ".gz", "wb") as fo:
        shutil.copyfileobj(fi, fo)

    cal_all, anomalies = [], []
    for m, (_, _, ev, _, cal) in results.items():
        c = cal.copy()
        c["mode"] = m
        cal_all.append(c)
        base = (2001, 2025) if m == "modis" else (2012, 2025)
        for metric in ("events", "frp_mw"):
            wk = H.weekly_anomalies(cal, metric, years=base, min_value=3 if metric == "events" else 100)
            if m != "modis":  # no VIIRS before 2012: no anomaly flags for that era
                wk = wk[wk["year"] >= 2012]
            wk = wk[wk["unusual"]]
            wk["mode"], wk["metric"] = m, metric
            anomalies.append(wk)
    cal_all = pd.concat(cal_all, ignore_index=True)
    an = pd.concat(anomalies, ignore_index=True)
    cal_json = {
        "description": "Daily fire-activity calendar per region (TR = Turkey total, TR-xx = province, "
                       "by event centroid). Day = local date (Europe/Istanbul). events = events active that day; "
                       "new_events = events first seen that day; frp_mw = sum of detection FRP that day.",
        "regions": {"TR": "Turkey", **names},
        "records": {
            m: {r: sub.drop(columns=["region", "mode"]).assign(day=sub["day"].dt.strftime("%Y-%m-%d"))
                .round(1).to_dict("list")
                for r, sub in cal_all[cal_all["mode"] == m].groupby("region")}
            for m in MODES},
        "unusual_weeks": an.assign(mean=an["mean"].round(2), std=an["std"].round(2), z=an["z"].round(2))
        [["mode", "metric", "region", "year", "week", "value", "mean", "std", "z"]].to_dict("records"),
    }
    write_json(OUT / "calendar_daily.json", cal_json)

    # ---------------- docs/data ----------------
    simplify_provinces(WEB / "provinces.geojson")
    sensors = (dH.groupby("satellite")["time_utc"].agg(["min", "max", "count"]))
    meta = {
        "epoch": "2000-01-01",
        "generated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
        "first_day": str(calH["day"].min().date()), "last_day": str(calH["day"].max().date()),
        "viirs_start": str(dH.loc[dH["sensor"] == "VIIRS", "time_utc"].min().date()),
        "satellites": {s: {"first": str(r["min"].date()), "last": str(r["max"].date()), "detections": int(r["count"])}
                       for s, r in sensors.iterrows()},
        "regions": {"TR": "Turkey", **names},
        "counts": {m: {"detections": int(len(res[0])), "events": int(len(res[2])),
                       "events_tr": int(res[2]["region"].notna().sum())} for m, res in results.items()},
        "agreement": evH["agreement"].value_counts().to_dict(),
        "constants": {"max_dt_hours": H.MAX_DT_HOURS, "spatial_tol_km": H.SPATIAL_TOL_KM,
                      "w_cross": H.W_CROSS, "w_repeat": H.W_REPEAT, "stale_half_life_h": H.STALE_HALF_LIFE_H,
                      "z_thresh": 1.5, "modis_low_max": H.MODIS_LOW_MAX, "modis_high_min": H.MODIS_HIGH_MIN,
                      "viirs_score": H.VIIRS_SCORE},
    }
    write_json(WEB / "meta.json", meta, compact=False)

    # per-region calendars (columnar)
    for region in ["TR"] + sorted(names):
        obj = {"region": region, "name": "Turkey" if region == "TR" else names[region], "modes": {}}
        for m in MODES:
            sub = cal_all[(cal_all["mode"] == m) & (cal_all["region"] == region)].sort_values("day")
            col = {"d": day_idx(sub["day"]).tolist(), "e": sub["events"].astype(int).tolist(),
                   "n": sub["new_events"].astype(int).tolist(), "f": sub["frp_mw"].round(0).astype(int).tolist(),
                   "dm": sub["det_modis"].astype(int).tolist(), "dv": sub["det_viirs"].astype(int).tolist()}
            if m == "harmonized":
                for k, kk in (("both", "b"), ("modis_only", "mo"), ("viirs_only", "vo")):
                    col[kk] = sub[k].astype(int).tolist()
            obj["modes"][m] = col
        write_json(WEB / "calendar" / f"{region}.json", obj)

    # per-year harmonized events for the map + per-event overpass timeline
    dH2 = dH.assign(event=labH)
    passes = (dH2.groupby(["event", "satellite", "time_utc"])
              .agg(n=("frp_mw", "size"), frp=("frp_mw", "sum"), conf=("confidence_score", "mean"))
              .reset_index().sort_values(["event", "time_utc"]))
    pas_by_ev = {e: g for e, g in passes.groupby("event")}
    evH["year"] = H.local_day(evH["first_seen"]).dt.year.to_numpy()
    for year, sub in evH.groupby("year"):
        rows = []
        for idx, r in sub.iterrows():
            p = pas_by_ev[idx]
            t0 = r.first_seen
            tl = [[int((t - t0).total_seconds() // 60), SAT_CODE.get(s, 9), int(n), round(float(f), 1)]
                  for s, t, n, f in zip(p["satellite"], p["time_utc"], p["n"], p["frp"])]
            rows.append([r.event_id, round(r.lat, 4), round(r.lon, 4),
                         int(t0.value // 60_000_000_000), int((r.last_seen - t0).total_seconds() // 60),
                         int(r.n_modis), int(r.n_viirs), round(float(r.max_frp), 1), round(float(r.sum_frp), 1),
                         round(float(r.base_conf), 3), round(float(r.harmonized_confidence), 3),
                         AGREE_CODE[r.agreement], r.region or "", tl])
        write_json(WEB / "events" / f"{year}.json",
                   {"fields": ["id", "lat", "lon", "t0_min_epoch1970", "dur_min", "n_modis", "n_viirs",
                               "max_frp", "sum_frp", "base_conf", "conf", "agree", "region", "timeline"],
                    "rows": rows})

    # per-year event-day records (all modes) for free-form rectangle selection
    mode_code = {"harmonized": 0, "modis": 1, "viirs": 2}
    ed_all = []
    for m, (_, _, ev, ed, _) in results.items():
        e = ed.copy()
        e["lat"] = (ev["lat"].to_numpy()[e["event"]] * 1000).round().astype(int)
        e["lon"] = (ev["lon"].to_numpy()[e["event"]] * 1000).round().astype(int)
        e["ag"] = ev["agreement"].map(AGREE_CODE).to_numpy()[e["event"]]
        e["mode"] = mode_code[m]
        ed_all.append(e)
    ed_all = pd.concat(ed_all, ignore_index=True)
    ed_all["year"] = ed_all["day"].dt.year
    ed_all["doy"] = ed_all["day"].dt.dayofyear - 1
    for year, sub in ed_all.groupby("year"):
        # flag = mode*8 + agree*2 + new
        flag = sub["mode"] * 8 + sub["ag"] * 2 + sub["new"]
        write_json(WEB / "eventdays" / f"{year}.json", {
            "fields": "lat*1000, lon*1000, day-of-year (0-based), frp MW, flag=mode*8+agree*2+new, modis dets, viirs dets",
            "data": np.column_stack([sub["lat"], sub["lon"], sub["doy"], sub["frp"].round().astype(int),
                                     flag, sub["m"], sub["v"]]).ravel().tolist()})
    years = sorted(int(y) for y in ed_all["year"].unique())
    meta["years"] = years
    write_json(WEB / "meta.json", meta, compact=False)

    # summary used by README / validation
    summary = {"raw_rows": int(len(raw)), "clean_detections": int(len(det)), **meta["counts"],
               "agreement": meta["agreement"], "satellites": meta["satellites"]}
    write_json(OUT / "summary.json", summary, compact=False)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
