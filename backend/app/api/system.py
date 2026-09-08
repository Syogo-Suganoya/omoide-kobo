from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app import repo
from app.agents.adk import adk_status
from app.agents.orchestrator import get_orchestrator
from app.config import get_settings
from app.infra.blobs import get_blobs
from app.models import AuditAction, AuditLog, ShareLink, ShareTarget, now
from app.services import audit

router = APIRouter(tags=["system"])


class ShareCreate(BaseModel):
    family_id: str
    target_type: ShareTarget
    target_id: str
    created_by: str = "owner"
    days: int = Field(default=7, ge=1, le=90)  # 期限なしの共有は作らせない


class ShareCreated(BaseModel):
    link: ShareLink
    path: str  # フロントの閲覧パス。家族が好きな手段でこの URL を渡す


@router.get("/agents")
async def agents() -> dict[str, object]:
    settings = get_settings()
    return {
        "roster": get_orchestrator().roster(),
        "modes": {
            "gemini": settings.gemini_mode,
            "youcam": settings.youcam_mode,
            "ekispert": settings.ekispert_mode,
            "speech": settings.speech_mode,
            "db": settings.db_driver,
            "storage": settings.storage_driver,
        },
        "adk": adk_status(),
        "policy": settings.no_training_policy,
    }


@router.get("/families/{family_id}/audit", response_model=list[AuditLog])
async def audit_log(family_id: str) -> list[AuditLog]:
    return await repo.list_audit(family_id)


# --------------------------------------------------------------------------- 共有リンク


@router.post("/share", response_model=ShareCreated)
async def create_share(payload: ShareCreate) -> ShareCreated:
    """期限付きの閲覧リンクを発行する。

    外部の配信サービスに家族の写真を預けず、リンクを家族が好きな手段で渡せるようにする。
    トークンは推測不能・必ず期限つき・いつでも失効可能（設計書 7-3 の明示共有の担保）。
    """
    if await repo.get_family(payload.family_id) is None:
        raise HTTPException(404, "家族が見つかりません")

    if payload.target_type is ShareTarget.photo:
        target = await repo.get_photo(payload.target_id)
    else:
        target = await repo.get_album(payload.target_id)
    if target is None or target.family_id != payload.family_id:
        raise HTTPException(404, "共有する対象が見つかりません")

    link = await repo.save_share(
        ShareLink(
            token=secrets.token_urlsafe(24),
            family_id=payload.family_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            created_by=payload.created_by,
            expires_at=now() + timedelta(days=payload.days),
        )
    )
    await audit.record(
        payload.family_id,
        AuditAction.share,
        actor=payload.created_by,
        target=payload.target_id,
        detail={
            "target_type": payload.target_type.value,
            "expires_at": link.expires_at.isoformat(),
            "days": payload.days,
        },
    )
    return ShareCreated(link=link, path=f"/s/{link.token}")


@router.get("/families/{family_id}/shares", response_model=list[ShareLink])
async def list_shares(family_id: str) -> list[ShareLink]:
    return await repo.list_shares(family_id)


@router.post("/shares/{token}/revoke", response_model=ShareLink)
async def revoke_share(token: str, actor: str = "owner") -> ShareLink:
    link = await repo.get_share_by_token(token)
    if link is None:
        raise HTTPException(404, "共有リンクが見つかりません")
    link.revoked = True
    await repo.save_share(link)
    await audit.record(
        link.family_id,
        AuditAction.share_revoke,
        actor=actor,
        target=link.target_id,
        detail={"token_tail": token[-6:], "target_type": link.target_type.value},
    )
    return link


async def _resolve(token: str) -> ShareLink:
    link = await repo.get_share_by_token(token)
    if link is None:
        raise HTTPException(404, "共有リンクが見つかりません")
    if not link.alive:
        raise HTTPException(410, "この共有リンクは期限切れ、または失効しています")
    return link


def _public_photo(photo: Any) -> dict[str, Any]:
    """閲覧リンクでは、家族が確定した内容と語りの要約だけを出す。

    AI の推定候補・確認質問・監査情報は共有相手には見せない。
    """
    return {
        "id": photo.id,
        "place": photo.resolved_place,
        "era": photo.confirmed.era,
        "story": photo.story.summary if photo.story else None,
        "has_image": bool(photo.restored_ref or photo.original_ref),
    }


@router.get("/shared/{token}")
async def view_shared(token: str) -> dict[str, Any]:
    link = await _resolve(token)

    if link.target_type is ShareTarget.photo:
        photo = await repo.get_photo(link.target_id)
        if photo is None:
            raise HTTPException(404, "写真が見つかりません")
        photos = [photo]
        title = photo.resolved_place or "思い出の一枚"
    else:
        album = await repo.get_album(link.target_id)
        if album is None:
            raise HTTPException(404, "アルバムが見つかりません")
        photos = await repo.list_photos(album.id)
        title = album.title

    link.view_count += 1
    await repo.save_share(link)
    await audit.record(
        link.family_id,
        AuditAction.share_view,
        actor="共有リンク",
        target=link.target_id,
        detail={"token_tail": token[-6:], "view_count": link.view_count},
    )
    return {
        "title": title,
        "expires_at": link.expires_at,
        "photos": [_public_photo(p) for p in photos],
    }


@router.get("/shared/{token}/photos/{photo_id}/image")
async def shared_image(token: str, photo_id: str) -> Response:
    link = await _resolve(token)
    photo = await repo.get_photo(photo_id)
    if photo is None or photo.family_id != link.family_id:
        raise HTTPException(404, "写真が見つかりません")
    # 写真単位のリンクで、別の写真を覗けないようにする
    if link.target_type is ShareTarget.photo and link.target_id != photo_id:
        raise HTTPException(403, "この共有リンクの対象ではありません")
    if link.target_type is ShareTarget.album and photo.album_id != link.target_id:
        raise HTTPException(403, "この共有リンクの対象ではありません")

    ref = photo.restored_ref or photo.original_ref
    if not ref:
        raise HTTPException(404, "画像がまだありません")
    data = await anyio.to_thread.run_sync(get_blobs().read, ref)
    return Response(content=data, media_type="image/jpeg")
