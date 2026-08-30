"""
test_abstain.py — Phase 2: Confidence Scoring & Abstention Rules
"""

import pytest
from backend.abstain import calculate_confidence, evaluate_abstention, score_confidence


# --- calculate_confidence ---

def test_confidence_all_fresh_and_explained():
    result = calculate_confidence(
        total_explained_variance=1.0,
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    assert result["score"] == pytest.approx(1.0, abs=0.01)


def test_confidence_zero_when_all_bad():
    result = calculate_confidence(
        total_explained_variance=0.0,
        freshness_penalty=1.0,
        is_sparse_history=True,
    )
    assert result["score"] == pytest.approx(0.0, abs=0.01)


def test_confidence_weights_correct():
    # 50% variance + 30% freshness + 20% completeness = weights sum to 1.0
    result = calculate_confidence(
        total_explained_variance=0.6,
        freshness_penalty=0.4,
        is_sparse_history=False,
    )
    expected = 0.5 * 0.6 + 0.3 * 0.6 + 0.2 * 1.0
    assert result["score"] == pytest.approx(expected, abs=0.01)


def test_confidence_includes_factors(db):
    result = calculate_confidence(0.7, 0.2, False)
    assert "explained_variance" in result["factors"]
    assert "freshness" in result["factors"]
    assert "completeness" in result["factors"]


# --- evaluate_abstention: Rule 1 (low explained variance) ---

def test_abstention_rule1_low_explained_variance():
    result = evaluate_abstention(
        kpi_name="Revenue",
        drivers=[{"driver_name": "price", "quantified": True, "direction": "-", "effect_value": -100}],
        total_explained_variance=0.3,  # < 0.5
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    assert result["should_abstain"] is True
    assert "30%" in result["clarifying_question"] or "30" in result["clarifying_question"]


def test_abstention_rule2_contradictory_drivers():
    drivers = [
        {"driver_name": "price", "quantified": True, "direction": "-", "effect_value": -500},
        {"driver_name": "volume", "quantified": True, "direction": "+", "effect_value": 480},
    ]
    result = evaluate_abstention(
        kpi_name="Revenue",
        drivers=drivers,
        total_explained_variance=0.8,
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    assert result["should_abstain"] is True, "Contradictory drivers of similar magnitude should trigger abstention"
    assert "conflicting" in result["abstention_reason"].lower() or "contradictory" in result["abstention_reason"].lower()


def test_abstention_rule3_low_overall_confidence():
    # variance=0.55 (rule 1 requires <0.5 AND not sparse, so rule 1 won't fire)
    # sparse=True zeros out completeness_factor (0.2 weight)
    # score = 0.5*0.55 + 0.3*(1-0.9) + 0.2*0.0 = 0.275 + 0.03 + 0.0 = 0.305 < 0.4
    result = evaluate_abstention(
        kpi_name="Churn_Rate",
        drivers=[],
        total_explained_variance=0.55,
        freshness_penalty=0.9,
        is_sparse_history=True,
    )
    assert result["should_abstain"] is True
    assert result["score"] < 0.4


def test_no_abstention_high_confidence():
    drivers = [
        {"driver_name": "price", "quantified": True, "direction": "-", "effect_value": -500},
        {"driver_name": "volume", "quantified": True, "direction": "-", "effect_value": -300},
    ]
    result = evaluate_abstention(
        kpi_name="Revenue",
        drivers=drivers,
        total_explained_variance=0.85,
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    assert result["should_abstain"] is False
    assert result["score"] >= 0.6


def test_abstention_returns_clarifying_question_when_abstaining():
    result = evaluate_abstention(
        kpi_name="Revenue",
        drivers=[],
        total_explained_variance=0.2,
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    assert result["should_abstain"] is True
    assert result["clarifying_question"] is not None
    assert len(result["clarifying_question"]) > 10


# --- score_confidence convenience wrapper ---

def test_score_confidence_wrapper():
    driver_analysis = {
        "kpi_name": "Churn_Rate",
        "drivers": [],
        "total_explained_variance": 0.3,
        "method_fallback": False,
    }
    freshness_info = {"table_name": "customer_events", "days_stale": 49}
    result = score_confidence(driver_analysis, freshness_info)
    assert result["should_abstain"] is True
    assert result["score"] < 0.5


def test_contradictory_drivers_do_not_fire_when_magnitudes_differ():
    """If d2 is < 80% of d1 magnitude, rule 2 should not trigger."""
    drivers = [
        {"driver_name": "price", "quantified": True, "direction": "-", "effect_value": -500},
        {"driver_name": "volume", "quantified": True, "direction": "+", "effect_value": 100},
    ]
    result = evaluate_abstention(
        kpi_name="Revenue",
        drivers=drivers,
        total_explained_variance=0.8,
        freshness_penalty=0.0,
        is_sparse_history=False,
    )
    # d2 is only 20% of d1, so rule 2 should not fire
    assert result["should_abstain"] is False
