"""Owner authentication: NEP-413 challenge, single-use verification, session."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import affected_rows
from ..errors import (
    E_BAD_SIGNATURE,
    E_CHALLENGE_EXPIRED,
    E_CHALLENGE_USED,
    E_UNAUTHORIZED,
    MnemosError,
)
from ..models import AuditEvent, AuthChallenge
from ..schemas import (
    ChallengeRequest,
    ChallengeResponse,
    ChallengeVerifyRequest,
    SessionResponse,
)
from ..security import (
    SESSION_COOKIE,
    SessionClaims,
    create_challenge,
    sign_session,
    verify_owner_nep413,
)
from .deps import get_db, get_services, limit_auth, optional_owner, require_owner

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/challenge", response_model=ChallengeResponse)
async def challenge(
    body: ChallengeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(limit_auth),
) -> ChallengeResponse:
    services = get_services(request)
    now = datetime.now(UTC)
    challenge_record = create_challenge(body.account, services.settings.broker_recipient, now=now)
    await session.execute(
        delete(AuthChallenge).where(
            AuthChallenge.account == body.account,
            AuthChallenge.expires_at < now,
        )
    )
    session.add(
        AuthChallenge(
            nonce=challenge_record.nonce_hex,
            account=body.account,
            message=challenge_record.message,
            expires_at=challenge_record.expires_at,
            created_at=now,
        )
    )
    await session.commit()
    return ChallengeResponse(
        nonce_hex=challenge_record.nonce_hex,
        nonce_b64=challenge_record.nonce_b64,
        message=challenge_record.message,
        recipient=challenge_record.recipient,
        expires_at=challenge_record.expires_at,
    )


@router.post("/verify", response_model=SessionResponse)
async def verify(
    body: ChallengeVerifyRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(limit_auth),
) -> SessionResponse:
    services = get_services(request)
    now = datetime.now(UTC)
    row = await session.get(AuthChallenge, body.nonce_hex)
    if row is None or row.account != body.account:
        raise MnemosError(401, E_UNAUTHORIZED, "challenge does not match this account")
    if row.used_at is not None:
        raise MnemosError(409, E_CHALLENGE_USED, "challenge was already used; request a new one")
    if now >= row.expires_at:
        raise MnemosError(401, E_CHALLENGE_EXPIRED, "challenge expired; request a new one")

    if not verify_owner_nep413(
        public_key=body.public_key,
        signature_b64=body.signature_b64,
        message=row.message,
        recipient=services.settings.broker_recipient,
        nonce_hex=row.nonce,
    ):
        session.add(
            AuditEvent(owner=None, kind="auth_failed", subject=body.account, code=E_BAD_SIGNATURE)
        )
        await session.commit()
        raise MnemosError(401, E_BAD_SIGNATURE, "NEP-413 signature verification failed")

    await services.chain.verify_account_key(
        body.account, body.public_key, require_function_call=False
    )

    consumed = await session.execute(
        update(AuthChallenge)
        .where(AuthChallenge.nonce == row.nonce, AuthChallenge.used_at.is_(None))
        .values(used_at=now)
    )
    if affected_rows(consumed) != 1:
        await session.rollback()
        raise MnemosError(409, E_CHALLENGE_USED, "challenge was already used; request a new one")
    session.add(AuditEvent(owner=body.account, kind="auth_ok", subject=body.public_key))
    await session.commit()

    ttl = timedelta(minutes=services.settings.session_ttl_minutes)
    token, expires_at = sign_session(
        body.account, services.settings.session_secret_bytes, ttl=ttl, now=now
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        secure=services.settings.session_cookie_secure,
        max_age=int(ttl.total_seconds()),
        path="/",
    )
    return SessionResponse(account=body.account, expires_at=expires_at)


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/session", response_model=SessionResponse)
async def session_info(claims: SessionClaims = Depends(require_owner)) -> SessionResponse:
    return SessionResponse(account=claims.account, expires_at=claims.expires_at, demo=claims.demo)


@router.get("/optional")
async def optional(
    claims: SessionClaims | None = Depends(optional_owner),
) -> dict[str, str | bool | None]:
    if claims is not None:
        return {"authenticated": True, "account": claims.account, "demo": claims.demo}
    return {"authenticated": False, "account": None, "demo": None}
