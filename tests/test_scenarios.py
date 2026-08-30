"""
test_scenarios.py — Deterministic Scenario Verification (Amendment #4)

Asserts that the data generation script deterministically produced
the 4 baked-in scenarios required for the demo.
"""

import sys
import os
import pandas as pd
import pytest

# Add backend to path for importing detect
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.database import init_db, get_db_connection
from backend.detect import get_material_movements, DEMO_TODAY

@pytest.fixture(scope="module")
def db_conn():
    # Initialize DB with the generated CSVs
    init_db("data")
    return get_db_connection()

def test_west_revenue_drop_is_detected(db_conn):
    """
    Scenario 1: West region revenue drops significantly in week of Aug 11-17.
    Must be flagged as a material movement.
    """
    movements = get_material_movements(db_conn, demo_today=DEMO_TODAY, regions=["West"])
    
    west_rev_drop = [
        m for m in movements 
        if m["kpi_name"] == "Revenue" 
        and m["region"] == "West" 
        and m["period_start"] == "2026-08-11"
        and m["is_material"] == True
    ]
    
    assert len(west_rev_drop) > 0, "West Revenue drop for Aug 11-17 was not detected as material."
    
    movement = west_rev_drop[0]
    assert movement["pct_change"] < -15.0, f"Expected >15% drop, got {movement['pct_change']}%"
    assert movement["composite_score"] >= 1.0, "Composite score too low."

def test_sku_new_sparse_history(db_conn):
    """
    Scenario 3: SKU-NEW has sparse history (introduced July 28).
    Since movements aggregate by region/KPI, we check if ANY movement flags as sparse,
    or we just test the raw data to ensure SKU-NEW has < 4 weeks.
    """
    df = db_conn.execute("SELECT MIN(date), MAX(date) FROM sales_transactions WHERE product_id = 'SKU-NEW'").df()
    assert not df.empty, "SKU-NEW not found in sales_transactions."
    
    min_date = pd.to_datetime(df.iloc[0, 0])
    max_date = pd.to_datetime(df.iloc[0, 1])
    
    days_alive = (max_date - min_date).days
    assert days_alive <= 25, f"SKU-NEW should have <28 days history, found {days_alive} days."

def test_stale_customer_events_data(db_conn):
    """
    Scenario: customer_events is deliberately stale (max month is June 2026).
    """
    df = db_conn.execute("SELECT MAX(month) FROM customer_events").df()
    assert not df.empty, "customer_events table is empty."
    
    max_month = pd.to_datetime(df.iloc[0, 0])
    
    assert max_month.year == 2026, f"Expected 2026, got {max_month.year}"
    assert max_month.month == 6, f"Expected June (6), got {max_month.month}. Data must be stale."

def test_competitor_promo_context_note(db_conn):
    """
    Scenario: Context notes contains the qualitative competitor promo driver.
    """
    df = db_conn.execute("SELECT * FROM context_notes WHERE category = 'competitor_activity' AND region = 'West'").df()
    assert not df.empty, "Competitor activity context note missing."
    
    note = df.iloc[0]["note"].lower()
    assert "20%" in note and "promo" in note, "Note text does not contain expected competitor promo details."
