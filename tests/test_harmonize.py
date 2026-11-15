import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import harmonize as H  # noqa: E402


def det(rows):
    """rows: (lat, lon, 'YYYY-mm-dd HH:MM', sensor, scan, track, frp, conf_score)"""
    df = pd.DataFrame(rows, columns=["lat", "lon", "time_utc", "sensor", "scan_km", "track_km",
                                     "frp_mw", "confidence_score"])
    df["time_utc"] = pd.to_datetime(df["time_utc"])
    df["satellite"] = np.where(df["sensor"] == "MODIS", "Aqua", "S-NPP")
    df["frp_mw_per_km2"] = df["frp_mw"] / (df["scan_km"] * df["track_km"])
    return df


KM_PER_DEG_LAT = 110.574


# ---------------- confidence normalisation ----------------
@pytest.mark.parametrize("conf,cls", [(0, "low"), (29, "low"), (30, "nominal"), (79, "nominal"),
                                      (80, "high"), (100, "high")])
def test_modis_class_boundaries(conf, cls):
    assert H.modis_confidence_class([conf])[0] == cls


def test_modis_score_scale():
    assert np.allclose(H.modis_confidence_score([0, 55, 100, 120]), [0, 0.55, 1, 1])


def test_viirs_scores_and_order():
    s = H.viirs_confidence_score(["l", "n", "h", "nominal", "H"])
    assert list(s) == [0.15, 0.55, 0.90, 0.55, 0.90]
    # VIIRS class scores fall inside the matching MODIS bands
    assert s[0] < H.MODIS_LOW_MAX / 100 <= s[1] < H.MODIS_HIGH_MIN / 100 <= s[2]


def test_common_schema_modis_and_viirs():
    m = pd.DataFrame({"latitude": [37.0], "longitude": [28.0], "brightness": [330.0], "scan": [2.0],
                      "track": [1.5], "acq_date": ["2021-08-01"], "acq_time": [1035], "satellite": ["Aqua"],
                      "confidence": [85], "frp": [30.0], "daynight": ["D"], "type": [0]})
    c = H.to_common_schema(m, "MODIS_SP")
    assert c.loc[0, "footprint_km2"] == pytest.approx(3.0)
    assert c.loc[0, "frp_mw_per_km2"] == pytest.approx(10.0)
    assert c.loc[0, "confidence_class"] == "high"
    assert c.loc[0, "time_utc"] == pd.Timestamp("2021-08-01 10:35")
    v = m.rename(columns={"brightness": "bright_ti4"}).assign(confidence=["n"], satellite=["N"],
                                                                scan=[0.4], track=[0.5])
    c = H.to_common_schema(v, "VIIRS_SNPP_SP")
    assert c.loc[0, "sensor"] == "VIIRS" and c.loc[0, "satellite"] == "S-NPP"
    assert c.loc[0, "confidence_score"] == 0.55
    assert c.loc[0, "footprint_km2"] == pytest.approx(0.2)


def test_clean_removes_static_sources_and_duplicates():
    base = dict(lat=37.0, lon=28.0, time_utc=pd.Timestamp("2021-08-01 10:35"), satellite="Aqua")
    df = pd.DataFrame([{**base, "fire_type": 0, "source": "MODIS_SP"},
                       {**base, "fire_type": np.nan, "source": "MODIS_NRT"},  # duplicate of SP
                       {**base, "lat": 38.0, "fire_type": 2, "source": "MODIS_SP"}])  # industrial
    out = H.clean(df)
    assert len(out) == 1 and out.loc[0, "source"] == "MODIS_SP"


# ---------------- linkage boundaries ----------------
def _pair(dlat_km, dt_h, scan_m=1.0, scan_v=0.375):
    t0 = pd.Timestamp("2021-08-01 10:00")
    return det([(37.0, 28.0, t0, "MODIS", scan_m, scan_m, 10, 0.8),
                (37.0 + dlat_km / KM_PER_DEG_LAT, 28.0, t0 + pd.Timedelta(hours=dt_h), "VIIRS",
                 scan_v, scan_v, 5, 0.55)])


def _limit(scan_m=1.0, scan_v=0.375):
    return float(H.footprint_radius_km([scan_m], [scan_m])[0] + H.footprint_radius_km([scan_v], [scan_v])[0]
                 + H.SPATIAL_TOL_KM)


def test_link_inside_distance_limit():
    assert len(H.candidate_pairs(_pair(_limit() - 0.02, 0))) == 1


def test_no_link_beyond_distance_limit():
    assert len(H.candidate_pairs(_pair(_limit() + 0.02, 0))) == 0


def test_larger_footprint_extends_limit():
    d = _limit() + 0.5  # too far for nadir pixels ...
    assert len(H.candidate_pairs(_pair(d, 0))) == 0
    assert len(H.candidate_pairs(_pair(d, 0, scan_m=3.0))) == 1  # ... fine for an off-nadir MODIS pixel


def test_time_limit_inclusive_12h():
    assert len(H.candidate_pairs(_pair(0.1, 12.0))) == 1
    assert len(H.candidate_pairs(_pair(0.1, 12.1))) == 0


