"""
reconcile.py — Data Reconciliation & Freshness (Objective 2)

Joins three source tables at different grains and refresh cadences
onto one shared calendar. Exposes freshness timestamps and native
grain per source, per insight.

The LLM is NOT used here — all computation is deterministic SQL/pandas.

Computed by: DuckDB SQL joins on shared calendar + freshness metadata calculation
"""

import pandas as pd
from datetime import date, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Known source table metadata — hardcoded since these are fixed for the prototype
SOURCE_TABLE_META = {
    "sales_transactions": {
        "native_grain": "daily",
        "refresh_cadence": "daily",
        "date_column": "date",
    },
    "marketing_spend": {
        "native_grain": "weekly",
        "refresh_cadence": "weekly",
        "date_column": "week_start",
    },
    "customer_events": {
        "native_grain": "monthly",
        "refresh_cadence": "monthly",
        "date_column": "month",
    },
    "context_notes": {
        "native_grain": "ad-hoc",
        "refresh_cadence": "ad-hoc",
        "date_column": "date",
    },
}


def get_freshness_info(db_conn, demo_today: str = "2026-08-18") -> list[dict]:
    """
    Compute freshness metadata for each source table.
    
    Freshness status:
    - FRESH: < 7 days stale
    - AGING: 7-30 days stale  
    - STALE: 30+ days stale
    
    Computed by: MAX(date_column) per table, days difference from demo_today
    """
    today = pd.Timestamp(demo_today)
    freshness = []
    cursor = db_conn.cursor()
    
    try:
        for table_name, meta in SOURCE_TABLE_META.items():
            try:
                date_col = meta["date_column"]
                result = cursor.execute(
                    f"SELECT MAX(CAST({date_col} AS DATE)) as last_date FROM {table_name}"
                ).fetchone()
                
                if result and result[0]:
                    last_refresh = pd.Timestamp(result[0])
                    days_stale = (today - last_refresh).days
                    
                    if days_stale < 7:
                        status = "FRESH"
                    elif days_stale < 30:
                        status = "AGING"
                    else:
                        status = "STALE"
                    
                    freshness.append({
                        "table_name": table_name,
                        "last_refresh": last_refresh.date().isoformat(),
                        "native_grain": meta["native_grain"],
                        "days_stale": days_stale,
                        "freshness_status": status,
                    })
                else:
                    freshness.append({
                        "table_name": table_name,
                        "last_refresh": None,
                        "native_grain": meta["native_grain"],
                        "days_stale": None,
                        "freshness_status": "UNKNOWN",
                    })
            except Exception as e:
                logger.warning(f"Failed to get freshness for {table_name}: {e}")
                freshness.append({
                    "table_name": table_name,
                    "last_refresh": None,
                    "native_grain": meta["native_grain"],
                    "days_stale": None,
                    "freshness_status": "ERROR",
                })
    finally:
        cursor.close()
    
    return freshness


def get_freshness_penalty(freshness_info: list[dict], source_tables: list[str]) -> float:
    """
    Compute a freshness penalty score (0.0 = fully fresh, 1.0 = critically stale).
    Used by abstain.py for confidence scoring.
    
    Computed by: max days_stale across source_tables, scaled to [0, 1]
    """
    max_stale = 0
    for fi in freshness_info:
        if fi["table_name"] in source_tables and fi.get("days_stale") is not None:
            max_stale = max(max_stale, fi["days_stale"])
    
    # Scale: 0 days = 0.0 penalty, 60+ days = 1.0 penalty
    penalty = min(max_stale / 60.0, 1.0)
    return round(penalty, 3)


