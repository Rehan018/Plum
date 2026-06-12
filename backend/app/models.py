from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class AgentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class RuleStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class DocumentInput(BaseModel):
    file_id: str
    file_name: str | None = None
    actual_type: str
    quality: str | None = "GOOD"
    patient_name_on_doc: str | None = None
    content: dict[str, Any] | None = None


class ClaimInput(BaseModel):
    member_id: str
    policy_id: str
    claim_category: str
    treatment_date: str
    claimed_amount: float
    documents: list[DocumentInput]
    ytd_claims_amount: float = 0
    hospital_name: str | None = None
    claims_history: list[dict[str, Any]] = Field(default_factory=list)
    simulate_component_failure: bool = False


class TraceCheck(BaseModel):
    rule_id: str | None = None
    source: str | None = None
    result: str
    details: str
    evidence: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    agent: str
    status: AgentStatus
    summary: str
    checks: list[TraceCheck] = Field(default_factory=list)
    confidence_delta: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RuleResult(BaseModel):
    rule_id: str
    status: RuleStatus
    reason: str
    evidence: list[str] = Field(default_factory=list)
    approved_amount: float | None = None
    rejected_amount: float = 0
    rejection_reason: str | None = None
    line_item_results: list[dict[str, Any]] = Field(default_factory=list)
    confidence_delta: float = 0.0


class ExtractionResult(BaseModel):
    patient_names: list[str] = Field(default_factory=list)
    diagnosis: str | None = None
    treatment: str | None = None
    hospital_name: str | None = None
    doctor_name: str | None = None
    doctor_registration: str | None = None
    tests_ordered: list[str] = Field(default_factory=list)
    medicines: list[str] = Field(default_factory=list)
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    total: float | None = None
    normalized_tags: list[str] = Field(default_factory=list)


class PolicyEvaluation(BaseModel):
    rule_results: list[RuleResult] = Field(default_factory=list)
    approved_amount: float
    rejected_amount: float = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    line_item_results: list[dict[str, Any]] = Field(default_factory=list)


class FraudEvaluation(BaseModel):
    manual_review: bool = False
    signals: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence_delta: float = 0.0


class DecisionResponse(BaseModel):
    claim_id: str
    decision: DecisionType
    approved_amount: float
    confidence_score: float
    reason: str
    evidence: list[str] = Field(default_factory=list)
    next_action: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    agent_health: dict[str, AgentStatus] = Field(default_factory=dict)


class ClaimContext(BaseModel):
    claim_id: str
    claim: ClaimInput
    policy: dict[str, Any]
    member: dict[str, Any] | None = None
    extracted: ExtractionResult = Field(default_factory=ExtractionResult)
    policy_evaluation: PolicyEvaluation | None = None
    fraud_evaluation: FraudEvaluation | None = None
    decision: DecisionResponse | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    should_stop: bool = False

    def add_trace(self, event: TraceEvent) -> None:
        self.trace.append(event)

    def confidence(self) -> float:
        value = 1.0 + sum(event.confidence_delta for event in self.trace)
        return round(max(0.0, min(value, 1.0)), 2)

    def agent_health(self) -> dict[str, AgentStatus]:
        return {event.agent: event.status for event in self.trace}
