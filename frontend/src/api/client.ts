/**
 * PACT API client — all backend calls go through here.
 * Base URL is '' because Vite proxies /api → localhost:8000.
 */

const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ---------- types ---------- */

export interface ScenarioInfo {
  name: string;
  description: string;
  expected_outcome: string;
}

export interface ScenarioRunResponse {
  run_id: string;
  scenario_name: string;
  status: string;
  total_actions: number;
  allowed_actions: number;
  blocked_actions: number;
  max_risk_score: number;
}

export interface RunSummary {
  run_id: string;
  agent_id: string;
  scenario_name: string | null;
  user_goal: string | null;
  status: string;
  started_at: string;
  completed_at: string | null;
  total_actions: number;
  allowed_actions: number;
  blocked_actions: number;
  max_risk_score: number;
  ledger_valid: boolean | null;
}

export interface PolicyDecisionData {
  decision: string;
  risk_score: number;
  severity: string;
  reasons: string[];
}

export interface ProvenanceData {
  influenced_by: string[];
  uses_data: string[];
  side_effect: string | null;
}

export interface ActionData {
  step_id: number;
  agent_id: string;
  tool: string;
  args_digest: string;
  intent_hash: string;
  provenance: ProvenanceData;
  parent_action_hash: string | null;
  action_hash: string;
  status: string;
  created_at: string | null;
  policy_decision: PolicyDecisionData | null;
}

export interface RunDetail {
  run_id: string;
  agent_id: string;
  scenario_name: string | null;
  user_goal: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  actions: ActionData[];
}

export interface ReplayStepData {
  step_id: number;
  timestamp: string;
  agent_id: string;
  tool: string;
  args: Record<string, unknown>;
  provenance: ProvenanceData;
  envelope: Record<string, unknown>;
  policy_decision: PolicyDecisionData;
  action_hash: string;
  parent_action_hash: string | null;
  signature_valid: boolean;
  chain_valid: boolean;
}

export interface ReplayData {
  run_id: string;
  scenario_name: string | null;
  user_goal: string | null;
  steps: ReplayStepData[];
  ledger_valid: boolean;
}

export interface DashboardOverview {
  total_runs: number;
  total_actions: number;
  allowed_actions: number;
  blocked_actions: number;
  critical_events: number;
  top_attacked_tools: { tool: string; count: number }[];
  top_provenance_sources: { source: string; count: number }[];
  risk_timeline: {
    timestamp: string | null;
    risk_score: number;
    severity: string;
    decision: string;
  }[];
}

export interface AgentTrustScore {
  agent_id: string;
  owner: string;
  risk_tier: string;
  trust_score: number;
  total_runs: number;
  blocked_actions: number;
  status: string;
}

export interface LedgerVerification {
  run_id: string;
  valid: boolean;
  issues: string[];
}

/* ---------- API functions ---------- */

export function getScenarios(): Promise<ScenarioInfo[]> {
  return request<ScenarioInfo[]>('/scenarios');
}

export function runScenario(name: string): Promise<ScenarioRunResponse> {
  return request<ScenarioRunResponse>(`/scenarios/run/${name}`, { method: 'POST' });
}

export function getRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>('/runs');
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`);
}

export function getReplay(runId: string): Promise<ReplayData> {
  return request<ReplayData>(`/runs/${runId}/replay`);
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return request<DashboardOverview>('/dashboard/overview');
}

export function getDashboardAgents(): Promise<AgentTrustScore[]> {
  return request<AgentTrustScore[]>('/dashboard/agents');
}

export function verifyLedger(runId: string): Promise<LedgerVerification> {
  return request<LedgerVerification>(`/runs/${runId}/ledger/verify`);
}
