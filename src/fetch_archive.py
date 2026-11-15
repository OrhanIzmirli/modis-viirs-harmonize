"""Fallback / fast path: NASA FIRMS yearly country archives (no MAP_KEY needed).

Same science-quality products as the Area API *_SP sources (MODIS C6.1, VIIRS 375 m),
but clipped to the country polygon by FIRMS. Files are cached under
data/raw_archive/<SOURCE>/ and never downloaded twice.

    python src/fetch_archive.py --start 2001 --end 2025
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw_archive"
URL = "https://firms.modaps.eosdis.nasa.gov/data/country/{p}/{y}/{p}_{y}_Turkey.csv"
PRODUCTS = {  # archive folder -> (local source name, first year)
    "modis": ("MODIS_SP", 2000),
    "viirs-snpp": ("VIIRS_SNPP_SP", 2012),
    "viirs-jpss1": ("VIIRS_NOAA20_SP", 2018),
    "viirs-jpss2": ("VIIRS_NOAA21_SP", 2024),
}


def get(p: str, y: int) -> str:
    src, _ = PRODUCTS[p]
    dst = OUT / src / f"{p}_{y}_Turkey.csv"
    if dst.exists():
        return f"cached {dst.name}"
    r = requests.get(URL.format(p=p, y=y), timeout=300)
    if r.status_code != 200 or not r.text.startswith("latitude"):
        return f"missing {p} {y} (HTTP {r.status_code})"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(r.text, encoding="utf-8")
    return f"ok {dst.name} {r.text.count(chr(10)) - 1} rows"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2001)
    ap.add_argument("--end", type=int, default=2025)
    a = ap.parse_args()
    jobs = [(p, y) for p, (_, y0) in PRODUCTS.items() for y in range(max(a.start, y0), a.end + 1)]
    with ThreadPoolExecutor(4) as ex:
        for msg in ex.map(lambda j: get(*j), jobs):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
