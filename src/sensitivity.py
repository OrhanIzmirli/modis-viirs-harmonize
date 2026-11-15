"""Sensitivity of the event linkage to its two thresholds (2021 subset).

Varies the spatial tolerance (0.375 km) and the time window (12 h) by -50 % / 0 / +50 %
and re-links 2021 detections inside Türkiye's provinces. Writes output/sensitivity.json.
    python src/sensitivity.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import harmonize as H

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def main(year: int = 2021):
    cols = ["lat", "lon", "time_utc", "sensor", "satellite", "frp_mw", "frp_mw_per_km2",
            "confidence_score", "scan_km", "track_km", "province"]
    d = pd.read_csv(OUT / "detections_harmonized.csv", usecols=cols)
    d["time_utc"] = pd.to_datetime(d["time_utc"])
    d = d[(d["time_utc"].dt.year == year) & d["province"].notna()].reset_index(drop=True)
    rows = []
    for f_tol in (0.5, 1.0, 1.5):
        for f_dt in (0.5, 1.0, 1.5):
            tol, dt = H.SPATIAL_TOL_KM * f_tol, H.MAX_DT_HOURS * f_dt
            lab = H.link_events(d, max_dt_h=dt, tol_km=tol)
            ev = H.build_events(d, lab)
            rows.append({"tol_km": round(tol, 4), "max_dt_h": dt, "tol_change": f"{f_tol - 1:+.0%}",
                         "dt_change": f"{f_dt - 1:+.0%}", "events": int(len(ev)),
                         "pct_both": round(100 * float((ev["agreement"] == "both").mean()), 2),
                         "detections_per_event": round(len(d) / len(ev), 3)})
            print(rows[-1], flush=True)
    base = next(r for r in rows if r["tol_change"] == "+0%" and r["dt_change"] == "+0%")
    for r in rows:
        r["events_vs_default_pct"] = round(100 * (r["events"] / base["events"] - 1), 1)
        r["pct_both_vs_default_pp"] = round(r["pct_both"] - base["pct_both"], 2)
    res = {"year": year, "subset": "detections inside Türkiye's 81 provinces", "detections": int(len(d)),
           "default": {"tol_km": H.SPATIAL_TOL_KM, "max_dt_h": H.MAX_DT_HOURS}, "runs": rows}
    (OUT / "sensitivity.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT / "sensitivity.json")


if __name__ == "__main__":
    main()
