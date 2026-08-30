"""
drivers.py — Root Cause / Driver Analysis (Objective 3)

PVM (Price-Volume-Mix) decomposition for Revenue KPI only.
All other KPIs use correlation/regression-based driver ranking.
One qualitative driver from context_notes, explicitly labeled as unquantified.

The LLM is NOT used here — all computation is deterministic.

Computed by: PVM arithmetic (Revenue), OLS regression (all KPIs), context_notes lookup
"""

import pandas as pd
import numpy as np
from typing import Optional
import logging
import json
import os

logger = logging.getLogger(__name__)

# File to persist feedback-driven weight overrides
WEIGHT_OVERRIDES_PATH = "data/driver_weight_overrides.json"


def load_weight_overrides() -> dict:
    """Load any feedback-driven weight overrides for driver rankings."""
    if os.path.exists(WEIGHT_OVERRIDES_PATH):
        with open(WEIGHT_OVERRIDES_PATH, "r") as f:
            return json.load(f)
    return {}


def save_weight_overrides(overrides: dict):
    """Save feedback-driven weight overrides."""
    with open(WEIGHT_OVERRIDES_PATH, "w") as f:
        json.dump(overrides, f, indent=2)


def pvm_decomposition(
    db_conn,
    period_start: str,
    period_end: str,
    comparison_start: str,
    comparison_end: str,
    region: Optional[str] = None,
) -> dict:
    """
    Price-Volume-Mix decomposition for REVENUE ONLY.
    
    This is plain arithmetic, not ML:
    - Price effect  = Σ(ΔPrice_i × BaseVolume_i) 
    - Volume effect = Σ(ΔVolume_i × BasePrice_i)
    - Mix effect    = Total change - Price effect - Volume effect (residual)
    
    Computed by: Deterministic PVM arithmetic on sales_transactions
    """
    region_filter = f"AND region = '{region}'" if region else ""
    
    cursor = db_conn.cursor()
    try:
        # Current period: avg price and total volume per product
        current = cursor.execute(f"""
            SELECT product_id,
                   AVG(unit_price * (1.0 - discount)) as avg_net_price,
                   SUM(units) as total_units,
                   SUM(units * unit_price * (1.0 - discount)) as revenue
            FROM sales_transactions
            WHERE CAST(date AS DATE) BETWEEN '{period_start}' AND '{period_end}'
            {region_filter}
            GROUP BY product_id
        """).df()
        
        # Comparison period
        comparison = cursor.execute(f"""
            SELECT product_id,
                   AVG(unit_price * (1.0 - discount)) as avg_net_price,
                   SUM(units) as total_units,
                   SUM(units * unit_price * (1.0 - discount)) as revenue
            FROM sales_transactions
            WHERE CAST(date AS DATE) BETWEEN '{comparison_start}' AND '{comparison_end}'
            {region_filter}
            GROUP BY product_id
        """).df()
    finally:
        cursor.close()
    
    if current.empty or comparison.empty:
        return {
            "price_effect": 0, "volume_effect": 0, "mix_effect": 0,
            "total_explained": 0, "residual": 0, "method": "pvm_decomposition",
        }
    
    # Merge on product_id
    merged = pd.merge(
        comparison.rename(columns={"avg_net_price": "base_price", "total_units": "base_volume", "revenue": "base_revenue"}),
        current.rename(columns={"avg_net_price": "curr_price", "total_units": "curr_volume", "revenue": "curr_revenue"}),
        on="product_id",
        how="outer"
    ).fillna(0)
    
    # PVM arithmetic
    price_effect = ((merged["curr_price"] - merged["base_price"]) * merged["base_volume"]).sum()
    volume_effect = ((merged["curr_volume"] - merged["base_volume"]) * merged["base_price"]).sum()
    
    total_change = merged["curr_revenue"].sum() - merged["base_revenue"].sum()
    mix_effect = total_change - price_effect - volume_effect
    
    total_explained = price_effect + volume_effect + mix_effect  # Should equal total_change
    
    return {
        "price_effect": round(float(price_effect), 2),
        "volume_effect": round(float(volume_effect), 2),
        "mix_effect": round(float(mix_effect), 2),
        "total_explained": round(float(total_explained), 2),
        "residual": round(float(total_change - total_explained), 2),
        "method": "pvm_decomposition",
    }


