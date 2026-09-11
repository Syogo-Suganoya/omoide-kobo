"""パイプラインとガバナンス要件（設計書 7章）の回帰テスト。"""

from __future__ import annotations

import pytest

from app import repo
from app.agents.orchestrator import get_orchestrator
from app.infra.blobs import get_blobs, make_ref
from app.models import (
    Album,
    AuditAction,
    Family,
    InviteStatus,
    Job,
    Member,
    Photo,
    PhotoStatus,
    Stamina,
    Trip,
)

pytestmark = pytest.mark.asyncio


async def _seed(gray_photo: bytes, count: int = 2) -> tuple[Family, Album, list[Photo]]:
    family = await repo.save_family(
        Family(name="菅谷家", members=[Member(name="母", relation="母", invite_status=InviteStatus.joined)])
    )
    album = await repo.save_album(Album(family_id=family.id, title="実家のアルバム"))
    photos = []
    for i in range(count):
        photo = Photo(album_id=album.id, family_id=family.id, filename=f"showa_{i}.jpg")
        ref = make_ref(family.id, album.id, "original", f"{photo.id}.bin")
        get_blobs().write(ref, gray_photo, "image/jpeg")
        photo.original_ref = ref
        photos.append(await repo.save_photo(photo))
    return family, album, photos


async def _run_ingest(family: Family, album: Album, photos: list[Photo]) -> Job:
    job = await repo.save_job(
        Job(family_id=family.id, album_id=album.id, total=len(photos), photo_ids=[p.id for p in photos])
    )
    await get_orchestrator().run(job=job)
    result = await repo.get_job(job.id)
    assert result is not None
    return result


async def test_ingest_proposes_without_confirming(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo)
    job = await _run_ingest(family, album, photos)

    assert job.status.value == "done"
    assert job.completed == len(photos)

    for photo in await repo.list_photos(album.id):
        # 預かった写真は、そのまま手を加えずに保管される
        assert photo.original_ref
        assert get_blobs().read(photo.original_ref) == gray_photo

        # 推定は候補・根拠・確度つき、確定はしていない
        assert photo.status is PhotoStatus.awaiting_family
        assert photo.estimate and photo.estimate.place_candidates
        assert all(c.evidence for c in photo.estimate.place_candidates)
        assert photo.estimate.era is not None
        assert photo.confirmed.place is None
        assert photo.questions


async def test_family_memory_overrides_ai(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=1)
    await _run_ingest(family, album, photos)

    photo = (await repo.list_photos(album.id))[0]
    ai_top = photo.estimate.place_candidates[0].name

    photo.confirmed.place = "JR五能線 驫木駅"
    photo.confirmed.confirmed_by = "母"
    photo.confirmed.family_correction = "駫木の駅。只見線ではないよ"
    await repo.save_photo(photo)

    reloaded = await repo.get_photo(photo.id)
    assert reloaded.resolved_place == "JR五能線 驫木駅"
    # AI の推定は消えずに残る（別フィールド保持）
    assert reloaded.estimate.place_candidates[0].name == ai_top


async def test_correction_feeds_back_into_next_estimate(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=2)
    await _run_ingest(family, album, photos)

    first, second = await repo.list_photos(album.id)
    hint = second.estimate.place_candidates[0].name.split()[-1]

    first.confirmed.place = second.estimate.place_candidates[0].name
    first.confirmed.confirmed_by = "母"
    first.confirmed.family_correction = f"この日は{hint}に行った日"
    await repo.save_photo(first)

    before = second.estimate.place_candidates[0].confidence
    await get_orchestrator().estimate.run(photo=second)
    after = (await repo.get_photo(second.id)).estimate.place_candidates[0].confidence
    assert after > before