def reconcile_for_period(
    db_conn,
    period_start: str,
    period_end: str,
    regions: Optional[list[str]] = None,
    demo_today: str = "2026-08-18",
) -> dict:
    """
    Join all source tables onto the shared calendar for a given period.
    Returns unified data + freshness metadata.
    
    Computed by: DuckDB SQL joins with grain alignment (daily/weekly/monthly)
    """
    cursor = db_conn.cursor()
    region_filter = ""
    if regions:
        regions_str = ", ".join([f"'{r}'" for r in regions])
        region_filter = f"AND region IN ({regions_str})"
    
    try:
        # 1. Daily sales data — direct join on calendar
        sales_df = cursor.execute(f"""
            SELECT c.date, st.region,
                   COALESCE(SUM(st.units * st.unit_price * (1.0 - st.discount)), 0) as revenue,
                   COALESCE(SUM(st.units), 0) as units_sold,
                   COALESCE(COUNT(DISTINCT st.order_id), 0) as order_count,
                   CASE WHEN COUNT(DISTINCT st.order_id) > 0 
                        THEN SUM(st.units * st.unit_price * (1.0 - st.discount)) / COUNT(DISTINCT st.order_id)
                        ELSE 0 END as aov
            FROM calendar c
            LEFT JOIN sales_transactions st 
                ON c.date = CAST(st.date AS DATE)
                {region_filter.replace('region', 'st.region') if region_filter else ''}
            WHERE c.date BETWEEN '{period_start}' AND '{period_end}'
            GROUP BY c.date, st.region
            ORDER BY c.date
        """).df()
        
        # 2. Weekly marketing data — align to daily via the week each day belongs to
        marketing_df = cursor.execute(f"""
            SELECT c.date, ms.region, ms.channel,
                   ms.spend / 7.0 as daily_spend,
                   ms.impressions / 7.0 as daily_impressions,
                   ms.clicks / 7.0 as daily_clicks,
                   ms.week_start as native_period_start
            FROM calendar c
            LEFT JOIN marketing_spend ms
                ON c.date >= CAST(ms.week_start AS DATE) 
                AND c.date < CAST(ms.week_start AS DATE) + INTERVAL 7 DAY
                {region_filter.replace('region', 'ms.region') if region_filter else ''}
            WHERE c.date BETWEEN '{period_start}' AND '{period_end}'
            ORDER BY c.date
        """).df()
        
        # 3. Monthly customer data — align to daily via the month each day belongs to
        customer_df = cursor.execute(f"""
            SELECT c.date, ce.region,
                   ce.active_customers,
                   ce.churned_customers,
                   CASE WHEN ce.active_customers > 0
                        THEN CAST(ce.churned_customers AS DOUBLE) / ce.active_customers
                        ELSE NULL END as churn_rate,
                   ce.nps_score,
                   CAST(ce.month AS DATE) as native_period_start
            FROM calendar c
            LEFT JOIN customer_events ce
                ON DATE_TRUNC('month', c.date) = DATE_TRUNC('month', CAST(ce.month AS DATE))
                {region_filter.replace('region', 'ce.region') if region_filter else ''}
            WHERE c.date BETWEEN '{period_start}' AND '{period_end}'
            ORDER BY c.date
        """).df()
        
        # 4. Context notes for the period
        context_df = cursor.execute(f"""
            SELECT * FROM context_notes
            WHERE CAST(date AS DATE) BETWEEN '{period_start}' AND '{period_end}'
            {region_filter}
        """).df()
        
    finally:
        cursor.close()
    
    # Get freshness metadata
    freshness = get_freshness_info(db_conn, demo_today)
    
    return {
        "period_start": period_start,
        "period_end": period_end,
        "regions": regions,
        "sales": sales_df,
        "marketing": marketing_df,
        "customer": customer_df,
        "context_notes": context_df,
        "freshness": freshness,
        "grain_notes": {
            "sales_transactions": "Native daily grain — no alignment needed",
            "marketing_spend": "Native weekly grain — allocated to daily via /7 for calendar alignment",
            "customer_events": "Native monthly grain — forward-filled to daily; last refresh June 2026 (STALE)",
            "context_notes": "Ad-hoc qualitative — joined by date/region overlap",
        },
    }


