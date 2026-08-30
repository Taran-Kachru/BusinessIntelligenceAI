"""
detect.py — KPI Anomaly Detection (Objective 1)

Detects material KPI movements using Z-score analysis and IsolationForest,
then ranks by a dual materiality score combining statistical significance
and dollar impact. The LLM is NOT used here — all computation is deterministic.

Computed by: Z-score (rolling 28-day window) + IsolationForest + business-rule materiality weighting
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from datetime import date, timedelta
from typing import Optional
import yaml
import logging

DEMO_TODAY = os.getenv("DEMO_TODAY", "2026-08-18")

logger = logging.getLogger(__name__)


def load_kpi_contract(path: str = "kpi_contract.yaml") -> dict:
    """Load KPI definitions and thresholds from the contract file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def compute_kpi_timeseries(db_conn, kpi_name: str, regions: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Compute daily KPI values from raw tables using DuckDB.
    Returns DataFrame with columns: [date, region, value]
    
    All computation is deterministic SQL — no LLM involvement.
    """
    # Literal region filter — safe since regions come from trusted config, not user input
    region_filter = ""
    if regions:
        regions_str = ", ".join([f"'{r}'" for r in regions])
        region_filter = f"AND region IN ({regions_str})"
        ms_region_filter = f"AND ms.region IN ({regions_str})"
        st_region_filter = f"AND st_inner.region IN ({regions_str})"
    else:
        ms_region_filter = ""
        st_region_filter = ""

    queries = {
        "Revenue": f"""
            SELECT date, region,
                   SUM(units * unit_price * (1.0 - discount)) as value
            FROM sales_transactions
            WHERE 1=1 {region_filter}
            GROUP BY date, region
            ORDER BY date
        """,
        "Units_Sold": f"""
            SELECT date, region,
                   SUM(units) as value
            FROM sales_transactions
            WHERE 1=1 {region_filter}
            GROUP BY date, region
            ORDER BY date
        """,
        "AOV": f"""
            SELECT date, region,
                   SUM(units * unit_price * (1.0 - discount)) / COUNT(DISTINCT order_id) as value
            FROM sales_transactions
            WHERE 1=1 {region_filter}
            GROUP BY date, region
            ORDER BY date
        """,
        "Marketing_ROI": f"""
            SELECT ms.week_start as date, ms.region,
                   CASE WHEN SUM(ms.spend) > 0
                        THEN (COALESCE(SUM(st_inner.revenue), 0) - SUM(ms.spend)) / SUM(ms.spend)
                        ELSE 0 END as value
            FROM marketing_spend ms
            LEFT JOIN (
                SELECT DATE_TRUNC('week', date) as week_start, region,
                       SUM(units * unit_price * (1.0 - discount)) as revenue
                FROM sales_transactions
                GROUP BY DATE_TRUNC('week', date), region
            ) st_inner ON ms.week_start = st_inner.week_start AND ms.region = st_inner.region
            WHERE 1=1 {ms_region_filter}
            GROUP BY ms.week_start, ms.region
            ORDER BY ms.week_start
        """,
        "Churn_Rate": f"""
            SELECT CAST(month AS DATE) as date, region,
                   CASE WHEN active_customers > 0
                        THEN CAST(churned_customers AS DOUBLE) / active_customers
                        ELSE 0 END as value
            FROM customer_events
            WHERE 1=1 {region_filter}
            ORDER BY month
        """,
    }

    if kpi_name not in queries:
        raise ValueError(f"Unknown KPI: {kpi_name}. Valid KPIs: {list(queries.keys())}")

    cursor = db_conn.cursor()
    try:
        df = cursor.execute(queries[kpi_name]).df()
    finally:
        cursor.close()

    df["date"] = pd.to_datetime(df["date"])
    return df


def detect_anomalies_zscore(
    ts: pd.Series,
    window: int = 28,
    threshold: float = 2.0
) -> pd.DataFrame:
    """
    Detect anomalies using rolling Z-score on a time series.
    
    Computed by: Rolling mean/std (28-day window), Z-score = (x - μ) / σ
    """
    rolling_mean = ts.rolling(window=window, min_periods=max(7, window // 4)).mean()
    rolling_std = ts.rolling(window=window, min_periods=max(7, window // 4)).std()
    
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)
    
    z_scores = (ts - rolling_mean) / rolling_std
    
    return pd.DataFrame({
        "value": ts,
        "rolling_mean": rolling_mean,
        "rolling_std": rolling_std,
        "z_score": z_scores,
        "abs_z": z_scores.abs(),
        "is_anomaly": z_scores.abs() > threshold,
    })


def detect_anomalies_isolation_forest(
    df: pd.DataFrame,
    value_col: str = "value",
    contamination: float = 0.05
) -> pd.Series:
    """
    Secondary anomaly detection using IsolationForest for multi-dimensional patterns.
    
    Computed by: scikit-learn IsolationForest (contamination={contamination})
    """
    if len(df) < 10:
        return pd.Series(False, index=df.index)
    
    features = df[[value_col]].copy()
    # Add rate-of-change as a feature
    features["roc"] = df[value_col].pct_change().fillna(0)
    features = features.fillna(0)
    
    iso = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = iso.fit_predict(features)
    
    return pd.Series(preds == -1, index=df.index, name="iso_anomaly")


def compute_materiality_score(
    z_score: float,
    dollar_impact: float,
    kpi_config: dict
) -> float:
    """
    Dual materiality score combining statistical significance and business impact.
    
    Computed by: composite = 0.5 * (|z| / z_threshold) + 0.5 * (|$_impact| / $_threshold)
    Both components normalized to their respective thresholds from kpi_contract.yaml.
    """
    z_threshold = kpi_config["materiality_threshold"].get("statistical_z", 2.0)
    
    # Get the dollar-equivalent threshold (could be dollar_impact, unit_impact, etc.)
    impact_threshold = (
        kpi_config["materiality_threshold"].get("dollar_impact")
        or kpi_config["materiality_threshold"].get("unit_impact")
        or kpi_config["materiality_threshold"].get("ratio_points_impact")
        or kpi_config["materiality_threshold"].get("rate_points_impact")
        or 1.0  # fallback
    )
    
    stat_component = min(abs(z_score) / z_threshold, 3.0)  # cap at 3x threshold
    impact_component = min(abs(dollar_impact) / impact_threshold, 3.0)
    
    composite = 0.5 * stat_component + 0.5 * impact_component
    return round(composite, 3)


def detect_movements(
    db_conn,
    demo_today: str = "2026-08-18",
    lookback_days: int = 7,
    contract_path: str = "kpi_contract.yaml",
    regions: Optional[list[str]] = None,
) -> list[dict]:
    """
    Main detection pipeline: find and rank material KPI movements.
    
    Returns a list of KPIMovement dicts, ranked by composite materiality score.
    Only material movements (composite_score > 1.0) are returned.
    
    Computed by: Z-score anomaly detection + IsolationForest + dual materiality scoring
    """
    contract = load_kpi_contract(contract_path)
    today = pd.Timestamp(demo_today)
    period_end = today
    period_start = today - timedelta(days=lookback_days)
    comparison_end = period_start - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=lookback_days)
    
    movements = []
    
    for kpi_name, kpi_config in contract["kpis"].items():
        try:
            ts_df = compute_kpi_timeseries(db_conn, kpi_name, regions)
        except Exception as e:
            logger.warning(f"Failed to compute {kpi_name}: {e}")
            continue
        
        if ts_df.empty:
            continue
        
        # Aggregate across all regions for overall KPI value
        if "region" in ts_df.columns:
            overall = ts_df.groupby("date")["value"].sum().reset_index()
        else:
            overall = ts_df.copy()
        
        overall = overall.set_index("date").sort_index()
        
        # Also check per-region for region-specific anomalies
        region_groups = [("ALL", overall)]
        if "region" in ts_df.columns:
            for region, rdf in ts_df.groupby("region"):
                r_ts = rdf.set_index("date")["value"].sort_index()
                region_groups.append((region, r_ts.to_frame()))
        
        for region_label, region_ts in region_groups:
            if isinstance(region_ts, pd.DataFrame):
                ts = region_ts["value"]
            else:
                ts = region_ts
            
            if len(ts) < 14:  # Need minimum history
                # Sparse history — flag but handle differently
                current_mask = (ts.index >= period_start) & (ts.index <= period_end)
                if current_mask.sum() == 0:
                    continue
                    
                current_val = ts[current_mask].mean()
                movements.append({
                    "kpi_name": kpi_name,
                    "region": region_label,
                    "period_start": period_start.date().isoformat(),
                    "period_end": period_end.date().isoformat(),
                    "current_value": round(float(current_val), 2),
                    "previous_value": None,
                    "absolute_change": None,
                    "pct_change": None,
                    "z_score": None,
                    "dollar_impact": None,
                    "composite_score": 0.5,  # Low score for sparse data
                    "detection_method": "sparse_history_flag",
                    "is_material": False,
                    "is_sparse": True,
                    "data_points": int(len(ts)),
                })
                continue
            
            # Z-score detection
            z_threshold = kpi_config["materiality_threshold"].get("statistical_z", 2.0)
            anomaly_df = detect_anomalies_zscore(ts, window=28, threshold=z_threshold)
            
            # IsolationForest as secondary check
            iso_flags = detect_anomalies_isolation_forest(ts.to_frame())
            anomaly_df["iso_anomaly"] = iso_flags
            
            # Current period values
            current_mask = (ts.index >= period_start) & (ts.index <= period_end)
            comparison_mask = (ts.index >= comparison_start) & (ts.index <= comparison_end)
            
            if current_mask.sum() == 0 or comparison_mask.sum() == 0:
                continue
            
            current_val = ts[current_mask].mean()
            previous_val = ts[comparison_mask].mean()
            absolute_change = current_val - previous_val
            pct_change = (absolute_change / previous_val * 100) if previous_val != 0 else 0
            
            # Get the most extreme Z-score in the current period
            current_z_scores = anomaly_df.loc[current_mask, "z_score"].dropna()
            if len(current_z_scores) == 0:
                continue
            
            max_z = current_z_scores.iloc[current_z_scores.abs().argmax()]
            
            # Dollar impact
            dollar_impact = absolute_change  # For revenue-like KPIs, this IS the dollar impact
            if kpi_name in ("Churn_Rate", "Marketing_ROI", "AOV"):
                # Scale to business-meaningful units
                dollar_impact = absolute_change
            
            # Dual materiality score
            composite = compute_materiality_score(max_z, dollar_impact, kpi_config)
            
            # Check if any anomaly was flagged
            current_anomalies = anomaly_df.loc[current_mask]
            has_zscore_anomaly = current_anomalies["is_anomaly"].any()
            has_iso_anomaly = current_anomalies["iso_anomaly"].any() if "iso_anomaly" in current_anomalies else False
            
            is_material = composite >= 1.0
            
            if has_zscore_anomaly or has_iso_anomaly:
                detection_method = "z_score"
                if has_iso_anomaly and not has_zscore_anomaly:
                    detection_method = "isolation_forest"
                elif has_iso_anomaly and has_zscore_anomaly:
                    detection_method = "z_score+isolation_forest"
            else:
                detection_method = "threshold_check"
            
            movements.append({
                "kpi_name": kpi_name,
                "region": region_label,
                "period_start": period_start.date().isoformat(),
                "period_end": period_end.date().isoformat(),
                "current_value": round(float(current_val), 2),
                "previous_value": round(float(previous_val), 2),
                "absolute_change": round(float(absolute_change), 2),
                "pct_change": round(float(pct_change), 2),
                "z_score": round(float(max_z), 3),
                "dollar_impact": round(float(dollar_impact), 2),
                "composite_score": composite,
                "detection_method": detection_method,
                "is_material": is_material,
                "is_sparse": False,
                "data_points": int(len(ts)),
            })
    
    # Rank by composite materiality score, descending
    movements.sort(key=lambda m: m["composite_score"], reverse=True)
    
    return movements


def get_material_movements(
    db_conn,
    demo_today: str = "2026-08-18",
    regions: Optional[list[str]] = None,
    contract_path: str = "kpi_contract.yaml",
) -> list[dict]:
    """
    Convenience function: return only material movements (composite_score >= 1.0)
    plus any sparse-history flags.
    """
    all_movements = detect_movements(db_conn, demo_today, regions=regions, contract_path=contract_path)
    return [m for m in all_movements if m["is_material"] or m.get("is_sparse")]
