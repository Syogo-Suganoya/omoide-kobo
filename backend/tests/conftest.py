from __future__ import annotations

import io
import os
import tempfile

os.environ.setdefault("APP_ENV", "test")
for provider in ("GEMINI", "YOUCAM", "EKISPERT", "SPEECH", "LINE"):
    os.environ[f"{provider}_MODE"] = "mock"
os.environ["DB_DRIVER"] = "memory"
os.environ["STORAGE_DRIVER"] = "local"

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.infra.blobs import LocalBlobStore, reset_blobs  # noqa: E402
from app.infra.store import MemoryStore, reset_store  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state(tmp_path):
    get_settings.cache_clear()
    os.environ["STORAGE_LOCAL_ROOT"] = str(tmp_path / "storage")
    reset_store(MemoryStore())
    reset_blobs(LocalBlobStore(str(tmp_path / "storage")))
    yield
    reset_store(None)
    reset_blobs(None)


@pytest.fixture
def gray_photo() -> bytes:
    """白黒写真のダミー（グラデーション）。"""
    img = Image.new("L", (240, 160))
    for x in range(240):
        for y in range(160):
            img.putpixel((x, y), (x + y) % 256)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def tmp_root() -> str:
    return tempfile.mkdtemp()
