#!/usr/bin/env python3
"""Live check: NEAR AI Cloud TEE answer with end-to-end encryption.

The script sends one chat completion with ``e2ee=True`` to the configured
model, then verifies the response signature and the TEE attestation. It prints
a JSON summary and exits non-zero when verification fails, so it can be used
as a gate in CI or in the verification log.

Usage:
    uv run --project apps/broker python scripts/verify-nearai.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "broker" / "src"))

from mnemos_broker.config import Settings
from mnemos_broker.inference import NearAiInferenceEngine


def api_key(settings: Settings) -> str:
    key = settings.nearai_api_key.get_secret_value().strip()
    if key:
        return key
    secret = ROOT / ".secrets" / "nearai_api_key"
    if secret.exists():
        return secret.read_text(encoding="utf-8").strip()
    raise SystemExit("no NEAR AI API key: set NEARAI_API_KEY or write .secrets/nearai_api_key")


async def main() -> int:
    settings = Settings()
    api_key(settings)
    engine = NearAiInferenceEngine(settings)
    system_prompt = (
        "You are a memory answering service. Answer only from the supplied memory "
        "block and never quote more than twelve consecutive words from it."
    )
    user_prompt = (
        "<MNEMOS_MEMORY>\n"
        "[MNEMOS-ITEM id=item-1 scope=health]\n"
        "My flight to Lisbon is on 14 March at 09:15.\n"
        "[/MNEMOS-ITEM]\n"
        "</MNEMOS_MEMORY>\n\n"
        "<MNEMOS_QUESTION>\nWhen is my flight?\n</MNEMOS_QUESTION>"
    )
    try:
        result = await engine.complete(
            system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=128
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "model": settings.nearai_model,
                    "error": f"{type(error).__name__}: {error}",
                },
                indent=2,
            )
        )
        return 1
    finally:
        await engine.close()

    summary: dict[str, Any] = {
        "ok": True,
        "model": settings.nearai_model,
        "e2ee": True,
        "chat_id": result.chat_id,
        "signature_kind": result.signature_kind,
        "signing_address": result.signing_address,
        "signing_algo": result.signing_algo,
        "request_sha256": hashlib.sha256(result.request_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(result.response_bytes).hexdigest(),
        "answer": result.answer,
        "attestation": result.attestation,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
