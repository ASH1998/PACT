# PACT — Progress Tracker

> Last updated: 2026-05-24

## Overall Status

**Project:** PACT — Provenance-Aware Capability Tokens for AI Agents
**Phase:** Project scaffold complete, ready for Phase 0 verification and Phase 1 implementation

---

## What's Done

### Documentation
- [x] `PLAN.md` — comprehensive implementation plan (1083 lines, 18 sections)
- [x] `pact_project_plan.md` — original project plan (pre-existing)
- [x] `pact_week_wise_build_plan.md` — week-wise build plan (pre-existing)
- [x] `pact_pitch_deck.md` — pitch deck (pre-existing)

### Protocol Schemas (`protocol/`)
- [x] `agent_passport.schema.json`
- [x] `intent_contract.schema.json`
- [x] `capability_token.schema.json`
- [x] `action_envelope.schema.json`
- [x] `policy_decision.schema.json`

### Backend Scaffold (`backend/`)
- [x] `pyproject.toml` — project config with dependencies
- [x] `requirements.txt` — pip dependencies
- [x] `.env.example` — environment variable template
- [x] `app/__init__.py` — package init
- [x] `app/config.py` — settings via pydantic-settings
- [x] `app/database.py` — async SQLAlchemy engine + session
- [x] `app/main.py` — FastAPI app with CORS, lifespan, all routers wired

### Backend Models (`backend/app/models/`)
- [x] `__init__.py` — model exports
- [x] `agent.py` — Agent table (passport, public key, status)
- [x] `intent.py` — Intent table (user goal, allowed/forbidden actions)
- [x] `capability.py` — CapabilityToken table (token hash, uses, expiry)
- [x] `run.py` — Run table (scenario, status, timestamps)
- [x] `action.py` — Action table (envelope data, hash chain, signature)
- [x] `policy_decision.py` — PolicyDecision table (decision, risk, reasons)

### Backend Schemas (`backend/app/schemas/`)
- [x] `__init__.py` — all Pydantic request/response models:
  - Enums: RiskTier, Decision, Severity, TokenStatus, RunStatus, ActionStatus
  - Agent: AgentPassport, AgentRegisterRequest, AgentResponse
  - Intent: IntentContract, IntentCreateRequest, IntentResponse
  - Capability: CapabilityToken, CapabilityIssueRequest, CapabilityValidateRequest, CapabilityResponse
  - Provenance: ProvenanceContext
  - Envelope: ActionEnvelope, ToolCallRequest, ToolCallResponse
  - Policy: PolicyDecision
  - Run: RunResponse, ActionResponse, ReplayStep, ReplayResponse
  - Scenario: ScenarioInfo, ScenarioRunResponse
  - Dashboard: DashboardOverview, AgentTrustScore

### Backend Crypto (`backend/app/crypto/`)
- [x] `__init__.py` — exports
- [x] `keys.py` — Ed25519 keypair generation + loading (PyNaCl)
- [x] `signatures.py` — sign and verify functions
- [x] `canonical.py` — canonical JSON serialization + SHA-256 hashing

### Backend Services (`backend/app/services/`)
- [x] `__init__.py` — service exports
- [x] `passport.py` — PassportService (create, sign, verify, fetch)
- [x] `intent.py` — IntentService (classify, create, fetch by ID/hash)
- [x] `capability.py` — CapabilityService (issue, validate, consume use)
- [x] `envelope.py` — EnvelopeService (create signed envelope, verify)
- [x] `provenance.py` — ProvenanceService (label tracking, taint propagation)
- [x] `policy.py` — PolicyService (10 rules, risk scoring, severity)
- [x] `ledger.py` — LedgerService (hash-chain append, chain verification)
- [x] `gateway.py` — GatewayService (11-step trust boundary: passport → signature → intent → capability → policy → ledger → execute)
- [x] `scenarios.py` — 6 demo scenario definitions (normal, injection, fake agent, expired token, secret exfil, malicious web)
- [x] `runtime.py` — RuntimeService (end-to-end scenario execution through PACT pipeline)

### Backend Mock Tools (`backend/app/tools/`)
- [x] `__init__.py` — tool registry + get_mock_tool()
- [x] `email.py` — email_read, email_send
- [x] `web.py` — web_read
- [x] `file.py` — file_read, file_read_secret
- [x] `shell.py` — shell_execute_mock
- [x] `base.py` — (exists, stub)
- [x] `seed_data.py` — 5 seed data items (normal email, malicious email, malicious webpage, .env secrets, safe file)

### Backend API Routes (`backend/app/api/`)
- [x] `__init__.py`
- [x] `agents.py` — POST /agents/register, GET /agents, GET /agents/{id}
- [x] `intents.py` — POST /intents/create, GET /intents/{id}
- [x] `capabilities.py` — POST /capabilities/issue, POST /capabilities/validate
- [x] `tools.py` — POST /tools/call (stub, directs to scenarios)
- [x] `scenarios.py` — GET /scenarios, POST /scenarios/run/{name}
- [x] `runs.py` — GET /runs, GET /runs/{id}, GET /runs/{id}/replay, GET /runs/{id}/ledger/verify
- [x] `dashboard.py` — GET /dashboard/overview, GET /dashboard/agents, GET /dashboard/risk-timeline, GET /dashboard/blocked-actions
- [x] `schemas.py` — (exists)

