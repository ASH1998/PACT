"""Persistent issuer keypair — loaded once per process."""

import os
import json
from pathlib import Path
from app.crypto import generate_keypair

_KEYS_FILE = Path(__file__).parent.parent.parent / "keys" / "issuer_keys.json"

# Try to load from env, otherwise generate
ISSUER_PRIVATE_KEY = os.environ.get("PACT_ISSUER_PRIVATE_KEY", "")
ISSUER_PUBLIC_KEY = os.environ.get("PACT_ISSUER_PUBLIC_KEY", "")

if not ISSUER_PRIVATE_KEY or not ISSUER_PUBLIC_KEY:
    # Try loading from file
    if _KEYS_FILE.exists():
        with open(_KEYS_FILE) as f:
            keys = json.load(f)
            ISSUER_PRIVATE_KEY = keys["private_key"]
            ISSUER_PUBLIC_KEY = keys["public_key"]
        os.chmod(_KEYS_FILE, 0o600)  # Always enforce permissions
    else:
        # Generate and save
        ISSUER_PRIVATE_KEY, ISSUER_PUBLIC_KEY = generate_keypair()
        _KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_KEYS_FILE, "w") as f:
            json.dump({"private_key": ISSUER_PRIVATE_KEY, "public_key": ISSUER_PUBLIC_KEY}, f)
        os.chmod(_KEYS_FILE, 0o600)
