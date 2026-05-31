# PACT Road to Production

## 0. Purpose

This document is a detailed implementation roadmap for turning the current PACT demo/MVP into a production-grade agent security protocol.

The current project proves the core claim from `PLAN.md`:

> Tools should not trust raw agent output. Every tool call must carry verifiable proof of agent identity, user intent, scoped capability, data provenance, and trace integrity.

The next goal is to move from a deterministic demo with mock tools into a real protocol layer that can be integrated with agent frameworks, model APIs, and arbitrary tools.

The immediate product direction is:

- PACT must remain a general protocol for agents, not an email-specific security app.
- PACT should be library-first, so teams can embed it into their own agent runtime.
- PACT should also provide an optional API proxy/sidecar, so existing applications can adopt it with minimal code changes.
- First real model integrations should target Gemini and AWS Bedrock.
- Compatibility with LangChain/LangGraph and custom tool-using runtimes is required.
- MCP compatibility should be part of the roadmap, but it should not block the first provider/API middleware work.

## 1. Current State

The truth sources for the existing MVP are:

- `PLAN.md`
- `pact_project_plan.md`
- `pact_pitch_deck.md`
- `pact_week_wise_build_plan.md`
- `progress.md`
- `docs/PROTOCOL.md`
- `docs/API.md`

Current implemented MVP:

- FastAPI backend.
- React/Vite SOC dashboard.
- Protocol schemas in `protocol/`.
- Ed25519 agent passports.
- Deterministic intent contracts.
- Signed, intent-bound capability tokens.
- Signed PACT action envelopes.
- Gateway-enforced mock tool execution.
- Coarse provenance labels.
- Policy engine with `ALLOW`, `BLOCK`, and `REQUIRE_APPROVAL`.
- Hash-chain action ledger.
- Demo scenarios and replay UI.
- Test suite covering protocol primitives, gateway, policy, ledger, provenance, tools, and integration paths.

Productionization work now present in the repo:

- `backend/app/core/runtime.py` adds a library-first `PactRuntime` wrapper over the existing services.
- `backend/app/core/interfaces.py` defines early storage, policy, and tool registry interfaces.
- `backend/app/core/tool_metadata.py` defines a generic tool metadata model and side-effect enum.
- `backend/app/core/registry.py` adds an in-memory tool registry and registers the current demo tools with metadata.
- `backend/app/core/key_management.py` adds separate key roles for passport issuer, capability issuer, ledger signer, approval signer, and agent actions.
- `backend/app/core/policy_config.py` and `backend/app/core/default_policy.yaml` add structured policy configuration that mirrors the current hardcoded rules.
- `backend/app/core/storage.py` adds an engine helper for SQLite and Postgres URLs.
- `backend/app/adapters/providers/` adds normalized provider interfaces plus Gemini, Bedrock, and OpenAI-compatible adapters.
- `backend/app/adapters/frameworks/` adds direct Python, LangChain, and LangGraph wrappers.
- `backend/app/api/proxy.py` adds `/v1/proxy/chat`, `/v1/proxy/gemini/{model_path}`, and `/v1/proxy/bedrock/converse`.
- `backend/app/api/v1/` adds first-cut v1 runs, actions, tools, policies, and approvals routes.
- New SQLAlchemy models exist for `agent_keys`, `approvals`, `model_events`, `provenance_events`, and `tool_registry`.
- `ActionEnvelopeV1`, approval schemas, model-event schema, tool-metadata schema, and programmatic-intent schema were added.
- New tests exist for core runtime, adapters, approvals, provider normalization/proxy paths, storage helpers, and v1 API routes.

Current productionization gaps to remove or reduce:

- Tools are mock implementations.
- Provider integration exists but is incomplete:
  - Gemini performs real HTTP through `httpx` when configured.
  - Bedrock currently returns a mock response and does not call AWS.
  - OpenAI-compatible calls are implemented through HTTP.
  - Provider proxy events are now persisted to `model_events`.
- Intent classification is deterministic keyword matching.
- Policy config exists and the production runtime uses `ConfigurablePolicyService`; the legacy MVP endpoints still use some legacy service construction.
- Provenance is still mostly coarse and run-level for tool execution, but proxy/model output provenance now writes `provenance_events`.
- SQLite is still the default persistent store; Postgres helper exists, but no migration system is present.
- JSON schemas and `ActionEnvelopeV1` exist, but strict runtime validation and replay/nonce enforcement are not complete.
- Human approval is now unified around `ApprovalService` for v1 approval APIs and `ApprovalGatewayService` can resume approved envelopes with approval-loop suppression.
- Agent runtime is deterministic and scenario-based.
- LangChain/LangGraph/direct wrappers exist, but they are thin adapters and not yet packaged or documented as public integration APIs.
- Tool metadata is DB-backed through `/v1/tools` and mirrored into the core in-memory registry.
- `/v1/policies` is DB-backed, returns active persisted policies, and reloads structured enabled rules into `PactRuntime` policy enforcement.
- V1 action proposal now routes through `PactRuntime.evaluate_action()` and uses gateway `dry_run=True`, so it does not execute tools, append ledger entries, or consume capability tokens.
- Crypto key role separation exists in `KeyManager`, and the production runtime factory now passes the key manager into `PactRuntime` for separate passport/capability issuer keys. Legacy MVP endpoints still use older issuer wiring.
- Runtime dependency cleanup for `PyYAML` and `asyncpg` is done in `backend/requirements.txt`.