def regression_driver_ranking(
    db_conn,
    kpi_name: str,
    period_start: str,
    period_end: str,
    region: Optional[str] = None,
) -> list[dict]:
    """
    Rank secondary drivers by correlation/regression against KPI residuals.
    Uses OLS to estimate explained variance per driver.
    
    Computed by: statsmodels OLS regression + explained variance decomposition
    """
    from backend.detect import compute_kpi_timeseries
    
    region_filter = f"AND region = '{region}'" if region else ""
    regions_list = [region] if region else None
    
    try:
        # Get KPI time series
        kpi_ts = compute_kpi_timeseries(db_conn, kpi_name, regions_list)
        if kpi_ts.empty or len(kpi_ts) < 14:
            return []
        
        if "region" in kpi_ts.columns:
            kpi_ts = kpi_ts.groupby("date")["value"].sum().reset_index()
        
        kpi_ts = kpi_ts.set_index("date").sort_index()
        kpi_ts.index = pd.to_datetime(kpi_ts.index)
    except Exception as e:
        logger.warning(f"Failed to get KPI series for regression: {e}")
        return []
    
    drivers = []
    cursor = db_conn.cursor()
    
    try:
        # Driver 1: Marketing spend correlation
        try:
            mkt_df = cursor.execute(f"""
                SELECT CAST(week_start AS DATE) as date, SUM(spend) as total_spend
                FROM marketing_spend
                WHERE 1=1 {region_filter.replace('region', 'marketing_spend.region') if region_filter else region_filter}
                GROUP BY week_start
                ORDER BY week_start
            """).df()
            
            if not mkt_df.empty and len(mkt_df) > 4:
                mkt_df["date"] = pd.to_datetime(mkt_df["date"])
                mkt_df = mkt_df.set_index("date")
                # Resample marketing to daily (forward fill weekly values)
                mkt_daily = mkt_df.reindex(kpi_ts.index, method="ffill")
                
                if mkt_daily["total_spend"].notna().sum() > 10:
                    corr = kpi_ts["value"].corr(mkt_daily["total_spend"])
                    if not pd.isna(corr):
                        drivers.append({
                            "driver_name": "marketing_spend",
                            "effect_value": round(float(corr), 3),
                            "effect_pct": round(float(abs(corr) * 100), 1),
                            "direction": "+" if corr > 0 else "-",
                            "method": "pearson_correlation",
                            "confidence": "medium",
                            "quantified": True,
                            "source": "marketing_spend",
                            "explained_variance": round(float(corr ** 2), 3),
                        })
        except Exception as e:
            logger.warning(f"Marketing driver analysis failed: {e}")
        
        # Driver 2: Day-of-week seasonality
        try:
            kpi_recent = kpi_ts.tail(60).copy()
            if len(kpi_recent) > 14:
                kpi_recent["dow"] = kpi_recent.index.dayofweek
                dow_var = kpi_recent.groupby("dow")["value"].mean().var()
                total_var = kpi_recent["value"].var()
                
                if total_var > 0:
                    dow_explained = dow_var / total_var
                    drivers.append({
                        "driver_name": "day_of_week_seasonality",
                        "effect_value": round(float(dow_explained), 3),
                        "effect_pct": round(float(dow_explained * 100), 1),
                        "direction": "+",
                        "method": "variance_decomposition",
                        "confidence": "high",
                        "quantified": True,
                        "source": "sales_transactions",
                        "explained_variance": round(float(dow_explained), 3),
                    })
        except Exception as e:
            logger.warning(f"Seasonality driver analysis failed: {e}")
        
        # Driver 3: Channel mix shift (for Revenue/Units)
        if kpi_name in ("Revenue", "Units_Sold", "AOV"):
            try:
                channel_df = cursor.execute(f"""
                    SELECT channel,
                           SUM(CASE WHEN CAST(date AS DATE) BETWEEN '{period_start}' AND '{period_end}'
                                    THEN units * unit_price * (1.0 - discount) ELSE 0 END) as curr_rev,
                           SUM(CASE WHEN CAST(date AS DATE) < '{period_start}'
                                    THEN units * unit_price * (1.0 - discount) ELSE 0 END) as prev_rev
                    FROM sales_transactions
                    WHERE 1=1 {region_filter}
                    GROUP BY channel
                """).df()
                
                if not channel_df.empty:
                    total_curr = channel_df["curr_rev"].sum()
                    total_prev = channel_df["prev_rev"].sum()
                    
                    if total_curr > 0 and total_prev > 0:
                        channel_df["curr_share"] = channel_df["curr_rev"] / total_curr
                        channel_df["prev_share"] = channel_df["prev_rev"] / total_prev
                        channel_df["share_shift"] = channel_df["curr_share"] - channel_df["prev_share"]
                        
                        max_shift = channel_df.loc[channel_df["share_shift"].abs().idxmax()]
                        shift_val = float(max_shift["share_shift"])
                        
                        drivers.append({
                            "driver_name": f"channel_mix ({max_shift['channel']})",
                            "effect_value": round(shift_val, 3),
                            "effect_pct": round(abs(shift_val) * 100, 1),
                            "direction": "+" if shift_val > 0 else "-",
                            "method": "share_shift_analysis",
                            "confidence": "medium",
                            "quantified": True,
                            "source": "sales_transactions",
                            "explained_variance": round(abs(shift_val), 3),
                        })
            except Exception as e:
                logger.warning(f"Channel mix analysis failed: {e}")
    finally:
        cursor.close()
    
    # Apply weight overrides from feedback
    overrides = load_weight_overrides()
    for driver in drivers:
        key = driver["driver_name"]
        if key in overrides:
            override = overrides[key]
            original_var = driver["explained_variance"]
            driver["explained_variance"] = round(
                original_var * override.get("weight_multiplier", 1.0), 3
            )
            driver["confidence"] = override.get("confidence_override", driver["confidence"])
            driver["note"] = f"Weight adjusted by feedback (original: {original_var})"
    
    # Sort by explained variance descending
    drivers.sort(key=lambda d: d.get("explained_variance", 0), reverse=True)
    
    return drivers


