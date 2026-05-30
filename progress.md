# PACT — Progress

> Product status tracker. Last updated: 2026-05-30 · Version **v0.0.1**

PACT is a runtime security layer for AI agents: every tool call must pass a signed
gateway that checks identity, intent, least-privilege capability, data-flow
provenance, and policy before the tool runs — and records the decision on a
tamper-evident ledger. **257 tests passing, 2 skipped.** Frontend builds clean.

---

## What PACT enforces today

| Capability | State | Where |
|---|---|---|
| **Agent identity** — Ed25519 passports, issuer-signed, verified per call | ✅ | `services/passport.py`, `crypto/` |
| **Intent contracts** — actions locked to the user's goal; tamper-evident hash | ✅ | `services/intent.py`, `models/intent.py` |
| **Least-privilege authority** — operator **grants** cap tools + resource scope | ✅ | `core/grants.py` |
| **Resource scope** — email-domain / URL-host / path-glob allowlists, default-deny | ✅ | `tools/resource.py`, gateway R12 |
| **Capability tokens** — short-lived, scoped, intent-bound, signed, use-limited | ✅ | `services/capability.py` |
| **Provenance / taint** — server-rebuilt; blocks tainted→external-write flows | ✅ | `services/provenance.py` |
| **Policy engine** — rules R1–R12; configurable via YAML/DB; risk scoring | ✅ | `services/policy.py`, `configurable_policy.py`, `core/policy_config.py` |
| **Human approval** — REQUIRE_APPROVAL gate, approval records, resume flow | ✅ | `services/approval.py`, `approval_gateway.py`, `api/v1/approvals.py` |
| **Tamper-evident ledger** — hash-chained actions, `verify_chain` | ✅ | `services/ledger.py` |
| **Gateway** — single trust boundary; rejects raw calls; audits every attempt | ✅ | `services/gateway.py` |
| **Library runtime** — framework-free `PactRuntime` composition root | ✅ | `core/runtime.py`, `core/factory.py` |
| **Framework adapters** — LangChain / LangGraph enforcement wrappers | ✅ | `adapters/frameworks/` |
| **Interactive CLI** — real Claude/Gemini/Bedrock agent under PACT | ✅ | `pact_chat.py` |
| **SOC dashboard** — runs, action graph, replay, ledger verify, trust scores | ✅ | `frontend/src/` |
| **v1 API** — agents, intents, capabilities, actions, policies, approvals, runs | ✅ | `api/v1/` |

---

## What changed in v0.0.1 (least-privilege authority + data-flow hardening)

- **Operator grants** (`core/grants.py`): a deny-by-default authority ceiling on
  tools and per-resource-type scope. The agent can no longer authorize itself —
  the CLI derives its intent from the grant, not "all tools".
- **Resource-scope enforcement** (rule **R12**): the gateway checks the requested
  resource against the operator allowlist (email domains, URL hosts, file globs);
  out-of-scope → BLOCK. Scope is folded into the intent hash (tamper-evident).
- **Secret-read approval** (rule **R11**): reading a critical-sensitivity resource
  (e.g. `.env`) now requires human approval instead of silently allowing.
- **Removed security theater**: deleted the keyword "intent screen" — exfiltration
  is blocked structurally by taint + scope, not by matching strings like `.env`.
- **Data-flow tests**: `test_dataflow_control.py`, `test_least_privilege.py`,
  `test_resource_scope.py` lock in structural blocking with no keyword matching.
- **Additive SQLite migrations** (`database.py`): existing DBs upgrade in place
  (added `intents.resource_scope_json`) — no data loss, pending Alembic.

---

## Roadmap (next tracks)

Detailed plan in [`road_to_prod.md`](road_to_prod.md).

1. **Data-flow control v2** — move taint off process-global memory into the ledger;
   object/field-level taint instead of run-global (removes over-blocking).
2. **Identity & authz** — authority-issued identity (no self-registration), tenant
   scoping, RBAC for approvals, **API authentication** (the API is currently open).
3. **Policy engine** — adopt OPA/Rego or Cedar: versioned, testable, shadow mode.
4. **Productionize** — Postgres + Alembic, horizontal scale, observability, an SDK
   and MCP gateway so teams adopt PACT without hand-writing envelopes.

---

## Changelog

### v0.0.1 — 2026-05-30
**Least-privilege authority + structural data-flow enforcement.**
- Added operator **grants** (`core/grants.py`) — deny-by-default tool + resource ceiling; example `examples/grant.acme.yaml`.
- Added **resource scope** on intents + matcher (`tools/resource.py`) and policy rule **R12** (out-of-scope → BLOCK); scope is part of the tamper-evident intent hash.
- Added rule **R11** — secret/critical reads require human approval.
- CLI (`pact_chat.py`) now takes authority from a grant (`--grant`), not all-tools; header/`/tools` show the active ceiling.
- Removed the keyword-based intent screen (security theater) in favor of structural taint + scope enforcement.
- Added additive in-place SQLite migrations in `init_db()`.
- Tests: +`test_resource_scope.py`, +`test_least_privilege.py`, +`test_dataflow_control.py` → 257 passing / 2 skipped.

### v0.0.0 — initial protocol MVP
- Protocol primitives (passport, intent, capability, envelope, policy decision) with JSON schemas.
- Ed25519 crypto, gateway trust boundary, provenance taint, policy rules R1–R10, hash-chained ledger.
- Human approval flow, configurable policies (YAML/DB), framework adapters (LangChain/LangGraph).
- React SOC dashboard (overview, runs, action graph, replay, agents), reference attack scenarios, interactive CLI.
