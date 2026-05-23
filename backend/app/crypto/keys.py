"""Ed25519 key generation and loading."""

import base64

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair. Returns (private_key_b64, public_key_b64)."""
    signing_key = SigningKey.generate()
    private_b64 = base64.b64encode(signing_key.encode()).decode("ascii")
    public_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    return private_b64, public_b64


def load_private_key(private_key_b64: str) -> SigningKey:
    """Load a SigningKey from a base64-encoded private key."""
    raw = base64.b64decode(private_key_b64)
    return SigningKey(raw)


def load_public_key(public_key_b64: str) -> VerifyKey:
    """Load a VerifyKey from a base64-encoded public key."""
    raw = base64.b64decode(public_key_b64)
    return VerifyKey(raw)
