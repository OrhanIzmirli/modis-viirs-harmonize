"""Presentation data for the web page's "Two satellites, one truth" block.

Reads the pipeline outputs (does not change them) and writes docs/data/story.json:
all raw MODIS/VIIRS detections and the merged fire events for one day and area.

    python src/make_story.py --day 2021-07-29 --bbox 30.95 36.45 32.15 37.15 --name "Manavgat, Antalya"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import harmonize as H

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2021-07-29")
    ap.add_argument("--bbox", nargs=4, type=float, default=[30.95, 36.45, 32.15, 37.15], metavar=("W", "S", "E", "N"))
    ap.add_argument("--name", default="Manavgat, Antalya")
    a = ap.parse_args()
    w, s, e, n = a.bbox
    d = pd.read_csv(ROOT / "output" / "detections_harmonized.csv", parse_dates=["time_utc"],
                    usecols=["lat", "lon", "time_utc", "sensor", "satellite", "frp_mw", "event_id", "agreement"])
    d["day"] = H.local_day(d["time_utc"]).dt.strftime("%Y-%m-%d").to_numpy()
    box = d[(d["day"] == a.day) & d["lon"].between(w, e) & d["lat"].between(s, n)]
    ev = d[d["event_id"].isin(box["event_id"].unique())].groupby("event_id").agg(
        lat=("lat", "mean"), lon=("lon", "mean"), agree=("agreement", "first"), frp=("frp_mw", "sum"),
        n=("frp_mw", "size"))
    out = {
        "day": a.day, "name": a.name, "bbox": [w, s, e, n],
        "detections": [[round(r.lat, 4), round(r.lon, 4), 0 if r.sensor == "MODIS" else 1]
                       for r in box.itertuples()],
        "events": [[round(r.lat, 4), round(r.lon, 4), r.agree, round(float(r.frp), 1), int(r.n), k]
                   for k, r in ev.iterrows()],
        "n_modis": int((box["sensor"] == "MODIS").sum()), "n_viirs": int((box["sensor"] == "VIIRS").sum()),
    }
    (ROOT / "docs" / "data" / "story.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{a.day} {a.name}: {len(box)} detections ({out['n_modis']} MODIS, {out['n_viirs']} VIIRS) "
          f"-> {len(ev)} events")


if __name__ == "__main__":
    main()
