# PACT for Claude Code

Run a **PACT-protected Claude Code session**. After `/pact start`, a
`PreToolUse` hook intercepts every native `Bash`, `Read`, `Edit`, `Write`,
`MultiEdit`, and `WebFetch` call, routes it through the PACT gateway (signed
intent + capability policy), and records the decision — `ALLOW`,
`REQUIRE_APPROVAL`, or `BLOCK` — in the PACT dashboard in real time.

This is the Claude Code counterpart to `plugins/pact-codex`. The difference:
Codex is advisory (the model must opt in via `/pact check`), whereas Claude Code
**actually enforces** through a real pre-tool hook.

## Layout

```
plugins/pact-claude/
├── .claude-plugin/plugin.json   # plugin manifest
├── commands/pact.md             # /pact slash command
├── skills/pact/SKILL.md         # model-invocable skill
├── hooks/hooks.json             # PreToolUse interceptor registration
├── scripts/
│   ├── pact_cli.py              # start/status/check/replay/complete CLI
│   ├── pact_hook.py             # PreToolUse hook -> PACT gateway
│   └── run_hook.sh              # picks venv python, pipes stdin to the hook
└── assets/default-grant.yaml    # conservative default capability grant
```

## Demo setup

1. **Backend** (port 8000):

   ```bash
   uv run --project backend --active uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

2. **Frontend** (the dashboard):

   ```bash
   cd frontend && npm run dev
   ```

3. **Install the plugin** in Claude Code, from the repo root:

   ```text
   /plugin marketplace add .
   /plugin install pact-claude@pact
   ```

   Or launch Claude Code with the plugin loaded directly:

   ```bash
   claude --plugin-dir ./plugins/pact-claude
   ```

4. **Use it:**

   ```text
   /pact start
   ```

   Then work normally. Each native tool call is PACT-checked; open the dashboard
   and watch the run's ledger update live. Inspect or finish with `/pact status`,
   `/pact replay`, `/pact complete`.

## Behavior

- **Fails open.** With no active session, a down backend, or an unmapped tool,
  the hook stays silent and Claude Code uses its normal permission flow.
  Enforcement starts only after `/pact start`.
- **No recursion.** The hook never intercepts PACT's own CLI/scripts.
- **Conservative grant.** The default grant allows reads/web/summarize/respond;
  writes, secret reads, and shell execution require approval. Supply a wider
  operator grant with `/pact start --grant <path>`.

## Configuration

- `PACT_BASE_URL` — backend URL (default `http://localhost:8000`).
- Session state: `.pact/claude-session.json` (created by `/pact start`, mode 600).
