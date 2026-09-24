from __future__ import annotations

from typing import Literal

import anyio
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app import repo
from app.agents.orchestrator import get_orchestrator
from app.infra.blobs import get_blobs
from app.models import AuditAction, Confirmed, Photo, PhotoStatus, now
from app.services import audit

router = APIRouter(tags=["photos"])


class Answer(BaseModel):
    question_id: str
    answer: str


class ConfirmPayload(BaseModel):
    """家族の記憶による確定。AI 推定（estimate）は残したまま別フィールドに書く。"""

    place: str | None = None
    era: str | None = None
    family_correction: str | None = None
    confirmed_by: str
    answers: list[Answer] = []


def _sniff(data: bytes) -> str:
    """アップロード時の形式は様々なので、先頭バイトから判定して返す。"""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return "image/heic"
    if data[:2] in (b"II", b"MM"):
        return "image/tiff"
    return "application/octet-stream"


async def _load(photo_id: str) -> Photo:
    photo = await repo.get_photo(photo_id)
    if photo is None:
        raise HTTPException(404, "写真が見つかりません")
    return photo


@router.get("/photos/{photo_id}", response_model=Photo)
async def get_photo(photo_id: str) -> Photo:
    return await _load(photo_id)


@router.get("/photos/{photo_id}/image/{kind}")
async def get_image(photo_id: str, kind: Literal["original"]) -> Response:
    photo = await _load(photo_id)
    ref = photo.original_ref
    if not ref:
        raise HTTPException(404, "画像がまだありません")
    data = await anyio.to_thread.run_sync(get_blobs().read, ref)
    media = _sniff(data) if kind == "original" else "image/jpeg"
    return Response(content=data, media_type=media, headers={"Cache-Control": "private, max-age=60"})


@router.post("/photos/{photo_id}/confirm", response_model=Photo)
async def confirm_photo(photo_id: str, payload: ConfirmPayload) -> Photo:
    """家族の記憶を確定として書き込む。以後この写真の場所表示は必ずこちらが優先される。"""
    photo = await _load(photo_id)

    answers = {a.question_id: a.answer for a in payload.answers}
    for question in photo.questions:
        if question.id in answers:
            question.answer = answers[question.id]
            question.answered = True

    photo.confirmed = Confirmed(
        place=payload.place or photo.confirmed.place,
        era=payload.era or photo.confirmed.era,
        confirmed_by=payload.confirmed_by,
        family_correction=payload.family_correction or photo.confirmed.family_correction,
        confirmed_at=now(),
    )
    if photo.confirmed.place:
        photo.status = PhotoStatus.confirmed
    await repo.save_photo(photo)

    top = photo.estimate.place_candidates[0].name if photo.estimate and photo.estimate.place_candidates else None
    await audit.record(
        photo.family_id,
        AuditAction.family_confirm,
        actor=payload.confirmed_by,
        target=photo.id,
        detail={
            "confirmed_place": photo.confirmed.place,
            "ai_top_candidate": top,
            "overrode_ai": bool(top and photo.confirmed.place and top != photo.confirmed.place),
            "correction": photo.confirmed.family_correction,
        },
    )
    return photo


@router.post("/photos/{photo_id}/reestimate", response_model=Photo)
async def reestimate(photo_id: str) -> Photo:
    """家族の訂正を踏まえて推定し直す（訂正が後続推定のコンテキストに入る）。"""
    photo = await _load(photo_id)
    await get_orchestrator().estimate.run(photo=photo)
    return await _load(photo_id)


