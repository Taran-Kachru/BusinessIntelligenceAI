"""
test_feedback.py — Phase 4: Feedback Loop & Weight Overrides
"""

import os
import json
import pytest
from backend.feedback import submit_feedback, get_expert_validation_queue
from backend.drivers import load_weight_overrides, save_weight_overrides, WEIGHT_OVERRIDES_PATH
from backend.models import FeedbackEntry
from datetime import datetime


@pytest.fixture(autouse=True)
def clean_weight_overrides():
    """Reset weight overrides before and after each test."""
    original = {}
    if os.path.exists(WEIGHT_OVERRIDES_PATH):
        with open(WEIGHT_OVERRIDES_PATH) as f:
            original = json.load(f)
    save_weight_overrides({})
    yield
    save_weight_overrides(original)


def test_submit_thumbs_up_stores_feedback(db):
    entry = FeedbackEntry(
        insight_id="INS-001",
        feedback_type="thumbs_up",
        target="insight",
        timestamp=datetime.now(),
    )
    result = submit_feedback(db, entry)
    assert result is True


def test_submit_thumbs_down_stores_feedback(db):
    entry = FeedbackEntry(
        insight_id="INS-002",
        feedback_type="thumbs_down",
        rating=-1,
        target="insight",
        timestamp=datetime.now(),
    )
    result = submit_feedback(db, entry)
    assert result is True


def test_driver_correction_updates_weight_override(db):
    entry = FeedbackEntry(
        insight_id="INS-003",
        feedback_type="correction",
        rating=1,
        correction_text="This driver should be ranked higher",
        target="driver",
        target_id="marketing_spend",
        timestamp=datetime.now(),
    )
    submit_feedback(db, entry)

    overrides = load_weight_overrides()
    assert "marketing_spend" in overrides
    assert overrides["marketing_spend"]["weight_multiplier"] > 1.0, (
        "Positive correction should boost driver weight"
    )


def test_driver_penalization_reduces_weight(db):
    entry = FeedbackEntry(
        insight_id="INS-004",
        feedback_type="correction",
        rating=-1,
        target="driver",
        target_id="day_of_week_seasonality",
        timestamp=datetime.now(),
    )
    submit_feedback(db, entry)

    overrides = load_weight_overrides()
    assert "day_of_week_seasonality" in overrides
    assert overrides["day_of_week_seasonality"]["weight_multiplier"] < 1.0, (
        "Negative correction should reduce driver weight"
    )


def test_weight_persists_across_calls(db):
    entry = FeedbackEntry(
        insight_id="INS-005",
        feedback_type="correction",
        rating=1,
        target="driver",
        target_id="test_driver_persistence",
        timestamp=datetime.now(),
    )
    submit_feedback(db, entry)

    # Load fresh to verify persistence
    overrides = load_weight_overrides()
    assert "test_driver_persistence" in overrides


def test_cumulative_corrections_compound(db):
    """Two positive corrections should compound the weight multiplier."""
    for _ in range(2):
        entry = FeedbackEntry(
            insight_id="INS-006",
            feedback_type="correction",
            rating=1,
            target="driver",
            target_id="compounding_driver",
            timestamp=datetime.now(),
        )
        submit_feedback(db, entry)

    overrides = load_weight_overrides()
    # 1.5 * 1.5 = 2.25
    assert overrides["compounding_driver"]["weight_multiplier"] > 1.5


def test_expert_validation_queue_returns_low_confidence_items(db):
    queue = get_expert_validation_queue(db)
    assert isinstance(queue, list)
    assert len(queue) > 0, "Expert queue should contain at least the scripted low-confidence scenario"
    item = queue[0]
    assert "insight_id" in item
    assert "kpi_name" in item
    assert "confidence_score" in item
    assert item["confidence_score"] < 0.5, "Items in queue should be low-confidence"
