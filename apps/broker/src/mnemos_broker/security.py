"""Owner sessions (NEP-413) and agent request signatures.

Two independent proofs live here:

* Owner login uses the NEP-413 message format. The challenge row stores the
  exact message so the broker never reconstructs a different string than the
  wallet displayed.
* Agent ``/v1/ask`` calls sign a canonical, pipe-delimited message defined in
  docs/DECISIONS.md (D-010). The signature is Ed25519 over SHA-256 of the UTF-8
  canonical bytes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .encoding import b64decode_strict, b64encode
from .errors import E_BAD_SIGNATURE, E_SESSION_EXPIRED, E_UNAUTHORIZED, MnemosError
from .near.keys import verify_ed25519, verify_nep413

SESSION_COOKIE = "mnemos_session"
CHALLENGE_TTL = timedelta(minutes=5)
ASK_RECIPIENT_SEPARATOR = "|"


@dataclass(frozen=True)
class Challenge:
    nonce_hex: str
    nonce_b64: str
    message: str
    recipient: str
    expires_at: datetime


@dataclass(frozen=True)
class SessionClaims:
    account: str
    issued_at: datetime
    expires_at: datetime
    demo: bool


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def create_challenge(account: str, recipient: str, *, now: datetime | None = None) -> Challenge:
    moment = now or datetime.now(UTC)
    nonce = secrets.token_bytes(32)
    nonce_hex = nonce.hex()
    expires_at = moment + CHALLENGE_TTL
    message = (
        "Mnemos sign-in\n"
        f"account: {account}\n"
        f"nonce: {nonce_hex}\n"
        f"issued_at: {_iso(moment)}\n"
        f"recipient: {recipient}\n"
        "This signature authorises vault access in this browser session only."
    )
    return Challenge(
        nonce_hex=nonce_hex,
        nonce_b64=b64encode(nonce),
        message=message,
        recipient=recipient,
        expires_at=expires_at,
    )


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_session(
    account: str,
    secret: bytes,
    *,
    ttl: timedelta,
    demo: bool = False,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    moment = now or datetime.now(UTC)
    expires_at = moment + ttl
    payload = {
        "account": account,
        "iat": int(moment.timestamp()),
        "exp": int(expires_at.timestamp()),
        "demo": demo,
    }
    encoded = _b64url(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}", expires_at


def verify_session(token: str, secret: bytes, *, now: datetime | None = None) -> SessionClaims:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as error:
        raise MnemosError(401, E_UNAUTHORIZED, "session cookie is malformed") from error
    expected = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise MnemosError(401, E_UNAUTHORIZED, "session cookie signature is invalid")
    try:
        payload = json.loads(_b64url_decode(encoded))
    except (ValueError, UnicodeDecodeError) as error:
        raise MnemosError(401, E_UNAUTHORIZED, "session cookie payload is invalid") from error
    if not isinstance(payload, dict):
        raise MnemosError(401, E_UNAUTHORIZED, "session cookie payload is invalid")
    account = payload.get("account")
    issued = payload.get("iat")
    expires = payload.get("exp")
    demo = payload.get("demo", False)
    if not isinstance(account, str) or not isinstance(issued, int) or not isinstance(expires, int):
        raise MnemosError(401, E_UNAUTHORIZED, "session cookie payload is incomplete")
    moment = now or datetime.now(UTC)
    expires_at = datetime.fromtimestamp(expires, UTC)
    if moment >= expires_at:
        raise MnemosError(401, E_SESSION_EXPIRED, "session has expired; sign in again")
    return SessionClaims(
        account=account,
        issued_at=datetime.fromtimestamp(issued, UTC),
        expires_at=expires_at,
        demo=bool(demo),
    )


def verify_owner_nep413(
    *,
    public_key: str,
    signature_b64: str,
    message: str,
    recipient: str,
    nonce_hex: str,
) -> bool:
    try:
        nonce = bytes.fromhex(nonce_hex)
        signature = b64decode_strict(signature_b64)
    except ValueError:
        return False
    return verify_nep413(
        public_key=public_key,
        signature=signature,
        message=message,
        recipient=recipient,
        nonce=nonce,
    )


def question_digest(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def question_hash(question: str, nonce_hex: str) -> str:
    """The on-chain q_hash: SHA-256(question UTF-8 || 32 nonce bytes)."""
    try:
        nonce = bytes.fromhex(nonce_hex)
    except ValueError as error:
        raise ValueError("nonce must be lowercase hex") from error
    if len(nonce) != 32:
        raise ValueError("nonce must be 32 bytes")
    return hashlib.sha256(question.encode("utf-8") + nonce).hexdigest()


def build_ask_message(req_id: int, question: str, nonce_hex: str, recipient: str) -> str:
    return ASK_RECIPIENT_SEPARATOR.join(
        ["mnemos:v1:ask", str(req_id), question_digest(question), nonce_hex, recipient]
    )


def verify_ask_signature(
    *,
    public_key: str,
    signature_b64: str,
    message: str,
) -> bool:
    try:
        signature = b64decode_strict(signature_b64)
    except ValueError:
        return False
    digest = hashlib.sha256(message.encode("utf-8")).digest()
    return verify_ed25519(public_key, signature, digest)


def require_ask_signature(
    *,
    public_key: str,
    signature_b64: str,
    message: str,
) -> None:
    if not verify_ask_signature(
        public_key=public_key, signature_b64=signature_b64, message=message
    ):
        raise MnemosError(401, E_BAD_SIGNATURE, "agent signature does not match the request")
