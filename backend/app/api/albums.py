from __future__ import annotations

import asyncio
import logging

import anyio
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import repo
from app.agents.orchestrator import get_orchestrator
from app.infra.blobs import get_blobs, make_ref
from app.models import Album, AuditAction, Job, JobStatus, Photo
from app.services import audit

router = APIRouter(tags=["albums"])
_logger = logging.getLogger("omoide.api")

ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/tiff"}


class AlbumCreate(BaseModel):
    family_id: str
    title: str


class IngestResult(BaseModel):
    job: Job
    photos: list[Photo]


@router.post("/albums", response_model=Album)
async def create_album(payload: AlbumCreate) -> Album:
    if await repo.get_family(payload.family_id) is None:
        raise HTTPException(404, "家族が見つかりません")
    return await repo.save_album(Album(family_id=payload.family_id, title=payload.title))


@router.get("/families/{family_id}/albums", response_model=list[Album])
async def list_albums(family_id: str) -> list[Album]:
    return await repo.list_albums(family_id)


@router.get("/albums/{album_id}", response_model=Album)
async def get_album(album_id: str) -> Album:
    album = await repo.get_album(album_id)
    if album is None:
        raise HTTPException(404, "アルバムが見つかりません")
    return album


@router.get("/albums/{album_id}/photos", response_model=list[Photo])
async def list_photos(album_id: str) -> list[Photo]:
    return await repo.list_photos(album_id)


@router.get("/families/{family_id}/photos", response_model=list[Photo])
async def list_family_photos(family_id: str) -> list[Photo]:
    """「いまやること」の集計用。アルバムごとに引くと枚数ぶん往復するので、家族単位で1回にする。"""
    return await repo.list_family_photos(family_id)


@router.post("/albums/{album_id}/photos", response_model=IngestResult)
async def upload_photos(album_id: str, files: list[UploadFile] = File(...)) -> IngestResult:
    """アルバム一括取り込み。保存後、場所・年代の推定をバックグラウンドで自律進行させる。"""
    album = await get_album(album_id)
    blobs = get_blobs()
    photos: list[Photo] = []

    for upload in files:
        if upload.content_type not in ALLOWED:
            raise HTTPException(415, f"未対応の形式です: {upload.content_type}")
        data = await upload.read()
        photo = Photo(
            album_id=album.id,
            family_id=album.family_id,
            filename=upload.filename or "photo.jpg",
        )
        # オリジナルは専用キーに保全し、以後どの工程でも上書きしない
        ref = make_ref(album.family_id, album.id, "original", f"{photo.id}.bin")
        await anyio.to_thread.run_sync(lambda r=ref, d=data: blobs.write(r, d, upload.content_type))
        photo.original_ref = ref
        photos.append(await repo.save_photo(photo))

    await audit.record(
        album.family_id,
        AuditAction.upload,
        actor="family",
        target=album.id,
        detail={"count": len(photos), "filenames": [p.filename for p in photos]},
    )

    job = await repo.save_job(
        Job(
            family_id=album.family_id,
            album_id=album.id,
            total=len(photos),
            photo_ids=[p.id for p in photos],
            status=JobStatus.queued,
        )
    )
    asyncio.create_task(_run_pipeline(job.id))
    return IngestResult(job=job, photos=photos)


async def _run_pipeline(job_id: str) -> None:
    job = await repo.get_job(job_id)
    if job is None:
        return
    try:
        await get_orchestrator().run(job=job)
    except Exception as exc:  # pragma: no cover - 保険
        _logger.exception("パイプラインが異常終了しました")
        job.status = JobStatus.failed
        job.error = str(exc)
        await repo.save_job(job)


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(404, "ジョブが見つかりません")
    return job
