# PACT agent TUI

A full-screen terminal UI for a PACT-protected agent — the Go/Bubble Tea
successor to `pact_chat.py`. Same functionality, real TUI.

Unlike the Python CLI (which imports the PACT runtime in-process), this is a
**real client of the PACT gateway over HTTP** — exactly how an enterprise
integration would work:

1. registers an agent passport (`POST /v1/agents/register`) and holds its
   Ed25519 private key,
2. registers tool metadata, creates the intent (operator-grant tools + resource
   scope) and a run,
3. for each tool call: issues a capability, **signs the Action Envelope locally**
   (Ed25519 over canonical JSON, byte-for-byte identical to the backend),
   submits it to the gateway for a decision, and only on `ALLOW` executes the
   tool **on this machine**, then posts the result back,
4. streams every decision into the dashboard ledger.

The agent can never widen its own authority: the operator grant is the ceiling,
and out-of-scope resources are blocked structurally (R12) — no keyword
matching.

## Build & run

Requires Go 1.26+. If you don't have Go and can't `sudo`, install it locally:

```bash
curl -L https://go.dev/dl/$(curl -s https://go.dev/VERSION?m=text).linux-amd64.tar.gz \
  | tar -C "$HOME/.local" -xz
export PATH="$HOME/.local/go/bin:$PATH"
```

Then, with the PACT backend running (`cd backend && uvicorn app.main:app --port 8000`):

```bash
cd clients/pact-tui
make build
./bin/pact-tui --provider claude          # or: go run . --provider auto

# Widen authority with an operator grant (deny-by-default otherwise):
./bin/pact-tui --provider claude --grant ../../examples/grant.acme.yaml
```

Provider keys are read from `../../.env` and `../../backend/.env` (same as the
Python CLI): `CLAUDE_API_KEY`, `GOOGLE_API_KEY`/`GEMINI_API_KEY`, or AWS creds
for Bedrock.

### Flags

| Flag | Default | Meaning |
|---|---|---|
| `--provider` | `auto` | `auto` / `claude` / `gemini` / `bedrock` |
| `--model` | env | Override `CLAUDE_MODEL` / `GOOGLE_MODEL` |
| `--goal` | generic | Intent contract goal recorded in PACT |
| `--grant` | built-in | Operator grant YAML (tools + resource scope) |
| `--backend` | `http://localhost:8000` | PACT backend base URL |
| `--dashboard` | `http://localhost:5173` | Dashboard base URL (shown in the sidebar) |
| `--repo-root` | `.` | Root the file/shell tools operate within |

### In-session

- Type to chat. Tool calls are decided by PACT before they run.
- Color-coded cards: **green** ALLOW · **amber** REQUIRE_APPROVAL · **red** BLOCK.
- When a tool needs approval, the prompt switches to `y / n`.
- Commands: `/help` `/tools` `/ledger` `/run` `/quit`. `ctrl+u`/`ctrl+d` scroll.

## Layout

```
main.go                 flags, .env loading, wiring
internal/pact/          canonical JSON + Ed25519 signing + HTTP gateway client
internal/grant/         operator grant model + YAML loader (mirrors grants.py)
internal/provider/      Claude / Gemini / Bedrock chat providers
internal/tools/         local tool implementations (web/file/email/shell/...)
internal/agent/         turn orchestration (model <-> gateway <-> tools)
internal/ui/            Bubble Tea model, views, styles
cmd/parity/             dev helper for the cross-language crypto parity check
```

## Tests

```bash
make test                 # crypto parity + canonical JSON (no backend needed)
make e2e                  # full flow against a running backend (PACT_E2E=1)
```

`internal/pact` pins the canonical-JSON args digest to the value the Python
backend produces, so any divergence in envelope serialization fails the build.
