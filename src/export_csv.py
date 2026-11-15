"""Export output/calendar_daily.json as a flat CSV (output/calendar_daily.csv.gz) for download.

Reads the pipeline output only; one row per (mode, region, local day).
    python src/export_csv.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    cal = json.loads((ROOT / "output" / "calendar_daily.json").read_text(encoding="utf-8"))
    rows = []
    for mode, regions in cal["records"].items():
        for region, rec in regions.items():
            df = pd.DataFrame(rec)
            df.insert(0, "region", region)
            df.insert(0, "mode", mode)
            rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    cols = ["mode", "region", "day", "events", "new_events", "frp_mw", "det_modis", "det_viirs",
            "both", "modis_only", "viirs_only"]
    out = out[[c for c in cols if c in out.columns]]
    dst = ROOT / "output" / "calendar_daily.csv.gz"
    out.to_csv(dst, index=False, compression="gzip")
    print(f"{len(out):,} rows -> {dst}")


if __name__ == "__main__":
    main()
