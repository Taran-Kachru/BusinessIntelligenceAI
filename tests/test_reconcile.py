"""
test_reconcile.py — Phase 1: Data Reconciliation & Freshness
"""

import pytest
from backend.reconcile import (
    get_freshness_info,
    get_freshness_penalty,
    reconcile_for_period,
    build_evidence_items,
)
from backend.detect import DEMO_TODAY

PERIOD_START = "2026-08-11"
PERIOD_END = "2026-08-18"


def test_freshness_info_returns_all_tables(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    table_names = {f["table_name"] for f in freshness}
    expected = {"sales_transactions", "marketing_spend", "customer_events", "context_notes"}
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_freshness_info_sales_is_fresh(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    sales = next(f for f in freshness if f["table_name"] == "sales_transactions")
    assert sales["freshness_status"] == "FRESH", (
        f"sales_transactions should be FRESH, got {sales['freshness_status']} ({sales['days_stale']} days)"
    )


def test_freshness_info_customer_events_is_stale(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    cust = next(f for f in freshness if f["table_name"] == "customer_events")
    assert cust["freshness_status"] == "STALE", (
        f"customer_events should be STALE, got {cust['freshness_status']}"
    )
    assert (cust["days_stale"] or 0) > 30


def test_freshness_penalty_scales_correctly(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    # Fresh data → low penalty
    fresh_penalty = get_freshness_penalty(freshness, ["sales_transactions"])
    stale_penalty = get_freshness_penalty(freshness, ["customer_events"])
    assert fresh_penalty < stale_penalty, "Stale source should have higher penalty than fresh"
    assert stale_penalty >= 0.5, f"Expected significant penalty for stale data, got {stale_penalty}"


def test_reconcile_returns_all_sources(db):
    result = reconcile_for_period(db, PERIOD_START, PERIOD_END, demo_today=DEMO_TODAY)
    assert "sales" in result
    assert "marketing" in result
    assert "customer" in result
    assert "context_notes" in result
    assert "freshness" in result
    assert not result["sales"].empty, "Sales data should not be empty"
    assert not result["marketing"].empty, "Marketing data should not be empty"


def test_reconcile_with_region_filter(db):
    result_west = reconcile_for_period(db, PERIOD_START, PERIOD_END, regions=["West"], demo_today=DEMO_TODAY)
    result_all = reconcile_for_period(db, PERIOD_START, PERIOD_END, demo_today=DEMO_TODAY)
    # West-filtered data should have fewer rows
    assert len(result_west["sales"]) <= len(result_all["sales"])


def test_build_evidence_items_revenue(db):
    result = reconcile_for_period(db, PERIOD_START, PERIOD_END, regions=["West"], demo_today=DEMO_TODAY)
    movement = {
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
    }
    evidence = build_evidence_items(result, "Revenue", movement)
    assert len(evidence) > 0, "Evidence should not be empty"
    # Each evidence item must have required fields
    for e in evidence:
        assert "evidence_id" in e
        assert "source_table" in e
        assert "metric" in e
        assert "method" in e


def test_evidence_ids_are_unique(db):
    result = reconcile_for_period(db, PERIOD_START, PERIOD_END, demo_today=DEMO_TODAY)
    movement = {"kpi_name": "Revenue", "current_value": 5000, "previous_value": 7000,
                "absolute_change": -2000, "pct_change": -28.6, "z_score": -3.5,
                "dollar_impact": -2000, "detection_method": "z_score"}
    evidence = build_evidence_items(result, "Revenue", movement)
    ids = [e["evidence_id"] for e in evidence]
    assert len(ids) == len(set(ids)), "Evidence IDs must be unique"


def test_freshness_info_has_native_grain(db):
    freshness = get_freshness_info(db, demo_today=DEMO_TODAY)
    grains = {f["table_name"]: f["native_grain"] for f in freshness}
    assert grains.get("sales_transactions") == "daily"
    assert grains.get("marketing_spend") == "weekly"
    assert grains.get("customer_events") == "monthly"
