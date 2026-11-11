"""NEAR AI Cloud inference through the official verified SDK.

The engine never falls back to an unverified path. A completion is returned only
after ``verify_response`` succeeds for the exact response id. Attestation data is
summarised (hashes, signer, TCB status) rather than storing raw quotes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, Protocol

import httpx
from nearai_inference_sdk import InferenceClient
from openai.types.chat import ChatCompletionMessageParam

from .config import Settings
from .errors import E_INFERENCE_FAILED, E_VERIFICATION_FAILED, MnemosError

SYSTEM_ROLE: Final[Literal["system"]] = "system"
USER_ROLE: Final[Literal["user"]] = "user"


class InferenceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class InferenceResult:
    answer: str
    chat_id: str
    signing_address: str
    signing_algo: str
    signature_kind: str
    attestation: dict[str, Any]
    request_bytes: bytes
    response_bytes: bytes


class InferenceProtocol(Protocol):
    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult: ...

    async def close(self) -> None: ...

    async def ready(self) -> bool: ...


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _attestation_summary(verified: Any) -> dict[str, Any]:
    attestation = verified.attestation
    deployment = attestation.deployment
    runtime = deployment.runtime_measurements
    compose_manager = deployment.compose_manager
    summary: dict[str, Any] = {
        "signature_kind": str(verified.signature_kind),
        "signer": {
            "signing_address": verified.signature.signer.signing_address,
            "signing_algo": verified.signature.signer.signing_algo,
        },
        "tcb_status": str(attestation.tcb_status),
        "advisory_ids": list(attestation.advisory_ids),
        "deployment": {
            "app_compose_sha256": hashlib.sha256(
                deployment.app_compose.encode("utf-8")
            ).hexdigest(),
            "os_image_hash": runtime.os_image_hash,
            "compose_hash": runtime.compose_hash,
            "compose_manager_verified": compose_manager is not None,
        },
        "deployment_provenance": str(attestation.deployment_provenance),
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    gpu_evidence = getattr(attestation, "gpu_evidence", None)
    if gpu_evidence is not None:
        summary["gpu_evidence"] = str(gpu_evidence)
    tls_binding = getattr(attestation, "tls_binding", None)
    if tls_binding is not None:
        summary["tls_binding"] = {
            "kind": str(tls_binding.kind),
            "spki_fingerprint": tls_binding.spki_fingerprint,
        }
    attestations = getattr(verified, "attestations", None)
    if attestations is not None:
        summary["model_attestations"] = len(attestations)
    return summary


class NearAiInferenceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: InferenceClient | None = None

    def _client_or_create(self) -> InferenceClient:
        if self._client is None:
            self._client = InferenceClient(
                self.settings.nearai_api_key.get_secret_value(),
                base_url=self.settings.nearai_base_url,
                e2ee=True,
            )
        return self._client

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        client = self._client_or_create()
        messages: list[ChatCompletionMessageParam] = [
            {"role": SYSTEM_ROLE, "content": system_prompt},
            {"role": USER_ROLE, "content": user_prompt},
        ]
        request_projection = {
            "model": self.settings.nearai_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            completion = await client.chat.completions.create(
                model=self.settings.nearai_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
            )
        except Exception as error:
            raise InferenceError(E_INFERENCE_FAILED, "NEAR AI Cloud request failed") from error

        if not completion.choices:
            raise InferenceError(E_INFERENCE_FAILED, "model returned no choices")
        choice = completion.choices[0]
        answer = choice.message.content
        if not isinstance(answer, str) or not answer.strip():
            raise InferenceError(E_INFERENCE_FAILED, "model returned an empty answer")

        try:
            verified = await client.verify_response(completion.id)
        except Exception as error:
            raise InferenceError(
                E_VERIFICATION_FAILED,
                "response signature or attestation verification failed",
            ) from error

        signing_address = verified.signature.signer.signing_address
        signing_algo = verified.signature.signer.signing_algo
        usage = completion.usage.model_dump(mode="json") if completion.usage else None
        response_projection = {
            "id": completion.id,
            "model": completion.model,
            "content": answer,
            "finish_reason": choice.finish_reason,
            "usage": usage,
        }
        return InferenceResult(
            answer=answer,
            chat_id=completion.id,
            signing_address=signing_address,
            signing_algo=str(signing_algo),
            signature_kind=str(verified.signature_kind),
            attestation=_attestation_summary(verified),
            request_bytes=canonical_json(request_projection),
            response_bytes=canonical_json(response_projection),
        )

    async def ready(self) -> bool:
        url = self.settings.nearai_base_url.rstrip("/") + "/models"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "authorization": f"Bearer {self.settings.nearai_api_key.get_secret_value()}"
                    },
                )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def inference_error(error: InferenceError) -> MnemosError:
    return MnemosError(502, error.code, error.message)
