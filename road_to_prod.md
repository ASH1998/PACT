# PACT Road to Production and Open Source Maturity

This roadmap turns PACT from a strong security-protocol MVP into a credible
open-source project that developers can try, contributors can understand, and
security reviewers can evaluate honestly.

PACT should avoid claiming production readiness until the control plane,
authentication, tenant isolation, key lifecycle, durable provenance, and audit
storage gaps are closed. The near-term goal is stronger: make the project easy
to verify, easy to demo, and explicit about its current trust assumptions.

## Guiding Principles

- Keep the core claim sharp: tools should not trust raw agent output.
- Prefer verifiable enforcement over prompt filtering or blocklists.
- Treat agents as untrusted requesters, not authority holders.
- Make security assumptions and non-goals explicit.
- Optimize early open-source work for reproducibility and reviewer trust.
- Ship small, documented releases instead of broad unfinished surfaces.

## Phase 0: Open Source Foundation

Target: 1-2 weeks

Goal: remove credibility blockers before wider public attention.

Deliverables:

- Add `SECURITY.md` with supported versions, private vulnerability reporting,
  expected response times, and disclosure process.
- Add `docs/THREAT_MODEL.md` covering assets, trust boundaries, adversaries,
  assumptions, in-scope attacks, and explicit non-goals.
- Add an enforced-vs-assumed matrix so README, examples, and demos cannot imply
  that planned production controls already exist.
- Add `CONTRIBUTING.md` with local setup, test commands, coding conventions,
  PR expectations, and DCO/CLA stance.
- Add `.github/ISSUE_TEMPLATE/` and a PR template with a test checklist.
- Add `CODE_OF_CONDUCT.md`, `CODEOWNERS`, and a short maintainer/governance note.
- Consolidate duplicate CI workflows into one required workflow.
- Add CodeQL, Dependabot, and dependency/security audit checks.
- Publish a lightweight external-review checklist for the signing, verification,
  capability issuance, and replay paths.
- Mark demo-only or unauthenticated authority paths clearly. Any endpoint that
  lets a caller create agents, intents, capabilities, grants, or approvals
  without production auth must be documented as local/demo-only until the
  control plane is hardened.
- Decide what belongs in the root directory versus `docs/archive/`.

Exit criteria:

- A new contributor can understand how to report security issues, run tests,
  open a PR, and evaluate PACT's security claims without asking the maintainer.
- No README or status links point at missing files.
- CI covers backend, frontend, Go TUI, and protocol/schema checks.

## Phase 1: Demo Reliability and Adoption Path

Target: 2-4 weeks

Goal: make the first 10 minutes excellent.

Feature rollouts:

- `docker compose up` or equivalent one-command local stack for backend,
  dashboard, and seed data.
- Optional `INSECURE_DEMO=1` or equivalent guard for local-only flows that expose
  unauthenticated registration, capability issuance, or policy mutation.
- "Attack blocked in 60 seconds" quickstart with expected terminal and dashboard
  output.
- Runnable examples under `examples/`:
  - blocked secret exfiltration
  - out-of-scope email recipient
  - out-of-scope file path
  - shell action requiring approval
  - tampered envelope or replay verification failure
- Static demo refresh with clearly labeled sample data and reproducible snapshot
  generation.
- A live tamper demo that edits or reorders ledger evidence and shows
  verification failing.
- Demo examples must show both in-scope resources allowed and out-of-scope
  resources blocked, so scope enforcement is visibly allowlist-based rather
  than string/blocklist-based.
- Smoke tests that run the quickstart path in CI or nightly.

Exit criteria:

- A reviewer can clone the repo, run one command, trigger one allowed action and
  one blocked action, and inspect the ledger/replay without reading source code.
- Examples are copy-pasteable and include expected decisions and reasons.
- Demo docs call out current bypasses honestly, including that unauthenticated
  raw API/control-plane surfaces are not a production boundary yet.

## Phase 2: Protocol and SDK Stabilization

Target: 1-2 months

Goal: make integrations stop hand-rolling envelopes.

Feature rollouts:

- Publish a versioned protocol package or SDK for canonical JSON, digests,
  envelope signing, signature verification, and capability validation helpers.
- Pick one reference SDK first and make it excellent before promising broad
  multi-language parity.
- Write the canonicalization and signing spec before freezing golden vectors:
  key ordering, absent vs. null, numeric representation, unicode handling,
  timestamp format, mutable fields, and signature coverage.
- Define protocol versioning independently from app release versioning.
- Add schema compatibility tests and golden vectors for Python and Go.
- Reserve future production fields such as `tenant_id`, `key_id`,
  `policy_version`, approval binding, and verifier version before declaring a
  stable wire format.
- Add a minimal MCP gateway path so MCP tools can be protected by PACT without
  custom integration code.
- Stabilize the `/v1` API and document legacy/demo routes as legacy.
- Stabilize only the secured subset of `/v1`; keep demo-only self-service
  authority endpoints explicitly unstable until Phase 3 moves authority out of
  the agent/client path.
- Add policy decision golden tests for R1-R12.

Exit criteria:

- External clients can build valid PACT envelopes using supported libraries.
- Python and Go canonicalization cannot drift silently.
- Golden vectors come from the written spec, not from blessing one
  implementation's current output.
