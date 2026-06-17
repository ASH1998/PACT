# PACT Threat Model

PACT is a security protocol and runtime pattern for mediating AI-agent tool
calls. This document describes the practical threat model for the current
open-source project. It is intentionally conservative: PACT demonstrates useful
controls, but it should not be treated as production-ready until the gaps below
are closed.

## Security Objectives

PACT's core security goal is to prevent tools from trusting raw agent output.
Every tool call should be evaluated before execution using verifiable evidence:

- Agent identity through an issuer-signed Agent Passport and action signature.
- User intent through an Intent Contract and intent hash.
- Authorization through scoped, signed, short-lived Capability Tokens.
- Operator authority through grants and resource scope.
- Data-flow context through provenance and taint labels.
- Policy decisions that return `ALLOW`, `BLOCK`, or `REQUIRE_APPROVAL`.
- Audit evidence through a tamper-evident action ledger and replay.

PACT is designed to reduce the blast radius of manipulated or overreaching
agents. It is not a prompt firewall, malware sandbox, or complete identity and
access management system.

## Enforced vs. Assumed Today

This project is pre-1.0. Some properties are enforced in the current demo/MVP
path, while others are assumptions or roadmap items. Public examples and README
claims should stay aligned with this table.

| Area | Current status | Notes |
|---|---|---|
| Signed Action Envelopes | Enforced in gateway paths | Raw tool calls must not be wired around the gateway in a real integration. |
| Passport and action signature checks | Enforced in gateway paths | Production key lifecycle still needs key IDs, rotation, revocation, and disabled states. |
| Intent, capability, and resource-scope checks | Enforced in gateway paths | Capability issuance is not yet a production authority service. |
| Provenance-aware block rules | Enforced at coarse label level | Provenance is not yet durable object-level or field-level taint. |
| Human approval gate | Implemented | Production approver auth/RBAC and one-time resume tokens remain hardening work. |
| Tamper-evident ledger hash chain | Implemented | Append-only storage, Merkle roots, and external anchoring are future work. |
| API authentication and tenant isolation | Not production-enforced | Current API surfaces must be treated as local/demo until authz is added. |
| Sensitive result storage | Partially controlled | Production needs redaction, encryption, retention policy, and secret scanning by default. |
| Connector sandboxing | Partial/demo | Real SaaS, shell, browser, email, and file connectors need additional sandboxing. |

## Assets

The main assets PACT is intended to protect are:

- Tool execution authority: the ability to read files, read web/email content,
  send messages, call APIs, run shell commands, or invoke connector actions.
- Operator grants: the configured ceiling on allowed tools and resource scope.
- Resource scope: email domains, URL hosts, file path globs, and other target
  allowlists that define where an agent may act.
- User intent: the original goal and derived Intent Contract that bind allowed
  actions for a run.
- Agent identity: passports, agent IDs, public keys, issuer signatures, and key
  lifecycle state.
- Capability tokens: signed, intent-bound, resource-bound permissions and their
  use counters.
- Action envelopes: signed proposed tool calls, arguments, argument digests,
  provenance, parent hashes, and timestamps.
- Provenance labels: `trusted.user`, `untrusted.email`, `untrusted.web`,
  `internal.data`, `secret`, `agent.generated`, and `external_write`.
- Policy decisions: decision values, risk scores, policy reasons, and policy
  versions where available.
- Approval records: pending approvals, approval decisions, approver identity,
  resume authority, and expiration state.
- Ledger and replay evidence: action records, hash chains, signatures, stored
  arguments/results, and replay verification output.
- Secrets and sensitive data touched by tools: credentials, tokens, private
  files, confidential email/web content, and any sensitive tool result.
- Dashboard and API control-plane data: agents, intents, capabilities, runs,
  actions, policies, approvals, and audit metadata.

## Trust Boundaries

PACT's primary trust boundary is the Gateway. Tools should execute only after a
Gateway decision authorizes the action.

