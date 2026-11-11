#!/usr/bin/env python3
"""Generate the committed cross-language envelope-encryption vectors.

Run from the repository root with the broker environment:

    cd apps/broker && uv run python ../../packages/crypto-vectors/generate.py

The output is deterministic: the same inputs always produce the same bytes, so
the TypeScript and Python test suites can compare their own encryption output
against the committed file and decrypt it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/broker/src"))

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey  # noqa: E402

from mnemos_broker.crypto import SealMaterials, seal_item  # noqa: E402

OWNER = "mnemos-owner-76badc8e.testnet"
OWNER_SALT = bytes.fromhex("00112233445566778899aabbccddeeff")
PASSPHRASE = "correct horse battery staple — mnemos"


def material(label: str, length: int) -> bytes:
    output = b""
    counter = 0
    while len(output) < length:
        output += hashlib.sha256(f"mnemos-vector:{label}:{counter}".encode()).digest()
        counter += 1
    return output[:length]


def main() -> int:
    broker_private = material("broker-private", 32)
    broker_public = (
        X25519PrivateKey.from_private_bytes(broker_private).public_key().public_bytes_raw()
    )

    items = [
        {
            "itemId": "6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
            "scope": "travel",
            "plaintextUtf8": "Flight to Lisbon on 14 March. Seat 12A. Hotel Baixa, check-in 15:00.",
        },
        {
            "itemId": "7a2d3b21-2c3d-4e4f-9a01-123456789abc",
            "scope": "work",
            "plaintextUtf8": (
                "Q3 planning notes:\n"
                "- ship the receipt ledger\n"
                "- redact agent prompts\n"
                "- review cap math"
            ),
        },
        {
            "itemId": "8b3e4c32-3d4e-4f50-ab12-23456789abcd",
            "scope": "preferences",
            "plaintextUtf8": (
                "Grüße aus Zürich — 東京のホテルは駅の北口。Bring an umbrella."
            ),
        },
    ]

    vectors = []
    for item in items:
        item_id = item["itemId"]
        materials = SealMaterials(
            dek=material(f"{item_id}:dek", 32),
            item_nonce=material(f"{item_id}:item-nonce", 12),
            owner_wrap_nonce=material(f"{item_id}:owner-wrap-nonce", 12),
            broker_ephemeral_secret=material(f"{item_id}:broker-ephemeral", 32),
            broker_wrap_nonce=material(f"{item_id}:broker-wrap-nonce", 12),
        )
        envelope = seal_item(
            owner=OWNER,
            scope=item["scope"],
            item_id=item_id,
            plaintext=item["plaintextUtf8"],
            passphrase=PASSPHRASE,
            owner_salt=OWNER_SALT,
            broker_public_key=broker_public,
            materials=materials,
        )
        vectors.append(
            {
                "itemId": item_id,
                "scope": item["scope"],
                "plaintextUtf8": item["plaintextUtf8"],
                "materials": {
                    "dek": materials.dek.hex(),
                    "itemNonce": materials.item_nonce.hex(),
                    "ownerWrapNonce": materials.owner_wrap_nonce.hex(),
                    "brokerEphemeralSecret": materials.broker_ephemeral_secret.hex(),
                    "brokerWrapNonce": materials.broker_wrap_nonce.hex(),
                },
                "expected": {
                    "ciphertext": envelope.ciphertext.hex(),
                    "nonce": envelope.nonce.hex(),
                    "wrappedDekOwner": envelope.wrapped_dek_owner.hex(),
                    "wrappedDekBroker": envelope.wrapped_dek_broker.hex(),
                    "contentHash": envelope.content_hash,
                },
            }
        )

    document = {
        "version": 1,
        "protocol": "mnemos:v1",
        "note": (
            "Deterministic vectors for AES-256-GCM items, PBKDF2 owner wrap and "
            "X25519/HKDF broker wrap. TS and Python tests must reproduce and "
            "decrypt every vector."
        ),
        "owner": OWNER,
        "ownerSalt": OWNER_SALT.hex(),
        "passphrase": PASSPHRASE,
        "pbkdf2Iterations": 600_000,
        "brokerPrivateKey": broker_private.hex(),
        "brokerPublicKey": broker_public.hex(),
        "items": vectors,
    }
    target = Path(__file__).with_name("vectors.json")
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {target} with {len(vectors)} vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
