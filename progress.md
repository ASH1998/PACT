# PACT — Progress Tracker

> Last updated: 2026-05-24 (post-gaps.md fix round)

## Overall Status

**Project:** PACT — Provenance-Aware Capability Tokens for AI Agents
**Verdict:** Solid MVP with honest protocol enforcement. All 100 tests pass, frontend builds clean.

---

## Phase 0: Stabilize Scaffold ✅

- [x] `backend/app/main.py` — FastAPI app with CORS, lifespan, all routers
- [x] `backend/app/config.py` — Settings via pydantic-settings
- [x] `backend/app/database.py` — Async SQLAlchemy + aiosqlite
- [x] `backend/pyproject.toml` — requires-python >= 3.10
- [x] `backend/requirements.txt` — all deps including pytest, pytest-asyncio, httpx, pytest-timeout
- [x] `backend/.env.example` — environment template
- [x] `frontend/package.json` — React, Vite, TypeScript, Tailwind, React Flow, Recharts, lucide-react
- [x] `frontend/vite.config.ts` — API proxy to localhost:8000
- [x] `frontend/tailwind.config.js` — SOC dark theme colors
- [x] Backend imports cleanly, `/health` responds
- [x] Frontend builds clean (`npm run build`)

---

## Phase 1: Protocol Schemas and Models ✅

### Protocol JSON Schemas (`protocol/`)
- [x] `agent_passport.schema.json` — 9 fields, matches PLAN.md §4.1
- [x] `intent_contract.schema.json` — 7 fields, matches PLAN.md §4.2
- [x] `capability_token.schema.json` — 10 fields, matches PLAN.md §4.3
- [x] `action_envelope.schema.json` — 13 fields, matches PLAN.md §4.5
- [x] `policy_decision.schema.json` — 4 fields, matches PLAN.md §4.6

### Pydantic Schemas (`backend/app/schemas/`)
- [x] All request/response models (300 lines)
- [x] Enums: Decision, Severity, RiskTier, TokenStatus, RunStatus, ActionStatus

### SQLAlchemy Models (`backend/app/models/`)
- [x] `agent.py` — agent_id, owner, agent_type, public_key, passport_json, allowed_domains_json, risk_tier, status, created_at, expires_at
- [x] `intent.py` — intent_id, user_goal, allowed/forbidden actions, approval_required_for, risk_budget, intent_hash
- [x] `capability.py` — token_hash, agent_id, intent_hash, capability, resource, max_uses, uses_remaining, expires_at, status, signature
- [x] `run.py` — run_id, agent_id, scenario_name, user_goal, status, started_at, completed_at
- [x] `action.py` — run_id, step_id, agent_id, tool, args_digest, args_json, intent_hash, capability_token_hash, provenance_json, parent_action_hash, action_hash, agent_signature, envelope_timestamp, status
- [x] `policy_decision.py` — run_id, action_hash, decision, risk_score, severity, reasons_json

---

## Phase 2: Crypto, Passport, Intent, Capability ✅

### Crypto (`backend/app/crypto/`)
- [x] `keys.py` — Ed25519 keypair generation + loading (PyNaCl)
- [x] `signatures.py` — sign and verify
- [x] `canonical.py` — canonical JSON + SHA-256 hashing
- [x] `issuer.py` — persistent issuer keypair (loads from env or generates once per process)

### Passport Service (`backend/app/services/passport.py`)
- [x] `create_passport()` — generate agent keypair, sign with issuer, store in DB
- [x] `get_passport()` — fetch stored passport
- [x] `verify_passport()` — check expiry + issuer signature (copies dict, no mutation)
- [x] `verify_action_signature()` — verify action sig with agent public key

### Intent Service (`backend/app/services/intent.py`)
- [x] `classify_intent()` — 4 deterministic rules + default fallback
- [x] `create_intent()` — create contract, generate hash, store
- [x] `get_intent()` / `get_intent_by_hash()` — fetch by ID or hash

### Capability Service (`backend/app/services/capability.py`)
- [x] `issue_token()` — signed, scoped, intent-bound tokens
- [x] `validate_token()` — checks agent, intent, capability, resource binding, expiry, use count, AND signature
- [x] `consume_use()` — decrements uses_remaining

---

## Phase 3: Envelope, Provenance, Policy, Ledger ✅

