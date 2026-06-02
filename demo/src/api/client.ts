/**
 * PACT API client — DEMO (static) build.
 *
 * This is the GitHub Pages demo. There is no live backend; every GET is served
 * from a pre-captured JSON snapshot under `public/data/` (copied to the site
 * root at build time). Mutations are synthesized client-side so the demo
 * buttons still do something visible. The real app lives in `frontend/` and
 * talks to the FastAPI backend over `/api` — that code is unchanged.
 *
 * Set VITE_STATIC=false to point the demo at a live backend instead (uses the
 * Vite `/api` proxy, same as the real frontend).
 */

const STATIC = import.meta.env.VITE_STATIC !== 'false';
// Snapshots live next to index.html; BASE_URL is '/PACT/' in the GH Pages build.
const DATA = `${import.meta.env.BASE_URL}data`;

/** Map a live API path to its captured static snapshot file. */
function snapshotUrl(path: string): string | null {
  const p = path.split('?')[0];
  if (p === '/scenarios') return `${DATA}/scenarios.json`;
  if (p === '/runs') return `${DATA}/runs.json`;
  if (p === '/dashboard/overview') return `${DATA}/dashboard-overview.json`;
  if (p === '/dashboard/agents') return `${DATA}/dashboard-agents.json`;
  if (p === '/dashboard/blocked-actions') return `${DATA}/dashboard-blocked-actions.json`;
  let m = p.match(/^\/runs\/([^/]+)\/replay$/);
  if (m) return `${DATA}/runs/${m[1]}/replay.json`;
  m = p.match(/^\/runs\/([^/]+)\/ledger\/verify$/);
  if (m) return `${DATA}/runs/${m[1]}/ledger-verify.json`;
  m = p.match(/^\/runs\/([^/]+)$/);
  if (m) return `${DATA}/runs/${m[1]}/detail.json`;
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (STATIC) {
    const url = snapshotUrl(path);
    if (!url) throw new Error(`No static snapshot for ${path} (demo build)`);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Snapshot ${res.status}: ${path}`);
    return res.json() as Promise<T>;
  }
  const res = await fetch(`/api${path}`, {
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
  influenced_by_sources: { label: string; source_step: number; source_tool: string; source_resource: string }[];
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
  result: Record<string, unknown> | null;
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
  intent_contract: IntentContractData | null;
}

export interface IntentContractData {
  intent_id: string;
  user_goal: string;
  allowed_actions: string[];
  forbidden_actions: string[];
  /** Per-resource-type allowlist (e.g. file_path, url, email_address → patterns). */
  resource_scope?: Record<string, string[]>;
  risk_budget: string;
  approval_required_for: string[];
  intent_hash: string;
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
  result: Record<string, unknown> | null;
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

export async function runScenario(name: string): Promise<ScenarioRunResponse> {
  if (STATIC) {
    // No backend to execute against — replay the captured run for this scenario.
    const runs = await getRuns();
    const match = runs.find((r) => r.scenario_name === name) ?? runs[0];
    if (!match) throw new Error('No captured run available for this scenario');
    return {
      run_id: match.run_id,
      scenario_name: name,
      status: match.status,
      total_actions: match.total_actions,
      allowed_actions: match.allowed_actions,
      blocked_actions: match.blocked_actions,
      max_risk_score: match.max_risk_score,
    };
  }
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

export interface BlockedActionData {
  run_id: string;
  step_id: number;
  agent_id: string;
  tool: string;
  risk_score: number;
  severity: string;
  reasons: string[];
  timestamp: string | null;
}

export function getBlockedActions(): Promise<BlockedActionData[]> {
  return request<BlockedActionData[]>('/dashboard/blocked-actions');
}

export interface TamperResult {
  run_id: string;
  tampered_field: string;
  ledger_valid_after_tamper: boolean;
  issues: string[];
}

export async function tamperLedger(runId: string): Promise<TamperResult> {
  if (STATIC) {
    // Demonstrate detection without mutating anything: tampering any action's
    // args breaks the hash chain, so verification would fail.
    return {
      run_id: runId,
      tampered_field: 'action[0].args_digest',
      ledger_valid_after_tamper: false,
      issues: [
        'Hash chain broken at step 1: stored action_hash does not match recomputed hash',
        'Tampered field detected: args_digest no longer matches signed envelope',
      ],
    };
  }
  return request<TamperResult>(`/runs/${runId}/tamper`, { method: 'POST' });
}