## 2. Product Target

PACT production should be a protocol and enforcement toolkit for agent actions.

The production system should answer these questions before any action executes:

1. Which agent is acting?
2. Which user, app, tenant, and run does this belong to?
3. What did the user authorize the agent to do?
4. Which tool/resource/capability is being requested?
5. What model outputs, tool outputs, user inputs, documents, or external sources influenced this action?
6. Does policy allow this action in the current context?
7. If approval is required, who approved it and what exactly did they approve?
8. Can the full run be audited and verified after the fact?

PACT should support at least three adoption modes:

1. Embedded library mode:
   - App imports PACT.
   - App wraps model calls and tool calls directly.
   - Best for custom runtimes and tightly controlled deployments.

2. Sidecar/proxy mode:
   - App points model/tool clients at a local or remote PACT proxy.
   - PACT records model interactions and enforces tool calls.
   - Best for existing apps that cannot deeply refactor immediately.

3. Framework adapter mode:
   - PACT provides adapters for LangChain/LangGraph and later MCP.
   - Best for teams already using agent frameworks.

## 3. Architecture Target

The production architecture should separate protocol logic from demo/API/UI concerns.

Recommended package/module split:

```text
backend/app/
  core/                  # Production protocol core
    crypto/
    protocol/
    policy/
    provenance/
    ledger/
    storage/
    tools/
    approvals/
  adapters/
    providers/
      gemini.py
      bedrock.py
      openai_compatible.py
    frameworks/
      langchain.py
      langgraph.py
    mcp/
  api/
    protocol/
    proxy/
    admin/
    dashboard/
  examples/
    mock_tools/
    sample_agents/
```

Current repo alignment:

- The repo now has `backend/app/core/`, `backend/app/adapters/providers/`, `backend/app/adapters/frameworks/`, `backend/app/api/v1/`, and `backend/app/api/proxy.py`.
- The current split is an incremental overlay, not a complete extraction:
  - core still wraps legacy services under `backend/app/services/`
  - FastAPI routes still instantiate legacy services directly in several places
  - model/provider proxy code is separate from `PactRuntime.record_model_event`
  - v1 APIs are not yet the single canonical API surface

The exact directory names can differ, but the separation must hold:

- Core protocol must not depend on FastAPI.
- Core protocol must not depend on the React dashboard.
- Provider adapters must not mutate protocol semantics.
- Framework adapters must call the same gateway/policy pipeline as HTTP tools.
- Demo scenarios must become examples/regression tests, not the architectural center.

Next architectural correction:

- Make `PactRuntime` the only composition root for production flows.
- Have v1 API routes, proxy routes, framework adapters, and direct SDK decorators call `PactRuntime` or a small runtime factory instead of rebuilding legacy service graphs independently.
- Keep legacy MVP endpoints working, but mark them compatibility/demo endpoints in docs.

## 4. Production Components

### 4.1 PACT Core Library

Status: partially implemented.

`PactRuntime` now exists and provides a first library-first interface over the existing services. It can create runs, create keyword/programmatic intents, issue capabilities, propose/evaluate/execute actions through the gateway, record model events, verify runs, and register agents.

Remaining work: make the legacy MVP routes use the runtime factory where practical, or clearly document them as compatibility/demo routes.

The reusable core layer should own:

- Agent identity.
- Intent contracts.
- Capability tokens.
- Action envelopes.
- Provenance events.
- Policy evaluation.
- Ledger append/verify.
- Approval tokens.
- Tool registry metadata.

The core library should expose stable interfaces:

```python
class PactRuntime:
    async def create_run(...)
    async def create_intent(...)
    async def issue_capability(...)
    async def propose_action(...)
    async def evaluate_action(...)
    async def execute_action(...)
    async def record_model_event(...)
    async def verify_run(...)
```

Important rule:

- Do not let adapter code create policy shortcuts.
- All integrations must converge into the same `propose_action -> evaluate -> ledger -> execute/deny/pending` flow.
- Do not let API routes create incompatible enforcement semantics. `/tools/call`, `/v1/actions/propose`, framework wrappers, and proxy tool calls must all go through the same runtime/gateway path.
- Keep "propose/evaluate only" separate from "execute tool". `PactRuntime.propose_action()` and `evaluate_action()` now call the gateway with `dry_run=True`; full execution remains `execute_action()`.

### 4.2 API Proxy / Sidecar

Status: initial implementation exists.

`backend/app/api/proxy.py` provides:

- `POST /v1/proxy/chat`
- `POST /v1/proxy/gemini/{model_path:path}`
- `POST /v1/proxy/bedrock/converse`

Provider adapters exist for Gemini, Bedrock, and OpenAI-compatible APIs. The proxy normalizes provider requests/responses, creates run records, persists `model_events`, and writes model-output `provenance_events`.

Build this into a production FastAPI sidecar that can sit between an agent app and model/tool providers.

Proxy responsibilities:

- Accept model API calls from clients.
- Authenticate app/agent/project.
- Create or attach to a PACT run.
- Record the user/developer/system messages as provenance inputs.
- Forward the request to the configured model provider.
- Record the model response as `agent.generated`.
- Normalize provider tool calls into PACT proposed actions where possible.
- Forward allowed calls to registered tools or return policy errors.

First provider integrations:

- Gemini API.
- AWS Bedrock Converse API.