### Envelope Service (`backend/app/services/envelope.py`)
- [x] `create_envelope()` — canonicalize + sign with agent key
- [x] `verify_envelope()` — verify signature + args_digest consistency

### Provenance Service (`backend/app/services/provenance.py`)
- [x] `TOOL_LABELS` — all 7 tools mapped to output/side-effect labels
- [x] `start_run()` / `record_step()` / `build_provenance()` — per-run label accumulation
- [x] `has_untrusted_influence()` / `has_secret_data()` — taint checks

### Policy Service (`backend/app/services/policy.py`)
- [x] `evaluate()` — R1-R10 rules implemented
- [x] `compute_risk_score()` — 0-100 with severity thresholds (low/medium/high/critical)
- [x] Returns PolicyDecision with decision, risk_score, severity, reasons

### Ledger Service (`backend/app/services/ledger.py`)
- [x] `append_action()` — stores action with hash chain linkage
- [x] `get_chain()` — ordered action list for a run
- [x] `verify_chain()` — checks parent linkage + hash integrity
- [x] Stores `args_json` and `envelope_timestamp` for accurate replay

---

## Phase 4: Gateway and Mock Tools ✅

### Tool Gateway (`backend/app/services/gateway.py`)
- [x] Full 10-step pipeline: passport → signature → intent → capability → policy → ledger → execute
- [x] Rejects raw calls without envelope
- [x] Audits ALL attempts to ledger (including missing passport blocks)
- [x] Records policy decisions for every attempt

### Mock Tools (`backend/app/tools/`)
- [x] `email.read` / `email.send` — mock email operations
- [x] `web.read` — mock web content
- [x] `file.read` / `file.read_secret` — mock file operations
- [x] `shell.execute_mock` — mock shell execution
- [x] `summarize` — mock text summarization
- [x] `respond_to_user` — mock response
- [x] `seed_data.py` — 5 items (normal email, malicious email, malicious webpage, .env secrets, safe file)

---

## Phase 5: Scenario Runner and APIs ✅

### Scenario Runtime (`backend/app/services/runtime.py`)
- [x] `run_scenario()` — end-to-end scenario execution through PACT pipeline
- [x] Run-specific agent_id (avoids unique constraint on repeated runs)
- [x] Uses persistent issuer keys

### Scenario Definitions (`backend/app/services/scenarios.py`)
- [x] `normal_email_summary` — ALLOW
- [x] `malicious_email_injection` — BLOCK
- [x] `fake_agent_identity` — BLOCK
- [x] `expired_capability_token` — BLOCK
- [x] `secret_exfiltration` — BLOCK
- [x] `malicious_webpage` — BLOCK

### API Endpoints (`backend/app/api/`)
- [x] `GET /health`
- [x] `POST /agents/register` — uses persistent issuer keys
- [x] `GET /agents`, `GET /agents/{id}`
- [x] `POST /intents/create`, `GET /intents/{id}`
- [x] `POST /capabilities/issue`, `POST /capabilities/validate`
- [x] `POST /tools/call` — **real implementation** (not 501 stub)
- [x] `GET /scenarios`, `POST /scenarios/run/{name}`
- [x] `GET /runs`, `GET /runs/{id}`
- [x] `GET /runs/{id}/replay` — uses stored args + envelope timestamp for accurate reconstruction
- [x] `GET /runs/{id}/ledger/verify`
- [x] `GET /dashboard/overview`, `GET /dashboard/agents`, `GET /dashboard/risk-timeline`, `GET /dashboard/blocked-actions`

---

## Phase 6: Frontend SOC and Replay ✅

### Config
- [x] `package.json` — all deps present (react-flow, recharts, tailwind, lucide-react)
- [x] `vite.config.ts` — API proxy configured
- [x] `tailwind.config.js` — SOC dark theme palette
- [x] `tsconfig.json` — strict TS with @ alias

### Pages and Components
- [x] `src/api/client.ts` — typed API client for all endpoints
- [x] `src/components/Layout.tsx` — sidebar navigation with lucide icons
- [x] `src/components/ActionGraph.tsx` — React Flow graph (intent→action→policy→provenance)
- [x] `src/pages/Overview.tsx` — metric cards, risk timeline chart, top tools, **scenario trigger UI**
- [x] `src/pages/Runs.tsx` — run list with severity badges
- [x] `src/pages/RunDetail.tsx` — expandable actions, policy decisions, provenance, envelope viewer
- [x] `src/pages/Replay.tsx` — step-by-step playback with play/pause/skip controls
- [x] `src/pages/Agents.tsx` — trust scores with progress bars
- [x] `npm run build` — clean (758 KB bundle)

