"""Core MODIS + VIIRS active-fire harmonization.

Pipeline
    raw FIRMS CSV -> common schema -> confidence normalisation
    -> spatio-temporal linkage (union-find over KD-tree candidate pairs)
    -> fire events -> fused confidence -> daily calendars per region

All thresholds live in module-level constants so the README, tests and code
reference one source of truth.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

# --------------------------------------------------------------------------
# Constants (documented in README "Method")
# --------------------------------------------------------------------------
MODIS_LOW_MAX = 30      # MODIS C6.1: confidence < 30 -> low
MODIS_HIGH_MIN = 80     # MODIS C6.1: confidence >= 80 -> high, 30-79 nominal
# VIIRS class -> 0-1 score, placed at the midpoint of the matching MODIS band
VIIRS_SCORE = {"l": 0.15, "n": 0.55, "h": 0.90}
CLASS_OF_VIIRS = {"l": "low", "n": "nominal", "h": "high"}

MAX_DT_HOURS = 12.0     # same event if detections are <= 12 h apart ...
SPATIAL_TOL_KM = 0.375  # ... and closer than r_i + r_j + tolerance (1 VIIRS I-band pixel)

# Fused confidence: c = clip(base + B_cross + B_repeat, 0, 1)
W_CROSS = 0.30          # bonus share of the remaining doubt when MODIS and VIIRS both saw it
W_REPEAT = 0.10         # bonus share when seen on >= 2 distinct overpasses
STALE_HALF_LIFE_H = 24  # staleness: c(t) = c * 0.5 ** ((t - last_seen) / 24 h)

LOCAL_TZ = "Europe/Istanbul"
EPOCH = pd.Timestamp("2000-01-01")
VIIRS_START = pd.Timestamp("2012-01-20")  # first S-NPP VIIRS science data

COMMON_COLS = [
    "lat", "lon", "time_utc", "sensor", "satellite", "frp_mw", "scan_km", "track_km",
    "footprint_km2", "frp_mw_per_km2", "day_night", "confidence_raw",
    "confidence_class", "confidence_score",
]

SOURCE_SATELLITE = {
    "VIIRS_SNPP": "S-NPP", "VIIRS_NOAA20": "NOAA-20", "VIIRS_NOAA21": "NOAA-21",
    "viirs-snpp": "S-NPP", "viirs-jpss1": "NOAA-20", "viirs-noaa20": "NOAA-20",
    "viirs-jpss2": "NOAA-21", "viirs-noaa21": "NOAA-21",
}
MODIS_SAT = {"T": "Terra", "A": "Aqua", "Terra": "Terra", "Aqua": "Aqua"}


# --------------------------------------------------------------------------
# 1-3. Common schema, confidence, resolution
# --------------------------------------------------------------------------
def modis_confidence_class(conf) -> np.ndarray:
    c = np.asarray(conf, dtype=float)
    return np.where(c < MODIS_LOW_MAX, "low", np.where(c >= MODIS_HIGH_MIN, "high", "nominal"))


def modis_confidence_score(conf) -> np.ndarray:
    return np.clip(np.asarray(conf, dtype=float) / 100.0, 0.0, 1.0)


def viirs_confidence_score(conf) -> np.ndarray:
    s = pd.Series(conf).astype(str).str.strip().str.lower().str[0]
    return s.map(VIIRS_SCORE).astype(float).to_numpy()


def footprint_radius_km(scan, track) -> np.ndarray:
    """Radius of the circle circumscribing a scan x track pixel (half diagonal)."""
    return 0.5 * np.hypot(np.asarray(scan, float), np.asarray(track, float))


def to_common_schema(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Map one FIRMS CSV (any MODIS / VIIRS product) to the common schema."""
    is_modis = "brightness" in df.columns or source.upper().startswith("MODIS")
    out = pd.DataFrame({
        "lat": df["latitude"].astype(float),
        "lon": df["longitude"].astype(float),
    })
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    out["time_utc"] = pd.to_datetime(df["acq_date"].astype(str) + hhmm, format="%Y-%m-%d%H%M")
    out["sensor"] = "MODIS" if is_modis else "VIIRS"
    if is_modis:
        out["satellite"] = df["satellite"].astype(str).map(MODIS_SAT).fillna(df["satellite"].astype(str))
    else:
        key = next((k for k in SOURCE_SATELLITE if source.startswith(k)), None)
        out["satellite"] = SOURCE_SATELLITE.get(key, str(df["satellite"].iloc[0]) if len(df) else "VIIRS")
    out["frp_mw"] = df["frp"].astype(float)
    out["scan_km"] = df["scan"].astype(float)
    out["track_km"] = df["track"].astype(float)
    out["footprint_km2"] = out["scan_km"] * out["track_km"]
    out["frp_mw_per_km2"] = out["frp_mw"] / out["footprint_km2"]
    out["day_night"] = df["daynight"].astype(str)
    out["confidence_raw"] = df["confidence"].astype(str)
    if is_modis:
        out["confidence_class"] = modis_confidence_class(df["confidence"])
        out["confidence_score"] = modis_confidence_score(df["confidence"])
    else:
        first = df["confidence"].astype(str).str.strip().str.lower().str[0]
        out["confidence_class"] = first.map(CLASS_OF_VIIRS)
        out["confidence_score"] = viirs_confidence_score(df["confidence"])
    if "type" in df.columns:
        out["fire_type"] = pd.to_numeric(df["type"], errors="coerce")
    return out