```text
User / Operator
      |
      v
Agent / Client Runtime  --untrusted requester-->
      |
      v
Signed Action Envelope
      |
      v
PACT Gateway  --trusted enforcement boundary-->
      |       verifies passport, signature, intent, capability,
      |       resource scope, provenance, policy, approval state
      v
Tool Runtime / Connector
      |
      v
Ledger / Replay / Dashboard
```

Important boundaries:

- User/operator to agent: user instructions and grants are trusted only after
  they are represented as explicit intent and grant data.
- External content to agent: email, webpages, attachments, and remote API output
  are untrusted inputs that may contain prompt-injection instructions.
- Agent to Gateway: the agent is a requester, not an authority. Signed envelopes
  are evidence to evaluate, not proof that execution is safe by themselves.
- Gateway to tool runtime: tool execution must be gated here. Direct raw tool
  calls bypass the security model.
- Control plane to agent: passports, grants, policies, capabilities, and
  approvals should be issued by trusted services, not self-declared by the
  agent.
- Gateway to ledger: the ledger records decisions and evidence. A hash chain
  detects later modification, but stronger append-only storage is still needed.
- Dashboard/API to operators: replay and approvals expose sensitive operational
  data and must be authenticated and authorized in production.

## Actors and Adversaries

Legitimate actors:

- User: asks the agent to perform a task.
- Operator: configures grants, policies, resource scope, and approval rules.
- Agent/client runtime: proposes tool calls and signs action envelopes.
- Gateway: validates evidence and makes pre-execution decisions.
- Tool runtime/connector: performs the requested operation after authorization.
- Approver: reviews actions that require human approval.
- Auditor/security reviewer: inspects ledgers, policy reasons, and replay data.

Adversaries:

- Prompt-injection attacker: controls email, webpage, file, issue, PR, or other
  content consumed by the agent and tries to steer it into unsafe actions.
- Malicious or compromised agent: attempts to widen its authority, forge
  evidence, skip the gateway, or call tools outside intent.
- Rogue client/integration: submits malformed envelopes, self-declared
  capabilities, or direct API mutations.
- Token thief: captures a capability token or approval resume artifact and tries
  to reuse it.
- Identity spoofer: attempts to act as a registered agent or tamper with a
  passport.
- Insider or compromised operator account: creates overly broad grants,
  approves unsafe actions, changes policy, or tampers with audit evidence.
- Ledger tamperer: modifies, deletes, inserts, or reorders action records to hide
  behavior.
- Data exfiltration attacker: tries to move secrets or sensitive internal data to
  an unauthorized external destination.
- Multi-tenant attacker: attempts to access another tenant's agents, runs,
  policies, approvals, or evidence. Current code is not yet production
  multi-tenant.
- Supply-chain attacker: compromises dependencies, build scripts, connector
  packages, schemas, or deployment artifacts.

## In-Scope Threats

### Indirect Prompt Injection

Threat: untrusted email, web, or file content instructs the agent to ignore the
user goal, send secrets, call external services, or change behavior.

Expected PACT control: untrusted content is labeled in provenance. External
writes influenced by `untrusted.email` or `untrusted.web` are blocked by policy
rules, and resource scope can independently block unauthorized destinations.

Security review focus:

- Verify each untrusted tool output receives the right label.
- Verify labels propagate to later actions in the same run.
- Verify external writes check both current inputs and accumulated influence.
- Verify prompt text cannot suppress or rewrite provenance labels.

### Intent Drift and Unauthorized Tool Use

Threat: an agent starts with a valid goal but attempts tools outside the Intent
Contract, such as sending email during a read-only summary task or running shell
commands during web research.

Expected PACT control: allowed and forbidden actions are checked against the
intent, and capability tokens are bound to the specific tool and intent.

Security review focus:

- Verify every tool call requires a matching intent hash.
- Verify forbidden actions are checked even if an action is also listed as
  allowed.