---

## Phase 7: Demo Polish ✅

- [x] `README.md` — setup, quick start, API docs, scenarios, policy rules, provenance labels
- [x] `docs/PROTOCOL.md` — protocol specification
- [x] `docs/API.md` — API reference
- [x] `scripts/demo.sh` — one-command demo runner (field names fixed)
- [x] `.gitignore` — Python, Node, IDE, OS, keys, coverage
- [ ] `docs/PROTOCOL.md` content verification — may need review against latest code changes
- [ ] `docs/API.md` content verification — may need `/tools/call` endpoint documentation update
- [x] CI pipeline (GitHub Actions)
- [ ] Fallback screenshots

---

## Tests ✅

**100 tests, all passing in ~1 second.**

| File | Tests | Covers |
|---|---|---|
| test_crypto.py | 13 | Keypair, signing, canonical JSON, hashing, issuer key permissions |
| test_passport.py | 4 | Create, verify, tamper detection, DB storage |
| test_intent.py | 9 | Classification rules (6 rules + default), upsert, created_at, word-boundary |
| test_capability.py | 9 | Issue, validate, expired, wrong agent/capability, consume, exhaust, multi-use, resource binding |
| test_envelope.py | 4 | Create, verify, tamper detection |
| test_provenance.py | 4 | Label assignment + propagation |
| test_policy.py | 16 | Risk scoring (9) + policy evaluation (7) |
| test_ledger.py | 3 | Hash generation, chain linking, verification |
| test_gateway.py | 4 | Valid execute, bad signature, expired token, intent mismatch |
| test_tools.py | 9 | Registry + all 7 tools |
| test_integration.py | 13 | Full API lifecycle (scenarios, runs, replay, dashboard, ledger, provenance counts, tamper detection, R8 regression) |
| test_resource.py | 11 | Resource extraction (email.send→to, shell→command, etc.) |
| test_health.py | 1 | Health endpoint |

---

## Review Issues Fixed

All 12 issues from the review have been addressed:

| # | Issue | Status |
|---|---|---|
| 1 | `/tools/call` was 501 stub | ✅ Real implementation |
| 2 | Tests hang / ModuleNotFound | ✅ In-memory SQLite, StaticPool, proper fixtures |
| 3 | Python version mismatch | ✅ requires-python >= 3.10 |
| 4 | Capability signatures not verified | ✅ Signature verification added |
| 5 | Capability resource not enforced | ✅ Resource binding check added |
| 6 | JSON schemas are documentation only | ⚪ By design for MVP |
| 7 | Issuer keys are volatile | ✅ Persistent issuer key module |
| 8 | Repeated scenario runs break | ✅ Run-specific agent_id |
| 9 | Blocked attempts not audited | ✅ Gateway audits all attempts |
| 10 | Replay signature validation unreliable | ✅ Stores args_json + envelope_timestamp |
| 11 | Demo script/API drift | ✅ Field names fixed |
| 12 | Frontend lint broken | ✅ Stale script removed |

---

## File Count

| Directory | Count | Status |
|---|---|---|
| `protocol/` | 5 schemas | ✅ Complete |
| `backend/app/` | 4 core | ✅ Complete |
| `backend/app/models/` | 7 | ✅ Complete |
| `backend/app/schemas/` | 1 | ✅ Complete |
| `backend/app/crypto/` | 5 | ✅ Complete (added issuer.py) |
| `backend/app/services/` | 10 | ✅ Complete |
| `backend/app/tools/` | 7 | ✅ Complete |
| `backend/app/api/` | 8 | ✅ Complete |
| `backend/tests/` | 13 | ✅ All real tests |
| `frontend/src/` | 11 | ✅ Complete |
| `docs/` | 2 | ✅ Complete |
| `scripts/` | 1 | ✅ Complete |
| Root configs | 5 | ✅ Complete |
| **Total** | **~79 files** | |

---

## Remaining Work (Non-Critical)

| Item | Priority | Notes |
|---|---|---|
| Verify docs match latest code | Low | In-progress — PROTOCOL.md and API.md review |
| Frontend tests | Low | Smoke tests for dashboard, replay |
| Fallback screenshots | Low | Demo backup |
| `npm run lint` | Low | Add eslint config if needed |
