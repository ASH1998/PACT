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
6. Check operator resource scope (R12)
7. Evaluate policy rules R1–R12 (identity, intent, capability, provenance, approval)
8. Record action to hash-chain ledger
9. Decision: ALLOW / BLOCK / REQUIRE_APPROVAL

## Protocol Primitives

| Primitive | Purpose | Details |
|---|---|---|
| Agent Passport | Identity proof | Ed25519 keypair, expiry |
| Intent Contract | Goal lock | Allowed actions list |
| Operator Grant | Authority ceiling | Allowed tools and resource scope |
| Capability Token | Scoped permission | Tool · resource · expiry · uses |
| Provenance Labels | Data taint tracking | Trusted · untrusted · secret · generated |
| Action Envelope | Verifiable tool call | Signed request payload |
| Hash-Chain Ledger | Tamper evidence | Append-only audit trail |

## Outcomes

- **ALLOW** → Execute tool call
- **BLOCK** → Reject action, log to ledger
- **REQUIRE_APPROVAL** → Pending human review

## Observability

- **SOC Dashboard**: Metrics, trust scores, blocked actions
- **Replay Timeline**: Step-through attack visualization
- **Approval Flow**: Pending action records and resume/deny paths for sensitive actions

## Visual

See [architecture-diagram.html](architecture-diagram.html)
