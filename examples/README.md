# PACT Runnable Examples

These examples are the fastest way to verify PACT's current demo/MVP behavior
from a clean local checkout.

PACT is pre-1.0. The examples run local demo authority endpoints with
`PACT_INSECURE_DEMO_API=true`; do not expose those endpoints on an untrusted
network. Production deployments still need authenticated, tenant-scoped
authority services.

## One-Command Demo

From the repository root:

```bash
./scripts/live_demo.sh
```

The script starts the backend if it is not already running, runs deterministic
scenarios through the gateway, verifies the ledger, runs a tamper-detection
check, prints expected and actual decisions, and then stops the backend it
started.

The output includes volatile `run_id` values and action hashes, so yours will
differ. The stable contract is the final decision and policy reason text for
each scenario.

If your backend is already running:

```bash
PACT_BACKEND_URL=http://127.0.0.1:8000 ./scripts/live_demo.sh
```

## Individual Scenario Runner

With the backend running:

```bash
python3 scripts/run_demo_scenarios.py --tamper
```

Run selected scenarios:

```bash
python3 scripts/run_demo_scenarios.py normal_email_summary malicious_email_injection
```

## Expected Outcomes

| Scenario | Expected final decision | What it demonstrates |
|---|---|---|
| `normal_email_summary` | `ALLOW` | In-scope read/summarize/respond workflow succeeds. |
| `malicious_email_injection` | `BLOCK` | Untrusted email influence plus unauthorized external write is blocked. |
| `secret_exfiltration` | `BLOCK` | Secret data cannot flow to an external sink. |
| `shell_execute_approval` | `REQUIRE_APPROVAL` | Shell execution pauses for human approval. |
| `ledger_tamper_detection` | invalid ledger | Modifying stored ledger evidence causes verification to fail. |

The important distinction is allowlist behavior: an in-scope workflow is
allowed, while out-of-scope or tainted external writes are blocked because they
violate authority and data-flow policy, not because a keyword was matched.

## Dashboard

To inspect the same runs visually:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and browse the newest runs.
