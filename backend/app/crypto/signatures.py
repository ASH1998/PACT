"""Ed25519 signing and verification."""

import base64

from app.crypto.keys import load_private_key, load_public_key


def sign(private_key_b64: str, payload: bytes) -> str:
    """Sign payload bytes with a private key. Returns base64-encoded signature."""
    sk = load_private_key(private_key_b64)
    signed = sk.sign(payload)
    return base64.b64encode(signed.signature).decode("ascii")


def verify(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
    """Verify a signature against payload and public key. Returns True if valid."""
    try:
        vk = load_public_key(public_key_b64)
        sig = base64.b64decode(signature_b64)
        vk.verify(payload, sig)
        return True
    except Exception:
        return False
