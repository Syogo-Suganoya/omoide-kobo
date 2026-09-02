"""ドキュメントストア抽象。

- firestore: 既定。開発はエミュレータ、本番は GCP（FIRESTORE_EMULATOR_HOST の有無で切り替わる）
- memory: テスト専用のフォールバック。プロセス内に持ち、/data/db.json に落とすだけ

コレクション名は設計書 6章 と対応: families / albums / photos / trips / shares / audit / jobs
"""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

Doc = dict[str, Any]


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


class Store(ABC):
    @abstractmethod
    async def put(self, collection: str, doc_id: str, data: Doc) -> None: ...

    @abstractmethod
    async def get(self, collection: str, doc_id: str) -> Doc | None: ...

    @abstractmethod
    async def query(self, collection: str, **equals: Any) -> list[Doc]: ...

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> None: ...

    @abstractmethod
    async def delete_where(self, collection: str, **equals: Any) -> int: ...


class MemoryStore(Store):
    def __init__(self, persist_path: str | None = None) -> None:
        self._data: dict[str, dict[str, Doc]] = {}
        self._lock = asyncio.Lock()
        self._path = Path(persist_path) if persist_path else None
        self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                self._data = json.loads(self._path.read_text("utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, default=str), "utf-8")
        tmp.replace(self._path)

    async def put(self, collection: str, doc_id: str, data: Doc) -> None:
        async with self._lock:
            self._data.setdefault(collection, {})[doc_id] = _jsonable(data)
            self._flush()

    async def get(self, collection: str, doc_id: str) -> Doc | None:
        return self._data.get(collection, {}).get(doc_id)

    async def query(self, collection: str, **equals: Any) -> list[Doc]:
        docs = list(self._data.get(collection, {}).values())
        for key, value in equals.items():
            docs = [d for d in docs if d.get(key) == value]
        return sorted(docs, key=lambda d: str(d.get("created_at", "")))

    async def delete(self, collection: str, doc_id: str) -> None:
        async with self._lock:
            self._data.get(collection, {}).pop(doc_id, None)
            self._flush()

    async def delete_where(self, collection: str, **equals: Any) -> int:
        targets = await self.query(collection, **equals)
        async with self._lock:
            bucket = self._data.get(collection, {})
            for doc in targets:
                bucket.pop(doc["id"], None)
            self._flush()
        return len(targets)


class FirestoreStore(Store):
    def __init__(self, project: str) -> None:
        from google.cloud import firestore  # 遅延 import（テストの memory 運用では触らない）

        self._client = firestore.AsyncClient(project=project)

    async def put(self, collection: str, doc_id: str, data: Doc) -> None:
        await self._client.collection(collection).document(doc_id).set(_jsonable(data))

    async def get(self, collection: str, doc_id: str) -> Doc | None:
        snap = await self._client.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    async def query(self, collection: str, **equals: Any) -> list[Doc]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        ref = self._client.collection(collection)
        for key, value in equals.items():
            ref = ref.where(filter=FieldFilter(key, "==", value))
        docs = [snap.to_dict() async for snap in ref.stream()]
        # 並びは created_at。複合インデックス無しで済ませるため、並べ替えは手元で行う
        return sorted(docs, key=lambda d: str(d.get("created_at", "")))

    async def delete(self, collection: str, doc_id: str) -> None:
        await self._client.collection(collection).document(doc_id).delete()

    async def delete_where(self, collection: str, **equals: Any) -> int:
        targets = await self.query(collection, **equals)
        for doc in targets:
            await self.delete(collection, doc["id"])
        return len(targets)

    def close(self) -> None:
        """gRPC のチャネルを閉じる。閉じないとテストプロセスが終了しない。"""
        self._client.close()


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        settings = get_settings()
        if settings.db_driver == "firestore":
            _store = FirestoreStore(settings.google_cloud_project)
        else:
            root = os.path.dirname(settings.storage_local_root.rstrip("/")) or "/data"
            _store = MemoryStore(persist_path=os.path.join(root, "db.json"))
    return _store


def reset_store(store: Store | None = None) -> None:
    """テスト用。"""
    global _store
    _store = store