def load_raw_dir(raw: Path) -> pd.DataFrame:
    """Read every cached FIRMS CSV under data/raw/<SOURCE>/ into the common schema."""
    frames = []
    for src_dir in sorted(p for p in raw.iterdir() if p.is_dir()):
        files = sorted(src_dir.glob("*.csv"))
        if not files:
            continue
        parts = [pd.read_csv(f) for f in files]
        parts = [p for p in parts if len(p)]
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True)
        c = to_common_schema(df, src_dir.name)
        c["source"] = src_dir.name
        frames.append(c)
    if not frames:
        raise FileNotFoundError(f"no CSV under {raw}")
    return pd.concat(frames, ignore_index=True)


def clean(det: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicates (SP/NRT overlap, chunk overlap) and non-vegetation sources.

    FIRMS standard-processing files flag `type`: 0 presumed vegetation fire,
    1 active volcano, 2 other static land source (industry, gas flares), 3 offshore.
    NRT files have no type column; their rows are kept (NaN).
    """
    det = det.copy()
    if "source" in det:
        det["_sp"] = det["source"].str.endswith("_SP").astype(int)
        det = det.sort_values("_sp", ascending=False)
    det = det.drop_duplicates(subset=["lat", "lon", "time_utc", "satellite"], keep="first")
    if "fire_type" in det:
        det = det[det["fire_type"].isna() | (det["fire_type"] == 0)]
    det = det.drop(columns=[c for c in ["_sp"] if c in det]).sort_values("time_utc")
    return det.reset_index(drop=True)


# --------------------------------------------------------------------------
# 4. Linkage
# --------------------------------------------------------------------------
def _xy_km(lat, lon):
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    y = lat * 110.574
    x = lon * 111.320 * np.cos(np.radians(lat))
    return x, y


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def candidate_pairs(det: pd.DataFrame, max_dt_h: float = MAX_DT_HOURS,
                    tol_km: float = SPATIAL_TOL_KM) -> np.ndarray:
    """All detection pairs satisfying the event-linkage rule.

    Rule: haversine(i, j) < r_i + r_j + tol   AND   |t_i - t_j| <= max_dt_h,
    with r = half pixel diagonal. Candidates come from a 3-D KD-tree (x, y,
    scaled time) queried with the Chebyshev metric, then filtered exactly.
    """
    n = len(det)
    if n < 2:
        return np.empty((0, 2), dtype=np.int64)
    r = footprint_radius_km(det["scan_km"], det["track_km"])
    rmax = 2 * float(np.nanmax(r)) + tol_km
    x, y = _xy_km(det["lat"], det["lon"])
    hours = (det["time_utc"].to_numpy("datetime64[s]").astype(np.int64) / 3600.0)
    t = (hours - hours.min()) * (rmax / max_dt_h)
    tree = cKDTree(np.column_stack([x, y, t]))
    pairs = tree.query_pairs(rmax + 1e-9, p=np.inf, output_type="ndarray")
    if len(pairs) == 0:
        return pairs.astype(np.int64)
    i, j = pairs[:, 0], pairs[:, 1]
    lat, lon = det["lat"].to_numpy(), det["lon"].to_numpy()
    d = haversine_km(lat[i], lon[i], lat[j], lon[j])
    ok = (d < r[i] + r[j] + tol_km) & (np.abs(hours[i] - hours[j]) <= max_dt_h + 1e-9)
    return pairs[ok].astype(np.int64)


def link_events(det: pd.DataFrame, **kw) -> np.ndarray:
    """Union-find (connected components) over linkage pairs -> event label per detection."""
    n = len(det)
    pairs = candidate_pairs(det, **kw)
    if n == 0:
        return np.empty(0, dtype=np.int64)
    g = coo_matrix((np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, labels = connected_components(g, directed=False)
    # relabel in chronological order of first detection
    order = pd.Series(det["time_utc"].to_numpy()).groupby(labels).min().sort_values()
    remap = np.empty(labels.max() + 1, dtype=np.int64)
    remap[order.index.to_numpy()] = np.arange(len(order))
    return remap[labels]


# --------------------------------------------------------------------------
# 5. Events and fused confidence
# --------------------------------------------------------------------------
def fused_confidence(base, both_sensors, n_passes) -> np.ndarray:
    """c = clip(base + W_CROSS*(1-base)*both + W_REPEAT*(1-base)*(passes>=2), 0, 1)."""
    base = np.asarray(base, float)
    doubt = 1.0 - base
    c = base + W_CROSS * doubt * np.asarray(both_sensors, float) \
        + W_REPEAT * doubt * (np.asarray(n_passes) >= 2)
    return np.clip(c, 0.0, 1.0)


def stale_confidence(conf, hours_since_last_seen) -> np.ndarray:
    """Staleness decay used when an event is viewed 'as of' a later time."""
    h = np.maximum(0.0, np.asarray(hours_since_last_seen, float))
    return np.asarray(conf, float) * 0.5 ** (h / STALE_HALF_LIFE_H)


def local_day(times_utc) -> pd.Series:
    t = pd.to_datetime(pd.Series(times_utc)).dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    return t.dt.tz_localize(None).dt.normalize()


def build_events(det: pd.DataFrame, labels: np.ndarray, prefix: str = "E") -> pd.DataFrame:
    d = det.assign(event=labels)
    # an "overpass" = one satellite, one acquisition minute
    d["pass_key"] = d["satellite"] + "|" + d["time_utc"].astype(str)
    g = d.groupby("event")
    ev = pd.DataFrame({
        "lat": g["lat"].mean(),
        "lon": g["lon"].mean(),
        "first_seen": g["time_utc"].min(),
        "last_seen": g["time_utc"].max(),
        "n_modis": g["sensor"].apply(lambda s: int((s == "MODIS").sum())),
        "n_viirs": g["sensor"].apply(lambda s: int((s == "VIIRS").sum())),
        "max_frp": g["frp_mw"].max(),
        "sum_frp": g["frp_mw"].sum(),
        "max_frp_density": g["frp_mw_per_km2"].max(),
        "n_passes": g["pass_key"].nunique(),
        "base_conf": g["confidence_score"].mean(),
        "satellites": g["satellite"].apply(lambda s: sorted(set(s))),
    })
    both = (ev["n_modis"] > 0) & (ev["n_viirs"] > 0)
    ev["agreement"] = np.where(both, "both", np.where(ev["n_modis"] > 0, "modis_only", "viirs_only"))
    ev["sensors"] = [(["MODIS"] if m else []) + (["VIIRS"] if v else [])
                     for m, v in zip(ev["n_modis"], ev["n_viirs"])]
    ev["harmonized_confidence"] = fused_confidence(ev["base_conf"], both, ev["n_passes"])
    width = max(6, len(str(len(ev))))
    ev.insert(0, "event_id", [f"{prefix}{i:0{width}d}" for i in ev.index])
    ev["duration_h"] = (ev["last_seen"] - ev["first_seen"]).dt.total_seconds() / 3600
    return ev.reset_index(drop=True)


# --------------------------------------------------------------------------
# 6. Calendar aggregation
# --------------------------------------------------------------------------
def event_days(det: pd.DataFrame, labels: np.ndarray, ev_region: pd.Series) -> pd.DataFrame:
    """One row per (event, local day) with FRP and sensor counts."""
    d = pd.DataFrame({
        "event": labels,
        "day": local_day(det["time_utc"]).to_numpy(),
        "frp": det["frp_mw"].to_numpy(),
        "m": (det["sensor"] == "MODIS").to_numpy().astype(int),
        "v": (det["sensor"] == "VIIRS").to_numpy().astype(int),
    })
    ed = d.groupby(["event", "day"], as_index=False).agg(frp=("frp", "sum"), m=("m", "sum"), v=("v", "sum"))
    ed["region"] = ev_region.to_numpy()[ed["event"].to_numpy()]
    first_day = ed.groupby("event")["day"].transform("min")
    ed["new"] = (ed["day"] == first_day).astype(int)
    return ed


def daily_calendar(ed: pd.DataFrame, agreement: pd.Series | None = None) -> pd.DataFrame:
    """Aggregate event-days to region x day.

    Columns: events (active that day), new_events, frp_mw, det_modis, det_viirs,
    and when `agreement` is given, active-event breakdown both/modis_only/viirs_only.
    """
    e = ed.copy()
    agg = {"events": ("event", "nunique"), "new_events": ("new", "sum"),
           "frp_mw": ("frp", "sum"), "det_modis": ("m", "sum"), "det_viirs": ("v", "sum")}
    if agreement is not None:
        a = agreement.to_numpy()[e["event"].to_numpy()]
        for k in ("both", "modis_only", "viirs_only"):
            e[k] = (a == k).astype(int)
            agg[k] = (k, "sum")
    out = []
    for region, sub in [("TR", e[e["region"].notna()])] + list(e.dropna(subset=["region"]).groupby("region")):
        c = sub.groupby("day").agg(**agg).reset_index()
        c.insert(0, "region", region)
        out.append(c)
    return pd.concat(out, ignore_index=True)


def week_index(days: pd.Series) -> pd.Series:
    """Monday-based week-of-year column used by the calendar grid (0..53)."""
    days = pd.to_datetime(days)
    jan1 = pd.to_datetime(days.dt.year.astype(str) + "-01-01")
    return ((days.dt.dayofyear - 1 + jan1.dt.dayofweek) // 7).astype(int)


def weekly_anomalies(cal: pd.DataFrame, metric: str = "events", years: tuple[int, int] | None = None,
                     z_thresh: float = 1.5, min_value: float = 1.0) -> pd.DataFrame:
    """Region x year x week totals with long-term mean / std per week-of-year and z-score.

    `years` limits the climatology baseline (all years still get a z-score).
    Missing weeks count as zero activity.
    """
    c = cal.copy()
    c["year"] = pd.to_datetime(c["day"]).dt.year
    c["week"] = week_index(c["day"])
    wk = c.groupby(["region", "year", "week"])[metric].sum()
    regions = c["region"].unique()
    yrs = np.arange(c["year"].min(), c["year"].max() + 1)
    full = pd.MultiIndex.from_product([regions, yrs, np.arange(54)], names=["region", "year", "week"])
    wk = wk.reindex(full, fill_value=0).rename("value").reset_index()
    in_base = np.ones(len(wk), bool) if years is None else \
        ((wk["year"] >= years[0]) & (wk["year"] <= years[1])).to_numpy()
    base = wk[in_base]
    agg = base.groupby(["region", "week"])["value"].agg(s="sum", ss=lambda v: float((v ** 2).sum()),
                                                        k="count").reset_index()
    wk = wk.merge(agg, on=["region", "week"], how="left")
    # Leave-one-out climatology: a year inside the baseline is compared with the *other*
    # years only, otherwise an extreme year inflates its own mean/std and caps z at (n-1)/sqrt(n).
    x = wk["value"].to_numpy(float)
    s, ss, k = wk["s"].to_numpy(float), wk["ss"].to_numpy(float), wk["k"].to_numpy(float)
    s, ss, k = np.where(in_base, s - x, s), np.where(in_base, ss - x ** 2, ss), np.where(in_base, k - 1, k)
    mean = s / k
    var = np.maximum(ss - k * mean ** 2, 0) / np.maximum(k - 1, 1)
    wk["mean"], wk["std"] = mean, np.sqrt(var)
    wk = wk.drop(columns=["s", "ss", "k"])
    wk["z"] = (wk["value"] - wk["mean"]) / wk["std"].replace(0, np.nan)
    wk["above_mean"] = wk["value"] > wk["mean"]
    wk["unusual"] = (wk["z"] > z_thresh) & (wk["value"] >= min_value)
    return wk


def risky_weeks(wk: pd.DataFrame, quantile: float = 0.85) -> pd.DataFrame:
    """Weeks of year whose climatological mean is in the region's top (1-quantile) share."""
    clim = wk.drop_duplicates(["region", "week"])[["region", "week", "mean"]]
    thr = clim.groupby("region")["mean"].transform(lambda s: s.quantile(quantile))
    clim = clim.assign(risky=(clim["mean"] >= thr) & (clim["mean"] > 0))
    return clim


def assign_regions(lat, lon, geojson_path: Path) -> np.ndarray:
    """Point-in-polygon province lookup (shapely STRtree). Returns ISO code or None."""
    import json
    from shapely import STRtree, points
    from shapely.geometry import shape

    gj = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    geoms = [shape(f["geometry"]) for f in gj["features"]]
    codes = np.array([f["properties"]["shapeISO"] for f in gj["features"]], dtype=object)
    tree = STRtree(geoms)
    pts = points(np.column_stack([np.asarray(lon, float), np.asarray(lat, float)]))
    res = np.full(len(pts), None, dtype=object)
    pi, gi = tree.query(pts, predicate="within")
    res[pi] = codes[gi]
    return res
