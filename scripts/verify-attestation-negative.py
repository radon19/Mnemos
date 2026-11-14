#!/usr/bin/env python3
"""Verify a real fresh quote, then prove the SDK rejects a different nonce."""

from __future__ import annotations

import asyncio
import json
import secrets

from nearai_inference_sdk import (
    AttestationClient,
    ModelClientBinding,
    VerificationError,
    verify_model_attestation,
)

from mnemos_broker.config import Settings


async def main() -> None:
    settings = Settings()
    client = AttestationClient(
        settings.nearai_api_key.get_secret_value(), base_url=settings.nearai_base_url
    )
    fetched = await client.fetch_model_attestations(
        settings.nearai_model, signing_algo="ed25519"
    )
    if len(fetched.attestations) != 1:
        raise SystemExit(
            "The configured model does not have a unique report; no negative-test pass claimed."
        )
    report = fetched.attestations[0]
    valid = await verify_model_attestation(report, fetched.client_binding)
    wrong = ModelClientBinding(nonce=secrets.token_hex(32))
    try:
        await verify_model_attestation(report, wrong)
    except VerificationError as error:
        if "nonce" not in error.failure.code:
            raise SystemExit(
                f"Unexpected verification failure: {error.failure.code}"
            ) from None
        print(
            json.dumps(
                {
                    "model": settings.nearai_model,
                    "valid_quote_verified": True,
                    "tcb_status": valid.tcb_status,
                    "gpu_evidence": valid.gpu_evidence,
                    "tampered_nonce_rejected": True,
                    "failure_code": error.failure.code,
                },
                indent=2,
            )
        )
    else:
        raise SystemExit("FAIL: a quote was accepted under a different client nonce")


if __name__ == "__main__":
    asyncio.run(main())
