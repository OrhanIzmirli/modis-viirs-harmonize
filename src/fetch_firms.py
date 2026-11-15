"""Download FIRMS active-fire archives through the NASA FIRMS Area API.

* Reads FIRMS_MAP_KEY from .env (never printed or logged).
* Every (source, bbox, date, day_range) request is cached as a CSV under
  data/raw/<SOURCE>/ so the same request is never sent twice.
* Respects the FIRMS transaction limit by backing off when the API says so.

Usage:
    python src/fetch_firms.py --region turkey --start 2012-01-01 --end 2025-12-31
    python src/fetch_firms.py --region southwest --sources MODIS_SP VIIRS_SNPP_SP
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "https://firms.modaps.eosdis.nasa.gov/api"

REGIONS = {
    # west, south, east, north
    "turkey": (25.6, 35.8, 44.9, 42.2),
    "southwest": (26.0, 36.0, 32.5, 39.0),  # Izmir - Mugla - Antalya
}

# Standard-processing (science quality) archives, plus NRT to extend past the SP end date.
DEFAULT_SOURCES = [
    "MODIS_SP", "MODIS_NRT",
    "VIIRS_SNPP_SP", "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_SP", "VIIRS_NOAA21_NRT",
]


def load_key() -> str:
    key = os.environ.get("FIRMS_MAP_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key or key == "your_map_key_here":
        sys.exit("FIRMS_MAP_KEY missing: put it in .env (see .env.example).")
    return key


class FirmsError(RuntimeError):
    pass


import threading  # noqa: E402

_PAUSE = {"until": 0.0}
_PAUSE_LOCK = threading.Lock()


def _pause_all(seconds: float) -> None:
    """Stop every worker until the FIRMS 10-minute transaction window has fully rolled over."""
    with _PAUSE_LOCK:
        _PAUSE["until"] = max(_PAUSE["until"], time.time() + seconds)
    print(f"transaction budget spent: pausing {seconds / 60:.0f} min", flush=True)


def _wait_pause() -> None:
    while time.time() < _PAUSE["until"]:
        time.sleep(5)


def _quota_exhausted(key: str) -> bool:
    try:
        r = requests.get(f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={key}", timeout=30)
        j = r.json()
        return int(j.get("current_transactions", 0)) >= int(j.get("transaction_limit", 5000)) - 50
    except Exception:
        return True


def _get(url: str, key: str, retries: int = 60) -> str:
    """GET with backoff. The key is only substituted here and never echoed."""
    delay = 30
    for attempt in range(retries):
        _wait_pause()
        try:
            r = requests.get(url.replace("{KEY}", key), timeout=120)
        except requests.RequestException as exc:  # network hiccup
            msg = type(exc).__name__
            time.sleep(min(delay, 120))
            delay *= 2
            if attempt == retries - 1:
                raise FirmsError(msg)
            continue
        text = r.text
        low = text[:300].lower()
        if r.status_code == 200 and "exceed" not in low and "invalid" not in low and "error" not in low[:40]:
            return text
        if "invalid map_key" in low:
            # FIRMS answers "Invalid MAP_KEY" once the 10-minute transaction budget is spent
            if time.time() >= _PAUSE["until"] and _quota_exhausted(key):
                _pause_all(660)
            elif time.time() >= _PAUSE["until"]:
                raise FirmsError("Invalid MAP_KEY")
            continue
        if "exceed" in low or r.status_code in (429, 500, 502, 503, 504):
            print(f"retry after HTTP {r.status_code}, sleeping {min(delay, 120)} s", flush=True)
            time.sleep(min(delay, 120))
            delay = min(delay * 2, 120)
            continue
        raise FirmsError(f"HTTP {r.status_code}: {text[:200].replace(key, '***')}")
    raise FirmsError("retries exhausted")


def data_availability(key: str) -> pd.DataFrame:
    txt = _get(f"{BASE}/data_availability/csv/{{KEY}}/ALL", key)
    return pd.read_csv(io.StringIO(txt))


def cache_path(source: str, bbox, date: dt.date, days: int) -> Path:
    b = "_".join(f"{v:g}" for v in bbox)
    return RAW / source / f"{source}_{b}_{date.isoformat()}_{days}d.csv"


def fetch_chunk(key: str, source: str, bbox, date: dt.date, days: int) -> tuple[Path, int, bool]:
    path = cache_path(source, bbox, date, days)
    if path.exists():
        return path, -1, True
    area = ",".join(f"{v:g}" for v in bbox)
    url = f"{BASE}/area/csv/{{KEY}}/{source}/{area}/{days}/{date.isoformat()}"
    txt = _get(url, key)
    if not txt.startswith("latitude"):
        raise FirmsError(f"unexpected response for {source} {date}: {txt[:120]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(path)
    return path, txt.count("\n") - 1, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="turkey", choices=REGIONS)
    ap.add_argument("--start", default="2001-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--sources", nargs="*", default=DEFAULT_SOURCES)
    ap.add_argument("--days", type=int, default=5, help="FIRMS day_range per request (API max)")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    key = load_key()
    bbox = REGIONS[args.region]
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)

    avail = data_availability(key).set_index("data_id")
    print("FIRMS data availability:")
    print(avail.to_string())

    jobs = []
    for src in args.sources:
        if src not in avail.index:
            print(f"skip {src}: not offered by FIRMS")
            continue
        a0 = dt.date.fromisoformat(str(avail.loc[src, "min_date"])[:10])
        a1 = dt.date.fromisoformat(str(avail.loc[src, "max_date"])[:10])
        # Use NRT only after the matching SP archive ends.
        if src.endswith("_NRT"):
            sp = src.replace("_NRT", "_SP")
            if sp in avail.index and sp in args.sources:
                a0 = max(a0, dt.date.fromisoformat(str(avail.loc[sp, "max_date"])[:10]) + dt.timedelta(days=1))
        d0, d1 = max(start, a0), min(end, a1)
        d = d0
        while d <= d1:
            n = min(args.days, (d1 - d).days + 1)
            jobs.append((src, d, n))
            d += dt.timedelta(days=n)
    print(f"{len(jobs)} requests planned ({sum(cache_path(s, bbox, d, n).exists() for s, d, n in jobs)} cached)")

    done = rows = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_chunk, key, s, bbox, d, n): (s, d) for s, d, n in jobs}
        for f in as_completed(futs):
            s, d = futs[f]
            try:
                _, nrows, cached = f.result()
            except FirmsError as exc:
                print(f"FAILED {s} {d}: {exc}", flush=True)
                continue
            done += 1
            rows += max(nrows, 0)
            if done % 50 == 0:
                print(f"{done}/{len(jobs)} chunks, {rows} new rows", flush=True)
    print(f"finished: {done}/{len(jobs)} chunks, {rows} new rows")


if __name__ == "__main__":
    main()
