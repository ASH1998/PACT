---
name: pact
description: Use when the user types /pact, asks to use PACT, wants Codex actions permission-checked before execution, or wants PACT dashboard monitoring/replay for Codex work. The argument after /pact is one of [start | status | check | replay | complete].
---

# PACT for Codex

PACT is an advisory permission and audit layer for Codex. Use the local CLI in
this plugin to create a PACT run, check proposed actions before using native
Codex tools, refuse blocked actions, and record allowed/blocked decisions for
the PACT dashboard.

## Important Limitation

This plugin does not install a native Codex pre-tool hook. It cannot forcibly
intercept every built-in Codex file, shell, or web action. It provides a
`/pact` workflow that Codex must follow when the user asks for PACT-protected
work.

When this skill is active, treat PACT decisions as authoritative:

- `ALLOW`: proceed with the requested action, then attach a concise result.
- `BLOCK`: do not perform the action; tell the user the PACT reasons.
- `REQUIRE_APPROVAL`: pause and ask the user before continuing.

## Command Routing

Determine the operation from the argument the user typed after `/pact`:

| Input | Operation |
|---|---|
| empty / no args | Show the `/pact` menu |
| `start` | Start or reset the active PACT Codex session |
| `status` | Show active run, grant, last decision, and ledger status |
| `check ...` | Check a proposed action before using native Codex tools |
| `replay` | Show replay and ledger verification for the active run |
| `complete` | Mark the active run completed |

If the user says `/pact` with no arguments, show:

```text
PACT for Codex

Available commands:
  /pact start       -> create an audited PACT session
  /pact status      -> show run, grant, last decision, ledger
  /pact check       -> authorize a proposed action before tool use
  /pact replay      -> show recorded steps and ledger verification
  /pact complete    -> mark the active run completed

Use /pact start before protected work.
```

## CLI

Run commands from the repository root:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py <command>
```

(On Windows, use `python` instead of `python3`.)

If Python cannot import `nacl`, the CLI automatically re-execs through the repo
virtualenv — `.venv/bin/python` on POSIX or `.venv\Scripts\python.exe` on
Windows, checking both the root `.venv` and `backend/.venv`. Otherwise run
through the backend environment:

```bash
uv run --project backend --active python plugins/pact-codex/scripts/pact_cli.py <command>
```

The CLI uses `PACT_BASE_URL` when set, otherwise `http://localhost:8000`.

## Slash Workflow

### `/pact start`

Start an audited Codex session:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py start --goal "<user goal>"
```

Use `--grant <path>` when the user supplies a custom operator grant. If the
backend is unavailable, report the returned start command to the user.

### `/pact status`

Show the current run, allowed tools, blocked tools, last decision, and ledger
status:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py status
```

### `/pact check`

Before a risky native action, call `check`.

Examples:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py check --tool file.read --args-json '{"path":"README.md"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool file.read_secret --args-json '{"path":".env"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool shell.execute_mock --args-json '{"command":"pytest -q"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool web.read --args-json '{"url":"https://example.com"}'
```

Use these mappings:

- Reading ordinary files: `file.read`
- Reading secrets or secret-looking paths: `file.read_secret`
- Running shell commands, builds, tests, package managers, or scripts:
  `shell.execute_mock`
- Fetching URLs: `web.read`
- Summarizing text: `summarize`
- Responding to the user: `respond_to_user`

### Attach Results

After an allowed action completes, attach a short result summary. Do not attach
raw secrets.

```bash
python3 plugins/pact-codex/scripts/pact_cli.py attach --action-hash "<hash>" --result-json '{"status":"ok","summary":"..."}'
```

### Replay and Complete

```bash
python3 plugins/pact-codex/scripts/pact_cli.py replay
python3 plugins/pact-codex/scripts/pact_cli.py complete
```

## Behavior Rules

- If no PACT session exists, run `start` before `check`.
- Do not widen the grant yourself. Use only the active grant path or the plugin
  default grant.
- If PACT blocks an action, do not perform it with native Codex tools.
- If PACT requires approval, ask the user and do not continue until they answer.
- Keep attached results short and redacted.
- Mention the run ID so the user can inspect the dashboard.
