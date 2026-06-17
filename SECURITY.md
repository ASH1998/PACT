# Security Policy

PACT is a pre-1.0 security project. It demonstrates signed action envelopes,
scoped capabilities, policy decisions, provenance/taint tracking, approvals,
and audit replay for AI-agent tool calls, but it is not production-ready unless
a future release states that explicitly.

## Supported Versions

Security fixes are expected to target the current `main` branch and the latest
tagged release, if any. Pre-1.0 APIs, schemas, and storage formats may change
while the project hardens.

## Reporting a Vulnerability

Report vulnerabilities through GitHub private vulnerability reporting first:

<https://github.com/ASH1998/PACT/security/advisories/new>

Do not open a public GitHub issue, discussion, pull request, or social post for
a suspected vulnerability. Public reports can put users and downstream projects
at risk before maintainers have had time to assess and coordinate a fix.

If GitHub private vulnerability reporting is unavailable, contact a maintainer
privately and ask for a secure reporting channel. Keep details limited until a
private channel is established.

## What To Include

Please include:

- Affected commit, release, or branch.
- Clear reproduction steps or a proof of concept.
- Expected impact and affected security boundary.
- Whether the issue involves signed envelopes, capability scope, policy
  decisions, provenance/taint, approvals, replay, plugins, or local tool
  execution.
- Any logs or screenshots that do not expose secrets.

## Scope

In scope examples:

- Bypassing envelope signature, passport, capability, or intent validation.
- Widening tool or resource authority beyond an operator grant.
- Incorrect `ALLOW`, `BLOCK`, or `REQUIRE_APPROVAL` decisions.
- Secret or untrusted data flowing to external sinks without enforcement.
- Approval bypasses or replay/audit evidence tampering.
- Plugin, TUI, or gateway behavior that executes tools without the expected
  PACT decision.

Out of scope examples:

- Findings that require running untrusted code outside PACT's documented threat
  model.
- Denial-of-service issues against local demo-only deployments without a
  security boundary impact.
- Reports about dependencies with no demonstrated exploit path in this project.

## Maintainer Response

Maintainers should acknowledge private reports within 72 hours when possible,
triage impact, and keep the reporter updated until resolution or closure. Fixes
for confirmed vulnerabilities should include regression tests or a written
reason when tests are not practical.

Coordinated disclosure is preferred. A 90-day disclosure window is the default
target unless the reporter and maintainers agree on a different timeline.
Maintainers may publish a security advisory after a fix is available or after
agreeing on disclosure timing with the reporter.