- Verify unknown or unregistered tools are blocked by default.
- Verify shell and sensitive reads require approval where configured.

### Resource-Scope Bypass

Threat: an agent uses an otherwise allowed tool against an unauthorized target,
such as an out-of-scope email recipient, URL host, or file path.

Expected PACT control: operator grants define resource scope, the intent stores
that scope, and policy rule R12 blocks out-of-scope resources.

Security review focus:

- Verify resource extraction is canonical and tool-specific.
- Verify path, host, email-domain, casing, encoding, symlink, redirect, and
  wildcard edge cases.
- Verify resource scope is default-deny for sensitive tools and external sinks.
- Verify agents cannot self-declare broader resource bindings at token issuance.

### Secret Exfiltration

Threat: an agent reads a secret or sensitive internal value and attempts to send
it to an external destination.

Expected PACT control: secret reads produce `secret` provenance. A later action
with `secret` influence and `external_write` side effect is blocked.

Security review focus:

- Verify secret tools and sensitive resources are consistently labeled.
- Verify result persistence redacts or encrypts sensitive values.
- Verify external sinks include email, HTTP APIs, shell/network commands, and
  connector side effects.
- Verify approval cannot turn an out-of-scope or secret-exfiltration block into
  execution unless policy explicitly permits that class.

### Identity Spoofing and Envelope Tampering

Threat: a caller forges an agent ID, modifies tool arguments, changes
provenance, swaps an intent hash, or submits an unsigned/malformed envelope.

Expected PACT control: passports are issuer-signed, envelopes are agent-signed,
arguments have canonical digests, and invalid signatures or mismatched hashes
are blocked.

Security review focus:

- Verify canonical JSON is identical across supported clients.
- Verify signatures exclude only fields intended to be mutable.
- Verify expired, revoked, disabled, or unknown passports are rejected.
- Verify `args_digest` always matches the actual tool arguments evaluated and
  executed.

### Capability Theft and Replay

Threat: a capability token is captured and replayed later, used for another
agent, used with another intent, or used against another resource.

Expected PACT control: tokens are signed, short-lived, use-limited, and bound to
agent, intent, capability, and resource.

Security review focus:

- Verify use counters are updated atomically.
- Verify repeated submissions cannot double-spend a token under concurrency.
- Verify expired tokens fail under clock-skew conditions.
- Verify token hashes and token records cannot be substituted across runs.
- Add idempotency keys for action submission and result attachment.

### Approval Bypass or Confused Approval

Threat: an agent or client resumes a `REQUIRE_APPROVAL` action without a real
approver, reuses a prior approval, changes args after approval, or tricks an
approver with incomplete context.

Expected PACT control: approval-gated actions pause before execution and should
resume only with server-authorized approval state.

Current caveat: production-grade approval RBAC and authenticated reviewer
identity are still pending.

Security review focus:

- Verify approvals are bound to action hash, args digest, run, tenant, policy,
  and expiration.
- Verify approvals are one-time use and cannot be replayed.
- Verify approver identity and authorization are recorded.
- Verify approving a sensitive action does not override hard blocks such as
  invalid identity, invalid signature, or out-of-scope resources.

### Ledger Tampering and Replay Mismatch

Threat: an attacker edits, deletes, inserts, or reorders ledger records, or replay
reports a misleading verification result.

Expected PACT control: action hashes include parent hashes, and replay can detect
hash-chain breaks.

Current caveat: database rows and static snapshots are not a complete
append-only audit system.

Security review focus:

- Verify every attempted action is recorded regardless of decision.
- Verify hash-chain validation detects modification, deletion, insertion, and
  reorder attacks.
- Verify replay separately reports hash-chain validity, envelope signature
  validity, passport validity, capability validity, intent hash validity,
  resource-scope validity, and policy reproducibility.
- Add append-only storage, Merkle roots, and external anchoring before relying on
  the ledger for strong audit evidence.

