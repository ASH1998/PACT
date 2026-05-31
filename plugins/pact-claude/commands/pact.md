---
description: Start, monitor, replay, or complete a PACT-protected Claude Code session. While a session is active, native tool calls are checked by the PACT PreToolUse hook.
argument-hint: "[start | status | check | replay | complete]"
allowed-tools:
  - Bash
  - Read
---

# /pact

Subcommand: **$1** (full args: `$ARGUMENTS`)

Run the PACT CLI from the repository root. Prefer the repo virtualenv so PyNaCl
is available for envelope signing:

```bash
.venv/bin/python plugins/pact-claude/scripts/pact_cli.py <command>
```

If `.venv` is missing, fall back to:

```bash
uv run --project backend --active python plugins/pact-claude/scripts/pact_cli.py <command>
```

The CLI talks to the backend at `PACT_BASE_URL` (default `http://localhost:8000`).

## Routing

| `$1` | Do this |
|---|---|
| empty | Show the menu below. Do not run the CLI. |
| `start` | `pact_cli.py start --goal "<goal>"` — use the user's current request as the goal when none is given. Then tell the user the `run_id` and that native tool calls are now PACT-checked. |
| `status` | `pact_cli.py status` |
| `check` | `pact_cli.py check --tool <tool> --args-json '<json>'` (manual one-off check; the hook does this automatically during normal work) |
| `replay` | `pact_cli.py replay` |
| `complete` | `pact_cli.py complete` |

## How enforcement works

Once `/pact start` has run, the plugin's **PreToolUse hook** intercepts every
native `Bash`, `Read`, `Edit`, `Write`, `MultiEdit`, and `WebFetch` call,
routes it through the PACT gateway, and:

- **ALLOW** — the tool runs; the decision is recorded in the dashboard.
- **REQUIRE_APPROVAL** — Claude Code prompts you before running.
- **BLOCK** — the tool is denied; PACT reasons are shown.

You do not need to call `/pact check` by hand during normal work — the hook
handles it. Open the PACT frontend and watch the run's ledger update live.

## Manual tool mapping (for `/pact check`)

- Read ordinary files: `file.read`
- Read secrets / secret-looking paths: `file.read_secret`
- Write or edit files: `file.write`
- Shell commands, builds, tests, scripts: `shell.execute_mock`
- Fetch URLs: `web.read`
- Summarize: `summarize`; respond: `respond_to_user`

## Menu (show when `$1` is empty)

```text
PACT for Claude Code

  /pact start       -> create an audited PACT session (enables the PreToolUse hook)
  /pact status      -> show run, grant, last decision, ledger
  /pact check       -> manually authorize a single proposed action
  /pact replay      -> show recorded steps and ledger verification
  /pact complete    -> mark the active run completed

Run /pact start, then work normally — native tool calls are PACT-checked and
streamed to the dashboard. Make sure the backend (port 8000) and frontend are up.
```

## Guardrails

- If the backend is down, report the start command from the CLI error.
- Do not widen the grant yourself; use the default grant or an operator-supplied
  `--grant <path>`.
- Never echo raw secrets into result summaries.
