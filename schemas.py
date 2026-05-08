from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class KPIBreach(BaseModel):
    metric: str
    current_value: float
    baseline_value: float
    severity: Literal["Critical", "Warning", "Info"]


class TriageOutput(BaseModel):
    problem_summary: str
    incident_timestamp: datetime
    affected_entities: List[str]
    breached_kpis: List[KPIBreach]
    category: Literal["throughput", "defect", "supplier", "safety"]


class Hypothesis(BaseModel):
    rank: int = Field(ge=1)
    cause: str
    confidence: Literal["High", "Medium", "Low"]
    evidence: str
    standard_id: str


class ActionItem(BaseModel):
    bucket: Literal["Stabilize", "Investigate", "Prevent"]
    action: str
    rationale: str
    linked_hypothesis_rank: int = Field(ge=1)


class ProductionIssueReport(BaseModel):
    problem_summary: str
    incident_timestamp: datetime
    hypotheses: List[Hypothesis]
    actions: List[ActionItem]
    explanation: str


class Check(BaseModel):
    name: str
    result: Literal["PASS", "FAIL"]
    notes: str


class ConfidenceAdjustment(BaseModel):
    hypothesis_rank: int = Field(ge=1)
    original: Literal["High", "Medium", "Low"]
    adjusted: Literal["High", "Medium", "Low"]
    reason: str


class VerificationResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    checks: List[Check]
    confidence_adjustments: List[ConfidenceAdjustment] = []
    overall_notes: str = ""
