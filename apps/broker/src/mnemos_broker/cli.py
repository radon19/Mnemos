"""`mnemos-broker` command line entry point."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from .near.keys import fingerprint_hex


def generate_broker_key(path: Path, *, force: bool = False) -> dict[str, str]:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to replace it")
    private_key = X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    record = {
        "private_key_b64": base64.b64encode(private_bytes).decode("ascii"),
        "public_key_b64": base64.b64encode(public_bytes).decode("ascii"),
        "fingerprint": fingerprint_hex(public_bytes),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return record


def _keygen(args: argparse.Namespace) -> int:
    path = Path(args.out)
    try:
        record = generate_broker_key(path, force=args.force)
    except FileExistsError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"wrote {path}")
    print(f"public key: {record['public_key_b64']}")
    print(f"fingerprint: {record['fingerprint']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mnemos-broker")
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen", help="Generate the broker X25519 envelope key")
    keygen.add_argument("--out", default=".secrets/broker_key.json")
    keygen.add_argument("--force", action="store_true")
    keygen.set_defaults(func=_keygen)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
