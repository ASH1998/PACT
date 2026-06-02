---
name: pact
description: Use when the user types /pact, asks to run a PACT-protected Claude Code session, wants native tool calls (Bash/Read/Edit/Write/WebFetch) permission-checked against signed intent + capability policy, or wants PACT dashboard monitoring/replay. The argument after /pact is one of [start | status | check | replay | complete].
argument-hint: "[start | status | check | replay | complete]"
allowed-tools:
  - Bash
  - Read
---

# PACT for Claude Code

PACT is a permission + audit layer. This plugin makes PACT enforce Claude Code's
own actions: after `/pact start`, a **PreToolUse hook** routes every native
`Bash`, `Read`, `Edit`, `Write`, `MultiEdit`, and `WebFetch` call through the
PACT gateway, and the decision (ALLOW / REQUIRE_APPROVAL / BLOCK) is recorded in
the dashboard. Unlike an advisory checklist, this is real interception.

## Prerequisites

- PACT backend running on `http://localhost:8000` (override with `PACT_BASE_URL`).
- PACT frontend running, to watch decisions live.
- Repo virtualenv at `./.venv` (has PyNaCl) or run via `uv` (see below).

## Command Routing

Determine the operation from the argument after `/pact`:

| Input | Operation |
|---|---|
| empty / no args | Show the `/pact` menu |
| `start` | Start (or reset) the active PACT session and arm the hook |
| `status` | Show active run, grant, last decision, and ledger status |
| `check ...` | Manually check one proposed action (the hook does this automatically) |
| `replay` | Show replay and ledger verification for the active run |
| `complete` | Mark the active run completed |

If the user types `/pact` with no arguments, show:

```text
PACT for Claude Code

  /pact start       -> create an audited PACT session (enables the PreToolUse hook)
  /pact status      -> show run, grant, last decision, ledger
  /pact check       -> manually authorize a single proposed action
  /pact replay      -> show recorded steps and ledger verification
  /pact complete    -> mark the active run completed

Run /pact start, then work normally — native tool calls are PACT-checked.
```

## CLI

Run from the repository root, preferring the venv Python. **Pick the path for
the current OS** — the virtualenv interpreter lives in a different place on
Windows than on POSIX:

```bash
# macOS / Linux / WSL
.venv/bin/python plugins/pact-claude/scripts/pact_cli.py <command>
```

```powershell
# Windows (PowerShell or cmd)
.venv\Scripts\python.exe plugins\pact-claude\scripts\pact_cli.py <command>
```

If you are unsure of the platform, run with a bare `python3`/`python` on PATH —
the CLI auto-re-execs into the repo virtualenv (`.venv/bin/python` on POSIX,
`.venv\Scripts\python.exe` on Windows) when `nacl` is missing:

```bash
python plugins/pact-claude/scripts/pact_cli.py <command>
```

Fallback when there is no `.venv`:

```bash
uv run --project backend --active python plugins/pact-claude/scripts/pact_cli.py <command>
```

## Workflow

### `/pact start`

```bash
python plugins/pact-claude/scripts/pact_cli.py start --goal "<user goal>"
```

Use `--grant <path>` for a custom operator grant. Report the `run_id` and tell
the user that native tool calls are now PACT-checked and visible in the
dashboard. If the backend is unavailable, surface the start command from the
CLI error.

### Working under PACT

After `start`, **just work normally**. The PreToolUse hook authorizes each
native tool call automatically:

- **ALLOW** — the call proceeds; recorded in the ledger.
- **REQUIRE_APPROVAL** — Claude Code prompts the user; do not proceed until they
  answer.
- **BLOCK** — the call is denied; explain the PACT reasons and do not retry it
  through another tool.

Do not try to bypass a BLOCK with a different native tool.

### `/pact check` (manual, optional)

```bash
python plugins/pact-claude/scripts/pact_cli.py check --tool file.read --args-json '{"path":"README.md"}'
python plugins/pact-claude/scripts/pact_cli.py check --tool shell.execute_mock --args-json '{"command":"pytest -q"}'
```

### Attach a result (optional)

```bash
python plugins/pact-claude/scripts/pact_cli.py attach --action-hash "<hash>" --result-json '{"status":"ok","summary":"..."}'
```

Keep summaries short and redacted — never attach raw secrets.

### `/pact status`, `/pact replay`, `/pact complete`

```bash
python plugins/pact-claude/scripts/pact_cli.py status
python plugins/pact-claude/scripts/pact_cli.py replay
python plugins/pact-claude/scripts/pact_cli.py complete
```

## Tool Mapping (native -> PACT)

The hook applies this mapping automatically; use it too for manual `check`:

| Native | PACT tool |
|---|---|
| `Read` (normal path) | `file.read` |
| `Read` (secret-looking path: `.env`, `*.pem`, `*secret*`, `*token*`, ...) | `file.read_secret` |
| `Edit` / `Write` / `MultiEdit` | `file.write` |
| `Bash` | `shell.execute_mock` |
| `WebFetch` / `WebSearch` | `web.read` |

## Behavior Rules

- If no PACT session exists and the user asks for protected work, run `start`
  first.
- The hook fails **open**: with no session, a down backend, or an unmapped tool,
  it stays silent and Claude Code uses its normal permission flow. Enforcement
  begins only after `/pact start`.
- The hook never intercepts PACT's own CLI/scripts (no recursion).
- Do not widen the grant yourself.
- Mention the `run_id` so the user can inspect the dashboard.

## Limitation

The hook covers the tools listed in its matcher. Actions outside those tools
(e.g. MCP tools) are not yet mapped to PACT capabilities.
