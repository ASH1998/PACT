# Governance

PACT uses a lightweight maintainer-led governance model while the project is
pre-1.0. The goal is to keep decisions fast, documented, and careful around
security boundaries.

## Maintainer Responsibilities

Maintainers are responsible for:

- Reviewing and merging pull requests.
- Protecting the security model and project reputation.
- Triaging bugs, feature requests, and vulnerability reports.
- Keeping documentation honest about production readiness and known gaps.
- Cutting releases and publishing advisories when needed.

## Decision Process

Routine fixes and documentation changes can be approved by one maintainer.

Security-sensitive or compatibility-impacting changes should have review from at
least two maintainers when available, or one maintainer plus a written rationale
when the project has only one active maintainer. These include changes to:

- Protocol schemas, canonicalization, signing, verification, or key handling.
- Passport, intent, capability, policy, gateway, provenance, approval, ledger,
  or replay behavior.
- Tool execution, resource scoping, plugin hooks, or client-side enforcement.
- Public security claims, production-readiness statements, or threat-model docs.

When maintainers disagree, prefer the safer option until the risk is understood.
Record important decisions in the relevant issue, pull request, or documentation
file.

## Releases

Before a release, maintainers should verify that:

- Tests relevant to the release have passed.
- Security-sensitive changes have reviewer sign-off.
- Known production gaps are documented.
- Release notes distinguish developer-preview behavior from production-ready
  guarantees.

Pre-1.0 releases may contain breaking changes. Breaking changes should be
intentional, documented, and justified by correctness, security, or project
simplicity.

## Vulnerability Handling

Vulnerabilities are handled privately first through GitHub private vulnerability
reporting. Public issues must not be used for vulnerability details.

For confirmed vulnerabilities, maintainers should:

- Assess impact and affected versions.
- Prepare a fix and regression test where practical.
- Coordinate disclosure timing with the reporter.
- Publish a GitHub advisory when appropriate.

## Adding Maintainers

Maintainers may add new maintainers when a contributor has shown sustained,
high-quality judgment, especially in security-sensitive review. New maintainers
should understand the protocol, threat model, and current production-readiness
limits before receiving broad repository permissions.
