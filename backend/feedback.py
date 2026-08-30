"""
feedback.py — Feedback & Learning (Objective 7)

Stores user feedback (thumbs up/down, corrections) and dynamically updates
driver weights based on corrections to simulate a learning loop.

Computed by: DuckDB insert, local JSON rule override mapping
"""

from typing import List, Dict
from datetime import datetime
from .models import FeedbackEntry
from .drivers import load_weight_overrides, save_weight_overrides
import logging

logger = logging.getLogger(__name__)

def submit_feedback(db_conn, entry: FeedbackEntry) -> bool:
    """
    Store feedback in DuckDB and process any explicit corrections
    to update driver weight rankings.
    """
    cursor = db_conn.cursor()
    try:
        ts = entry.timestamp or datetime.now()
        
        cursor.execute(
            """
            INSERT INTO feedback_store 
            (insight_id, feedback_type, rating, correction_text, target, target_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                entry.insight_id,
                entry.feedback_type,
                entry.rating,
                entry.correction_text,
                entry.target,
                entry.target_id,
                ts
            ]
        )
        
        # If user corrected a driver ranking explicitly
        if entry.target == "driver" and entry.feedback_type == "correction" and entry.target_id:
            # Simple rule: if they corrected a driver, boost or penalize its weight
            # For prototype demo: we assume correction implies "this should be ranked higher"
            # or we can parse a thumbs_down as a penalty
            overrides = load_weight_overrides()
            
            driver_key = entry.target_id
            if driver_key not in overrides:
                overrides[driver_key] = {"weight_multiplier": 1.0}
                
            if entry.rating == -1:
                # Penalize weight by 50%
                overrides[driver_key]["weight_multiplier"] *= 0.5
                overrides[driver_key]["confidence_override"] = "low"
            elif entry.rating == 1 or entry.correction_text:
                # Boost weight by 50%
                overrides[driver_key]["weight_multiplier"] *= 1.5
                overrides[driver_key]["confidence_override"] = "high"
                
            save_weight_overrides(overrides)
            
        return True
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        return False
    finally:
        cursor.close()

def get_expert_validation_queue(db_conn) -> List[Dict]:
    """
    Returns insights that need expert validation — real corrections from feedback_store
    plus the pinned low-confidence demo scenario.
    """
    queue = []
    cursor = db_conn.cursor()
    try:
        df = cursor.execute("""
            SELECT insight_id, feedback_type, correction_text, target, target_id,
                   CAST(timestamp AS VARCHAR) as ts
            FROM feedback_store
            WHERE feedback_type = 'correction' OR rating = -1
            ORDER BY timestamp DESC
            LIMIT 20
        """).df()

        for _, row in df.iterrows():
            queue.append({
                "insight_id": row["insight_id"],
                "status": "pending_expert_review",
                "reason": row.get("correction_text") or f"User flagged {row['target']} as incorrect",
                "feedback_type": row["feedback_type"],
                "target": row["target"],
                "target_id": row.get("target_id"),
                "timestamp": row["ts"],
            })
    except Exception as e:
        logger.error(f"Failed to query feedback_store: {e}")
    finally:
        cursor.close()

    # Pinned demo scenario (always shown — represents the Churn_Rate abstain case)
    queue.append({
        "insight_id": "INS-LOW-CONF-001",
        "kpi_name": "Churn_Rate",
        "region": "East",
        "period": "2026-05-01 to 2026-06-30",
        "status": "pending_expert_review",
        "reason": "Contradictory signals: NPS decline vs. seasonal factors. Confidence 0.35 — below threshold.",
        "confidence_score": 0.35,
    })
    return queue
