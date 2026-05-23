from __future__ import annotations
"""Pydantic models for PACT API request/response schemas."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TokenStatus(str, Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PENDING_APPROVAL = "pending_approval"


# --- Agent Passport ---

class AgentPassport(BaseModel):
    agent_id: str
    owner: str
    agent_type: str
    public_key: str
    allowed_domains: list[str]
    risk_tier: RiskTier
    issued_at: datetime
    expires_at: datetime
    issuer_signature: str


class AgentRegisterRequest(BaseModel):
    agent_id: str
    owner: str
    agent_type: str
    allowed_domains: list[str]
    risk_tier: RiskTier = RiskTier.MEDIUM
    ttl_days: int = 30


class AgentResponse(BaseModel):
    agent_id: str
    owner: str
    agent_type: str
    allowed_domains: list[str]
    risk_tier: RiskTier
    status: str
    created_at: datetime
    expires_at: datetime


# --- Intent Contract ---

class IntentContract(BaseModel):
    intent_id: str
    user_goal: str
    allowed_actions: list[str]
    forbidden_actions: list[str]
    risk_budget: RiskTier
    approval_required_for: list[str]
    intent_hash: str


class IntentCreateRequest(BaseModel):
    user_goal: str


class IntentResponse(BaseModel):
    intent_id: str
    user_goal: str
    allowed_actions: list[str]
    forbidden_actions: list[str]
    risk_budget: RiskTier
    approval_required_for: list[str]
    intent_hash: str
    created_at: datetime


# --- Capability Token ---

class CapabilityToken(BaseModel):
    token_type: str = "PACT-CAP"
    token_hash: str
    agent_id: str
    intent_hash: str
    capability: str
    resource: str
    max_uses: int
    uses_remaining: int
    expires_at: datetime
    signature: str


class CapabilityIssueRequest(BaseModel):
    agent_id: str
    intent_hash: str
    capability: str
    resource: str = "default"
    max_uses: int = 5
    ttl_seconds: int = 300


class CapabilityValidateRequest(BaseModel):
    token_hash: str
    agent_id: str
    intent_hash: str
    capability: str


class CapabilityResponse(BaseModel):
    token_hash: str
    agent_id: str
    intent_hash: str
    capability: str
    resource: str
    max_uses: int
    uses_remaining: int
    expires_at: datetime
    status: TokenStatus


# --- Provenance ---

class ProvenanceContext(BaseModel):
    influenced_by: list[str] = Field(default_factory=list)
    uses_data: list[str] = Field(default_factory=list)
    side_effect: Optional[str] = None


# --- Action Envelope ---

class ActionEnvelope(BaseModel):
    protocol: str = "PACT/0.1"
    run_id: str
    step_id: int
    agent_id: str
    tool: str
    args: dict
    args_digest: str
    intent_hash: str
    capability_token_hash: str
    provenance: ProvenanceContext
    parent_action_hash: Optional[str] = None
    timestamp: datetime
    agent_signature: str


class ToolCallRequest(BaseModel):
    """Used by the scenario runner / runtime to submit a tool call through the gateway."""
    envelope: ActionEnvelope


class ToolCallResponse(BaseModel):
    decision: Decision
    risk_score: int
    severity: Severity
    reasons: list[str]
    tool_result: Optional[dict] = None
    action_hash: Optional[str] = None


# --- Policy Decision ---

class PolicyDecision(BaseModel):
    decision: Decision
    risk_score: int
    severity: Severity
    reasons: list[str]


# --- Runs ---

class RunResponse(BaseModel):
    run_id: str
    agent_id: str
    scenario_name: Optional[str] = None
    user_goal: Optional[str] = None
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_actions: int = 0
    allowed_actions: int = 0
    blocked_actions: int = 0
    max_risk_score: int = 0
    ledger_valid: bool = True


class ActionResponse(BaseModel):
    run_id: str
    step_id: int
    agent_id: str
    tool: str
    args_digest: str
    intent_hash: str
    provenance: ProvenanceContext
    parent_action_hash: Optional[str] = None
    action_hash: str
    agent_signature: str
    status: ActionStatus
    created_at: datetime
    policy_decision: Optional[PolicyDecision] = None


class ReplayStep(BaseModel):
    step_id: int
    timestamp: datetime
    agent_id: str
    tool: str
    args: dict
    provenance: ProvenanceContext
    envelope: ActionEnvelope
    policy_decision: PolicyDecision
    action_hash: str
    parent_action_hash: Optional[str] = None
    signature_valid: bool = True
    chain_valid: bool = True


class ReplayResponse(BaseModel):
    run_id: str
    scenario_name: Optional[str] = None
    user_goal: Optional[str] = None
    steps: list[ReplayStep]
    ledger_valid: bool = True


# --- Scenario ---

class ScenarioInfo(BaseModel):
    name: str
    description: str
    expected_outcome: str


class ScenarioRunResponse(BaseModel):
    run_id: str
    scenario_name: str
    status: RunStatus
    total_actions: int
    allowed_actions: int
    blocked_actions: int
    max_risk_score: int


# --- Dashboard ---

class DashboardOverview(BaseModel):
    total_runs: int
    total_actions: int
    allowed_actions: int
    blocked_actions: int
    critical_events: int
    top_attacked_tools: list[dict]
    top_provenance_sources: list[dict]
    risk_timeline: list[dict]


class AgentTrustScore(BaseModel):
    agent_id: str
    owner: str
    risk_tier: RiskTier
    trust_score: int
    total_runs: int
    blocked_actions: int
    status: str
