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

    def _new_client(self) -> InferenceClient:
        # One client per completion: no hour-long attestation session can be reused.
        # The SDK generates fresh 32-byte nonces and verifies gateway/model evidence
        # before sending the encrypted prompt, retaining exact wire bytes itself.
        return InferenceClient(
            self.settings.nearai_api_key.get_secret_value(),
            base_url=self.settings.nearai_base_url,
            e2ee=True,
            attestation_cache_time_to_live_ms=0,
        )

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        client = self._new_client()
        try:
            return await self._complete_with_client(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
        finally:
            await client.aclose()

    async def _complete_with_client(
        self, client: InferenceClient, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        preflight_started_at = datetime.now(UTC).isoformat(timespec="seconds")
        messages: list[ChatCompletionMessageParam] = [
            {"role": SYSTEM_ROLE, "content": system_prompt},
            {"role": USER_ROLE, "content": user_prompt},
        ]
        extra_body: dict[str, Any] = {}
        if self.settings.nearai_model.startswith("Qwen/Qwen3"):
            # Qwen3 thinks by default. Hidden reasoning can exhaust the owner's
            # small output budget before producing any answer. Keep that budget
            # for the direct response, without increasing the grant's token cap.
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}
        request_projection = {
            "model": self.settings.nearai_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            **extra_body,
        }
        try:
            completion = await client.chat.completions.create(
                model=self.settings.nearai_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                extra_body=extra_body,
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
            if (
                verified.signature_kind != "provider_tee"
                or len(getattr(verified, "attestations", ())) != 1
            ):
                raise ValueError("a unique verified model-serving TEE signature is required")
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
            attestation={
                **_attestation_summary(verified),
                "fresh_preflight": True,
                "preflight_started_at": preflight_started_at,
                "verification_policy": "unique-provider-tee-per-inference",
                "receipt_hash_basis": "application-projections-not-sdk-wire-signature",
            },
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
        # Every per-inference SDK session closes before complete() returns.
        pass


def inference_error(error: InferenceError) -> MnemosError:
    return MnemosError(502, error.code, error.message)