### Control-Plane Abuse

Threat: an unauthenticated or overprivileged caller registers agents, creates
intents, issues capabilities, changes policy, approves actions, or reads another
run's evidence.

Expected PACT control: in a production architecture, these actions must be behind
authenticated, tenant-scoped, role-based services.

Current caveat: current demo/MVP APIs are not yet hardened enough for production
control-plane use.

Security review focus:

- Add API authentication for every control-plane endpoint.
- Add tenant IDs and authorization checks to agents, intents, capabilities,
  runs, actions, approvals, policies, keys, and audit events.
- Split roles for operator, agent, approver, auditor, and admin.
- Move capability issuance and approval authority out of the agent/client path.

## Out of Scope and Non-Goals

The following are not security guarantees of the current project:

- Production readiness. PACT is currently a security-protocol MVP/demo, not a
  hardened production service.
- Prompt filtering. PACT does not try to classify or remove malicious prompt
  text before it reaches the model.
- Full agent sandboxing. PACT gates tool calls but does not isolate arbitrary
  code execution by itself.
- Complete connector security. Real email, browser, SaaS, file, shell, and API
  connectors need their own sandboxing and authorization controls.
- Compromised host defense. If the host, runtime, OS, Python/Go process, or tool
  binary is fully compromised, PACT's guarantees may not hold.
- Colluding trusted services. If a trusted Gateway or trusted tool intentionally
  lies or bypasses policy, PACT cannot prevent that by protocol alone.
- Fine-grained taint for arbitrary data structures. Current provenance is coarse
  label-level taint, not field-perfect or byte-level data-flow tracking.
- Cryptographic side-channel resistance. Timing, power, cache, and hardware
  side-channel attacks are out of scope.
- Production KMS/HSM key management. Strong key custody, certificate chains, and
  distributed revocation are future hardening work.
- Multi-agent delegation and trust propagation. Current enforcement is centered
  on a single agent action path.
- Multi-tenant hosted service guarantees. Tenant isolation and RBAC are planned
  hardening items, not current production guarantees.
- Supply-chain security completeness. Dependency, build, release, and artifact
  integrity controls still need additional work.

## Assumptions

PACT's current security model relies on these assumptions:

- Tools are integrated so that raw tool calls cannot bypass the Gateway.
- The Gateway, policy engine, ledger append path, and issuer keys are trusted
  components.
- The agent runtime signs envelopes honestly with its configured key, even if
  the model output itself is untrusted or manipulated.
- Operator grants are created by a legitimate operator and reflect the intended
  authority ceiling for the agent.
- Capability tokens are issued by trusted code and are not self-minted by an
  untrusted agent in production deployments.
- Resource extraction correctly identifies the actual target of each tool call.
- Provenance labels are applied by trusted tool wrappers and propagated across
  run steps.
- System clocks are close enough for token and passport expiry checks, or the
  deployment defines acceptable skew.
- Ledger verification has access to the evidence needed to reconstruct and check
  prior actions.
- Stored args, results, and replay evidence are protected according to their data
  sensitivity.

## Current Known Gaps

These are known gaps from the current readiness and roadmap docs:

- API authentication, tenant isolation, and RBAC are not complete.
- Agent registration and capability issuance need to be authority-controlled,
  not agent/client-controlled.
- Agent private key lifecycle needs production treatment: no raw private-key
  returns, key IDs, rotation, revocation, expiry, disabled states, and audit
  events.
- Approval flow needs authenticated approvers, RBAC, one-time resume tokens,
  expiration, policy binding, and dashboard-first operations.
- Replay verification needs to distinguish hash-chain validity from envelope
  signature validity, passport validity, capability validity, intent hash
  validity, resource-scope validity, policy version, and key status at action
  time.
- Provenance is currently too coarse and not sufficiently durable for scaled
  production use.
