from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, Literal, Dict, List

class UserContext(BaseModel):
    user_id: str
    role: Literal["ceo", "regional_manager"]
    name: str
    allowed_regions: List[str]
    can_view_pii: bool

class KPIMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kpi_name: str
    region: str = "ALL"
    period_start: date
    period_end: date
    current_value: float
    previous_value: Optional[float] = None
    absolute_change: Optional[float] = None
    pct_change: Optional[float] = None
    z_score: Optional[float] = None
    dollar_impact: Optional[float] = None
    composite_score: float
    detection_method: str
    is_material: bool
    is_sparse: bool = False

class FreshnessInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    table_name: str
    last_refresh: Optional[date] = None
    native_grain: str
    days_stale: Optional[int] = None
    freshness_status: Literal["FRESH", "AGING", "STALE", "UNKNOWN", "ERROR"]

class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    evidence_id: str
    source_table: str
    metric: str
    value: float
    comparison_value: Optional[float] = None
    method: str
    freshness: Optional[FreshnessInfo] = None
    note: Optional[str] = None

class DriverBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")
    driver_name: str
    effect_value: float
    effect_pct: float
    direction: Literal["+", "-"]
    method: str
    confidence: str
    quantified: bool
    source: Optional[str] = None
    note: Optional[str] = None

class PVMDecomposition(BaseModel):
    price_effect: float
    volume_effect: float
    mix_effect: float
    total_explained: float
    residual: float

class DriverAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kpi_name: str
    period: str
    pvm: Optional[PVMDecomposition] = None
    drivers: List[DriverBreakdown]
    qualitative_drivers: List[DriverBreakdown]
    total_explained_variance: float
    method_used: str
    method_fallback: bool = False
    fallback_reason: Optional[str] = None

class Citation(BaseModel):
    citation_id: str
    evidence_id: str
    text_span: str

class NarrativeResponse(BaseModel):
    persona: str
    text: str
    citations: List[Citation]
    evidence_ids: List[str]
    model_used: str
    is_fallback: bool = False

class ActionCard(BaseModel):
    driver: str
    controllable_lever: str
    action: str
    expected_impact: str
    owner: str
    confidence: str
    monitoring_plan: str
    exceeds_authority: bool = False

class ConfidenceResult(BaseModel):
    score: float
    should_abstain: bool
    abstention_reason: Optional[str] = None
    clarifying_question: Optional[str] = None
    factors: Dict[str, float]

class FeedbackEntry(BaseModel):
    insight_id: str
    feedback_type: Literal["thumbs_up", "thumbs_down", "correction"]
    rating: Optional[int] = None
    correction_text: Optional[str] = None
    target: Literal["insight", "driver", "action"]
    target_id: Optional[str] = None
    timestamp: Optional[datetime] = None

class TelemetryRecord(BaseModel):
    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    estimated_cost: float
    cache_hit: bool
    call_type: str

class SessionTelemetry(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float
    total_latency_ms: float
    cache_hit_rate: float
    calls: List[TelemetryRecord]

class AccessLogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timestamp: datetime
    user_id: str
    resource: str
    action: str
    allowed: bool
    details: Optional[str] = None

class InsightResponse(BaseModel):
    movement: KPIMovement
    evidence: List[EvidenceItem]
    freshness: List[FreshnessInfo]
    drivers: DriverAnalysis
    confidence: ConfidenceResult
    narrative: Optional[NarrativeResponse] = None
    actions: Optional[List[ActionCard]] = None

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    evidence: List[EvidenceItem]
    model_used: str