- The public API surface is clearly separated from demo-only endpoints.

## Phase 3: Production Control Plane

Target: 2-4 months

Goal: move authority out of the agent/client path.

Feature rollouts:

- API authentication with OIDC/JWT, mTLS, or workload identity.
- Tenant IDs on agents, intents, capabilities, runs, actions, approvals,
  policies, keys, and audit events.
- RBAC for operator, agent, approver, auditor, and admin roles.
- Authority-controlled registration: clients register public keys or workload
  identities, not raw private keys.
- Capability issuance service that validates authenticated agent identity,
  tenant, operator grant, intent, tool, resource scope, and consent state.
- Server-authorized approval records and one-time resume tokens; remove
  client-controlled approval bypasses.
- Key IDs, key rotation, revocation, expiry, disabled states, and audit events.

Exit criteria:

- An agent can request authority, but cannot mint or widen it.
- Approvals are authenticated, auditable, scoped, expiring, and one-time use.
- Every control-plane mutation is tenant-scoped and authorization checked.

## Phase 4: Durable Evidence and Data-Flow Control v2

Target: 3-5 months

Goal: make audit and provenance evidence durable and precise enough for real
review.

Feature rollouts:

- Postgres support with Alembic migrations.
- Verification-path latency benchmarks for envelope validation, policy decision,
  ledger append, and replay verification.
- Durable provenance storage instead of process-local run state.
- Object-level or field-level taint with source object IDs and content digests.
- Separate pre-action input provenance from post-action output provenance.
- Redacted result previews, encrypted evidence blobs, retention policies, and
  secret scanning before persistence.
- Append-only ledger tables, idempotency keys, Merkle roots, and optional
  external anchoring or WORM snapshot export.
- Replay verification that separately reports:
  - hash-chain validity
  - envelope signature validity
  - passport validity at action time
  - capability validity at action time
  - intent hash validity
  - resource-scope validity
  - policy version and decision reproducibility
  - key ID and key status at action time

Exit criteria:

- Restarting or scaling the backend does not lose taint state.
- Replay explains exactly which evidence passed, failed, or could not be
  verified.
- Sensitive data is not stored in plaintext by default.

## Phase 5: Policy, Integrations, and Operator Experience

Target: 4-6 months

Goal: turn the protocol into an operator-friendly platform.

Feature rollouts:

- Adopt or integrate a formal policy engine such as OPA/Rego or Cedar.
- Add policy versions, shadow mode, policy tests, and reproducible decision
  reports.
- Build an approval console in the dashboard.
- Add SIEM export for audit events.
- Expand connector sandboxing for file, shell, browser/web, email, and HTTP API
  tools.
- Add LangChain, LangGraph, MCP, Claude Code, Codex, and direct SDK examples
  with the same scenario matrix.
- Add adversarial replay suites and multi-agent scenarios.

Exit criteria:

- Operators can review pending approvals, inspect policy decisions, and export
  audit evidence.
- Integrators can adopt PACT through SDKs or gateway adapters rather than
  copying demo code.
- Policy changes can be tested, versioned, and rolled out safely.

## Release Plan

### v0.1: Public Developer Preview

- Open-source foundation files in place.
- One-command demo stack.
- Runnable attack examples.
- CI covers backend, frontend, Go TUI, and schema/golden-vector tests.
- Documentation states that PACT is not production-ready yet.

### v0.2: Integration Preview

- Stable `/v1` API subset.
- SDK helpers for canonicalization, signing, and verification.
- MCP gateway prototype.
- Cross-language golden vectors.
- Demo routes marked legacy.

### v0.3: Control Plane Preview

- API auth, tenant scoping, RBAC foundation.
- Authority-controlled capability issuance.
- Server-authorized approvals.
- Key lifecycle model.

### v0.4: Audit and Provenance Preview

- Postgres and Alembic.
- Durable object-level provenance.
- Redacted/encrypted evidence storage.
- Strong replay verification report.

### v0.5: Operator Preview

- Policy engine integration.
- Approval console.
- SIEM export.
- Expanded connector and adapter examples.

### v1.0: Production Candidate

Do not target v1.0 until:

- Control-plane trust is no longer client-controlled.
- Tenant isolation and RBAC are enforced everywhere.
- Key lifecycle and approval lifecycle are auditable.
- Durable provenance and append-only evidence are in place.
- Threat model, security process, and CI security checks are mature.
- At least one external integration path is stable and documented.

## Defer Explicitly

- Generalized field-perfect taint for every arbitrary data structure.
- Real SaaS connector breadth before the security core is stable.
- Multi-tenant hosted service promises before tenant isolation is complete.
- Broad marketplace positioning before the first 10-minute demo is excellent.
- v1.0 language until production blockers are closed.

## Immediate Next Issues

1. Add `SECURITY.md`.
2. Add `docs/THREAT_MODEL.md`.
3. Add `CONTRIBUTING.md`.
4. Consolidate duplicate CI workflows.
5. Add CodeQL and Dependabot.
6. Add runnable examples for blocked exfiltration and approval flow.
7. Add one-command local demo setup.
8. Move historical planning artifacts into `docs/archive/` after confirming they
   are no longer needed at the repository root.
