"""
ask.py — Tier 2: Conversational Ask Box

Parses free-text intent into parameters for existing deterministic functions.
Then generates a lightweight cited answer.

Computed by: gemini-3.1-flash-lite (intent parsing & answer) + deterministic pipeline
"""

import json
import logging
from typing import Dict, Any
from .models import AskResponse, Citation, EvidenceItem, UserContext
from .telemetry import call_llm_with_telemetry

logger = logging.getLogger(__name__)

async def parse_intent(llm_client, question: str, fallback_mode: bool = False) -> dict:
    """Extract KPI, region, and intent from the user's question using Haiku."""
    system_prompt = (
        "You are an intent parsing routing system.\n"
        "Extract the 'kpi', 'region', and 'period' from the user's question.\n"
        "Allowed KPIs: Revenue, Units_Sold, AOV, Marketing_ROI, Churn_Rate. (Default to Revenue if unsure)\n"
        "Allowed Regions: ALL, West, East, North, South. (Default to ALL if unsure)\n"
        "Return ONLY a JSON object: {\"kpi\": \"...\", \"region\": \"...\"}"
    )
    
    fallback_raw = {"kpi": "Revenue", "region": "ALL"}
    
    llm_response = await call_llm_with_telemetry(
        client=llm_client,
        model="gemini-3.1-flash-lite",
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
        call_type="intent_parsing",
        force_fallback=fallback_mode,
        fallback_response=json.dumps(fallback_raw)
    )
    
    try:
        return json.loads(llm_response["text"])
    except:
        return fallback_raw

async def answer_question(
    llm_client,
    question: str,
    evidence: list,
    drivers: list,
    fallback_mode: bool = False
) -> AskResponse:
    """Generate a conversational answer using the retrieved evidence."""
    evidence_text = "\n".join([
        f"[{e['evidence_id']}] {e['source_table']} - {e['metric']}: {e['value']}"
        for e in evidence
    ])
    
    drivers_text = json.dumps([d for d in drivers[:3]], indent=2)
    
    system_prompt = (
        "You are a helpful business intelligence assistant.\n"
        "Answer the user's question based strictly on the provided Context Evidence and Drivers.\n"
        "You MUST append an evidence citation like [E001] to EVERY sentence you write.\n"
        "Return a JSON object with 'answer' and 'citations'."
    )
    
    prompt = (
        f"Question: {question}\n\n"
        f"Context Evidence:\n{evidence_text}\n\n"
        f"Top Drivers:\n{drivers_text}\n"
    )
    
    fallback_raw = {
        "answer": "Based on the evidence, the movement is driven by factors detailed in the dashboard. [E001]",
        "citations": [{"citation_id": "c1", "evidence_id": "E001", "text_span": "dashboard"}]
    }
    
    llm_response = await call_llm_with_telemetry(
        client=llm_client,
        model="gemini-3.1-flash-lite",
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        call_type="ask_answer",
        force_fallback=fallback_mode,
        fallback_response=json.dumps(fallback_raw)
    )
    
    try:
        result = json.loads(llm_response["text"])
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', llm_response["text"], re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
            except:
                result = fallback_raw
        else:
            result = fallback_raw
            
    citations = []
    for i, c in enumerate(result.get("citations", [])):
        eid = str(c.get("evidence_id", ""))
        import re
        eids = re.findall(r'E\d{3}', eid)
        if not eids and 'E' in eid:
            eids = [eid]
        for extracted_eid in eids:
            citations.append(Citation(
                citation_id=f"ac{i}_{extracted_eid}",
                evidence_id=extracted_eid,
                text_span=str(c.get("text_span", ""))
            ))
            
    # Map raw evidence dicts back to EvidenceItem models for response
    ev_models = [EvidenceItem(**e) for e in evidence]
            
    return AskResponse(
        answer=result.get("answer", ""),
        citations=citations,
        evidence=ev_models,
        model_used="gemini-3.1-flash-lite" if not llm_response["is_fallback"] else "fallback-template"
    )
