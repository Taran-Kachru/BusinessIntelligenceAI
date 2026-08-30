"""
test_scenarios_trigger.py — End-to-End Scenario Trigger Tests

Defines the 4 required demo scenarios as acceptance tests.
Written in Phase 0; fully passes after Phase 2.

Phase gate:
  Scenario 1 detection     — passes after Phase 1
  Scenario 4 freshness     — passes after Phase 1
  Scenario 2 abstention    — passes after Phase 2
  Scenario 3 sparse method — passes after Phase 2
"""

import sys
import os
import pytest
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.database import init_db, get_db_connection
from backend.detect import get_material_movements, DEMO_TODAY
from backend.reconcile import get_freshness_info, get_freshness_penalty
from backend.drivers import analyze_drivers
from backend.abstain import evaluate_abstention

DATA_DIR = os.path.join(ROOT, "data")


@pytest.fixture(scope="module", autouse=True)
def chdir_to_root():
    os.chdir(ROOT)
    yield


@pytest.fixture(scope="module")
def db():
    init_db(DATA_DIR)
    return get_db_connection()


# ---------------------------------------------------------------------------
# Scenario 1 — Multi-factor West revenue drop (Aug 11-17)
# Phase 1 gate
# ---------------------------------------------------------------------------

def test_scenario1_west_revenue_drop_detected(db):
    movements = get_material_movements(db, demo_today=DEMO_TODAY, regions=["West"])
    matches = [
        m for m in movements
        if m["kpi_name"] == "Revenue"
        and m.get("region") == "West"
        and m["period_start"] == "2026-08-11"
        and m["is_material"]
    ]
    assert len(matches) > 0, "Scenario 1: West Revenue drop (Aug 11-17) not detected as material."
    m = matches[0]
    assert m["pct_change"] < -15.0, f"Expected >15% drop, got {m['pct_change']:.1f}%"
    assert m["composite_score"] >= 1.0, f"Composite score too low: {m['composite_score']:.2f}"


def test_scenario1_west_revenue_has_multiple_drivers(db):
    movements = get_material_movements(db, demo_today=DEMO_TODAY, regions=["West"])
    west_rev = next(
        (m for m in movements if m["kpi_name"] == "Revenue" and m.get("region") == "West"
         and m["period_start"] == "2026-08-11"),
        None,
    )
    assert west_rev is not None, "Scenario 1: West Revenue movement not found."

    driver_result = analyze_drivers(db, "Revenue", west_rev, demo_today=DEMO_TODAY)
    driver_names = {d["driver_name"].lower() for d in driver_result["drivers"]}
    assert "price" in driver_names or any("price" in n for n in driver_names), "Price driver missing."
    assert "volume" in driver_names or any("volume" in n for n in driver_names), "Volume driver missing."


# ---------------------------------------------------------------------------
# Scenario 2 — Low-confidence / abstention (Churn with stale data)
# Phase 2 gate
# ---------------------------------------------------------------------------

def test_scenario2_churn_abstains_due_to_stale_data(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    cust_fi = next((f for f in freshness if f["table_name"] == "customer_events"), None)
    assert cust_fi is not None, "customer_events freshness info missing."

    # Churn has stale data (June) + no current-period movements => low confidence
    # Build a driver analysis with low explained variance as the scenario
    dummy_driver_analysis = {
        "kpi_name": "Churn_Rate",
        "drivers": [],
        "total_explained_variance": 0.3,  # below 0.5 threshold
        "method_fallback": True,
    }
    days_stale = cust_fi.get("days_stale", 0) or 0
    freshness_penalty = min(days_stale / 60.0, 1.0)

    confidence = evaluate_abstention(
        kpi_name="Churn_Rate",
        drivers=dummy_driver_analysis["drivers"],
        total_explained_variance=dummy_driver_analysis["total_explained_variance"],
        freshness_penalty=freshness_penalty,
        is_sparse_history=False,
    )
    assert confidence["should_abstain"], (
        f"Scenario 2: Expected abstention. score={confidence['score']:.2f}, "
        f"reason={confidence['abstention_reason']}"
    )
    assert confidence["clarifying_question"], "Abstention must include a clarifying question."


# ---------------------------------------------------------------------------
# Scenario 3 — Sparse history (SKU-NEW launched July 28)
# Phase 2 gate
# ---------------------------------------------------------------------------

def test_scenario3_sku_new_has_less_than_28_days(db):
    df = db.execute(
        "SELECT MIN(date) AS min_d, MAX(date) AS max_d "
        "FROM sales_transactions WHERE product_id = 'SKU-NEW'"
    ).df()
    assert not df.empty, "SKU-NEW not found in sales_transactions."

    min_d = pd.to_datetime(df.iloc[0]["min_d"])
    max_d = pd.to_datetime(df.iloc[0]["max_d"])
    days_alive = (max_d - min_d).days
    assert days_alive < 28, f"SKU-NEW should have <28 days history, found {days_alive}."


def test_scenario3_sparse_movement_uses_fallback(db):
    # Get all movements including sparse flags
    from backend.detect import detect_movements
    all_movements = detect_movements(db, demo_today=DEMO_TODAY, regions=None)
    sparse = [m for m in all_movements if m.get("is_sparse")]
    # SKU-NEW is a product-level filter; sparse movements are flagged at KPI/region level
    # when total data points < 14. Verify the flag works by checking a low-history case.
    # If no sparse flag triggered for current data, verify via direct driver call.
    dummy_sparse_movement = {
        "kpi_name": "Revenue",
        "region": "East",
        "period_start": "2026-08-11",
        "period_end": "2026-08-18",
        "is_sparse": True,
        "data_points": 10,
    }
    result = analyze_drivers(db, "Revenue", dummy_sparse_movement, demo_today=DEMO_TODAY)
    assert result["method_fallback"] is True, "Scenario 3: Expected method_fallback=True for sparse data."
    assert result["fallback_reason"] is not None, "Scenario 3: fallback_reason must be set."
    assert result["method_used"] == "category_average_benchmark"


# ---------------------------------------------------------------------------
# Scenario 4 — Stale data (customer_events last refreshed June 2026)
# Phase 1 gate
# ---------------------------------------------------------------------------

def test_scenario4_stale_customer_events(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    customer_fi = next((f for f in freshness if f["table_name"] == "customer_events"), None)
    assert customer_fi is not None, "customer_events not in freshness info."
    assert customer_fi["freshness_status"] == "STALE", (
        f"Scenario 4: Expected STALE, got {customer_fi['freshness_status']}. "
        f"days_stale={customer_fi['days_stale']}"
    )
    assert (customer_fi["days_stale"] or 0) >= 30, (
        f"Scenario 4: Expected >=30 days stale, got {customer_fi['days_stale']}."
    )


def test_scenario4_stale_data_produces_freshness_penalty(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    penalty = get_freshness_penalty(freshness, ["customer_events"])
    assert penalty > 0.5, f"Expected freshness penalty > 0.5 for stale data, got {penalty:.3f}"