def test_union_find_chains_multiday_fire():
    t = pd.Timestamp("2021-07-28 10:00")
    rows = [(36.9, 31.4, t + pd.Timedelta(hours=10 * k), "VIIRS" if k % 2 else "MODIS", 0.5, 0.5, 50, 0.9)
            for k in range(6)]  # same spot, 10 h steps: chained over 50 h
    rows.append((36.9, 31.4, t + pd.Timedelta(hours=100), "VIIRS", 0.5, 0.5, 5, 0.5))  # 50 h gap -> new event
    rows.append((38.5, 27.0, t, "VIIRS", 0.4, 0.4, 3, 0.55))  # far away -> new event
    d = det(rows).sort_values("time_utc").reset_index(drop=True)
    labels = H.link_events(d)
    assert len(set(labels)) == 3
    ev = H.build_events(d, labels)
    big = ev.loc[ev["n_modis"] + ev["n_viirs"] == 6].iloc[0]
    assert big["agreement"] == "both" and big["duration_h"] == pytest.approx(50)
    assert set(ev["agreement"]) == {"both", "viirs_only"}


# ---------------- fused confidence ----------------
def test_fused_confidence_formula():
    assert H.fused_confidence([0.5], [False], [1])[0] == pytest.approx(0.5)
    assert H.fused_confidence([0.5], [True], [1])[0] == pytest.approx(0.5 + 0.3 * 0.5)
    assert H.fused_confidence([0.5], [True], [3])[0] == pytest.approx(0.5 + 0.4 * 0.5)
    assert H.fused_confidence([1.0], [True], [3])[0] == pytest.approx(1.0)
    # cross-sensor confirmation never lowers confidence
    b = np.linspace(0, 1, 11)
    assert np.all(H.fused_confidence(b, True, 2) >= H.fused_confidence(b, False, 2))


def test_staleness_half_life():
    assert H.stale_confidence([0.8], [24])[0] == pytest.approx(0.4)
    assert H.stale_confidence([0.8], [-5])[0] == pytest.approx(0.8)


# ---------------- calendar aggregation ----------------
def _calendar_fixture():
    t = pd.Timestamp("2021-07-28 22:30")  # 01:30 local on 29 Jul (UTC+3)
    rows = [(36.9, 31.4, t, "MODIS", 1, 1, 100, 0.9),
            (36.9, 31.4, t + pd.Timedelta(hours=11), "VIIRS", 0.4, 0.4, 40, 0.9),   # same event, same local day
            (36.9, 31.4, t + pd.Timedelta(hours=23), "VIIRS", 0.4, 0.4, 20, 0.9),   # 00:30 local 30 Jul: same event, next day
            (37.2, 28.3, t + pd.Timedelta(hours=12), "VIIRS", 0.4, 0.4, 2, 0.55)]   # other event / province
    d = det(rows).sort_values("time_utc").reset_index(drop=True)
    labels = H.link_events(d)
    ev = H.build_events(d, labels)
    region = pd.Series(np.where(ev["lon"] > 30, "TR-07", "TR-48"))
    return d, labels, ev, region


def test_event_days_local_date_and_new_flag():
    d, labels, ev, region = _calendar_fixture()
    ed = H.event_days(d, labels, region)
    assert set(ed["day"].dt.strftime("%Y-%m-%d")) == {"2021-07-29", "2021-07-30"}
    assert ed["new"].sum() == len(ev)  # each event is new exactly once


def test_daily_calendar_totals():
    d, labels, ev, region = _calendar_fixture()
    cal = H.daily_calendar(H.event_days(d, labels, region), ev["agreement"])
    tr = cal[cal["region"] == "TR"].set_index(cal[cal["region"] == "TR"]["day"].dt.strftime("%m-%d"))
    assert tr.loc["07-29", "events"] == 2 and tr.loc["07-29", "new_events"] == 2
    assert tr.loc["07-29", "frp_mw"] == pytest.approx(142)
    assert tr.loc["07-30", "events"] == 1 and tr.loc["07-30", "new_events"] == 0
    assert tr.loc["07-29", "both"] == 1 and tr.loc["07-29", "viirs_only"] == 1
    # province totals add up to the national total
    prov = cal[cal["region"] != "TR"]
    assert prov["frp_mw"].sum() == pytest.approx(cal.loc[cal["region"] == "TR", "frp_mw"].sum())
    assert prov["det_modis"].sum() + prov["det_viirs"].sum() == len(d)


def test_weekly_anomaly_flags_spike():
    days = pd.date_range("2012-01-01", "2021-12-31", freq="D")
    rng = np.random.default_rng(0)
    vals = rng.poisson(2, len(days)).astype(float)
    spike = (days >= "2021-07-28") & (days <= "2021-08-10")
    vals[spike] += 40
    cal = pd.DataFrame({"region": "TR", "day": days, "events": vals})
    wk = H.weekly_anomalies(cal, "events")
    flagged = wk[wk["unusual"]]
    weeks = set(H.week_index(pd.Series(days[spike])))
    assert weeks <= set(flagged.loc[flagged["year"] == 2021, "week"])
    # noise weeks can cross z=1.5, but the spike is far stronger than anything else
    assert set(wk.loc[wk["z"] > 10, "year"]) == {2021}
    assert wk.loc[wk["year"] < 2021, "unusual"].mean() < 0.12


def test_week_index_monday_based():
    w = H.week_index(pd.Series(pd.to_datetime(["2021-01-01", "2021-01-03", "2021-01-04", "2021-12-31"])))
    assert list(w) == [0, 0, 1, 52]  # 2021-01-01 is a Friday
