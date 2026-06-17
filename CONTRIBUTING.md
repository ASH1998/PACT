# Contributing

PACT is an MIT-licensed, pre-1.0 security project for protecting AI-agent tool
calls with signed envelopes, scoped capabilities, policy decisions,
provenance/taint, approvals, and audit replay. Contributions are welcome, but
security-sensitive changes need careful review and tests.

## Current Status

PACT is not production-ready unless a future release says otherwise. The current
codebase is a developer preview and demo/MVP. Avoid wording in code, docs, or
examples that implies production readiness, complete isolation, or formal
security certification.

## Setup

Prerequisites:

- Python 3.10+
- Node.js 18+
- Go 1.26+ for the TUI
- `uv` for backend dependency management

Backend:

```bash
uv venv .venv
source .venv/bin/activate
uv sync --project backend --active --extra dev --link-mode=copy
cp backend/.env.example backend/.env
uv run --project backend --active uvicorn app.main:app --app-dir backend --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Go TUI:

```bash
cd clients/pact-tui
make build
./bin/pact-tui --provider claude
```

## Tests

Run the checks that match your change:

```bash
uv run --project backend --active pytest -q -c backend/pyproject.toml backend/tests
```

```bash
cd frontend
npm run build
npm test
```

```bash
cd clients/pact-tui
make test
PACT_E2E=1 make e2e
```

For a lightweight CLI import check:

```bash
python3 pact_chat.py --help
```

If a test is not run, say why in the pull request.

## Security-Sensitive Areas

Treat these areas as security-sensitive:

- Protocol schemas and canonicalization under `protocol/` and
  `backend/app/crypto/`.
- Passport, envelope, intent, capability, policy, gateway, provenance, ledger,
  approval, and replay code under `backend/app/core/`,
  `backend/app/services/`, `backend/app/api/v1/`, and `backend/app/models/`.
- Tool execution and resource extraction under `backend/app/tools/`.
- Agent adapters, clients, and plugins under `backend/app/adapters/`,
  `clients/pact-tui/`, `plugins/pact-codex/`, and `plugins/pact-claude/`.
- Documentation that describes the security model, threat model, or production
  readiness.

Changes in these areas should explain the security boundary, include regression
tests for allow/block/approval behavior, and avoid broadening authority without
explicit maintainer review.

## Pull Requests

Good pull requests are small, reviewable, and explicit about risk. Please:

- Describe the problem, approach, and user-visible behavior.
- Link related issues when available.
- Include tests or explain why tests are not practical.
- Update relevant docs when behavior, setup, protocol, or security assumptions
  change.
- Keep unrelated formatting, generated data, and refactors out of the PR.
- Avoid committing secrets, local `.env` files, private keys, or real customer
  data.

Breaking changes are acceptable before 1.0 when they improve correctness or
security, but they should be called out clearly.

## Certificate of Origin / CLA

PACT does not currently require a Contributor License Agreement. By opening a
pull request, you agree that your contribution may be distributed under the
project's MIT license. Maintainers may add a CLA or DCO process later if the
project needs one.

## Security Reports

Do not report vulnerabilities in public issues. Use the private process in
`SECURITY.md`.