def build_evidence_items(
    reconciled: dict,
    kpi_name: str,
    movement: dict,
) -> list[dict]:
    """
    Build EvidenceItem list from reconciled data for a specific KPI movement.
    Each evidence item is tagged with its source, method, and freshness.
    
    Computed by: Deterministic extraction from reconciled DataFrames
    """
    evidence = []
    eid = 0
    
    # Evidence from the movement itself
    eid += 1
    evidence.append({
        "evidence_id": f"E{eid:03d}",
        "source_table": "sales_transactions" if kpi_name in ("Revenue", "Units_Sold", "AOV") else "customer_events",
        "metric": f"{kpi_name}_current",
        "value": movement.get("current_value", 0),
        "comparison_value": movement.get("previous_value"),
        "method": movement.get("detection_method", "z_score"),
        "freshness": _find_freshness(reconciled["freshness"], 
                                      "sales_transactions" if kpi_name in ("Revenue", "Units_Sold", "AOV") else "customer_events"),
    })
    
    # Z-score evidence
    if movement.get("z_score") is not None:
        eid += 1
        evidence.append({
            "evidence_id": f"E{eid:03d}",
            "source_table": "computed",
            "metric": "z_score",
            "value": movement["z_score"],
            "comparison_value": 2.0,  # threshold
            "method": "rolling_28day_zscore",
            "freshness": None,
        })
    
    # Dollar impact evidence
    if movement.get("dollar_impact") is not None:
        eid += 1
        evidence.append({
            "evidence_id": f"E{eid:03d}",
            "source_table": "computed",
            "metric": "dollar_impact",
            "value": movement["dollar_impact"],
            "comparison_value": None,
            "method": "absolute_change_calculation",
            "freshness": None,
        })
    
    # Marketing data evidence (if available and relevant)
    if not reconciled["marketing"].empty and kpi_name in ("Revenue", "Marketing_ROI"):
        mkt = reconciled["marketing"]
        total_spend = mkt["daily_spend"].sum() if "daily_spend" in mkt.columns else 0
        if total_spend > 0:
            eid += 1
            evidence.append({
                "evidence_id": f"E{eid:03d}",
                "source_table": "marketing_spend",
                "metric": "total_marketing_spend",
                "value": round(total_spend, 2),
                "comparison_value": None,
                "method": "weekly_to_daily_allocation",
                "freshness": _find_freshness(reconciled["freshness"], "marketing_spend"),
            })
    
    # Customer events evidence (if available and relevant)
    if not reconciled["customer"].empty and kpi_name in ("Churn_Rate",):
        cust = reconciled["customer"]
        if "churn_rate" in cust.columns:
            avg_churn = cust["churn_rate"].dropna().mean()
            if not pd.isna(avg_churn):
                eid += 1
                evidence.append({
                    "evidence_id": f"E{eid:03d}",
                    "source_table": "customer_events",
                    "metric": "avg_churn_rate",
                    "value": round(avg_churn, 4),
                    "comparison_value": None,
                    "method": "monthly_average",
                    "freshness": _find_freshness(reconciled["freshness"], "customer_events"),
                })
    
    # Context notes evidence
    if not reconciled["context_notes"].empty:
        for _, note_row in reconciled["context_notes"].iterrows():
            eid += 1
            evidence.append({
                "evidence_id": f"E{eid:03d}",
                "source_table": "context_notes",
                "metric": "qualitative_context",
                "value": 0,  # No numeric value for qualitative
                "comparison_value": None,
                "method": "analyst_note",
                "freshness": _find_freshness(reconciled["freshness"], "context_notes"),
                "note": str(note_row.get("note", "")),
            })
    
    return evidence


def _find_freshness(freshness_list: list[dict], table_name: str) -> dict | None:
    """Find freshness info for a specific table."""
    for fi in freshness_list:
        if fi["table_name"] == table_name:
            return fi
    return None
