"""
abstain.py — Confidence & Abstention (Objective 5)

Calculates confidence scores and applies deterministic abstention rules.
Prevents the LLM from confabulating answers when evidence is weak.

Computed by: Weighted confidence formula + business logic rules
"""

from typing import Optional


def score_confidence(driver_analysis: dict, freshness_info: dict) -> dict:
    """
    Convenience wrapper for evaluate_abstention that accepts the raw dicts
    returned by analyze_drivers and get_freshness_info.
    """
    days_stale = freshness_info.get("days_stale") or 0
    freshness_penalty = min(days_stale / 60.0, 1.0)
    return evaluate_abstention(
        kpi_name=driver_analysis.get("kpi_name", ""),
        drivers=driver_analysis.get("drivers", []),
        total_explained_variance=driver_analysis.get("total_explained_variance", 0.0),
        freshness_penalty=freshness_penalty,
        is_sparse_history=driver_analysis.get("method_fallback", False),
    )


def calculate_confidence(
    total_explained_variance: float,
    freshness_penalty: float,
    is_sparse_history: bool,
) -> dict:
    """
    Calculate confidence score (0.0 to 1.0) based on multiple factors.
    
    Weights:
    - Explained Variance: 50%
    - Freshness: 30% (inverted penalty)
    - Data Completeness: 20%
    """
    # 1. Variance factor (0 to 1)
    variance_factor = min(max(total_explained_variance, 0.0), 1.0)
    
    # 2. Freshness factor (0 to 1, where 1 is fresh, 0 is stale)
    freshness_factor = 1.0 - min(max(freshness_penalty, 0.0), 1.0)
    
    # 3. Completeness factor (0 to 1)
    completeness_factor = 0.0 if is_sparse_history else 1.0
    
    # Weighted sum
    score = (0.5 * variance_factor) + (0.3 * freshness_factor) + (0.2 * completeness_factor)
    
    return {
        "score": round(score, 3),
        "factors": {
            "explained_variance": round(variance_factor, 3),
            "freshness": round(freshness_factor, 3),
            "completeness": round(completeness_factor, 3)
        }
    }


def evaluate_abstention(
    kpi_name: str,
    drivers: list[dict],
    total_explained_variance: float,
    freshness_penalty: float,
    is_sparse_history: bool,
) -> dict:
    """
    Evaluate deterministic abstention rules based on evidence.
    Returns a dictionary mapping to the ConfidenceResult schema.
    """
    # Calculate confidence score
    confidence_data = calculate_confidence(
        total_explained_variance, 
        freshness_penalty, 
        is_sparse_history
    )
    score = confidence_data["score"]
    factors = confidence_data["factors"]
    
    should_abstain = False
    abstention_reason = None
    clarifying_question = None
    
    # Rule 1: Sparse history explicitly skips some rules but has its own fallback
    # Sparse history is handled by method_fallback in drivers.py, but we still lower confidence
    
    # Rule 2: Low explained variance (< 50%)
    if not is_sparse_history and total_explained_variance < 0.50:
        should_abstain = True
        abstention_reason = "Cannot confidently identify root cause (explained variance < 50%)"
        clarifying_question = f"The identified drivers only explain {total_explained_variance*100:.0f}% of the {kpi_name} movement. Are there external factors or missing data sources we should consider?"

    # Rule 3: Contradictory top drivers
    # If the top 2 quantified drivers point in opposite directions and are close in magnitude
    elif len(drivers) >= 2:
        d1 = drivers[0]
        d2 = drivers[1]
        
        # Check if they have opposite directions
        if d1.get("quantified") and d2.get("quantified") and d1.get("direction") != d2.get("direction"):
            val1 = abs(d1.get("effect_value", 0))
            val2 = abs(d2.get("effect_value", 0))
            
            # If magnitude is similar (e.g., d2 is at least 80% as strong as d1)
            if val1 > 0 and (val2 / val1) > 0.8:
                should_abstain = True
                abstention_reason = "Contradictory signals detected between top drivers"
                clarifying_question = f"We see conflicting signals: {d1['driver_name']} is driving {kpi_name} {d1['direction']}, while {d2['driver_name']} is driving it {d2['direction']} with almost equal force. Which of these aligns with current field reality?"

    # Rule 4: Overall low confidence (< 0.4)
    if not should_abstain and score < 0.4:
        should_abstain = True
        abstention_reason = "Overall confidence score below threshold (0.4)"
        if factors["freshness"] < 0.5:
            clarifying_question = f"Confidence is low due to stale data. Can we refresh the relevant data sources before finalizing this insight?"
        else:
            clarifying_question = f"Confidence is low ({score:.2f}). Please have a domain expert review the contributing factors before taking action."

    return {
        "score": score,
        "should_abstain": should_abstain,
        "abstention_reason": abstention_reason,
        "clarifying_question": clarifying_question,
        "factors": factors
    }
