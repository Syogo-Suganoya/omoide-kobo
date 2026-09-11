"""API の疎通と権限まわり。"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _wait_job(client: AsyncClient, job_id: str, tries: int = 200) -> dict:
    for _ in range(tries):
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError("ジョブが完了しませんでした")


async def test_full_flow(client: AsyncClient, gray_photo: bytes) -> None:
    family = (await client.post("/api/families", json={"name": "菅谷家"})).json()
    album = (
        await client.post("/api/albums", json={"family_id": family["id"], "title": "実家のアルバム"})
    ).json()

    res = await client.post(
        f"/api/albums/{album['id']}/photos",
        files=[
            ("files", ("a.jpg", gray_photo, "image/jpeg")),
            ("files", ("b.jpg", gray_photo, "image/jpeg")),
        ],
    )
    assert res.status_code == 200
    ingest = res.json()
    job = await _wait_job(client, ingest["job"]["id"])
    assert job["status"] == "done"

    photos = (await client.get(f"/api/albums/{album['id']}/photos")).json()
    assert len(photos) == 2
    first = photos[0]
    assert first["status"] == "awaiting_family"
    assert first["estimate"]["place_candidates"]
    assert first["questions"]

    # 預かった写真が取得できる
    image = await client.get(f"/api/photos/{first['id']}/image/original")
    assert image.status_code == 200 and image.content

    # 家族の確定
    confirm = await client.post(
        f"/api/photos/{first['id']}/confirm",
        json={
            "place": "JR五能線 驫木駅",
            "confirmed_by": "母",
            "family_correction": "只見線ではなく五能線",
            "answers": [{"question_id": first["questions"][0]["id"], "answer": "驫木の駅です"}],
        },
    )
    confirmed = confirm.json()
    assert confirmed["confirmed"]["place"] == "JR五能線 驫木駅"
    assert confirmed["status"] == "confirmed"
    assert confirmed["estimate"]["place_candidates"][0]["name"] != "JR五能線 驫木駅"
    assert confirmed["questions"][0]["answered"] is True

    # 語り（テキスト経路）
    story = await client.post(
        f"/api/photos/{first['id']}/story/text",
        json={"transcript": "母さんが女学校に通ってた駅なの。祖母もよく来ていた。", "narrator": "母"},
    )
    assert story.json()["story"]["summary"]
    assert all(not p["confirmed_by_family"] for p in story.json()["story"]["people"])

    # 旅程
    second = photos[1]
    await client.post(
        f"/api/photos/{second['id']}/confirm",
        json={"place": "尾道本通り商店街", "confirmed_by": "母"},
    )
    trip = await client.post(
        "/api/trips",
        json={
            "family_id": family["id"],
            "photo_ids": [first["id"], second["id"]],
            "origin": "東京",
            "stamina": "low",
        },
    )
    assert trip.status_code == 200
    itinerary = trip.json()["itinerary"]
    assert itinerary["breaks"] > 0
    assert itinerary["total_minutes"] > 0

    # 監査ログ
    logs = (await client.get(f"/api/families/{family['id']}/audit")).json()
    assert {log["action"] for log in logs} >= {"upload", "estimate", "family_confirm", "trip_plan"}

    # 削除権
    deleted = await client.delete(f"/api/families/{family['id']}")
    assert deleted.json()["deleted"] is True
    assert (await client.get(f"/api/photos/{first['id']}")).status_code == 404


async def test_share_link_lifecycle(client: AsyncClient, gray_photo: bytes) -> None:
    family = (await client.post("/api/families", json={"name": "菅谷家"})).json()
    album = (
        await client.post("/api/albums", json={"family_id": family["id"], "title": "実家のアルバム"})
    ).json()
    await client.post(
        f"/api/albums/{album['id']}/photos",
        files=[("files", ("a.jpg", gray_photo, "image/jpeg"))],
    )
    photo = (await client.get(f"/api/albums/{album['id']}/photos")).json()[0]
    await client.post(
        f"/api/photos/{photo['id']}/confirm",
        json={"place": "JR五能線 驫木駅", "confirmed_by": "母"},
    )

    created = await client.post(
        "/api/share",
        json={
            "family_id": family["id"],
            "target_type": "album",
            "target_id": album["id"],
            "created_by": "owner",
            "days": 7,
        },
    )
    assert created.status_code == 200
    token = created.json()["link"]["token"]
    assert created.json()["path"] == f"/s/{token}"

    view = await client.get(f"/api/shared/{token}")
    assert view.status_code == 200
    body = view.json()
    assert body["title"] == "実家のアルバム"
    # 共有相手に見えるのは確定内容だけ。AI の推定候補は含めない
    assert body["photos"][0]["place"] == "JR五能線 驫木駅"
    assert "estimate" not in body["photos"][0]

    image = await client.get(f"/api/shared/{token}/photos/{photo['id']}/image")
    assert image.status_code == 200 and image.content

    revoked = await client.post(f"/api/shares/{token}/revoke")
    assert revoked.json()["revoked"] is True
    assert (await client.get(f"/api/shared/{token}")).status_code == 410
    assert (await client.get(f"/api/shared/{token}/photos/{photo['id']}/image")).status_code == 410


async def test_photo_share_link_cannot_reach_other_photos(client: AsyncClient, gray_photo: bytes) -> None:
    family = (await client.post("/api/families", json={"name": "菅谷家"})).json()
    album = (await client.post("/api/albums", json={"family_id": family["id"], "title": "x"})).json()
    await client.post(
        f"/api/albums/{album['id']}/photos",
        files=[
            ("files", ("a.jpg", gray_photo, "image/jpeg")),
            ("files", ("b.jpg", gray_photo, "image/jpeg")),
        ],
    )
    first, second = (await client.get(f"/api/albums/{album['id']}/photos")).json()

    created = await client.post(
        "/api/share",
        json={
            "family_id": family["id"],
            "target_type": "photo",
            "target_id": first["id"],
            "created_by": "owner",
            "days": 1,
        },
    )
    token = created.json()["link"]["token"]

    assert (await client.get(f"/api/shared/{token}/photos/{first['id']}/image")).status_code == 200
    assert (await client.get(f"/api/shared/{token}/photos/{second['id']}/image")).status_code == 403


async def test_share_rejects_other_familys_target(client: AsyncClient) -> None:
    mine = (await client.post("/api/families", json={"name": "菅谷家"})).json()
    theirs = (await client.post("/api/families", json={"name": "よその家"})).json()
    album = (await client.post("/api/albums", json={"family_id": theirs["id"], "title": "x"})).json()

    res = await client.post(
        "/api/share",
        json={
            "family_id": mine["id"],
            "target_type": "album",
            "target_id": album["id"],
            "created_by": "owner",
            "days": 7,
        },
    )
    assert res.status_code == 404


async def test_agents_roster(client: AsyncClient) -> None:
    body = (await client.get("/api/agents")).json()
    names = {a["name"] for a in body["roster"]}
    assert names == {"orchestrator", "estimate", "story", "itinerary"}
    assert body["modes"]["gemini"] == "mock"
    assert body["policy"]


async def test_rejects_non_image(client: AsyncClient) -> None:
    family = (await client.post("/api/families", json={"name": "菅谷家"})).json()
    album = (await client.post("/api/albums", json={"family_id": family["id"], "title": "x"})).json()
    res = await client.post(
        f"/api/albums/{album['id']}/photos",
        files=[("files", ("a.txt", b"hello", "text/plain"))],
    )
    assert res.status_code == 415
