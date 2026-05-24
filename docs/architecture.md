# PACT Architecture

## Protocol Flow

```
User → Agent Runtime → PACT Envelope → Tool Gateway → Policy Engine → Allow/Block → Ledger → SOC
```

## Gateway Steps

1. Verify envelope shape & protocol version
2. Verify agent Ed25519 signature
3. Verify agent passport (identity, expiry)
4. Load intent contract (allowed/forbidden actions)
5. Validate capability token (scope, expiry, uses)
6. Evaluate policy rules R1–R10 (provenance + risk)
7. Record action to hash-chain ledger
8. Decision: ALLOW / BLOCK / REQUIRE_APPROVAL

## Protocol Primitives

| Primitive | Purpose | Details |
|---|---|---|
| Agent Passport | Identity proof | Ed25519 keypair, expiry |
| Intent Contract | Goal lock | Allowed actions list |
| Capability Token | Scoped permission | Scope · expiry · uses |
| Provenance Labels | Data taint tracking | Source · transform chain |
| Action Envelope | Verifiable tool call | Signed request payload |
| Hash-Chain Ledger | Tamper evidence | Append-only audit trail |

## Outcomes

- **ALLOW** → Execute tool call
- **BLOCK** → Reject action, log to ledger
- **REQUIRE_APPROVAL** → Pending human review

## Observability

- **SOC Dashboard**: Metrics, trust scores, blocked actions
- **Replay Timeline**: Step-through attack visualization

## Visual

See [architecture-diagram.html](architecture-diagram.html)
