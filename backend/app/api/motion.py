"""ウゴクアルバムの API（設計書 12章）。

生成は「家族全員の同意が揃ってから」しか起こらない。同意の状態遷移はここに閉じ込め、
エージェント側も二重にチェックする（片方を書き換えても素通りしないように）。
"""

from __future__ import annotations

import asyncio
import logging

import anyio
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import repo
from app.agents.motion import ConsentRequired, MotionAgent
from app.infra.blobs import get_blobs
from app.models import (
    AuditAction,
    ConsentStatus,
    MotionClip,
    MotionStatus,
    Photo,
    now,
)
from app.services import audit

router = APIRouter(tags=["motion"])
_logger = logging.getLogger("omoide.motion")
_agent = MotionAgent()


class MotionRequest(BaseModel):
    requested_by: str
    # 故人が写っているかは家族の申告。写るなら参加済み家族全員の同意が要る
    includes_deceased: bool = False


class ConsentDecision(BaseModel):
    uid: str
    status: ConsentStatus


async def _load_photo(photo_id: str) -> Photo:
    photo = await repo.get_photo(photo_id)
    if photo is None:
        raise HTTPException(404, "写真が見つかりません")
    return photo


async def _generate(motion_id: str) -> None:
    clip = await repo.get_motion(motion_id)
    if clip is None:
        return
    photo = await repo.get_photo(clip.photo_id)
    if photo is None:
        return
    try:
        await _agent.run(clip=clip, photo=photo)
    except Exception:  # pragma: no cover - 生成失敗は clip.status に残る
        _logger.exception("ウゴクアルバムの生成に失敗しました")


@router.post("/photos/{photo_id}/motion", response_model=MotionClip)
async def request_motion(photo_id: str, payload: MotionRequest) -> MotionClip:
    photo = await _load_photo(photo_id)
    if not photo.restored_ref:
        raise HTTPException(400, "先に修復を終えてください")

    family = await repo.get_family(photo.family_id)
    if family is None:
        raise HTTPException(404, "家族が見つかりません")

    clip = _agent.prepare(
        photo=photo,
        family=family,
        requested_by=payload.requested_by,
        includes_deceased=payload.includes_deceased,
    )
    if payload.includes_deceased and not clip.consents:
        raise HTTPException(
            400, "同意を取る家族がいません。先にメンバーを招待し、参加を承諾してもらってください"
        )
    await repo.save_motion(clip)

    await audit.record(
        photo.family_id,
        AuditAction.motion_request,
        actor=payload.requested_by,
        target=clip.id,
        detail={
            "photo_id": photo.id,
            "includes_deceased": clip.includes_deceased,
            "scope": clip.scope,
            "consent_required_from": [c.name for c in clip.consents],
        },
    )

    # 同意が要らない場合だけ、その場で生成を始める
    if clip.status is MotionStatus.generating:
        asyncio.create_task(_generate(clip.id))
    return clip


@router.post("/motions/{motion_id}/consent", response_model=MotionClip)
async def decide_consent(motion_id: str, payload: ConsentDecision) -> MotionClip:
    clip = await repo.get_motion(motion_id)
    if clip is None:
        raise HTTPException(404, "ウゴクアルバムの依頼が見つかりません")
    if clip.status not in (MotionStatus.pending_consent, MotionStatus.denied):
        raise HTTPException(409, "この依頼はすでに処理済みです")

    for consent in clip.consents:
        if consent.uid == payload.uid:
            consent.status = payload.status
            consent.decided_at = now()
            break
    else:
        raise HTTPException(404, "同意を求められているメンバーではありません")

    await audit.record(
        clip.family_id,
        AuditAction.motion_consent,
        actor=payload.uid,
        target=clip.id,
        detail={"status": payload.status.value, "photo_id": clip.photo_id},
    )

    # 一人でも反対したら生成しない。全員そろって初めて動き出す
    if clip.consent_denied:
        clip.status = MotionStatus.denied
    elif clip.consent_complete:
        clip.status = MotionStatus.generating
    await repo.save_motion(clip)

    if clip.status is MotionStatus.generating:
        asyncio.create_task(_generate(clip.id))
    return clip


@router.get("/photos/{photo_id}/motions", response_model=list[MotionClip])
async def list_motions(photo_id: str) -> list[MotionClip]:
    return await repo.list_motions(photo_id)


@router.get("/motions/{motion_id}", response_model=MotionClip)
async def get_motion(motion_id: str) -> MotionClip:
    clip = await repo.get_motion(motion_id)
    if clip is None:
        raise HTTPException(404, "ウゴクアルバムの依頼が見つかりません")
    return clip


@router.get("/motions/{motion_id}/video")
async def get_video(motion_id: str) -> Response:
    clip = await repo.get_motion(motion_id)
    if clip is None or not clip.video_ref:
        raise HTTPException(404, "まだ生成されていません")
    data = await anyio.to_thread.run_sync(get_blobs().read, clip.video_ref)
    return Response(content=data, media_type=clip.media_type)


# --------------------------------------------------------------------------- 修復結果の選択


class VariantChoice(BaseModel):
    variant: str  # "restored" | "alt"
    chosen_by: str


@router.post("/photos/{photo_id}/variant", response_model=Photo)
async def choose_variant(photo_id: str, payload: VariantChoice) -> Photo:
    """どちらの修復結果を採るかは家族が決める（設計書 12章の比較提示）。"""
    if payload.variant not in ("restored", "alt"):
        raise HTTPException(400, "restored か alt を指定してください")
    photo = await _load_photo(photo_id)
    if payload.variant == "alt" and not photo.alt_restored_ref:
        raise HTTPException(400, "比較用の修復結果がありません")

    photo.preferred_variant = payload.variant  # type: ignore[assignment]
    await repo.save_photo(photo)
    await audit.record(
        photo.family_id,
        AuditAction.variant_select,
        actor=payload.chosen_by,
        target=photo.id,
        detail={
            "variant": payload.variant,
            "provider": photo.alt_restored_provider
            if payload.variant == "alt"
            else photo.restored_provider,
        },
    )
    return photo