Optional compatibility target:

- OpenAI-compatible chat completions shape, to support clients that allow configurable base URLs.

Proxy endpoint strategy:

```text
POST /proxy/chat
POST /proxy/gemini/{model}:generateContent
POST /proxy/bedrock/converse
POST /tools/call
POST /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/replay
```

For provider-specific endpoints, prefer minimal compatibility over full emulation at first. The proxy does not need to implement every provider feature on day one.

Required next fixes:

- Create corresponding `provenance_events` for user/system/developer input messages, not only model outputs.
- Normalize provider tool calls into PACT action proposals.
- Preserve raw provider payloads in DB, not only normalized summaries.
- Add auth headers/API keys for proxy access.
- Make provider route behavior explicit: either return normalized PACT response or provider-native response, and document which endpoint does which.

### 4.3 Provider Interface

Status: implemented as an initial interface.

`ModelProvider`, `ModelRequest`, `ModelResponse`, and `ToolCall` exist in `backend/app/adapters/providers/base.py`.

Continue evolving this common internal model provider interface.

```python
class ModelProvider:
    name: str

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        ...

    def normalize_request(self, raw: dict) -> ModelRequest:
        ...

    def normalize_response(self, raw: dict) -> ModelResponse:
        ...
```

`ModelRequest` should capture:

- provider
- model
- messages/content
- tool declarations
- generation params
- metadata
- run_id
- agent_id
- intent_hash

`ModelResponse` should capture:

- provider
- model
- raw response
- text/content parts
- tool call proposals
- token usage if available
- safety/blocking metadata if available

Do not force all providers into a lossy lowest-common-denominator format. Store raw request/response JSON alongside normalized fields.

Provider-specific status:

- Gemini: normalizes `generateContent` requests/responses, extracts function calls, and invokes the real Gemini HTTP endpoint with `GEMINI_API_KEY`.
- Bedrock: normalizes Converse request/response format and extracts `toolUse`, but `invoke()` is currently mocked and must be replaced with real AWS Bedrock client logic.
- OpenAI-compatible: normalizes `/v1/chat/completions`, extracts function/tool calls, and invokes an OpenAI-compatible endpoint through HTTP.

Next provider work:

- Add credential validation and clear error messages.
- Add retry/timeout configuration.
- Add provider request IDs where available.
- Add streaming support later; do not block non-streaming production path on streaming.
- Ensure provider tests never require real network calls in CI.

### 4.4 LangChain and LangGraph Compatibility

Status: first wrappers exist.

Current files:

- `backend/app/adapters/frameworks/direct.py`
- `backend/app/adapters/frameworks/langchain.py`
- `backend/app/adapters/frameworks/langgraph.py`

They prove the shape of direct, LangChain, and LangGraph integration. They are not yet production-grade public adapters.

Continue implementing PACT adapters that work with common LangChain/LangGraph tool execution.

Minimum adapter behavior:

- Wrap a LangChain tool.
- Before the underlying tool function runs, create a PACT action envelope.
- Evaluate it through the PACT gateway.
- Execute the tool only when `ALLOW`.
- Return a structured blocked/approval-required result when denied.
- Record tool result provenance after execution.

Possible API:

```python
from pact.adapters.langchain import pact_tool, PactCallbackHandler

secure_tool = pact_tool(
    tool=existing_tool,
    tool_id="calendar.create_event",
    side_effect="external_write",
    resource_extractor=lambda args: args["calendar_id"],
)
```

LangGraph path:

- Provide node middleware around tool nodes.
- Preserve graph state keys for `run_id`, `agent_id`, `intent_hash`, and `parent_action_hash`.
- Expose errors in a format the graph can branch on.

Required next fixes:

- Register adapter-wrapped tools in the core/DB tool registry.
- Avoid fallback direct execution without PACT context in production mode. It is okay for tests/dev, but production should fail closed unless explicitly configured otherwise.
- Make return values structured, not plain strings like `"PACT BLOCKED: ..."`.
- Support sync and async tools consistently.
- Package optional dependencies cleanly, e.g. extras such as `pact[langchain]`.

### 4.5 Direct SDK / Custom Runtime Compatibility

Status: initial decorator exists.

`@pact_tool` exists in `backend/app/adapters/frameworks/direct.py` and requires a `pact_context` kwarg.

Not every user will use LangChain. Continue providing simple primitives:

```python
@pact_tool(
    tool_id="crm.update_contact",
    side_effect="internal_write",
    resource_arg="contact_id",
)
async def update_contact(contact_id: str, fields: dict):
    ...
```

And a manual API:

```python
decision = await pact.propose_action(
    run_id=run_id,
    agent_id=agent_id,
    tool="crm.update_contact",
    args=args,
)

if decision.allowed:
    result = await real_tool(**args)
    await pact.record_tool_result(...)
```

This path is required so PACT is not locked to one framework.

Required next fixes:

- Support non-kwargs args safely when computing action args.
- Feed extracted resource into capability validation or token issuance, not only local metadata.
- Allow app-provided provenance context instead of always defaulting to `trusted.user`.
- Provide ergonomic context creation helpers so users do not hand-build `pact_context` dictionaries.

### 4.6 MCP Adapter

MCP should be treated as a later integration surface over the same core.

MCP goals:

- Register MCP tools into PACT tool registry.
- Parse MCP tool metadata into PACT tool metadata.
- Intercept tool calls from MCP clients/servers.
- Detect risky tool metadata changes or prompt-injection-like tool descriptions where feasible.
- Apply the same gateway/policy/ledger pipeline.

Do not create separate MCP-only policy semantics.

## 5. Tool Metadata Model

Status: partially implemented.

`backend/app/core/tool_metadata.py` defines `ToolMetadata` and `SideEffect`. `backend/app/core/registry.py` has an in-memory `ToolRegistry` and registers the existing demo tools with metadata. `backend/app/models/tool_registry.py` adds a DB model, and `/v1/tools` now persists tool metadata to DB while also updating the core in-memory registry.

Replace remaining demo-specific assumptions with a formal, persisted tool metadata schema.

Tool metadata should include:

```json
{
  "tool_id": "email.send",
  "display_name": "Send Email",
  "version": "1.0.0",
  "description": "Send an email to an external recipient.",
  "input_schema": {},
  "output_schema": {},
  "side_effect": "external_write",
  "resource_type": "email_address",
  "resource_extractor": {
    "type": "json_path",
    "path": "$.to"
  },
  "output_provenance": ["external_write"],
  "sensitivity": "high",
  "default_requires_approval": true
}
```

Required side-effect classes:

- `none`
- `read`
- `internal_write`
- `external_write`
- `delete`
- `payment`
- `shell`
- `network`
- `privileged`

Required provenance labels:

- `trusted.system`
- `trusted.developer`
- `trusted.user`
- `untrusted.web`
- `untrusted.email`
- `untrusted.document`
- `untrusted.tool_metadata`
- `internal.data`
- `secret`
- `agent.generated`
- `external_write`

The current labels should remain valid, but the model must support arbitrary source families.

Required next fixes:

- Make the DB-backed tool registry authoritative across process restarts.
- Have gateway policy consult registered tool metadata for side effects and approval defaults.
- Fail closed for unknown/unregistered tools in production mode.
- Keep built-in mock tools registered as examples, not special cases.

## 6. Intent Contracts in Production

Status: partially implemented.

`PactRuntime.create_intent()` now supports explicit `allowed_actions` and `forbidden_actions` in addition to the legacy keyword classifier. `ProgrammaticIntentRequest` exists in schemas. This is the right direction, but v1 APIs do not yet expose a complete production intent API.

The current keyword classifier is useful for tests, but production needs explicit intent construction.

Support three intent creation modes:

1. Programmatic intent:
   - App provides allowed actions/resources directly.
   - Best for deterministic workflows.

2. Assisted intent:
   - PACT proposes an intent from user goal.
   - App/user confirms or edits it.

3. Policy-derived intent:
   - Org policy maps task templates to allowed capabilities.
   - Best for enterprise workflows.

Intent contract should include:

- user goal
- creator/owner
- agent_id or agent group
- allowed tool IDs
- forbidden tool IDs
- allowed side-effect classes
- allowed resources/resource patterns
- approval requirements
- risk budget
- expiry
- intent hash
- version

Important production rule:

- Do not allow an agent to self-authorize arbitrary resources by simply requesting a capability token.
- Capabilities must derive from user/app/org-approved intent scope.

Required next fixes:

- Add `/v1/intents` endpoints for programmatic and assisted intents.
- Add resource scope to intent contracts, not only allowed action names.
- Add side-effect scope and approval policy to intent contracts.
- Bind capability issuance to stored intent scope.
- Keep keyword classifier as demo/dev helper, not the production default.

## 7. Capability Tokens in Production

Capability tokens should become production authorization artifacts.

Status: MVP token validation still powers the gateway. Production fields below are not yet fully implemented. `KeyManager` defines separate key roles, and `PactRuntime(key_manager=...)` wires passport and capability services to separate issuer keys.

Add:

- `key_id`
- `issuer`
- `audience`
- `not_before`
- `expires_at`
- `jti` or nonce
- revocation status
- resource scope
- side-effect scope
- approval binding where relevant

Validation must check:

- token exists or signature is trusted
- issuer key is valid
- token not expired
- token not before time has passed
- token not revoked
- token has remaining uses
- agent matches
- intent matches
- tool matches
- resource matches
- side-effect class is within scope
- approval token exists when required

Use-count decrement must be safe under concurrency.

Required next fixes:

- Add `key_id`, issuer role, nonce/JTI, and revocation fields to the token model/schema.
- Keep legacy endpoints compatible while moving new production paths to `KeyManager`-managed issuer roles.
- Enforce resource scope from intent/tool metadata.
- Add DB-backed revocation.
- Add concurrency-safe use consumption with tests against the production DB path.

## 8. Action Envelope vNext

Status: partially implemented.

`ActionEnvelopeV1` exists in `backend/app/schemas/__init__.py`, and `ToolCallRequest` accepts both `PACT/0.1` and `PACT/1.0`. The gateway still primarily operates on the legacy dictionary envelope shape and does not enforce all `PACT/1.0` requirements.

Keep `PACT/0.1` for compatibility, but complete the `PACT/1.0` envelope implementation.

Recommended fields:

```json
{
  "protocol": "PACT/1.0",
  "action_id": "act_...",
  "run_id": "run_...",
  "step_id": 7,
  "parent_action_hash": "sha256:...",
  "agent_id": "agent_...",
  "tenant_id": "tenant_...",
  "intent_hash": "sha256:...",
  "capability_token_hash": "sha256:...",
  "tool": {
    "tool_id": "crm.update_contact",
    "version": "1.0.0"
  },
  "args_digest": "sha256:...",
  "provenance": {
    "influenced_by": [],
    "uses_data": [],
    "side_effect": "internal_write",
    "sources": []
  },
  "timestamp": "2026-05-24T00:00:00Z",
  "nonce": "...",
  "agent_signature": "...",
  "key_id": "agent-key-..."
}
```

Verification must include:

- required fields
- protocol version
- canonical JSON
- signature
- timestamp skew
- nonce/replay status
- args digest
- token binding
- intent ownership
- capability scope
- ledger parent integrity

Required next fixes:

- Add dedicated envelope validation service for `PACT/1.0`.
- Add nonce/replay store.
- Add timestamp skew checks.
- Add key ID lookup.
- Add tool version and tenant/project binding checks.
- Ensure v1 APIs never use unsigned synthetic envelopes for production paths.

## 9. Provenance Model

Status: partially wired.

`backend/app/models/provenance_event.py` defines a `provenance_events` table. Proxy/model output now writes provenance events. The gateway/tool/runtime paths still mostly use coarse label dictionaries.

The current provenance service accumulates labels at run-level. Production needs event-level provenance.

Add provenance event records:

```text
provenance_events:
  id
  run_id
  event_id
  source_type
  source_uri
  source_label
  sensitivity
  produced_by_action_hash
  parent_event_ids
  content_digest
  metadata_json
  created_at
```

Source types:

- user_message
- system_message
- developer_message
- model_output
- tool_output
- document
- web_page
- email
- file
- api_response
- memory

Action envelopes should reference event IDs or content digests, not only broad labels.

First production milestone can still enforce coarse labels, but the data model should support finer tracing.

Required next fixes:

- Write provenance events for user messages, system/developer messages, model responses, tool outputs, documents, web pages, files, API responses, and memory reads.
- Link action envelopes to event IDs/content digests.
- Make replay render both action chain and provenance event graph.
- Store raw and redacted/summarized provenance separately when content is sensitive.

## 10. Policy System

Status: policy config exists, production runtime enforcement uses it, and `/v1/policies` now persists policy documents to DB.

`backend/app/core/policy_config.py` and `backend/app/core/default_policy.yaml` define structured rules matching current behavior. `ConfigurablePolicyService` consumes `PolicyConfig` and is used by `PactRuntime`. `/v1/policies` stores policy documents in the database, lists enabled policies, and reloads enabled structured rules into the runtime evaluator as additive rules on top of the built-in safety baseline. Loose legacy policy documents are still accepted and persisted for API compatibility, but only rules with the current `condition` plus `action` shape are enforced.

Move from hardcoded Python-only rules to policy-as-data with a default ruleset.

Default built-in rules:

- invalid passport -> block
- invalid signature -> block
- invalid capability -> block
- intent mismatch -> block
- untrusted source plus external write -> block or approval
- secret plus external write -> block
- shell/delete/payment -> approval
- high-risk side effect outside risk budget -> block
- unknown tool metadata -> block
- stale/replayed envelope -> block

Policy configuration should support:

```yaml
rules:
  - id: secret_external_write
    when:
      uses_data_contains: secret
      side_effect: external_write
    decision: BLOCK
    severity: critical

  - id: shell_requires_approval
    when:
      side_effect: shell
    decision: REQUIRE_APPROVAL
    severity: high
```

Do not build a large policy language first. Start with structured YAML/JSON that maps cleanly to the current evaluator.

Required next fixes:

- Persist policy versions.
- Add policy simulation/dry-run endpoint.
- Include tool metadata and intent resource scope in policy context.
- Add tests proving persisted YAML/JSON rules affect full gateway decisions, not only runtime config loading.

Later options:

- Rego/OPA adapter.
- Cedar adapter.
- Policy simulation/dry run.

## 11. Approval Workflow

Status: partially implemented and mostly unified for v1.

New approval pieces:

- `backend/app/models/approval.py`
- `backend/app/services/approval.py`
- `backend/app/services/approval_gateway.py`
- `backend/app/api/v1/approvals.py`
- `backend/tests/test_approval.py`

`ApprovalService` supports pending approval creation, approve, deny, expiry checks, listing pending approvals, and validating approved action hashes. `ApprovalGatewayService` wraps the existing gateway and creates approval records when a decision is `REQUIRE_APPROVAL`.

`/v1/approvals` now operates on real approval IDs through `ApprovalService`. Approval resume uses `skip_approval=True` in the gateway to avoid repeated approval loops after a human approval.

Unify this into real approval state instead of returning only `REQUIRE_APPROVAL`.

Approval flow:

1. Gateway evaluates proposed action.
2. Policy returns `REQUIRE_APPROVAL`.
3. Gateway stores pending action and full envelope.
4. API returns `approval_id`.
5. Dashboard shows approval request.
6. Approver approves or denies.
7. Approval decision is signed or stored with immutable audit fields.
8. If approved, gateway executes exactly the originally approved action.
9. Ledger links action, approval, and final result.

Approval table:

```text
approvals:
  id
  approval_id
  run_id
  action_hash
  requested_by_agent_id
  status
  requested_at
  expires_at
  decided_at
  decided_by
  decision_reason
  approval_token_hash
  approved_envelope_digest
```

Rules:

- Approved args cannot be changed after approval.
- Approval expires.
- Denied action never executes.
- Approval decision is visible in replay.

Required next fixes:

- Route every approval-required production execution path through `ApprovalGatewayService`.
- Ensure approved resume executes exactly the originally approved envelope.
- Prevent a resumed action from creating a second approval loop.
- Show approval request/decision in replay.
- Add dashboard approval UI.

## 12. Storage and Migrations

Status: early storage support exists.

`backend/app/core/storage.py` can create SQLite and Postgres async engines. New production-oriented models exist for tool registry, provenance events, model events, approvals, and agent keys. `asyncpg` is listed in requirements. There is still no migration system.

Keep SQLite for local development, but production should target Postgres.

Add Alembic migrations.

Production tables should include:

- agents
- agent_keys
- intents
- capability_tokens
- runs
- model_events
- tool_registry
- actions
- provenance_events
- policy_decisions
- approvals
- ledger_entries
- audit_exports

Storage interfaces should allow tests to use in-memory SQLite, but production docs should recommend Postgres.

Ledger storage:

- Keep hash-chain verification.
- Include append-only semantics at application level.
- Consider later WORM/object-store export.

Required next fixes:

- Add Alembic migrations.
- Add migration tests or at least schema creation tests that cover all new models.
- Decide whether DB models are authoritative for registry/policies/events and update routes accordingly.
- Add indexes for run/action/event lookup.
- Add migration tests or at least schema creation tests that cover all new models.

## 13. Key Management

Separate trust domains:

- passport issuer key
- capability issuer key
- ledger signer key
- approval signer key
- agent action keys

Status: `KeyManager` now exists and generates separate file-backed keys for all listed roles. It supports key IDs, rotation, revocation in memory, and public-key lookup. The production runtime factory now passes it into `PactRuntime`; legacy demo endpoints still use older issuer wiring.

Add:

- key IDs
- active/inactive status
- created_at/expires_at
- rotation support
- revocation support
- environment or KMS-backed loading

Initial implementation:

- file/env keys for local dev
- clear production interface for KMS/HSM later

Do not continue using one issuer key for all production roles.

Required next fixes:

- Wire passport service to `passport_issuer`.
- Wire capability service to `capability_issuer`.
- Wire ledger signing/verification to `ledger_signer`.
- Wire approval tokens to `approval_signer`.
- Persist key revocation instead of only in process memory.
- Keep old public keys available for historical ledger verification after rotation.

## 14. API Surface

Status: initial v1 API exists.

`backend/app/api/v1/` currently includes:

- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/replay`
- `GET /v1/runs/{run_id}/ledger/verify`
- `POST /v1/actions/propose`
- `POST /v1/actions/{action_id}/execute`
- `POST /v1/tools/register`
- `GET /v1/tools`
- `GET /v1/tools/{tool_id}`
- `POST /v1/policies`
- `GET /v1/policies`
- `POST /v1/approvals/{approval_id}/approve`
- `POST /v1/approvals/{approval_id}/deny`

Keep existing MVP endpoints for compatibility, but finish the grouped production APIs.

Protocol/runtime:

```text
POST /v1/runs
POST /v1/intents
POST /v1/capabilities
POST /v1/actions/propose
POST /v1/actions/{action_id}/execute
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/replay
GET  /v1/runs/{run_id}/ledger/verify
```

Proxy:

```text
POST /v1/proxy/chat
POST /v1/proxy/gemini/{model}:generateContent
POST /v1/proxy/bedrock/converse
```

Registry/admin:

```text
POST /v1/tools/register
GET  /v1/tools
GET  /v1/tools/{tool_id}
POST /v1/policies
GET  /v1/policies
GET  /v1/policies/{policy_id}
POST /v1/approvals/{approval_id}/approve
POST /v1/approvals/{approval_id}/deny
```

Dashboard APIs can remain separate but should read from the same production tables.

Required next fixes:

- Add `/v1/intents` and `/v1/capabilities`.
- Make `/v1/actions/propose` verify signed envelopes or clearly rename it as an unsigned simulation endpoint.
- Make `/v1/actions/{action_id}/execute` use registered tools and approval validation, not only mock tools.
- Add API auth before treating v1 as production.

## 15. Frontend Roadmap

The current frontend is scenario-oriented. Convert it into an operations console.

Pages:

- Overview:
  - runs, blocked actions, pending approvals, high-risk agents, policy trend
- Runs:
  - real runs, not just scenarios
- Run detail:
  - model calls, tool calls, decisions, approvals, provenance graph
- Replay:
  - timeline across user messages, model responses, tool proposals, gateway decisions
- Agents:
  - passports, keys, trust score, revocation
- Tools:
  - registered tools, side effects, schemas, risk tier
- Policies:
  - active policies, test/simulation UI
- Approvals:
  - pending, approved, denied, expired
- Audit exports:
  - export run or date range

Keep scenarios as a demo page or example mode, not the main navigation.

## 16. Testing Strategy

Preserve current tests as regression coverage.

New tests already added:

- `backend/tests/test_core.py`
- `backend/tests/test_adapters.py`
- `backend/tests/test_approval.py`
- `backend/tests/test_providers.py`
- `backend/tests/test_proxy.py`
- `backend/tests/test_storage.py`
- `backend/tests/test_v1_api.py`

These cover the first productionization slice: runtime wrapper, registry, key manager, policy config, direct/LangChain/LangGraph adapters, approval service, provider normalization/proxy behavior, storage helper, and v1 APIs.

Add test layers:

1. Unit tests:
   - canonical JSON
   - signatures
   - key IDs
   - token validation
   - envelope validation
   - resource extractors
   - policy rules

2. Storage tests:
   - SQLite dev
   - Postgres production path
   - migrations
   - concurrent token use

3. Provider tests:
   - Gemini mocked HTTP
   - Bedrock mocked client
   - raw provider response stored
   - normalized tool calls extracted

4. Adapter tests:
   - direct Python tool wrapper
   - LangChain tool wrapper
   - LangGraph node/tool flow

5. End-to-end tests:
   - safe model call plus tool call
   - malicious document/web/email influence blocked
   - secret-to-external blocked
   - shell requires approval
   - approval approve/deny/timeout
   - replayed envelope rejected
   - tampered ledger detected

6. Contract tests:
   - JSON schema validation
   - API response shapes
   - example snippets in docs

Immediate test gaps:

- Tests should assert proxy writes rows to `model_events`, not only returns response-local events.
- Tests should assert provenance events are written for model inputs/outputs and tool outputs.
- Tests should assert DB-backed v1 tools/policies affect complete gateway decisions, including tool metadata and runtime policy reload paths.
- Tests should cover `PACT/1.0` nonce/replay/timestamp/key-id validation.
- Tests should cover real approval API by `approval_id`, not action-hash mutation.
- Tests should cover `KeyManager` integration with passport/capability/ledger/approval services.
- Tests should cover Bedrock real-client wrapper with a mocked AWS client once the mock invoke is replaced.

## 17. Documentation Roadmap

Update docs to reflect production architecture.

Required docs:

- `docs/PROTOCOL.md`
  - add `PACT/1.0` envelope
  - add provider/model events
  - add arbitrary tool metadata
  - add approval semantics

- `docs/API.md`
  - document `/v1` APIs
  - keep legacy MVP endpoint notes

- `docs/INTEGRATIONS.md`
  - Gemini
  - Bedrock
  - LangChain
  - LangGraph
  - direct SDK/custom runtime

- `docs/DEPLOYMENT.md`
  - library mode
  - sidecar/proxy mode
  - Postgres
  - key management

- `docs/SECURITY.md`
  - threat model
  - guarantees
  - limitations
  - key rotation
  - production checklist

- `docs/EXAMPLES.md`
  - safe run
  - prompt injection
  - approval flow
  - custom tool

## 18. Implementation Phases

### Phase 1: Protocol Core Refactor

Status: partially complete.

Goal: make PACT reusable outside the demo FastAPI app.

Tasks:

- Extract protocol logic into core modules.
- Define storage interfaces.
- Define policy interface.
- Define tool registry interface.
- Keep current FastAPI endpoints working.
- Keep current tests passing.
- Add schema validation for envelopes/tokens/passports.

Acceptance criteria:

- Existing demo scenarios still pass.
- Core services can be imported without FastAPI.
- A direct Python call can create intent, issue capability, evaluate action, and append ledger.

Remaining work:

- Move remaining legacy/demo endpoints toward the runtime factory or document them explicitly as compatibility surfaces.
- Keep tests around dry-run behavior so evaluation cannot accidentally reintroduce tool execution, ledger writes, or token consumption.

### Phase 2: Generic Tool Registry

Status: partially complete.

Goal: stop hardcoding mock tool behavior into the protocol.

Tasks:

- Add tool metadata schema/model.
- Add registry service.
- Register current mock tools through registry.
- Add resource extractor support.
- Update policy to use side-effect metadata.

Acceptance criteria:

- Existing mock scenarios work through registered tool metadata.
- A new arbitrary tool can be registered without editing policy code.
- Unknown tools are blocked by default.

Remaining work:

- Make DB-backed tool registration load into the core registry on process startup, not only at registration time.
- Keep gateway execution on registry metadata/callables and retain legacy mock fallback only for demo compatibility.

### Phase 3: Model Event and Provider Interface

Status: partially complete.

Goal: record model interactions as part of the PACT run.

Tasks:

- Add `model_events` table/model.
- Add provider interface.
- Add normalized model request/response objects.
- Record raw and normalized provider payloads.
- Add provenance labels for model outputs.

Acceptance criteria:

- A model request/response appears in run detail and replay.
- Tool calls proposed by a model can be linked to the model event that produced them.

Remaining work:

- Link provider tool calls to PACT action proposals.
- Include model events in replay output.

### Phase 4: Gemini and Bedrock Proxy

Status: partially complete.

Goal: support first real provider middleware.

Tasks:

- Add Gemini provider adapter.
- Add Bedrock provider adapter.
- Add proxy endpoints.
- Add config for provider credentials and model routing.
- Mock external provider calls in tests.

Acceptance criteria:

- A client can call the PACT proxy and receive a Gemini response.
- A client can call the PACT proxy and receive a Bedrock response.
- Requests/responses are recorded in PACT runs.
- No real provider calls are required in CI.

Remaining work:

- Replace Bedrock mock invocation with a real boto3/Bedrock runtime client behind mockable boundaries.
- Add OpenAI-compatible endpoint docs because that adapter now exists.
- Add provider extras/config docs.

### Phase 5: LangChain/LangGraph and Direct Tool Adapters

Status: partially complete.

Goal: make PACT usable from real agent code.

Tasks:

- Add direct `@pact_tool` wrapper.
- Add LangChain tool wrapper.
- Add LangGraph middleware/helper.
- Add examples.
- Add tests with small fake tools.

Acceptance criteria:

- A LangChain tool call is blocked before execution when policy denies it.
- A direct Python tool wrapper executes only after PACT `ALLOW`.
- Blocked and approval-required results are returned in framework-compatible form.

Remaining work:

- Package adapters cleanly.
- Add production fail-closed mode.
- Return structured adapter results.
- Document required `pact_context` and provide helper builders.

### Phase 6: Approval Flow

Status: partially complete.

Goal: turn `REQUIRE_APPROVAL` into a real workflow.

Tasks:

- Add approval model/table.
- Add approval APIs.
- Add dashboard approval UI.
- Add approval token/digest binding.
- Add resume/execute path.

Acceptance criteria:

- Shell action produces pending approval.
- Approver can approve and then exact original action executes.
- Approver can deny and action never executes.
- Replay shows approval request and decision.

Remaining work:

- Wire `ApprovalGatewayService` into every actual gateway/API execution path that can produce `REQUIRE_APPROVAL`.
- Add approval UI.
- Prevent duplicate execution or repeated approval loops on resume.

### Phase 7: Production Storage and Security

Status: started.

Goal: production-grade operational base.

Tasks:

- Add Alembic.
- Add Postgres support.
- Add key IDs and separate issuer roles.
- Add token revocation.
- Add timestamp skew and replay checks.
- Add API authentication.
- Add structured logging.

Acceptance criteria:

- App runs against Postgres.
- Migrations create all tables.
- Replay attack test fails as expected.
- Keys can be rotated without breaking old ledger verification.

Remaining work:

- Add Alembic.
- Add auth.
- Add persistent key revocation and historical key verification.
- Add structured logs/metrics.

### Phase 8: Dashboard and Docs Production Polish

Status: not started in frontend/docs, except this roadmap.

Goal: move from demo to usable protocol product.

Tasks:

- Convert scenario-first UI into operations-first UI.
- Add tool/policy/approval pages.
- Add integration docs.
- Add deployment docs.
- Add protocol conformance examples.

Acceptance criteria:

- A new user can run PACT with a custom tool and Gemini/Bedrock proxy from docs.
- Dashboard can inspect a real provider-backed run.
- Demo scenarios remain available but no longer define the whole product.

## 19. Non-Goals for the Next Immediate Build

Do not start with:

- Managed SaaS billing/multi-plan features.
- Full MCP implementation before provider proxy and tool registry.
- Fully generalized fine-grained taint analysis.
- A complex custom policy language before structured config rules.
- Real Gmail/Slack/Drive integrations before generic tool registration works.
- Rewriting the whole backend from scratch.

## 20. First Concrete Build Slice

The original first slice has mostly been completed. The next concrete build slice should focus on the remaining production gaps rather than adding more placeholder surfaces.

Recommended next slice:

1. Finish runtime convergence.
   - Move remaining production-intended routes through the runtime factory.
   - Leave legacy MVP routes as explicitly documented demo/compatibility paths.

2. Preserve proposal/execution separation.
   - Keep `evaluate/propose` as `dry_run=True`.
   - Keep ledger writes, token consumption, and tool execution behind explicit execution paths.
   - Add regression tests for no ledger write and no token decrement during dry-run.

3. Complete model/provenance event graph.
   - Add provenance events for user/system/developer input messages.
   - Link model-generated tool calls to the model event that produced them.
   - Include model/provenance events in replay output.

4. Complete tool registry lifecycle.
   - Load DB-backed tools into the core registry on startup.
   - Keep side-effect validation strict.
   - Decide how registered external callables are resolved in production.

5. Complete approval execution.
   - Route approval-required execution paths through `ApprovalGatewayService`.
   - Add tests proving approved resume executes once and cannot alter approved args.

6. Complete key management.
   - Persist key revocation.
   - Preserve historical public keys for old ledger/capability verification.
   - Add key ID fields to new protocol artifacts.

7. Operational hardening.
   - Add Alembic.
   - Add API auth.
   - Add structured logs/metrics.
   - Remove accidentally tracked/generated `__pycache__` files from consideration before committing.

This slice keeps the repo from accumulating multiple disconnected production paths.

## 21. Verification Checklist

Before considering the productionization successful:

- Existing MVP tests still pass.
- New production tests cover provider proxy and generic tools.
- No direct raw tool execution path bypasses PACT.
- All provider/framework/v1 integrations converge on the same runtime/gateway.
- Policy decisions are stored for all allowed, blocked, and approval-required actions.
- Ledger/replay verification covers model events, tool actions, approvals, and tamper cases.
- Docs explain both embedded library mode and proxy/sidecar mode.
- Examples include direct Python, LangChain/LangGraph, Gemini, and Bedrock paths.

Current updated verification target:

- `pytest` should pass for the legacy and new test suites.
- `/v1/proxy/chat` creates a run and persists model events.
- `/v1/tools/register` persists to DB and affects gateway policy through the runtime registry.
- `REQUIRE_APPROVAL` creates an approval row and returns real `approval_id`.
- Approving by `approval_id` resumes exactly the original envelope.
- Replaying a run should show model events, action events, policy decisions, and approval decisions in order.
