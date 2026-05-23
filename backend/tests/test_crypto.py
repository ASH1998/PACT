"""Test: crypto service — Ed25519 keys, signing, verification, hashing."""

import pytest
from app.crypto import generate_keypair, sign, verify, canonical_json, hash_payload, hash_bytes


class TestKeypair:
    def test_generate_keypair_returns_two_strings(self):
        private, public = generate_keypair()
        assert isinstance(private, str)
        assert isinstance(public, str)
        assert len(private) > 0
        assert len(public) > 0

    def test_generate_keypair_unique(self):
        priv1, pub1 = generate_keypair()
        priv2, pub2 = generate_keypair()
        assert priv1 != priv2
        assert pub1 != pub2


class TestSigning:
    def test_sign_and_verify_roundtrip(self):
        private, public = generate_keypair()
        payload = b"test message"
        sig = sign(private, payload)
        assert verify(public, payload, sig) is True

    def test_verify_rejects_tampered_message(self):
        private, public = generate_keypair()
        payload = b"original message"
        sig = sign(private, payload)
        assert verify(public, b"tampered message", sig) is False

    def test_verify_rejects_wrong_key(self):
        priv1, pub1 = generate_keypair()
        priv2, pub2 = generate_keypair()
        payload = b"test"
        sig = sign(priv1, payload)
        assert verify(pub2, payload, sig) is False


class TestCanonicalJson:
    def test_sorted_keys(self):
        data = {"z": 1, "a": 2, "m": 3}
        result = canonical_json(data)
        assert b'"a":2' in result
        assert result.index(b'"a"') < result.index(b'"m"')
        assert result.index(b'"m"') < result.index(b'"z"')

    def test_no_whitespace(self):
        data = {"key": "value", "list": [1, 2]}
        result = canonical_json(data)
        assert b" " not in result
        assert b"\n" not in result

    def test_deterministic(self):
        data = {"b": 2, "a": 1}
        assert canonical_json(data) == canonical_json(data)


class TestHashing:
    def test_hash_payload_format(self):
        result = hash_payload({"key": "value"})
        assert result.startswith("sha256:")
        assert len(result) == 71  # "sha256:" + 64 hex chars

    def test_hash_payload_deterministic(self):
        data = {"b": 2, "a": 1}
        assert hash_payload(data) == hash_payload(data)

    def test_hash_bytes_format(self):
        result = hash_bytes(b"hello")
        assert result.startswith("sha256:")
        assert len(result) == 71
