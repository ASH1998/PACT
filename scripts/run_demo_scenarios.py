#!/usr/bin/env python3
"""Run deterministic PACT demo scenarios against a local backend."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


DEFAULT_SCENARIOS = [
    "normal_email_summary",
    "malicious_email_injection",
    "secret_exfiltration",
    "shell_execute_approval",
]

EXPECTED = {
    "normal_email_summary": "ALLOW",
    "malicious_email_injection": "BLOCK",
    "secret_exfiltration": "BLOCK",
    "shell_execute_approval": "REQUIRE_APPROVAL",
}


def request_json(method: str, url: str) -> dict:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc
    return json.loads(body)


def latest_decision(backend: str, run_id: str) -> tuple[str | None, list[str]]:
    replay = request_json("GET", f"{backend}/runs/{run_id}/replay")
    steps = replay.get("steps", [])
    if not steps:
        return None, []
    decision = steps[-1].get("policy_decision", {}).get("decision")
    reasons = steps[-1].get("policy_decision", {}).get("reasons") or []
    return decision, reasons


def run_scenario(backend: str, name: str) -> tuple[bool, str]:
    expected = EXPECTED.get(name)
    result = request_json("POST", f"{backend}/scenarios/run/{name}")
    run_id = result["run_id"]
    decision, reasons = latest_decision(backend, run_id)
    ledger = request_json("GET", f"{backend}/runs/{run_id}/ledger/verify")

    ok = decision == expected and ledger.get("valid") is True
    status = "PASS" if ok else "FAIL"
    print(f"{status} {name}")
    print(f"  run_id: {run_id}")
    print(f"  expected: {expected}")
    print(f"  actual:   {decision}")
    print(f"  ledger:   {ledger.get('valid')}")
    if reasons:
        print("  reasons:")
        for reason in reasons:
            print(f"    - {reason}")
    return ok, run_id


def run_tamper_demo(backend: str, run_id: str) -> bool:
    result = request_json("POST", f"{backend}/runs/{run_id}/tamper")
    ok = result.get("ledger_valid_after_tamper") is False and bool(result.get("issues"))
    status = "PASS" if ok else "FAIL"
    print(f"{status} ledger_tamper_detection")
    print(f"  run_id: {run_id}")
    print(f"  tampered_field: {result.get('tampered_field')}")
    print(f"  ledger_valid_after_tamper: {result.get('ledger_valid_after_tamper')}")
    for issue in result.get("issues", []):
        print(f"    - {issue}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--tamper", action="store_true", help="Run ledger tamper demo")
    parser.add_argument("scenarios", nargs="*", default=DEFAULT_SCENARIOS)
    args = parser.parse_args()

    backend = args.backend.rstrip("/")
    try:
        request_json("GET", f"{backend}/health")
    except Exception as exc:
        print(f"Backend is not reachable at {backend}: {exc}", file=sys.stderr)
        return 2

    all_ok = True
    first_run_id = ""
    for scenario in args.scenarios:
        ok, run_id = run_scenario(backend, scenario)
        all_ok = all_ok and ok
        first_run_id = first_run_id or run_id

    if args.tamper and first_run_id:
        all_ok = run_tamper_demo(backend, first_run_id) and all_ok

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
