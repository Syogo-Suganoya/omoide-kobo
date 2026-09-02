"""Firestore ドライバの疎通テスト。

本番と開発の既定の保存先はここなので、エミュレータがいるときは必ず通す。
（単体テストは memory ドライバなので、このファイルだけが FirestoreStore の実コードを踏む）
エミュレータが無い環境では skip する。
"""

from __future__ import annotations

import os
import socket
import uuid

import pytest

from app.infra.store import FirestoreStore

pytestmark = pytest.mark.asyncio


def _emulator_up() -> bool:
    host_port = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not host_port:
        return False
    host, _, port = host_port.partition(":")
    try:
        with socket.create_connection((host, int(port or 8080)), timeout=2):
            return True
    except OSError:
        return False


pytest.importorskip("google.cloud.firestore")
if not _emulator_up():
    pytest.skip("Firestore エミュレータが無いので飛ばします", allow_module_level=True)


@pytest.fixture
def store():
    client = FirestoreStore(os.environ.get("GOOGLE_CLOUD_PROJECT", "omoide-kobo-local"))
    yield client
    client.close()


async def test_put_get_query_delete(store) -> None:
    collection = f"test_{uuid.uuid4().hex[:8]}"
    family = f"fam_{uuid.uuid4().hex[:8]}"

    await store.put(collection, "a", {"id": "a", "family_id": family, "created_at": "2026-01-01", "n": 1})
    await store.put(collection, "b", {"id": "b", "family_id": family, "created_at": "2026-01-02", "n": 2})
    await store.put(collection, "c", {"id": "c", "family_id": "other", "created_at": "2026-01-03", "n": 3})

    assert (await store.get(collection, "a"))["n"] == 1
    assert await store.get(collection, "missing") is None

    # 家族スコープで絞れること、created_at 昇順で返ること
    mine = await store.query(collection, family_id=family)
    assert [d["id"] for d in mine] == ["a", "b"]

    await store.delete(collection, "a")
    assert await store.get(collection, "a") is None

    # 家族単位の一括削除が他家族に及ばないこと
    assert await store.delete_where(collection, family_id=family) == 1
    assert [d["id"] for d in await store.query(collection)] == ["c"]

    await store.delete(collection, "c")
