"""ウゴクアルバムのガバナンス（設計書 12章）。

故人を動かす以上、同意ゲートと透かしと生成範囲の3つは機能ではなく前提。
ここが落ちる変更は、実装ではなく設計の後退。
"""

from __future__ import annotations

import asyncio
import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app import repo
from app.adapters.gmi import WATERMARK, MockGmi, stamp_watermark
from app.agents.motion import ConsentRequired, MotionAgent
from app.main import app
from app.models import Family, InviteStatus, Member, Photo

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed(client: AsyncClient, gray_photo: bytes, members: int = 2) -> tuple[dict, dict]:
    family = (
        await client.post(
            "/api/families",
            json={
                "name": "菅谷家",
                "members": [
                    {"name": f"家族{i}", "relation": "家族", "invite_status": "joined"}
                    for i in range(members)
                ],
            },
        )
    ).json()
    album = (await client.post("/api/albums", json={"family_id": family["id"], "title": "実家"})).json()
    ingest = (
        await client.post(
            f"/api/albums/{album['id']}/photos", files=[("files", ("a.jpg", gray_photo, "image/jpeg"))]
        )
    ).json()

    # 修復はレスポンス後にバックグラウンドで走るので、終わるまで待つ
    for _ in range(200):
        job = (await client.get(f"/api/jobs/{ingest['job']['id']}")).json()
        if job["status"] in ("done", "failed"):
            break
        await asyncio.sleep(0.05)
    else:
        raise AssertionError("取り込みが終わりませんでした")

    photo = (await client.get(f"/api/albums/{album['id']}/photos")).json()[0]
    return family, photo


async def _wait(client: AsyncClient, motion_id: str, tries: int = 200) -> dict:
    for _ in range(tries):
        clip = (await client.get(f"/api/motions/{motion_id}")).json()
        if clip["status"] in ("ready", "failed", "denied", "pending_consent"):
            if clip["status"] != "pending_consent" or clip["video_ref"] is None:
                return clip
        await asyncio.sleep(0.05)
    raise AssertionError("生成が終わりませんでした")


async def test_restore_produces_two_variants(client: AsyncClient, gray_photo: bytes) -> None:
    """YouCam と GMI の2系統が並び、どちらを採るかは家族が選ぶ（AI は選ばない）。"""
    _, photo = await _seed(client, gray_photo)

    assert photo["restored_ref"] and photo["alt_restored_ref"]
    assert photo["restored_ref"] != photo["alt_restored_ref"]
    assert photo["restored_provider"] == "youcam-mock"
    assert photo["alt_restored_provider"] == "gmi-mock"
    assert photo["preferred_variant"] is None  # AI は決めない

    for kind in ("original", "restored", "alt"):
        res = await client.get(f"/api/photos/{photo['id']}/image/{kind}")
        assert res.status_code == 200 and res.content

    chosen = await client.post(
        f"/api/photos/{photo['id']}/variant", json={"variant": "alt", "chosen_by": "母"}
    )
    assert chosen.json()["preferred_variant"] == "alt"


async def test_deceased_photo_waits_for_every_family_member(client: AsyncClient, gray_photo: bytes) -> None:
    family, photo = await _seed(client, gray_photo, members=3)
    uids = [m["uid"] for m in family["members"]]

    clip = (
        await client.post(
            f"/api/photos/{photo['id']}/motion",
            json={"requested_by": "娘", "includes_deceased": True},
        )
    ).json()
    assert clip["status"] == "pending_consent"
    assert len(clip["consents"]) == 3
    assert clip["video_ref"] is None

    # 2人だけ同意しても始まらない
    for uid in uids[:2]:
        body = (
            await client.post(f"/api/motions/{clip['id']}/consent", json={"uid": uid, "status": "granted"})
        ).json()
        assert body["status"] == "pending_consent"
        assert body["video_ref"] is None

    # 最後の1人で初めて動き出す
    await client.post(f"/api/motions/{clip['id']}/consent", json={"uid": uids[2], "status": "granted"})
    done = await _wait(client, clip["id"])
    assert done["status"] == "ready"
    assert done["video_ref"] and done["watermarked"] is True


async def test_one_refusal_blocks_generation(client: AsyncClient, gray_photo: bytes) -> None:
    family, photo = await _seed(client, gray_photo, members=2)
    uids = [m["uid"] for m in family["members"]]

    clip = (
        await client.post(
            f"/api/photos/{photo['id']}/motion",
            json={"requested_by": "娘", "includes_deceased": True},
        )
    ).json()
    await client.post(f"/api/motions/{clip['id']}/consent", json={"uid": uids[0], "status": "granted"})
    denied = (
        await client.post(f"/api/motions/{clip['id']}/consent", json={"uid": uids[1], "status": "denied"})
    ).json()

    assert denied["status"] == "denied"
    assert denied["video_ref"] is None
    assert (await client.get(f"/api/motions/{clip['id']}/video")).status_code == 404


async def test_agent_refuses_to_generate_without_consent(gray_photo: bytes) -> None:
    """API を迂回してエージェントを直接叩いても、同意なしでは生成しない。"""
    family = await repo.save_family(
        Family(name="菅谷家", members=[Member(name="母", relation="母", invite_status=InviteStatus.joined)])
    )
    photo = await repo.save_photo(
        Photo(album_id="alb_x", family_id=family.id, filename="a.jpg", original_ref="x", restored_ref="y")
    )
    agent = MotionAgent()
    clip = agent.prepare(photo=photo, family=family, requested_by="娘", includes_deceased=True)

    with pytest.raises(ConsentRequired):
        await agent.run(clip=clip, photo=photo)


async def test_generated_clip_is_watermarked_and_moving(gray_photo: bytes) -> None:
    video, media_type = await MockGmi().animate(gray_photo, "prompt")
    clip = Image.open(io.BytesIO(video))

    assert media_type == "image/gif"
    assert getattr(clip, "n_frames", 1) > 1  # 静止画ではない

    # 透かしが焼き込まれていること（同じ入力に透かしを足すと画が変わる）
    plain = Image.open(io.BytesIO(gray_photo)).convert("RGB")
    assert stamp_watermark(plain).tobytes() != plain.tobytes()
    assert WATERMARK


async def test_audit_records_consent_and_scope(client: AsyncClient, gray_photo: bytes) -> None:
    family, photo = await _seed(client, gray_photo, members=1)
    uid = family["members"][0]["uid"]

    clip = (
        await client.post(
            f"/api/photos/{photo['id']}/motion",
            json={"requested_by": "娘", "includes_deceased": True},
        )
    ).json()
    await client.post(f"/api/motions/{clip['id']}/consent", json={"uid": uid, "status": "granted"})
    await _wait(client, clip["id"])

    logs = (await client.get(f"/api/families/{family['id']}/audit")).json()
    actions = {log["action"] for log in logs}
    assert {"motion_request", "motion_consent", "motion_generate"} <= actions

    generated = next(log for log in logs if log["action"] == "motion_generate")
    assert generated["detail"]["watermarked"] is True
    assert "発話" in generated["detail"]["scope"]  # 生成範囲の制限が証跡に残る
    assert generated["detail"]["consents"][0]["status"] == "granted"


async def test_motion_status_included_in_roster(client: AsyncClient) -> None:
    body = (await client.get("/api/agents")).json()
    motion = next(a for a in body["roster"] if a["name"] == "motion")
    assert motion["autonomy"] == "consent_gated"
    assert body["modes"]["gmi"] == "mock"
