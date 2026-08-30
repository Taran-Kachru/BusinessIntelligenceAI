"""
main.py — FastAPI Application Entrypoint

Wires together all deterministic analytical modules and LLM wrappers.
Satisfies Objective 8 (Full-stack architecture).
"""

from dotenv import load_dotenv
load_dotenv()  # must run before any os.getenv call

from contextlib import asynccontextmanager
from typing import List, Optional, Dict
import os
import json
import pandas as pd
from datetime import date
from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from .database import init_db, get_db, DEMO_TODAY
from .models import (
    UserContext, KPIMovement, InsightResponse, NarrativeResponse,
    ActionCard, FeedbackEntry, SessionTelemetry, AccessLogEntry,
    AskRequest, AskResponse
)
from .security import parse_user_context, get_access_log
from .detect import get_material_movements, detect_movements, compute_kpi_timeseries
from .reconcile import reconcile_for_period, build_evidence_items, get_freshness_penalty
from .drivers import analyze_drivers
from .abstain import evaluate_abstention
from .narrative import generate_narrative
from .actions import generate_actions
from .feedback import submit_feedback, get_expert_validation_queue
from .telemetry import get_session_telemetry
from .ask import parse_intent, answer_question

# Gemini client
gemini_api_key = os.getenv("GEMINI_API_KEY", "mock-key-for-fallback")
client = genai.Client(api_key=gemini_api_key)
fallback_mode = os.getenv("FALLBACK_MODE", "false").lower() == "true" or gemini_api_key == "mock-key-for-fallback"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DuckDB and load CSVs
    init_db("data")
    yield
    # No explicit teardown needed for in-memory DuckDB unless persistent

app = FastAPI(title="KPI Pulse API", lifespan=lifespan)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For prototype
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_user_context(x_user_id: Optional[str] = Header(None)) -> UserContext:
    """Dependency to extract UserContext from request headers."""
    return parse_user_context(x_user_id)


# --- Helper ---
def _prepare_insight_context(db_conn, kpi_name: str, region: str, period_start: str, period_end: str):
    """Recompute deterministic insight data for a specific movement."""
    # 1. Get the movement
    region_filter = [region] if region and region != "ALL" else None
    movements = detect_movements(db_conn, demo_today=DEMO_TODAY, regions=region_filter)
    
    movement = None
    for m in movements:
        if m["kpi_name"] == kpi_name and m["region"] == region and m["period_start"] == period_start and m["period_end"] == period_end:
            movement = m
            break
            
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
        
    # 2. Reconcile evidence
    regions_for_recon = [region] if region and region != "ALL" else None
    reconciled = reconcile_for_period(db_conn, period_start, period_end, regions_for_recon, demo_today=DEMO_TODAY)
    
    # 3. Build evidence items
    evidence = build_evidence_items(reconciled, kpi_name, movement)
    
    # 4. Analyze drivers
    drivers_analysis = analyze_drivers(db_conn, kpi_name, movement, demo_today=DEMO_TODAY)
    
    # 5. Abstention evaluation
    source_tables = [e["source_table"] for e in evidence if e["source_table"] != "computed"]
    freshness_penalty = get_freshness_penalty(reconciled["freshness"], source_tables)
    is_sparse = movement.get("is_sparse", False)
    
    confidence = evaluate_abstention(
        kpi_name=kpi_name,
        drivers=drivers_analysis["drivers"],
        total_explained_variance=drivers_analysis["total_explained_variance"],
        freshness_penalty=freshness_penalty,
        is_sparse_history=is_sparse
    )
    
    return {
        "movement": movement,
        "evidence": evidence,
        "freshness": reconciled["freshness"],
        "drivers_analysis": drivers_analysis,
        "confidence": confidence
    }


# --- Routes ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "fallback_mode": fallback_mode}

@app.get("/api/movements", response_model=List[KPIMovement])
def list_movements(
    db_conn=Depends(get_db), 
    user: UserContext = Depends(get_user_context)
):
    """Return ranked material KPI movements (Objective 1)."""
    regions = user.allowed_regions if "ALL" not in user.allowed_regions else None
    movements = get_material_movements(db_conn, demo_today=DEMO_TODAY, regions=regions)
    return movements

@app.get("/api/insight", response_model=InsightResponse)
def get_insight_details(
    kpi_name: str,
    region: str,
    period_start: str,
    period_end: str,
    db_conn=Depends(get_db),
    user: UserContext = Depends(get_user_context)
):
    """Return full deterministic drill-in for a movement (Objectives 2, 3, 5)."""
    ctx = _prepare_insight_context(db_conn, kpi_name, region, period_start, period_end)
    
    return InsightResponse(
        movement=ctx["movement"],
        evidence=ctx["evidence"],
        freshness=ctx["freshness"],
        drivers=ctx["drivers_analysis"],
        confidence=ctx["confidence"]
    )

@app.post("/api/insight/narrative", response_model=NarrativeResponse)
async def generate_insight_narrative(
    kpi_name: str,
    region: str,
    period_start: str,
    period_end: str,
    db_conn=Depends(get_db),
    user: UserContext = Depends(get_user_context)
):
    """Generate persona-specific narrative (Objective 4)."""
    ctx = _prepare_insight_context(db_conn, kpi_name, region, period_start, period_end)
    
    # If confidence is too low, we might skip LLM or provide a different prompt
    # but abstain.py handles the UI message. We still generate narrative for demo.
    
    narrative = await generate_narrative(
        llm_client=client,
        evidence=ctx["evidence"],
        drivers=ctx["drivers_analysis"]["drivers"],
        user_context=user,
        kpi_name=kpi_name,
        fallback_mode=fallback_mode
    )
    return narrative