### Backend Tests (`backend/tests/`)
- [x] `conftest.py` — test DB setup, async client fixture
- [x] `test_health.py` — health endpoint test
- [x] `test_crypto.py` — keypair, signing, canonical JSON, hashing tests
- [x] `test_intent.py` — intent classification tests
- [x] `test_policy.py` — risk scoring + policy evaluation tests (13 test cases)
- [x] `test_integration.py` — full API lifecycle tests (scenario run → run detail → replay → dashboard → ledger verify)
- [ ] `test_capability.py` — stub (needs implementation)
- [ ] `test_envelope.py` — stub (needs implementation)
- [ ] `test_passport.py` — stub (needs implementation)
- [ ] `test_ledger.py` — stub (needs implementation)
- [ ] `test_tools.py` — stub (needs implementation)
- [ ] `test_provenance.py` — stub (needs implementation)
- [ ] `test_gateway.py` — stub (needs implementation)

### Frontend Scaffold (`frontend/`)
- [x] `package.json` — React + Vite + TypeScript + Tailwind
- [x] `vite.config.ts` — Vite config with API proxy
- [x] `tailwind.config.js` — Tailwind CSS config
- [x] `postcss.config.js` — PostCSS config
- [x] `tsconfig.json` — TypeScript config
- [x] `tsconfig.node.json` — Node TypeScript config
- [x] `index.html` — HTML entry point
- [x] `src/main.tsx` — React entry point
- [x] `src/App.tsx` — App component with router
- [x] `src/index.css` — Tailwind base styles

---

## What's NOT Done Yet

### Phase 0: Stabilize Scaffold
- [ ] Install backend dependencies (`pip install -r requirements.txt`)
- [ ] Verify `python -c "from app.main import app"` works
- [ ] Verify `/health` endpoint responds
- [ ] Install frontend dependencies (`npm install`)
- [ ] Verify frontend dev server starts

### Phase 1: Protocol Schemas and Models
- [ ] Verify all models import correctly
- [ ] Verify SQLite tables create on startup

### Phase 2: Crypto, Passport, Intent, Capability
- [ ] Run unit tests for crypto
- [ ] Run unit tests for intent classification
- [ ] Run unit tests for capability service
- [ ] Run unit tests for passport service
- [ ] Fill in stub test files

### Phase 3: Envelope, Provenance, Policy, Ledger
- [ ] Run unit tests for envelope service
- [ ] Run unit tests for provenance service
- [ ] Run unit tests for policy engine
- [ ] Run unit tests for ledger service

### Phase 4: Gateway and Mock Tools
- [ ] Run gateway tests
- [ ] Verify raw calls are rejected
- [ ] Verify valid envelopes execute

### Phase 5: Scenario Runner and APIs
- [ ] Run all 6 scenarios via API
- [ ] Verify replay data is complete
- [ ] Run integration tests

### Phase 6: Frontend SOC and Replay
- [ ] Build dashboard layout + navigation
- [ ] Build Overview page (metrics, charts, blocked actions table)
- [ ] Build Runs list page
- [ ] Build Run Detail page (actions, decisions, envelope viewer)
- [ ] Build Action Graph (React Flow nodes + edges)
- [ ] Build Replay page (step-by-step playback with controls)
- [ ] Build Agents page (trust scores)

### Phase 7: Demo Polish
- [x] `README.md` — setup, quick start, API docs, scenarios, policy rules, provenance labels
- [x] `.gitignore` — Python, Node, IDE, OS, keys, coverage
- [ ] `docs/PROTOCOL.md` — full protocol spec
- [ ] `docs/API.md` — API reference
- [ ] Demo seed script (`scripts/demo.sh`)
- [ ] Final demo rehearsal

---

## File Count Summary

| Directory | Files | Status |
|---|---|---|
| `protocol/` | 5 schemas | Done |
| `backend/app/` | 6 core files | Done |
| `backend/app/models/` | 7 models | Done |
| `backend/app/schemas/` | 1 file (all Pydantic models) | Done |
| `backend/app/crypto/` | 4 files | Done |
| `backend/app/services/` | 10 files | Done |
| `backend/app/tools/` | 7 files | Done |
| `backend/app/api/` | 8 routers | Done |
| `backend/tests/` | 7 test files (6 real + 7 stubs) | Partial |
| `frontend/` | 10 scaffold files | Done (no pages yet) |
| **Total** | **~65 files** | |

---

## Plan Phase Mapping

| PLAN.md Phase | Status | Notes |
|---|---|---|
| Phase 0: Stabilize Scaffold | Files exist, not verified | Need to install deps and test imports |
| Phase 1: Schemas and Models | Files created | Need to verify table creation |
| Phase 2: Crypto/Passport/Intent/Capability | Files created | Need to run unit tests |
| Phase 3: Envelope/Provenance/Policy/Ledger | Files created | Need to run unit tests |
| Phase 4: Gateway and Mock Tools | Files created | Need to run gateway tests |
| Phase 5: Scenario Runner and APIs | Files created | Need to run integration tests |
| Phase 6: Frontend SOC and Replay | Scaffold only | Need to build pages |
| Phase 7: Demo Polish | Not started | README, docs, scripts |
