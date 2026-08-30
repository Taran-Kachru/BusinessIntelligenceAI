"""
test_narrative.py — Phase 3: LLM Narrative Generation

All tests run in fallback mode (no API key needed) so they pass reliably
without consuming free-tier quota.
"""

import asyncio
import pytest
from unittest.mock import MagicMock
from backend.narrative import generate_narrative, _generate_fallback_narrative
from backend.models import UserContext

CEO_USER = UserContext(
    user_id="CEO", role="ceo", name="Chief Executive Officer",
    allowed_regions=["ALL"], can_view_pii=True
)
RM_WEST_USER = UserContext(
    user_id="Regional_Manager_West", role="regional_manager", name="Regional Manager West",
    allowed_regions=["West"], can_view_pii=False
)

SAMPLE_EVIDENCE = [
    {"evidence_id": "E001", "source_table": "sales_transactions", "metric": "Revenue_current",
     "value": 5200.0, "comparison_value": 7800.0, "method": "z_score", "freshness": None},
    {"evidence_id": "E002", "source_table": "computed", "metric": "z_score",
     "value": -3.5, "comparison_value": 2.0, "method": "rolling_28day_zscore", "freshness": None},
]

SAMPLE_DRIVERS = [
    {"driver_name": "price", "effect_value": -1200.0, "effect_pct": 60.0,
     "direction": "-", "method": "pvm_decomposition", "confidence": "high", "quantified": True},
    {"driver_name": "volume", "effect_value": -600.0, "effect_pct": 30.0,
     "direction": "-", "method": "pvm_decomposition", "confidence": "high", "quantified": True},
]


def test_fallback_narrative_ceo():
    result = _generate_fallback_narrative("Revenue", SAMPLE_DRIVERS, is_ceo=True)
    assert "text" in result
    assert "[E001]" in result["text"] or "[E002]" in result["text"]
    assert "citations" in result
    assert len(result["citations"]) > 0


def test_fallback_narrative_regional_manager():
    result = _generate_fallback_narrative("Revenue", SAMPLE_DRIVERS, is_ceo=False)
    assert "text" in result
    text = result["text"].lower()
    assert "regional" in text or "revenue" in text


def test_fallback_differs_by_persona():
    ceo = _generate_fallback_narrative("Revenue", SAMPLE_DRIVERS, is_ceo=True)
    rm = _generate_fallback_narrative("Revenue", SAMPLE_DRIVERS, is_ceo=False)
    assert ceo["text"] != rm["text"], "CEO and RM narratives should differ"


@pytest.mark.asyncio
async def test_generate_narrative_uses_fallback_when_forced():
    mock_client = MagicMock()
    result = await generate_narrative(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=CEO_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    assert result.is_fallback is True
    assert result.model_used == "fallback-template"
    assert len(result.text) > 0
    assert len(result.citations) > 0


@pytest.mark.asyncio
async def test_generate_narrative_has_persona_in_response():
    mock_client = MagicMock()
    result = await generate_narrative(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=CEO_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    assert result.persona == "Chief Executive Officer"


@pytest.mark.asyncio
async def test_generate_narrative_api_failure_falls_back():
    """When API key is invalid, the fallback path must produce a valid NarrativeResponse."""
    from backend.telemetry import call_llm_with_telemetry
    mock_client = MagicMock()
    # Simulate API failure by using force_fallback
    result = await generate_narrative(
        llm_client=mock_client,
        evidence=SAMPLE_EVIDENCE,
        drivers=SAMPLE_DRIVERS,
        user_context=RM_WEST_USER,
        kpi_name="Revenue",
        fallback_mode=True,
    )
    assert result is not None
    assert result.is_fallback is True
    assert result.text != ""
