"""
narrative.py — Persona-Specific Narratives (Objective 4)

Translates pre-computed evidence and drivers into a role-appropriate narrative.
Every sentence must be cited back to the evidence table.

Computed by: gemini-3.5-flash (generation) + fixed prompt templates
"""

import json
import logging
from typing import List, Dict, Any
from .models import NarrativeResponse, Citation, UserContext
from .telemetry import call_llm_with_telemetry

logger = logging.getLogger(__name__)

# Prompt templates stored as string constants
CEO_TEMPLATE = """
Write a one-paragraph executive summary for the CEO.
Focus on:
1. The top-line $-impact of the movement.
2. The primary root cause identified by the analysis.
3. The strategic implications or top-level recommendation across all regions.
Keep it concise and strategic. Do not get bogged down in SKU-level details.
"""

REGIONAL_MANAGER_TEMPLATE = """
Write a detailed operational narrative for the Regional Manager.
Focus on:
1. Region-specific impacts and operational reality.
2. Specific drivers (e.g., channel mix, seasonality, SKU-level impacts).
3. Operational actions required at the regional level.
Be specific and pragmatic.
"""

def _generate_fallback_narrative(kpi_name: str, drivers: list, is_ceo: bool) -> dict:
    """Template-based fallback if LLM is unavailable."""
    top_driver = drivers[0]["driver_name"] if drivers else "unknown factors"
    direction = drivers[0]["direction"] if drivers else "impacted"
    
    if is_ceo:
        text = f"The {kpi_name} movement is primarily driven by {top_driver} ({direction}). [E001] Strategic review is recommended. [E002]"
    else:
        text = f"Regional {kpi_name} has been affected by {top_driver} ({direction}). [E001] Please review operational metrics and channel performance. [E002]"
        
    return {
        "text": text,
        "citations": [
            {"citation_id": "c1", "evidence_id": "E001", "text_span": "primary driver"},
            {"citation_id": "c2", "evidence_id": "E002", "text_span": "action recommended"}
        ]
    }

async def generate_narrative(
    llm_client,
    evidence: list,
    drivers: list,
    user_context: UserContext,
    kpi_name: str,
    fallback_mode: bool = False
) -> NarrativeResponse:
    """
    Generate persona-specific narrative with citations using Gemini.
    """
    is_ceo = user_context.role.lower() == "ceo"
    persona_template = CEO_TEMPLATE if is_ceo else REGIONAL_MANAGER_TEMPLATE
    
    # Format evidence for the prompt
    evidence_text = "\n".join([
        f"[{e['evidence_id']}] {e['source_table']} - {e['metric']}: {e['value']} (Method: {e['method']})"
        for e in evidence
    ])
    
    drivers_text = json.dumps([d for d in drivers[:3]], indent=2)
    
    system_prompt = (
        "You are an expert data analyst translating quantitative evidence into a business narrative.\n"
        "RULES:\n"
        "1. You MUST append an evidence citation like [E001] to EVERY sentence you write.\n"
        "2. ONLY use evidence IDs provided in the Context.\n"
        "3. NEVER invent numbers. Use only the provided evidence.\n"
        "4. Respond with a JSON object containing 'text' (the narrative string) and 'citations' (a list of objects with 'citation_id', 'evidence_id', 'text_span')."
    )
    
    prompt = (
        f"Context Evidence:\n{evidence_text}\n\n"
        f"Top Drivers:\n{drivers_text}\n\n"
        f"Target Persona:\n{user_context.name} (Role: {user_context.role})\n"
        f"Persona Instructions:\n{persona_template}\n\n"
        f"KPI: {kpi_name}\n"
    )
    
    fallback_raw = _generate_fallback_narrative(kpi_name, drivers, is_ceo)
    
    llm_response = await call_llm_with_telemetry(
        client=llm_client,
        model="gemini-3.5-flash",
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        call_type="narrative_generation",
        force_fallback=fallback_mode,
        fallback_response=json.dumps(fallback_raw)
    )
    
    try:
        result = json.loads(llm_response["text"])
    except json.JSONDecodeError:
        # Failsafe parsing
        import re
        match = re.search(r'\{.*\}', llm_response["text"], re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
            except:
                result = fallback_raw
        else:
            result = fallback_raw
            
    text = result.get("text", "")
    raw_citations = result.get("citations", [])
    
    # Map back to specific evidence items
    citations = []
    evidence_ids = set()
    
    for i, c in enumerate(raw_citations):
        eid = str(c.get("evidence_id", ""))
        # Simple extraction if they gave multiple e.g. [E001, E002]
        import re
        eids = re.findall(r'E\d{3}', eid)
        if not eids and 'E' in eid:
            eids = [eid] # fallback
            
        for extracted_eid in eids:
            citations.append(Citation(
                citation_id=f"c{i}_{extracted_eid}",
                evidence_id=extracted_eid,
                text_span=str(c.get("text_span", ""))
            ))
            evidence_ids.add(extracted_eid)
            
    return NarrativeResponse(
        persona=user_context.name,
        text=text,
        citations=citations,
        evidence_ids=list(evidence_ids),
        model_used="gemini-3.5-flash" if not llm_response["is_fallback"] else "fallback-template",
        is_fallback=llm_response["is_fallback"]
    )
