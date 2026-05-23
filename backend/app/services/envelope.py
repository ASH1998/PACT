from __future__ import annotations
"""Envelope Service — create and verify PACT action envelopes."""

from datetime import datetime, timezone

from app.crypto import sign, verify, canonical_json, hash_payload
from app.schemas import ActionEnvelope, ProvenanceContext


class EnvelopeService:
    """Handles action envelope creation and verification."""

    def create_envelope(
        self,
        agent_id: str,
        agent_private_key: str,
        run_id: str,
        step_id: int,
        tool: str,
        args: dict,
        intent_hash: str,
        capability_token_hash: str,
        provenance: dict,
        parent_action_hash: str | None = None,
    ) -> dict:
        """Create a signed PACT action envelope."""
        args_digest = hash_payload(args)

        # Build envelope (without signature)
        envelope_data = {
            "protocol": "PACT/0.1",
            "run_id": run_id,
            "step_id": step_id,
            "agent_id": agent_id,
            "tool": tool,
            "args": args,
            "args_digest": args_digest,
            "intent_hash": intent_hash,
            "capability_token_hash": capability_token_hash,
            "provenance": provenance,
            "parent_action_hash": parent_action_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Sign: canonicalize everything except agent_signature
        payload = canonical_json(envelope_data)
        signature = sign(agent_private_key, payload)
        envelope_data["agent_signature"] = signature

        return envelope_data

    def verify_envelope(self, envelope: dict, agent_public_key: str) -> tuple[bool, str]:
        """Verify an envelope's signature and field consistency."""
        # Extract signature
        sig = envelope.get("agent_signature")
        if not sig:
            return False, "Missing agent_signature"

        # Reconstruct payload (without signature)
        envelope_copy = {k: v for k, v in envelope.items() if k != "agent_signature"}
        payload = canonical_json(envelope_copy)

        # Verify signature
        if not verify(agent_public_key, payload, sig):
            return False, "Invalid signature"

        # Verify args_digest
        expected_digest = hash_payload(envelope.get("args", {}))
        if envelope.get("args_digest") != expected_digest:
            return False, "args_digest mismatch"

        # Verify protocol version
        if envelope.get("protocol") != "PACT/0.1":
            return False, "Unsupported protocol version"

        return True, "Valid"
