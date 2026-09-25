"""モデル ⇄ ストアの薄いリポジトリ層。"""

from __future__ import annotations

from app.infra.store import get_store
from app.models import Album, AuditLog, Family, Job, Photo, ShareLink, Trip, now

FAMILIES = "families"
ALBUMS = "albums"
PHOTOS = "photos"
TRIPS = "trips"
AUDIT = "audit"
JOBS = "jobs"
SHARES = "shares"


async def save_family(family: Family) -> Family:
    await get_store().put(FAMILIES, family.id, family.model_dump(mode="json"))
    return family


async def get_family(family_id: str) -> Family | None:
    doc = await get_store().get(FAMILIES, family_id)
    return Family(**doc) if doc else None


async def list_families() -> list[Family]:
    return [Family(**d) for d in await get_store().query(FAMILIES)]


async def save_album(album: Album) -> Album:
    await get_store().put(ALBUMS, album.id, album.model_dump(mode="json"))
    return album


async def get_album(album_id: str) -> Album | None:
    doc = await get_store().get(ALBUMS, album_id)
    return Album(**doc) if doc else None


async def list_albums(family_id: str) -> list[Album]:
    return [Album(**d) for d in await get_store().query(ALBUMS, family_id=family_id)]


async def save_photo(photo: Photo) -> Photo:
    photo.updated_at = now()
    await get_store().put(PHOTOS, photo.id, photo.model_dump(mode="json"))
    return photo


async def get_photo(photo_id: str) -> Photo | None:
    doc = await get_store().get(PHOTOS, photo_id)
    return Photo(**doc) if doc else None


async def list_photos(album_id: str) -> list[Photo]:
    return [Photo(**d) for d in await get_store().query(PHOTOS, album_id=album_id)]


async def list_family_photos(family_id: str) -> list[Photo]:
    return [Photo(**d) for d in await get_store().query(PHOTOS, family_id=family_id)]


async def save_trip(trip: Trip) -> Trip:
    await get_store().put(TRIPS, trip.id, trip.model_dump(mode="json"))
    return trip


async def get_trip(trip_id: str) -> Trip | None:
    doc = await get_store().get(TRIPS, trip_id)
    return Trip(**doc) if doc else None


async def list_trips(family_id: str) -> list[Trip]:
    return [Trip(**d) for d in await get_store().query(TRIPS, family_id=family_id)]


async def save_job(job: Job) -> Job:
    job.updated_at = now()
    await get_store().put(JOBS, job.id, job.model_dump(mode="json"))
    return job


async def get_job(job_id: str) -> Job | None:
    doc = await get_store().get(JOBS, job_id)
    return Job(**doc) if doc else None


async def save_share(link: ShareLink) -> ShareLink:
    await get_store().put(SHARES, link.id, link.model_dump(mode="json"))
    return link


async def get_share_by_token(token: str) -> ShareLink | None:
    docs = await get_store().query(SHARES, token=token)
    return ShareLink(**docs[0]) if docs else None


async def list_shares(family_id: str) -> list[ShareLink]:
    links = [ShareLink(**d) for d in await get_store().query(SHARES, family_id=family_id)]
    return sorted(links, key=lambda link: link.created_at, reverse=True)


async def append_audit(log: AuditLog) -> AuditLog:
    await get_store().put(AUDIT, log.id, log.model_dump(mode="json"))
    return log


async def list_audit(family_id: str) -> list[AuditLog]:
    logs = [AuditLog(**d) for d in await get_store().query(AUDIT, family_id=family_id)]
    return sorted(logs, key=lambda log: log.created_at, reverse=True)


async def purge_family(family_id: str) -> dict[str, int]:
    """家族単位の完全削除。監査ログは証跡として残す。"""
    store = get_store()
    removed = {
        PHOTOS: await store.delete_where(PHOTOS, family_id=family_id),
        ALBUMS: await store.delete_where(ALBUMS, family_id=family_id),
        TRIPS: await store.delete_where(TRIPS, family_id=family_id),
        JOBS: await store.delete_where(JOBS, family_id=family_id),
        SHARES: await store.delete_where(SHARES, family_id=family_id),
    }
    await store.delete(FAMILIES, family_id)
    removed[FAMILIES] = 1
    return removed