async def test_story_does_not_confirm_relations(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=1)
    await _run_ingest(family, album, photos)
    photo = (await repo.list_photos(album.id))[0]

    await get_orchestrator().story.run(photo=photo, audio=b"dummy-audio", filename="talk.webm", narrator="母")
    reloaded = await repo.get_photo(photo.id)

    assert reloaded.story and reloaded.story.transcript
    assert reloaded.story.people
    assert all(not p.confirmed_by_family for p in reloaded.story.people)
    assert reloaded.story.audio_ref


async def test_itinerary_inserts_breaks_for_low_stamina(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=2)
    await _run_ingest(family, album, photos)

    stored = await repo.list_photos(album.id)
    for photo in stored:
        photo.confirmed.place = photo.estimate.place_candidates[0].name
        photo.confirmed.confirmed_by = "母"
        await repo.save_photo(photo)

    trip = await repo.save_trip(Trip(family_id=family.id, origin="東京", stamina=Stamina.low))
    await get_orchestrator().itinerary.run(trip=trip, photos=stored)
    planned = await repo.get_trip(trip.id)

    assert planned.itinerary and planned.itinerary.legs
    assert planned.itinerary.breaks > 0
    assert any(leg.kind == "break" for leg in planned.itinerary.legs)
    assert any(leg.kind == "stay" for leg in planned.itinerary.legs)
    assert planned.itinerary.accessibility_notes
    assert [s.place for s in planned.spots] == [p.confirmed.place for p in stored]


async def test_itinerary_times_never_go_backwards(gray_photo: bytes) -> None:
    """休憩を挟んだぶん、以降の時刻が後ろにずれること。"""
    family, album, photos = await _seed(gray_photo, count=2)
    await _run_ingest(family, album, photos)
    stored = await repo.list_photos(album.id)
    for photo in stored:
        photo.confirmed.place = photo.estimate.place_candidates[0].name
        await repo.save_photo(photo)

    trip = await repo.save_trip(Trip(family_id=family.id, origin="東京", stamina=Stamina.low))
    await get_orchestrator().itinerary.run(trip=trip, photos=stored, start_time="09:00")
    legs = (await repo.get_trip(trip.id)).itinerary.legs

    cursor = "09:00"
    for leg in legs:
        assert leg.depart == cursor, f"{leg.means} の出発時刻が前の区間の到着とつながっていません"
        cursor = leg.arrive


async def test_high_stamina_has_fewer_breaks(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=2)
    await _run_ingest(family, album, photos)
    stored = await repo.list_photos(album.id)
    for photo in stored:
        photo.confirmed.place = photo.estimate.place_candidates[0].name
        await repo.save_photo(photo)

    low = await repo.save_trip(Trip(family_id=family.id, stamina=Stamina.low))
    high = await repo.save_trip(Trip(family_id=family.id, stamina=Stamina.high))
    await get_orchestrator().itinerary.run(trip=low, photos=stored)
    await get_orchestrator().itinerary.run(trip=high, photos=stored)

    assert (await repo.get_trip(low.id)).itinerary.breaks > (await repo.get_trip(high.id)).itinerary.breaks


async def test_audit_records_external_calls_with_policy(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=1)
    await _run_ingest(family, album, photos)

    logs = await repo.list_audit(family.id)
    actions = {log.action for log in logs}
    assert AuditAction.estimate in actions
    external = [log for log in logs if log.action is AuditAction.external_call]
    assert external and all(log.policy for log in external)
    assert all(log.detail.get("opt_out_training") for log in external)


async def test_purge_family_removes_photos_and_blobs(gray_photo: bytes) -> None:
    family, album, photos = await _seed(gray_photo, count=2)
    await _run_ingest(family, album, photos)

    removed_blobs = get_blobs().delete_prefix(f"family/{family.id}")
    removed_docs = await repo.purge_family(family.id)

    assert removed_blobs >= 2  # original × 2
    assert removed_docs["photos"] == 2
    assert await repo.get_family(family.id) is None
    assert await repo.list_photos(album.id) == []
    # 監査ログは証跡として残る
    assert await repo.list_audit(family.id)