@app.post("/api/insight/actions", response_model=List[ActionCard])
async def generate_insight_actions(
    kpi_name: str,
    region: str,
    period_start: str,
    period_end: str,
    db_conn=Depends(get_db),
    user: UserContext = Depends(get_user_context)
):
    """Generate recommended actions (Objective 6)."""
    ctx = _prepare_insight_context(db_conn, kpi_name, region, period_start, period_end)
    
    actions = await generate_actions(
        llm_client=client,
        evidence=ctx["evidence"],
        drivers=ctx["drivers_analysis"]["drivers"],
        user_context=user,
        kpi_name=kpi_name,
        fallback_mode=fallback_mode
    )
    return actions

@app.post("/api/ask", response_model=AskResponse)
async def ask_question_api(
    request: AskRequest,
    db_conn=Depends(get_db),
    user: UserContext = Depends(get_user_context)
):
    """Tier 2: Ask Box feature."""
    # 1. Parse intent
    intent = await parse_intent(client, request.question, fallback_mode)
    kpi = intent.get("kpi", "Revenue")
    region = intent.get("region", "ALL")
    
    if "ALL" not in user.allowed_regions and region not in user.allowed_regions:
        region = user.allowed_regions[0] # Enforce RLS on Ask box
        
    # Standard period for demo
    period_start = "2026-08-11"
    period_end = "2026-08-18"
    
    try:
        ctx = _prepare_insight_context(db_conn, kpi, region, period_start, period_end)
    except:
        # Fallback if no specific movement matches exactly
        regions_for_recon = [region] if region != "ALL" else None
        reconciled = reconcile_for_period(db_conn, period_start, period_end, regions_for_recon, demo_today=DEMO_TODAY)
        ctx = {
            "evidence": build_evidence_items(reconciled, kpi, {}),
            "drivers_analysis": {"drivers": []}
        }
        
    response = await answer_question(
        llm_client=client,
        question=request.question,
        evidence=ctx["evidence"],
        drivers=ctx["drivers_analysis"]["drivers"],
        fallback_mode=fallback_mode
    )
    return response

@app.post("/api/feedback")
def submit_user_feedback(entry: FeedbackEntry, db_conn=Depends(get_db)):
    """Submit user feedback (Objective 7)."""
    success = submit_feedback(db_conn, entry)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save feedback")
    return {"status": "success"}

@app.get("/api/feedback/queue")
def expert_queue(db_conn=Depends(get_db)):
    """Get expert validation queue (Objective 7)."""
    return get_expert_validation_queue(db_conn)

@app.get("/api/telemetry/session", response_model=SessionTelemetry)
def telemetry_session():
    """Get live session telemetry (Objective 8)."""
    return get_session_telemetry()

@app.get("/api/security/access-log", response_model=List[AccessLogEntry])
def access_log(db_conn=Depends(get_db)):
    """Get access audit log (Objective 8)."""
    return get_access_log(db_conn)

@app.get("/api/kpi/history")
def get_kpi_history(
    kpi_name: str,
    region: str = "ALL",
    days: int = 60,
    db_conn=Depends(get_db),
    user: UserContext = Depends(get_user_context)
):
    """Return deterministic KPI time-series for charting (Computed by: DuckDB SQL)."""
    if "ALL" not in user.allowed_regions and region not in user.allowed_regions and region != "ALL":
        region = user.allowed_regions[0]

    regions = None if region == "ALL" else [region]
    try:
        ts_df = compute_kpi_timeseries(db_conn, kpi_name, regions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if ts_df.empty:
        return {"series": [], "kpi_name": kpi_name, "region": region}

    if "region" in ts_df.columns:
        if region == "ALL":
            ts_df = ts_df.groupby("date")["value"].sum().reset_index()
        else:
            ts_df = ts_df[ts_df["region"] == region][["date", "value"]].copy()

    today = pd.Timestamp(DEMO_TODAY)
    cutoff = today - pd.Timedelta(days=days)
    ts_df = ts_df[ts_df["date"] >= cutoff].copy().sort_values("date").reset_index(drop=True)

    window = min(28, max(7, len(ts_df) // 2))
    ts_df["rolling_mean"] = ts_df["value"].rolling(window=window, min_periods=7).mean()

    period_start = today - pd.Timedelta(days=7)
    ts_df["in_current_period"] = (ts_df["date"] >= period_start) & (ts_df["date"] <= today)

    return {
        "kpi_name": kpi_name,
        "region": region,
        "period_start": period_start.date().isoformat(),
        "period_end": today.date().isoformat(),
        "series": [
            {
                "date": row["date"].strftime("%m/%d"),
                "value": round(float(row["value"]), 4) if pd.notna(row["value"]) else None,
                "rolling_mean": round(float(row["rolling_mean"]), 4) if pd.notna(row["rolling_mean"]) else None,
                "in_current_period": bool(row["in_current_period"])
            }
            for _, row in ts_df.iterrows()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
