"""Owner vault endpoints. The broker stores ciphertext and validates readability."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..crypto import CryptoError, ItemEnvelope, open_item_with_broker
from ..db import affected_rows
from ..encoding import b64decode_strict, b64encode
from ..errors import (
    E_INVALID_ENVELOPE,
    E_ITEM_EXISTS,
    E_ITEM_NOT_FOUND,
    E_OWNER_NOT_FOUND,
    E_TOO_MANY_ITEMS,
    MnemosError,
)
from ..models import OwnerAccount, VaultItem
from ..schemas import (
    OwnerSaltResponse,
    VaultItemCreate,
    VaultItemPage,
    VaultItemView,
)
from ..security import SessionClaims
from .deps import get_db, get_services, require_owner

router = APIRouter(prefix="/vault", tags=["vault"])


def _item_view(row: VaultItem) -> VaultItemView:
    return VaultItemView(
        id=row.id,
        scope=row.scope,
        ciphertext_b64=b64encode(row.ciphertext),
        nonce_b64=b64encode(row.nonce),
        wrapped_dek_owner_b64=b64encode(row.wrapped_dek_owner),
        content_hash=row.content_hash,
        created_at=row.created_at,
    )


def _encode_cursor(created_at: datetime, item_id: uuid.UUID) -> str:
    payload = {"created_at": created_at.astimezone(UTC).isoformat(), "id": str(item_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        item_id = uuid.UUID(str(payload["id"]))
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as error:
        raise MnemosError(400, "E_VALIDATION", "cursor is not valid") from error
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at, item_id


@router.post("/items", response_model=VaultItemView, status_code=201)
async def create_item(
    body: VaultItemCreate,
    request: Request,
    claims: SessionClaims = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> VaultItemView:
    services = get_services(request)
    now = datetime.now(UTC)
    owner = claims.account
    ciphertext = b64decode_strict(body.ciphertext_b64)
    nonce = b64decode_strict(body.nonce_b64)
    wrapped_owner = b64decode_strict(body.wrapped_dek_owner_b64)
    wrapped_broker = b64decode_strict(body.wrapped_dek_broker_b64)
    owner_salt = b64decode_strict(body.owner_salt_b64)
    if hashlib.sha256(ciphertext).hexdigest() != body.content_hash:
        raise MnemosError(400, E_INVALID_ENVELOPE, "content_hash does not match the ciphertext")

    envelope = ItemEnvelope(
        item_id=str(body.id),
        owner=owner,
        scope=body.scope,
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_dek_owner=wrapped_owner,
        wrapped_dek_broker=wrapped_broker,
        content_hash=body.content_hash,
    )
    try:
        open_item_with_broker(
            envelope=envelope, broker_private_key=services.settings.broker_private_key
        )
    except CryptoError as error:
        raise MnemosError(
            400,
            E_INVALID_ENVELOPE,
            "the broker could not open this envelope; re-encrypt it for the current broker key",
        ) from error

    await session.execute(
        pg_insert(OwnerAccount)
        .values(account=owner, kdf_salt=owner_salt, created_at=now)
        .on_conflict_do_nothing(index_elements=["account"])
    )
    owner_row = await session.get(OwnerAccount, owner, with_for_update=True)
    if owner_row is None:
        raise MnemosError(500, "E_INTERNAL", "owner record could not be created")
    if owner_row.kdf_salt != owner_salt:
        raise MnemosError(
            409,
            E_INVALID_ENVELOPE,
            "owner salt does not match this vault; unlock with the passphrase used to create it",
        )

    active_count = await session.scalar(
        select(func.count())
        .select_from(VaultItem)
        .where(VaultItem.owner == owner, VaultItem.deleted_at.is_(None))
    )
    if int(active_count or 0) >= services.settings.max_vault_items:
        raise MnemosError(
            409,
            E_TOO_MANY_ITEMS,
            f"at most {services.settings.max_vault_items} active items are allowed",
        )

    existing = await session.get(VaultItem, body.id, with_for_update=True)
    if existing is not None and existing.owner != owner:
        raise MnemosError(409, E_ITEM_EXISTS, "item id is already in use")
    if existing is not None and existing.deleted_at is None:
        raise MnemosError(409, E_ITEM_EXISTS, "item id already exists in this vault")
    if existing is None:
        row = VaultItem(
            id=body.id,
            owner=owner,
            scope=body.scope,
            ciphertext=ciphertext,
            nonce=nonce,
            wrapped_dek_owner=wrapped_owner,
            wrapped_dek_broker=wrapped_broker,
            content_hash=body.content_hash,
            created_at=now,
        )
        session.add(row)
    else:
        existing.scope = body.scope
        existing.ciphertext = ciphertext
        existing.nonce = nonce
        existing.wrapped_dek_owner = wrapped_owner
        existing.wrapped_dek_broker = wrapped_broker
        existing.content_hash = body.content_hash
        existing.created_at = now
        existing.deleted_at = None
        row = existing
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise MnemosError(409, E_ITEM_EXISTS, "item id already exists") from error
    await session.refresh(row)
    return _item_view(row)


@router.get("/items", response_model=VaultItemPage)
async def list_items(
    request: Request,
    scope: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    claims: SessionClaims = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> VaultItemPage:
    if scope is not None and not all(
        character.islower() or character.isdigit() or character == "-" for character in scope
    ):
        raise MnemosError(400, "E_VALIDATION", "scope is not valid")
    statement = (
        select(VaultItem)
        .where(VaultItem.owner == claims.account, VaultItem.deleted_at.is_(None))
        .order_by(VaultItem.created_at.desc(), VaultItem.id.desc())
        .limit(limit + 1)
    )
    if scope is not None:
        statement = statement.where(VaultItem.scope == scope)
    if cursor is not None:
        cursor_time, cursor_id = _decode_cursor(cursor)
        statement = statement.where(
            (VaultItem.created_at < cursor_time)
            | ((VaultItem.created_at == cursor_time) & (VaultItem.id < cursor_id))
        )
    rows = list((await session.scalars(statement)).all())
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1].created_at, page[-1].id) if has_more else None
    return VaultItemPage(items=[_item_view(row) for row in page], next_cursor=next_cursor)


@router.get("/salt", response_model=OwnerSaltResponse)
async def owner_salt(
    claims: SessionClaims = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> OwnerSaltResponse:
    row = await session.get(OwnerAccount, claims.account)
    if row is None:
        raise MnemosError(
            404, E_OWNER_NOT_FOUND, "this account has no vault yet; add an item first"
        )
    return OwnerSaltResponse(owner_salt_b64=b64encode(row.kdf_salt))


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    claims: SessionClaims = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> Response:
    now = datetime.now(UTC)
    result = await session.execute(
        update(VaultItem)
        .where(
            VaultItem.id == item_id,
            VaultItem.owner == claims.account,
            VaultItem.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )
    if affected_rows(result) != 1:
        await session.rollback()
        raise MnemosError(404, E_ITEM_NOT_FOUND, "item does not exist in this vault")
    await session.commit()
    return Response(status_code=204)
