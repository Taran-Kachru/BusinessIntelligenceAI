"""
test_detect.py — Phase 1: KPI Anomaly Detection
"""

import pytest
import pandas as pd
from backend.detect import (
    compute_kpi_timeseries,
    detect_anomalies_zscore,
    detect_anomalies_isolation_forest,
    compute_materiality_score,
    get_material_movements,
    DEMO_TODAY,
)


def test_kpi_timeseries_revenue(db):
    ts = compute_kpi_timeseries(db, "Revenue")
    assert not ts.empty, "Revenue timeseries should not be empty"
    assert "date" in ts.columns
    assert "value" in ts.columns
    assert ts["value"].min() >= 0, "Revenue cannot be negative"


def test_kpi_timeseries_all_five_kpis(db):
    for kpi in ["Revenue", "Units_Sold", "AOV", "Marketing_ROI", "Churn_Rate"]:
        ts = compute_kpi_timeseries(db, kpi)
        assert not ts.empty, f"{kpi} timeseries should not be empty"


def test_kpi_timeseries_unknown_raises(db):
    with pytest.raises(ValueError):
        compute_kpi_timeseries(db, "NonExistentKPI")


def test_kpi_timeseries_region_filter(db):
    west = compute_kpi_timeseries(db, "Revenue", regions=["West"])
    all_regions = compute_kpi_timeseries(db, "Revenue")
    # West revenue should be less than all-region revenue
    west_total = west["value"].sum()
    all_total = all_regions["value"].sum()
    assert west_total < all_total, "West region should be a subset of all-region revenue"


def test_zscore_detects_injected_anomaly(db):
    ts = compute_kpi_timeseries(db, "Revenue", regions=["West"])
    west_daily = ts.groupby("date")["value"].sum()
    anomaly_df = detect_anomalies_zscore(west_daily, window=28, threshold=2.0)

    # The injected drop week (Aug 11-17) should have negative z-scores
    drop_period = anomaly_df.loc["2026-08-11":"2026-08-17"]
    assert len(drop_period) > 0, "No data in drop period"
    has_negative = (drop_period["z_score"] < -1.5).any()
    assert has_negative, "Expected significant negative z-scores in the injected drop week"


def test_isolation_forest_flags_anomaly(db):
    ts = compute_kpi_timeseries(db, "Revenue", regions=["West"])
    west_daily = ts.groupby("date")["value"].sum().reset_index()
    flags = detect_anomalies_isolation_forest(west_daily, value_col="value")
    assert flags.dtype == bool, "IsolationForest should return boolean series"
    assert flags.any(), "IsolationForest should flag at least one anomaly in the drop scenario"


def test_materiality_score_revenue(db):
    kpi_config = {
        "materiality_threshold": {"statistical_z": 2.0, "dollar_impact": 5000}
    }
    score = compute_materiality_score(z_score=-4.0, dollar_impact=-10000, kpi_config=kpi_config)
    assert score >= 1.0, f"Expected composite_score >= 1.0 for significant drop, got {score}"


def test_materiality_score_low_impact():
    kpi_config = {
        "materiality_threshold": {"statistical_z": 2.0, "dollar_impact": 5000}
    }
    score = compute_materiality_score(z_score=0.5, dollar_impact=100, kpi_config=kpi_config)
    assert score < 1.0, f"Expected composite_score < 1.0 for minor movement, got {score}"


def test_get_material_movements_returns_ranked_list(db):
    movements = get_material_movements(db, demo_today=DEMO_TODAY)
    assert isinstance(movements, list)
    # Verify descending sort by composite_score
    scores = [m["composite_score"] for m in movements]
    assert scores == sorted(scores, reverse=True), "Movements not sorted by composite_score"


def test_get_material_movements_west_only(db):
    movements = get_material_movements(db, demo_today=DEMO_TODAY, regions=["West"])
    regions_in_result = {m.get("region") for m in movements}
    # Should only contain West or ALL (aggregate)
    assert all(r in ("West", "ALL") for r in regions_in_result), (
        f"Non-West regions in result: {regions_in_result}"
    )


def test_material_flag_threshold(db):
    movements = get_material_movements(db, demo_today=DEMO_TODAY)
    for m in movements:
        if m["is_material"]:
            assert m["composite_score"] >= 1.0, (
                f"Material movement has composite_score < 1.0: {m['composite_score']}"
            )
