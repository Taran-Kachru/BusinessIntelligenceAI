"""
telemetry.py — LLM Economics & Caching (Objective 8 cont.)

Logs every LLM call, tracks tokens/latency/costs, and provides a caching layer.
Satisfies the 'LLM economics' complexity bullet.

Computed by: Deterministic python wrapping and token/cost counting.
"""

import json
import time
import hashlib
import logging
from datetime import datetime
from typing import Optional
from google.genai import types
from .models import TelemetryRecord, SessionTelemetry

# In-memory storage for prototype
_TELEMETRY_LOG: list[TelemetryRecord] = []
_RESPONSE_CACHE: dict[str, dict] = {}

# Estimated costs per 1M tokens
# Using approximate Gemini pricing
COSTS_PER_1M = {
    "gemini-3.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.1-flash-lite": {"input": 0.04, "output": 0.16},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
}

def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = COSTS_PER_1M.get(model, COSTS_PER_1M["gemini-3.5-flash"])
    cost = (prompt_tokens / 1_000_000) * rates["input"] + (completion_tokens / 1_000_000) * rates["output"]
    return round(cost, 6)

def _generate_cache_key(model: str, system_prompt: str, messages: list) -> str:
    """Generate a deterministic hash for caching based on model and prompt content."""
    payload = {
        "model": model,
        "system": system_prompt,
        "messages": messages
    }
    key_str = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()

def get_session_telemetry() -> SessionTelemetry:
    """Return aggregated telemetry for the current session."""
    total_calls = len(_TELEMETRY_LOG)
    total_prompt = sum(r.prompt_tokens for r in _TELEMETRY_LOG)
    total_completion = sum(r.completion_tokens for r in _TELEMETRY_LOG)
    total_cost = sum(r.estimated_cost for r in _TELEMETRY_LOG)
    total_latency = sum(r.latency_ms for r in _TELEMETRY_LOG)
    
    hits = sum(1 for r in _TELEMETRY_LOG if r.cache_hit)
    hit_rate = (hits / total_calls) if total_calls > 0 else 0.0
    
    return SessionTelemetry(
        total_calls=total_calls,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_cost=round(total_cost, 6),
        total_latency_ms=round(total_latency, 2),
        cache_hit_rate=round(hit_rate, 3),
        calls=list(reversed(_TELEMETRY_LOG))[:50] # Return last 50
    )

def clear_cache():
    """Clear the LLM response cache (useful for testing/demo)."""
    global _RESPONSE_CACHE
    _RESPONSE_CACHE = {}

async def call_llm_with_telemetry(
    client,
    model: str,
    system: str,
    messages: list,
    call_type: str = "general",
    temperature: float = 0.0,
    force_fallback: bool = False,
    fallback_response: str = "",
    use_cache: bool = True
) -> dict:
    """
    Wrap Anthropic client calls to track latency, tokens, cost, and handle caching/fallback.
    """
    cache_key = _generate_cache_key(model, system, messages)
    
    if use_cache and cache_key in _RESPONSE_CACHE and not force_fallback:
        cached = _RESPONSE_CACHE[cache_key]
        _TELEMETRY_LOG.append(TelemetryRecord(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0.0,
            estimated_cost=0.0,
            cache_hit=True,
            call_type=call_type
        ))
        return {"text": cached["text"], "is_fallback": False, "cache_hit": True}

    if force_fallback:
        # Simulate fallback mode
        time.sleep(0.1) # artificial tiny delay
        _TELEMETRY_LOG.append(TelemetryRecord(
            timestamp=datetime.now(),
            model="fallback-template",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=100.0,
            estimated_cost=0.0,
            cache_hit=False,
            call_type=call_type + "_fallback"
        ))
        return {"text": fallback_response, "is_fallback": True, "cache_hit": False}

    start_time = time.time()
    try:
        contents = [
            types.Content(role="user", parts=[types.Part(text=m["content"])])
            if m["role"] == "user" else
            types.Content(role="model", parts=[types.Part(text=m["content"])])
            for m in messages
        ]

        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=2048
            )
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract token usage
        prompt_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        completion_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        cost = _estimate_cost(model, prompt_tokens, completion_tokens)
        
        # Log telemetry
        _TELEMETRY_LOG.append(TelemetryRecord(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(latency_ms, 2),
            estimated_cost=cost,
            cache_hit=False,
            call_type=call_type
        ))
        
        result_text = response.text
        
        if use_cache:
            _RESPONSE_CACHE[cache_key] = {"text": result_text}
            
        return {"text": result_text, "is_fallback": False, "cache_hit": False}
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"LLM API Call failed: {e}")
        
        # Auto-trigger permanent fallback on API failure
        latency_ms = (time.time() - start_time) * 1000
        _TELEMETRY_LOG.append(TelemetryRecord(
            timestamp=datetime.now(),
            model="error-fallback",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=round(latency_ms, 2),
            estimated_cost=0.0,
            cache_hit=False,
            call_type=call_type + "_error"
        ))
        return {"text": fallback_response, "is_fallback": True, "cache_hit": False}