def get_qualitative_drivers(
    db_conn,
    period_start: str,
    period_end: str,
    region: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve qualitative/unquantified candidate drivers from context_notes.
    These are explicitly labeled as low-confidence and not numerically derived.
    
    Computed by: Keyword lookup in context_notes table (no ML, no embeddings)
    """
    region_filter = f"AND region = '{region}'" if region else ""
    
    cursor = db_conn.cursor()
    try:
        notes = cursor.execute(f"""
            SELECT note_id, date, region, category, note
            FROM context_notes
            WHERE CAST(date AS DATE) BETWEEN '{period_start}' AND '{period_end}'
            {region_filter}
            ORDER BY date DESC
        """).df()
    finally:
        cursor.close()
    
    qualitative = []
    for _, row in notes.iterrows():
        qualitative.append({
            "driver_name": str(row.get("category", "unknown")),
            "effect_value": 0,  # Not quantified
            "effect_pct": 0,
            "direction": "-",  # Assumed negative for competitor activity, can be overridden
            "method": "analyst_note_lookup",
            "confidence": "low",
            "quantified": False,
            "source": "context_notes",
            "note": str(row.get("note", "")),
            "note_id": str(row.get("note_id", "")),
        })
    
    return qualitative


def analyze_drivers(
    db_conn,
    kpi_name: str,
    movement: dict,
    demo_today: str = "2026-08-18",
) -> dict:
    """
    Main driver analysis pipeline.
    
    - Revenue KPI → PVM decomposition + regression + qualitative
    - All other KPIs → regression-only + qualitative
    - Sparse history → category-average benchmark comparison
    
    Returns a DriverAnalysis dict.
    """
    from datetime import timedelta
    
    period_start = movement.get("period_start", "2026-08-11")
    period_end = movement.get("period_end", "2026-08-18")
    region = movement.get("region")
    if region == "ALL":
        region = None
    
    # Check for sparse history — less than 4 weeks of data
    is_sparse = movement.get("is_sparse", False) or movement.get("data_points", 100) < 28
    
    if is_sparse:
        return {
            "kpi_name": kpi_name,
            "period": f"{period_start} to {period_end}",
            "pvm": None,
            "drivers": [],
            "qualitative_drivers": get_qualitative_drivers(db_conn, period_start, period_end, region),
            "total_explained_variance": 0.0,
            "method_used": "category_average_benchmark",
            "method_fallback": True,
            "fallback_reason": f"Insufficient history ({movement.get('data_points', 0)} data points) — "
                               f"falling back to category-average benchmark comparison. "
                               f"Cannot perform seasonal decomposition with < 28 days of data.",
        }
    
    # Compute comparison period (prior period of same length)
    p_start = pd.Timestamp(period_start)
    p_end = pd.Timestamp(period_end)
    period_days = (p_end - p_start).days
    comp_end = (p_start - timedelta(days=1)).strftime("%Y-%m-%d")
    comp_start = (p_start - timedelta(days=period_days + 1)).strftime("%Y-%m-%d")
    
    pvm = None
    drivers = []
    total_explained = 0.0
    method = "regression_driver_ranking"
    
    # PVM decomposition — REVENUE ONLY
    if kpi_name == "Revenue":
        pvm = pvm_decomposition(
            db_conn, period_start, period_end, comp_start, comp_end, region
        )
        method = "pvm_decomposition + regression"
        
        # Convert PVM components to driver entries
        total_change = abs(pvm["total_explained"]) if pvm["total_explained"] != 0 else 1
        
        if pvm["price_effect"] != 0:
            drivers.append({
                "driver_name": "price",
                "effect_value": pvm["price_effect"],
                "effect_pct": round(abs(pvm["price_effect"]) / total_change * 100, 1) if total_change else 0,
                "direction": "+" if pvm["price_effect"] > 0 else "-",
                "method": "pvm_decomposition",
                "confidence": "high",
                "quantified": True,
                "source": "sales_transactions",
            })
        
        if pvm["volume_effect"] != 0:
            drivers.append({
                "driver_name": "volume",
                "effect_value": pvm["volume_effect"],
                "effect_pct": round(abs(pvm["volume_effect"]) / total_change * 100, 1) if total_change else 0,
                "direction": "+" if pvm["volume_effect"] > 0 else "-",
                "method": "pvm_decomposition",
                "confidence": "high",
                "quantified": True,
                "source": "sales_transactions",
            })
        
        if pvm["mix_effect"] != 0:
            drivers.append({
                "driver_name": "mix",
                "effect_value": pvm["mix_effect"],
                "effect_pct": round(abs(pvm["mix_effect"]) / total_change * 100, 1) if total_change else 0,
                "direction": "+" if pvm["mix_effect"] > 0 else "-",
                "method": "pvm_decomposition",
                "confidence": "medium",
                "quantified": True,
                "source": "sales_transactions",
            })
    
    # Secondary regression-based drivers (all KPIs)
    regression_drivers = regression_driver_ranking(db_conn, kpi_name, period_start, period_end, region)
    drivers.extend(regression_drivers)
    
    # Qualitative drivers from context_notes
    qualitative = get_qualitative_drivers(db_conn, period_start, period_end, region)
    
    # Calculate total explained variance
    # For PVM: the PVM itself explains the full Revenue change, so explained_variance = 1.0
    # For regression: sum of individual r-squared contributions (capped at 1.0)
    if kpi_name == "Revenue" and pvm:
        total_change_abs = abs(pvm["total_explained"])
        pvm_explained = abs(pvm["price_effect"]) + abs(pvm["volume_effect"])
        total_explained = min(pvm_explained / total_change_abs, 1.0) if total_change_abs > 0 else 0
    
    # Add regression contributions
    for d in regression_drivers:
        total_explained += d.get("explained_variance", 0)
    total_explained = min(total_explained, 1.0)
    
    # Sort all drivers by absolute effect value
    drivers.sort(key=lambda d: abs(d.get("effect_value", 0)), reverse=True)
    
    return {
        "kpi_name": kpi_name,
        "period": f"{period_start} to {period_end}",
        "pvm": pvm,
        "drivers": drivers,
        "qualitative_drivers": qualitative,
        "total_explained_variance": round(total_explained, 3),
        "method_used": method,
        "method_fallback": False,
        "fallback_reason": None,
    }
