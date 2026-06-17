## Summary

-

## Testing

- [ ] Backend tests: `uv run --project backend --active pytest -q -c backend/pyproject.toml backend/tests`
- [ ] Frontend build/tests: `cd frontend && npm run build && npx vitest run`
- [ ] Go TUI tests: `cd clients/pact-tui && make test`
- [ ] Not applicable; docs-only or tooling-only change

## Security Considerations

- [ ] This change does not affect signing, verification, capability issuance,
      policy decisions, provenance, approvals, ledger integrity, or secret
      handling.
- [ ] This change affects security-sensitive behavior and includes tests or a
      written rationale.
- [ ] This PR does not disclose secrets, credentials, private keys, or
      vulnerability details that should be reported privately.
