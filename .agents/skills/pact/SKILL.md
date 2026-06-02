---
name: pact
description: Use PACT to permission-check Codex actions, refuse blocked actions, and monitor activity in the PACT dashboard.
arguments: command
user-invocable: true
argument-hint: "[start | status | check | replay | complete]"
license: MIT
---

# PACT for Codex

This repo exposes `/pact` as a user-invocable skill command. The implementation
lives in `plugins/pact-codex/`.

## Command Routing

Determine the operation from `$command`:

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

## Behavior

Run CLI commands from the repository root:

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

When this skill is active, treat PACT decisions as authoritative:

- `ALLOW`: proceed with the requested action, then attach a concise result.
- `BLOCK`: do not perform the action; tell the user the PACT reasons.
- `REQUIRE_APPROVAL`: pause and ask the user before continuing.

## Commands

Start a session:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py start --goal "<user goal>"
```

Check a proposed action:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py check --tool file.read --args-json '{"path":"README.md"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool file.read_secret --args-json '{"path":".env"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool shell.execute_mock --args-json '{"command":"pytest -q"}'
python3 plugins/pact-codex/scripts/pact_cli.py check --tool web.read --args-json '{"url":"https://example.com"}'
```

After an allowed action, attach a short redacted result:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py attach --action-hash "<hash>" --result-json '{"status":"ok","summary":"..."}'
```

Inspect or finish the active run:

```bash
python3 plugins/pact-codex/scripts/pact_cli.py status
python3 plugins/pact-codex/scripts/pact_cli.py replay
python3 plugins/pact-codex/scripts/pact_cli.py complete
```

## Tool Mapping

- Reading ordinary files: `file.read`
- Reading secrets or secret-looking paths: `file.read_secret`
- Running shell commands, builds, tests, package managers, or scripts:
  `shell.execute_mock`
- Fetching URLs: `web.read`
- Summarizing text: `summarize`
- Responding to the user: `respond_to_user`

## Limitation

This is a user-invocable skill command. It does not install a native pre-tool
hook. Codex must follow the `/pact` workflow for actions to be checked and
recorded in the dashboard.
