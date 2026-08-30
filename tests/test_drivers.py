"""
test_drivers.py — Phase 2: Driver Analysis
"""

import pytest
from backend.drivers import (
    pvm_decomposition,
    regression_driver_ranking,
    get_qualitative_drivers,
    analyze_drivers,
)
from backend.detect import DEMO_TODAY

PERIOD_START = "2026-08-11"
PERIOD_END = "2026-08-18"
COMP_START = "2026-07-14"
COMP_END = "2026-08-10"

WEST_REVENUE_MOVEMENT = {
    "kpi_name": "Revenue",
    "region": "West",
    "period_start": PERIOD_START,
    "period_end": PERIOD_END,
    "current_value": 5000.0,
    "previous_value": 7000.0,
    "absolute_change": -2000.0,
    "pct_change": -28.6,
    "z_score": -3.5,
    "dollar_impact": -2000.0,
    "detection_method": "z_score",
    "is_sparse": False,
    "data_points": 150,
}


# --- PVM Decomposition (Revenue ONLY) ---

def test_pvm_decomposition_returns_all_components(db):
    pvm = pvm_decomposition(db, PERIOD_START, PERIOD_END, COMP_START, COMP_END, region="West")
    assert "price_effect" in pvm
    assert "volume_effect" in pvm
    assert "mix_effect" in pvm
    assert "total_explained" in pvm


def test_pvm_price_and_volume_effects_are_negative_for_drop(db):
    pvm = pvm_decomposition(db, PERIOD_START, PERIOD_END, COMP_START, COMP_END, region="West")
    # Both price and volume were injected as negative
    assert pvm["price_effect"] < 0, f"Price effect should be negative, got {pvm['price_effect']}"
    assert pvm["volume_effect"] < 0, f"Volume effect should be negative, got {pvm['volume_effect']}"


def test_pvm_not_called_for_non_revenue_kpis(db):
    """Critical: PVM must never run for non-Revenue KPIs."""
    for kpi in ["Units_Sold", "AOV", "Marketing_ROI", "Churn_Rate"]:
        movement = {**WEST_REVENUE_MOVEMENT, "kpi_name": kpi}
        result = analyze_drivers(db, kpi, movement, demo_today=DEMO_TODAY)
        assert result["pvm"] is None, (
            f"PVM must be None for {kpi}, got {result['pvm']}"
        )


# --- Regression Driver Ranking ---

def test_regression_returns_driver_list(db):
    drivers = regression_driver_ranking(db, "Revenue", PERIOD_START, PERIOD_END, region="West")
    assert isinstance(drivers, list)


def test_regression_drivers_have_required_fields(db):
    drivers = regression_driver_ranking(db, "Revenue", PERIOD_START, PERIOD_END)
    for d in drivers:
        assert "driver_name" in d
        assert "effect_value" in d
        assert "direction" in d
        assert d["direction"] in ("+", "-")
        assert "quantified" in d


def test_regression_drivers_sorted_by_variance(db):
    drivers = regression_driver_ranking(db, "Revenue", PERIOD_START, PERIOD_END)
    if len(drivers) > 1:
        variances = [d.get("explained_variance", 0) for d in drivers]
        assert variances == sorted(variances, reverse=True), "Drivers not sorted by explained_variance"


# --- Qualitative Drivers ---

def test_qualitative_driver_from_context_notes(db):
    qualitative = get_qualitative_drivers(db, "2026-08-10", "2026-08-18", region="West")
    assert len(qualitative) > 0, "Should find competitor activity note for West Aug period"
    cats = [d["driver_name"] for d in qualitative]
    assert any("competitor" in c.lower() or "competitor_activity" in c.lower() for c in cats), (
        f"Expected competitor_activity note, found: {cats}"
    )


def test_qualitative_drivers_are_explicitly_unquantified(db):
    qualitative = get_qualitative_drivers(db, PERIOD_START, PERIOD_END, region="West")
    for d in qualitative:
        assert d["quantified"] is False, "Qualitative drivers must have quantified=False"
        assert d["confidence"] == "low", "Qualitative drivers must have low confidence"


# --- Full analyze_drivers pipeline ---

def test_analyze_drivers_revenue_uses_pvm(db):
    result = analyze_drivers(db, "Revenue", WEST_REVENUE_MOVEMENT, demo_today=DEMO_TODAY)
    assert result["pvm"] is not None, "Revenue analysis should include PVM decomposition"
    assert result["method_used"] == "pvm_decomposition + regression"


def test_analyze_drivers_non_revenue_no_pvm(db):
    units_movement = {**WEST_REVENUE_MOVEMENT, "kpi_name": "Units_Sold"}
    result = analyze_drivers(db, "Units_Sold", units_movement, demo_today=DEMO_TODAY)
    assert result["pvm"] is None, "Units_Sold must not use PVM"


def test_analyze_drivers_sparse_history_fallback(db):
    sparse_movement = {
        "kpi_name": "Revenue",
        "region": "East",
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "is_sparse": True,
        "data_points": 10,
    }
    result = analyze_drivers(db, "Revenue", sparse_movement, demo_today=DEMO_TODAY)
    assert result["method_fallback"] is True
    assert result["method_used"] == "category_average_benchmark"
    assert result["fallback_reason"] is not None


def test_analyze_drivers_returns_total_explained_variance(db):
    result = analyze_drivers(db, "Revenue", WEST_REVENUE_MOVEMENT, demo_today=DEMO_TODAY)
    assert 0.0 <= result["total_explained_variance"] <= 1.0


def test_analyze_drivers_has_qualitative_drivers(db):
    result = analyze_drivers(db, "Revenue", WEST_REVENUE_MOVEMENT, demo_today=DEMO_TODAY)
    # Context note for West Aug period should surface
    assert isinstance(result["qualitative_drivers"], list)
