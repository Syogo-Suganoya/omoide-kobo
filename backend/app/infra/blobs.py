"""家族限定バケット。

参照は `family/{familyId}/{albumId}/{kind}/{name}` 形式で、必ず familyId 配下に閉じる。
読み書きの入口はここだけにして、家族スコープ外のパスは弾く。
預かった写真は元のまま保管し、上書きしない。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings

_REF = re.compile(r"^family/(?P<family>[A-Za-z0-9_\-]+)/(?P<rest>[A-Za-z0-9_\-./]+)$")


class BlobRefError(ValueError):
    pass


def make_ref(family_id: str, album_id: str, kind: str, name: str) -> str:
    ref = f"family/{family_id}/{album_id}/{kind}/{name}"
    validate_ref(ref, family_id)
    return ref


def validate_ref(ref: str, family_id: str | None = None) -> str:
    match = _REF.match(ref)
    if not match or ".." in ref:
        raise BlobRefError(f"不正な参照です: {ref}")
    if family_id and match.group("family") != family_id:
        raise BlobRefError("家族スコープ外の参照です")
    return ref


class BlobStore(ABC):
    @abstractmethod
    def write(self, ref: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...

    @abstractmethod
    def read(self, ref: str) -> bytes: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int: ...


class LocalBlobStore(BlobStore):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, ref: str) -> Path:
        validate_ref(ref)
        return self.root / ref

    def write(self, ref: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return ref

    def read(self, ref: str) -> bytes:
        return self._path(ref).read_bytes()

    def delete_prefix(self, prefix: str) -> int:
        base = self.root / prefix
        if not base.exists():
            return 0
        count = sum(1 for p in base.rglob("*") if p.is_file())
        for path in sorted(base.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        base.rmdir()
        return count


class GcsBlobStore(BlobStore):
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage  # 遅延 import

        self._bucket = storage.Client().bucket(bucket)

    def write(self, ref: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        validate_ref(ref)
        self._bucket.blob(ref).upload_from_string(data, content_type=content_type)
        return ref

    def read(self, ref: str) -> bytes:
        validate_ref(ref)
        return self._bucket.blob(ref).download_as_bytes()

    def delete_prefix(self, prefix: str) -> int:
        blobs = list(self._bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
        return len(blobs)


_blobs: BlobStore | None = None


def get_blobs() -> BlobStore:
    global _blobs
    if _blobs is None:
        settings = get_settings()
        if settings.storage_driver == "gcs":
            _blobs = GcsBlobStore(settings.gcs_bucket)
        else:
            _blobs = LocalBlobStore(settings.storage_local_root)
    return _blobs


def reset_blobs(store: BlobStore | None = None) -> None:
    global _blobs
    _blobs = store