- The ledger is hash-chained, but production audit needs append-only storage,
  migrations, Merkle roots, and optional external anchoring or WORM export.
- Args and tool results can contain sensitive data; production storage needs
  redaction, encryption, retention policy, and secret scanning.
- Resource scope must become mandatory for sensitive tools and external sinks.
- Canonicalization and golden-vector tests are needed across supported clients
  to prevent signature drift.
- Connector sandboxing for real email, file, shell, browser, web, and SaaS tools
  remains future work.
- Policy needs versioning, reproducible decision reports, stronger test vectors,
  and eventually a formal policy engine such as OPA/Rego or Cedar.

## Security Review Checklist

Use this checklist before trusting a new PACT integration, release, or deployment.

Identity and keys:

- Passports are issuer-signed, non-expired, and verified on every action.
- Agent action signatures are checked against the passport public key.
- Key IDs, rotation, revocation, disabled state, and expiry are modeled.
- Private keys are not returned by registration APIs in production paths.
- Canonical signing payloads have golden tests across clients.

Intent and authority:

- Intent Contracts are derived or approved through a trusted path.
- The intent hash covers all fields that affect authorization, including
  resource scope where applicable.
- Operator grants define the maximum authority; the agent can only narrow it.
- Unknown tools and omitted resource scopes are handled as default-deny for
  sensitive tools and external sinks.
- Capability tokens are short-lived, signed, use-limited, and bound to agent,
  intent, tool, and resource.

Policy and enforcement:

- Every tool call passes through the Gateway before execution.
- The Gateway records attempted actions regardless of decision.
- `BLOCK` decisions cannot be overridden by client flags.
- `REQUIRE_APPROVAL` pauses execution until a server-authorized approval is
  present.
- Policy rules cover identity, signature, capability, intent, forbidden tools,
  resource scope, provenance, secret flow, shell, and unknown tools.
- Policy versions and decision reasons are stored for replay.

Provenance and data flow:

- Tool outputs receive correct provenance labels.
- Taint propagates across run steps and cannot be modified by the agent.
- Secret labels are applied consistently to credentials, tokens, and private
  files.
- External write side effects are identified for all relevant connectors.
- Pre-action input provenance and post-action output provenance are separated or
  clearly represented.

Resource scope:

- Email addresses/domains, URL hosts, file paths, and API targets are extracted
  from the executed arguments, not merely from displayed text.
- Canonicalization handles case, encoding, redirects, path traversal, symlinks,
  wildcards, and alternate host representations.
- Out-of-scope resources are hard blocks, not approval prompts.
- Scope checks run before tool execution and before external side effects.

Approval:

- Approval records are created by the Gateway and bound to action hash, args
  digest, run ID, tenant, policy version, and expiry.
- Approvers are authenticated and authorized for the tenant and action class.
- Approval resume artifacts are one-time use.
- The approver sees enough context to understand target resource, side effects,
  provenance, policy reasons, and risk.

Ledger and replay:

- Hash-chain verification detects modification, deletion, insertion, and reorder
  attacks.
- Replay verifies signatures and authorization evidence separately from chain
  integrity.
- Ledger records are append-only or externally anchored for production audit.
- Stored args and results are redacted or encrypted by default.
- Replay output clearly distinguishes verified, failed, missing, and
  unverifiable evidence.

Control plane and operations:

- All APIs require authentication.
- Tenants are enforced on every object and query.
- RBAC separates operator, agent, approver, auditor, and admin capabilities.
- Policy, grant, approval, and key changes are audited.
- Rate limits, structured logs, metrics, tracing, and alerting are configured.
- Dependency, CI, release, and artifact integrity controls are in place.

## Review Status

This threat model should be updated whenever the protocol primitives, gateway
behavior, approval flow, connector model, key lifecycle, or ledger design change.
Until the current known gaps are closed, PACT should be described as a
developer-preview security protocol/runtime rather than a production-ready
security boundary.
