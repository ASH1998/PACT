# PACT Production Readiness

This document captures the current production-readiness assessment based on the
backend, Go TUI, and static demo snapshots under `demo/public/data`.

## Current State

The current system is a strong demo/MVP for PACT's core claim: model-generated
tool calls should not execute directly. The Go TUI routes each tool call through
the PACT gateway by:

1. Registering an agent passport and tool metadata.
2. Creating an intent contract from the active operator grant.
3. Deriving the requested resource from tool arguments.
4. Issuing a capability token for the action.
5. Building and signing an Action Envelope locally.
6. Submitting the envelope to the gateway for an authoritative decision.
7. Executing the local tool only after `ALLOW`.
8. Attaching the result to the recorded action for dashboard/replay.

The captured static demo currently contains 20 runs and 30 recorded actions:

| Decision | Count |
|---|---:|
| `ALLOW` | 15 |
| `BLOCK` | 13 |
| `REQUIRE_APPROVAL` | 2 |

The snapshots show the important behaviors:

- Out-of-scope email recipients and file paths are blocked.
- Tools outside the intent contract are blocked.
- Fake/unregistered agent identity is blocked.
- Shell execution can require human approval.
- Every captured run has a valid hash-chain ledger check.

## Production Blockers

### 1. API Authentication and Tenant Isolation

The v1 API is currently open enough for a caller to register an agent, create
intents, issue capabilities, and submit gateway requests. Production needs:

- OIDC/JWT, mTLS, or workload identity for every API caller.
- Tenant ID on agents, intents, capabilities, runs, actions, approvals, and
  policies.
- RBAC for operator, agent, approver, auditor, and admin roles.
- Request-level authorization checks before every control-plane mutation.

### 2. Authority Must Not Be Agent-Controlled

The TUI currently issues a capability token for each tool call before submitting
the envelope. That is acceptable for a demo, but in production the agent must
not mint or widen its own authority.

Production capability issuance should be controlled by an authority service that
validates:

- The authenticated agent identity.
- The tenant and operator grant.
- The intent contract.
- The requested tool.
- The requested resource scope.
- User consent or delegated authorization where applicable.

The agent should only be a signed requester. Grants, policies, approvals, and
capability issuance should live outside the agent's control.

### 3. Private Key Lifecycle

The registration flow currently returns an `agent_private_key`. For production:

- Generate agent keys client-side, in KMS/HSM, or through workload identity.
- Register public keys/passport requests, not raw private keys.
- Add key IDs, rotation, revocation, expiry, and disabled states.
- Record key lifecycle events in the audit log.

### 4. Approval Must Be Server-Authorized

The gateway currently supports a client-supplied `skip_approval` path for
approved resumes. Production needs approval records that are:

- Created by the gateway when policy returns `REQUIRE_APPROVAL`.
- Approved or denied by an authenticated approver with sufficient RBAC.
- Bound to the action hash, run ID, tenant, policy version, and requested args.
- Expiring and one-time use.
- Recorded with approver identity, timestamp, reason, and decision.

Clients should resume with an approval token or approval ID, not a boolean.

### 5. Replay Signature Verification

The demo ledgers verify as hash-chain valid, but most replay steps currently show
`signature_valid: false` in the static snapshots. That may be a replay verifier
or canonicalization issue, but production audit cannot leave this ambiguous.

Production verification should report all of the following separately:

- Hash-chain validity.
- Envelope signature validity.
- Passport validity at action time.
- Capability validity at action time.
- Intent hash validity.
- Resource-scope validity.
- Policy version and decision reproducibility.
- Key ID and key status at action time.

### 6. Durable Provenance

Current provenance is process-local state. That does not survive restarts and
does not work reliably across multiple workers or horizontally scaled services.

Production provenance should be stored durably and should track:

- Source object IDs and content digests.
- Tool output labels.
- Data dependencies between actions.
- Object-level or field-level taint, not only run-level labels.
- Redacted source references suitable for audit and replay.

The gateway should distinguish pre-action input provenance from post-action
output provenance. This avoids over-tainting and makes replay explanations more
accurate.

### 7. Append-Only Audit Evidence

The hash-chain ledger is a good base, but database rows alone are not enough for
production-grade tamper evidence.

Add:

- Postgres-backed ledger tables with migrations.
- Append-only write discipline.
- Periodic Merkle roots over action records.
- External anchoring or WORM/object-storage snapshots for audit evidence.
- Canonical evidence payloads for policy decisions and signed envelopes.

### 8. Sensitive Result Storage

The demo stores args and tool results directly for replay. Production should not
store full sensitive data by default.

Use:

- Redacted previews in the primary action table.
- Content hashes for evidence.
- Encrypted result blobs with strict access control when full evidence is needed.
- Retention policies per tenant and data class.
- Secret scanning before persistence.

## Recommended Roadmap

### P0: Required Before Real Users

- Add API auth, RBAC, and tenant scoping.
- Replace open agent registration with authority-controlled registration.
- Replace open capability issuance with grant-validated issuance.
- Replace `skip_approval` with server-side approval records and resume tokens.
- Make resource scope mandatory for sensitive tools and external sinks.
- Fix replay signature verification and expose verification status explicitly.
- Add production-safe redaction for args and results.

### P1: Production Hardening

- Move from SQLite to Postgres.
- Add Alembic migrations.
- Store provenance durably instead of in process memory.
- Add append-only audit anchoring.
- Add idempotency keys for action submission and result attachment.
- Add rate limits, request tracing, structured logs, and metrics.
- Add policy versions and policy-decision reproducibility tests.

### P2: Product Maturity

- Build SDKs and an MCP gateway so integrations do not hand-roll envelopes.
- Add real connector sandboxing for email, files, shell, browser, and web.
- Add a policy console and approval UI.
- Export audit events to SIEM systems.
- Adopt a formal policy engine such as OPA/Rego or Cedar.
- Add adversarial replay tests and multi-agent scenarios.

## Production Target Architecture

In production, the agent should be treated as an untrusted requester:

```text
User / Operator Grant
        |
        v
Authority Service ---- Policy Store ---- Approval Service
        |                    |                 |
        v                    v                 v
Capability Issuer ---> PACT Gateway ---> Append-Only Ledger
        ^                    |
        |                    v
Agent / TUI / SDK ---> Tool Sandbox / Connector Runtime
```

The gateway remains the trust boundary. Agents may propose actions, but only the
authority layer can issue capabilities, only the approval service can resume
approval-gated actions, and only the ledger/audit layer can produce evidence.

## Summary

PACT is currently in a strong demo-ready state. The system already demonstrates
signed envelopes, intent/capability checks, resource-scope enforcement,
provenance-aware policy decisions, approval gating, and replayable ledgers.

The largest production gap is control-plane trust: registration, capability
issuance, approvals, and policy authority must move out of the agent/client path
and behind authenticated, tenant-scoped, auditable services.
