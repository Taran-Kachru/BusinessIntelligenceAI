"""
actions.py — Recommended Actions (Objective 6)

LLM drafts recommended actions from a fixed lever catalog.
Enforces decision rights deterministically by escalating the "owner"
if the requesting persona lacks authority.

Computed by: gemini-3.5-flash (generation) + Deterministic schema validation
"""

import json
import yaml
import logging
from typing import List, Dict
from .models import ActionCard, UserContext
from .telemetry import call_llm_with_telemetry
import os

logger = logging.getLogger(__name__)

def get_lever_catalog() -> Dict:
    with open("kpi_contract.yaml", "r") as f:
        config = yaml.safe_load(f)
    return config.get("lever_catalog", {})

def get_persona_config(role: str) -> Dict:
    with open("kpi_contract.yaml", "r") as f:
        config = yaml.safe_load(f)
    for p_name, p_data in config.get("personas", {}).items():
        if p_data.get("role") == role or p_name.lower() == role.lower():
            return p_data
    return {}

def _generate_fallback_actions(drivers: list, lever_catalog: dict) -> list:
    """Deterministic fallback if LLM is unavailable."""
    actions = []
    for d in drivers[:2]:
        driver_name = d.get("driver_name", "unknown")
        
        # Pick a default lever based on driver
        lever = "marketing_budget_reallocation" if "marketing" in driver_name else "pricing_adjustment"
        if lever not in lever_catalog:
            lever = list(lever_catalog.keys())[0]
            
        actions.append({
            "driver": driver_name,
            "controllable_lever": lever,
            "action": f"Adjust {lever} to address {driver_name}.",
            "expected_impact": "Stabilize KPI trajectory.",
            "owner": "TBD",
            "confidence": "Medium",
            "monitoring_plan": "Review next week."
        })
    return actions

async def generate_actions(
    llm_client,
    evidence: list,
    drivers: list,
    user_context: UserContext,
    kpi_name: str,
    fallback_mode: bool = False
) -> List[ActionCard]:
    """
    Generate actions using Gemini, selecting from fixed lever catalog.
    Enforces decision rights after generation.
    """
    lever_catalog = get_lever_catalog()
    persona_config = get_persona_config(user_context.role)
    
    # Filter to top quantified drivers
    top_drivers = [d for d in drivers if d.get("quantified")][:3]
    if not top_drivers and drivers:
        top_drivers = [drivers[0]]
        
    fallback_raw = _generate_fallback_actions(top_drivers, lever_catalog)
    
    system_prompt = (
        "You are a business strategy assistant recommending actions based on analytical evidence.\n"
        "You MUST choose from the provided Fixed Lever Catalog.\n"
        "Respond ONLY with a JSON array of action objects. No markdown formatting, no preamble."
    )
    
    prompt = (
        f"Generate 1-2 recommended actions for the recent movement in {kpi_name}.\n\n"
        f"Fixed Lever Catalog:\n{json.dumps(lever_catalog, indent=2)}\n\n"
        f"Top Drivers:\n{json.dumps(top_drivers, indent=2)}\n\n"
        f"Target Persona:\n{user_context.name} (Role: {user_context.role})\n\n"
        "Output format must be a JSON array of objects with exactly these keys:\n"
        '- "driver": The specific driver this action addresses\n'
        '- "controllable_lever": The exact key from the Fixed Lever Catalog (e.g., "pricing_adjustment")\n'
        '- "action": Specific, actionable recommendation\n'
        '- "expected_impact": Brief description of expected outcome\n'
        '- "owner": Leave as "Self" if the persona can execute it, or name the role needed\n'
        '- "confidence": High, Medium, or Low\n'
        '- "monitoring_plan": How to track success\n'
    )
    
    llm_response = await call_llm_with_telemetry(
        client=llm_client,
        model="gemini-3.5-flash",
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        call_type="action_generation",
        force_fallback=fallback_mode,
        fallback_response=json.dumps(fallback_raw)
    )
    
    try:
        raw_actions = json.loads(llm_response["text"])
    except json.JSONDecodeError:
        # Failsafe if LLM outputs markdown or bad JSON
        import re
        match = re.search(r'\[.*\]', llm_response["text"], re.DOTALL)
        if match:
            try:
                raw_actions = json.loads(match.group(0))
            except:
                raw_actions = fallback_raw
        else:
            raw_actions = fallback_raw
            
    validated_actions = []
    
    for act in raw_actions:
        # Validate lever against catalog
        lever = act.get("controllable_lever")
        if lever not in lever_catalog:
            # Try to map to first available if invalid
            lever = list(lever_catalog.keys())[0]
            
        lever_config = lever_catalog[lever]
        req_authority = lever_config.get("min_authority", "CEO")
        
        # Enforce decision rights
        has_authority = False
        allowed_levers = persona_config.get("decision_authority", [])
        
        # Basic authority check - if the persona's config explicitly lists this lever
        if lever in allowed_levers:
            has_authority = True
        elif user_context.role.lower() == "ceo":
            has_authority = True # CEO can do anything
            
        exceeds = not has_authority
        owner = act.get("owner", user_context.name)
        
        if exceeds:
            owner = req_authority # Escalate to required authority
            
        validated_actions.append(ActionCard(
            driver=str(act.get("driver", "")),
            controllable_lever=str(lever),
            action=str(act.get("action", "")),
            expected_impact=str(act.get("expected_impact", "")),
            owner=str(owner),
            confidence=str(act.get("confidence", "Medium")),
            monitoring_plan=str(act.get("monitoring_plan", "")),
            exceeds_authority=exceeds
        ))
        
    return validated_actions
