# /pact

Start, check, monitor, replay, or complete a PACT-protected Codex session.

## Arguments

- `command`: `start`, `status`, `check`, `replay`, or `complete` (optional)
- `goal`: session goal text for `start` (optional)
- `tool`: PACT tool id for `check` (optional)
- `args`: JSON object for `check` (optional)

## Workflow

1. If no command is provided, show the PACT command menu.
2. For `start`, run:
   ```bash
   python3 plugins/pact-codex/scripts/pact_cli.py start --goal "<goal>"
   ```
   Use the current user request as the goal when no explicit goal is provided.
3. For `status`, run:
   ```bash
   python3 plugins/pact-codex/scripts/pact_cli.py status
   ```
4. For `check`, map the proposed action to a PACT tool and run:
   ```bash
   python3 plugins/pact-codex/scripts/pact_cli.py check --tool <tool> --args-json '<json>'
   ```
5. For `replay`, run:
   ```bash
   python3 plugins/pact-codex/scripts/pact_cli.py replay
   ```
6. For `complete`, run:
   ```bash
   python3 plugins/pact-codex/scripts/pact_cli.py complete
   ```

## Tool Mapping

- Reading ordinary files: `file.read`
- Reading secrets or secret-looking paths: `file.read_secret`
- Running shell commands, tests, builds, package managers, or scripts:
  `shell.execute_mock`
- Fetching URLs: `web.read`
- Summarizing text: `summarize`
- Responding to the user: `respond_to_user`

## Decision Rules

- `ALLOW`: proceed with the requested action and attach a concise result summary.
- `BLOCK`: refuse the action and show the PACT reasons.
- `REQUIRE_APPROVAL`: pause and ask the user before continuing.

## Menu

When invoked without arguments, show:

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

## Guardrails

- Do not run a blocked action through native Codex tools.
- Do not attach raw secrets in result summaries.
- If the backend is unavailable, report the CLI's backend start command.
- This command records actions routed through `/pact`; it is not a native
  pre-tool hook for actions that bypass `/pact`.
