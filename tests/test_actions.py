"""
test_actions.py — Phase 3: Action Generation & Decision Rights

All tests run in fallback mode to avoid API quota usage.
"""

import asyncio
import pytest
from unittest.mock import MagicMock
from backend.actions import generate_actions, get_lever_catalog, _generate_fallback_actions
from backend.models import UserContext, ActionCard

CEO_USER = UserContext(
    user_id="CEO", role="ceo", name="Chief Executive Officer",
    allowed_regions=["ALL"], can_view_pii=True
)
RM_WEST_USER = UserContext(
    user_id="Regional_Manager_West", role="regional_manager", name="Regional Manager West",
    allowed_regions=["West"], can_view_pii=False
)

SAMPLE_DRIVERS = [
    {"driver_name": "price", "effect_value": -1200.0, "effect_pct": 60.0,
     "direction": "-", "method": "pvm_decomposition", "confidence": "high", "quantified": True},
    {"driver_name": "volume", "effect_value": -600.0, "effect_pct": 30.0,
     "direction": "-", "method": "pvm_decomposition", "confidence": "high", "quantified": True},
]

SAMPLE_EVIDENCE = [
    {"evidence_id": "E001", "source_table": "sales_transactions", "metric": "Revenue",
     "value": 5200.0, "method": "z_score"},
]


def test_lever_catalog_loads():
    catalog = get_lever_catalog()
    assert len(catalog) > 0, "Lever catalog should not be empty"
    assert "pricing_adjustment" in catalog
    assert "promo_calendar" in catalog


def test_lever_catalog_has_min_authority():
    catalog = get_lever_catalog()
    for lever, config in catalog.items():
        assert "min_authority" in config, f"{lever} missing min_authority"


def test_fallback_actions_respect_catalog():
    catalog = get_lever_catalog()
    actions = _generate_fallback_actions(SAMPLE_DRIVERS, catalog)
    assert len(actions) > 0
    for act in actions:
        assert act["controllable_lever"] in catalog, (
            f"Lever '{act['controllable_lever']}' not in catalog"
        )


def test_fallback_actions_have_all_7_fields():
    catalog = get_lever_catalog()
    actions = _generate_fallback_actions(SAMPLE_DRIVERS, catalog)
    required = {"driver", "controllable_lever", "action", "expected_impact", "owner", "confidence", "monitoring_plan"}
    for act in actions:
        assert required.issubset(act.keys()), f"Missing fields: {required - act.keys()}"


@pytest.mark.asyncio
async def test_generate_actions_fallback_mode():
    mock_client = MagicMock()
    actions = await generate_actions(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=CEO_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    assert len(actions) > 0
    assert all(isinstance(a, ActionCard) for a in actions)


@pytest.mark.asyncio
async def test_generate_actions_lever_in_catalog():
    mock_client = MagicMock()
    catalog = get_lever_catalog()
    actions = await generate_actions(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=CEO_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    for act in actions:
        assert act.controllable_lever in catalog, (
            f"Generated lever '{act.controllable_lever}' not in fixed catalog — schema violation"
        )


@pytest.mark.asyncio
async def test_decision_rights_escalated_for_regional_manager():
    """
    Regional Manager should not have authority over pricing_adjustment.
    That lever requires VP Pricing → exceeds_authority=True, owner escalated.
    """
    mock_client = MagicMock()

    # Force the fallback to return a pricing_adjustment action
    # by patching the fallback function
    from unittest.mock import patch
    pricing_fallback = [{
        "driver": "price",
        "controllable_lever": "pricing_adjustment",
        "action": "Reduce price by 5%",
        "expected_impact": "Volume recovery",
        "owner": "Self",
        "confidence": "Medium",
        "monitoring_plan": "Weekly review"
    }]

    import json
    import backend.actions as actions_mod
    original = actions_mod._generate_fallback_actions
    actions_mod._generate_fallback_actions = lambda d, c: pricing_fallback

    try:
        actions = await generate_actions(
            llm_client=mock_client,
            evidence=SAMPLE_EVIDENCE,
            drivers=SAMPLE_DRIVERS,
            user_context=RM_WEST_USER,
            kpi_name="Revenue",
            fallback_mode=True,
        )
        pricing_actions = [a for a in actions if a.controllable_lever == "pricing_adjustment"]
        if pricing_actions:
            act = pricing_actions[0]
            assert act.exceeds_authority is True, "RM requesting pricing_adjustment must be flagged"
            assert act.owner != RM_WEST_USER.name, "Owner must be escalated above RM"
    finally:
        actions_mod._generate_fallback_actions = original


@pytest.mark.asyncio
async def test_ceo_has_full_authority():
    mock_client = MagicMock()
    actions = await generate_actions(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=CEO_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    # CEO should not have any escalated actions
    escalated = [a for a in actions if a.exceeds_authority]
    assert len(escalated) == 0, f"CEO should not have escalated actions, got: {escalated}"
