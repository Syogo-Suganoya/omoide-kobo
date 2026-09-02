"""修復エージェントが使う画像処理ポート（スポンサー: YouCam API）。

mock は Pillow でカラー化相当の見た目（輝度→肌・空・草の色域へのグラデーションマップ）と
退色補正・ノイズ除去・折れ跡の緩和をローカル実行する。デモは鍵なしで最後まで通る。
live は YouCam(Perfect Corp) S2S API を叩く。
"""

from __future__ import annotations

import asyncio
import io
from typing import Protocol

import httpx
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.config import get_settings


class RestorePort(Protocol):
    name: str

    async def colorize(self, image: bytes) -> bytes: ...

    async def enhance(self, image: bytes) -> bytes: ...

    async def remove_defects(self, image: bytes) -> bytes: ...


def _load(image: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image)).convert("RGB")


def _dump(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# 影→中間→ハイライト の3点を通す色ランプ。褪せた白黒に自然な色味を戻す狙い。
_RAMP = ((34, 42, 68), (176, 134, 104), (252, 244, 224))


def _ramp_lut() -> tuple[list[int], list[int], list[int]]:
    shadow, mid, high = _RAMP
    luts: list[list[int]] = [[], [], []]
    for i in range(256):
        t = i / 255
        for ch in range(3):
            if t < 0.5:
                k = t / 0.5
                value = shadow[ch] + (mid[ch] - shadow[ch]) * k
            else:
                k = (t - 0.5) / 0.5
                value = mid[ch] + (high[ch] - mid[ch]) * k
            luts[ch].append(int(max(0, min(255, value))))
    return luts[0], luts[1], luts[2]


_R_LUT, _G_LUT, _B_LUT = _ramp_lut()


class MockYouCam:
    name = "youcam-mock"

    async def colorize(self, image: bytes) -> bytes:
        img = _load(image)
        gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
        toned = Image.merge(
            "RGB", (gray.point(_R_LUT), gray.point(_G_LUT), gray.point(_B_LUT))
        )
        # 元の階調を残すため、グレー画像と重ねてから彩度を少し戻す
        blended = Image.blend(img, toned, 0.72)
        return _dump(ImageEnhance.Color(blended).enhance(1.15))

    async def enhance(self, image: bytes) -> bytes:
        img = _load(image)
        img = ImageOps.autocontrast(img, cutoff=1)  # 退色補正
        img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=110, threshold=3))
        return _dump(ImageEnhance.Brightness(img).enhance(1.03))

    async def remove_defects(self, image: bytes) -> bytes:
        img = _load(image)
        # 折れ跡・粒状ノイズをメディアンで均し、輪郭はシャープで戻す
        img = img.filter(ImageFilter.MedianFilter(size=3))
        return _dump(img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=4)))


class LiveYouCam:
    """YouCam(Perfect Corp) S2S API 実装。

    フロー: client/auth でアクセストークン取得 → file/photo-* でアップロード先取得 →
    task 作成 → ポーリングで結果 URL を取得。エンドポイントは契約プランで異なるため、
    実キー投入時に docs.perfectcorp.com と突き合わせて確認すること。
    """

    name = "youcam"
    BASE = "https://yce-api-01.perfectcorp.com"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.youcam_api_key:
            raise RuntimeError("YOUCAM_API_KEY が未設定です")
        self._api_key = settings.youcam_api_key
        self._secret = settings.youcam_secret_key
        self._token: str | None = None

    async def _auth(self, client: httpx.AsyncClient) -> str:
        if self._token:
            return self._token
        res = await client.post(
            f"{self.BASE}/s2s/v1.0/client/auth",
            json={"client_id": self._api_key, "id_token": self._secret},
        )
        res.raise_for_status()
        self._token = res.json()["result"]["access_token"]
        return self._token

    async def _run(self, image: bytes, action: str) -> bytes:
        async with httpx.AsyncClient(timeout=120) as client:
            token = await self._auth(client)
            headers = {"Authorization": f"Bearer {token}"}

            upload = await client.post(
                f"{self.BASE}/s2s/v1.0/file/photo-{action}",
                headers=headers,
                json={"files": [{"content_type": "image/jpeg", "file_name": "src.jpg"}]},
            )
            upload.raise_for_status()
            entry = upload.json()["result"]["files"][0]
            await client.put(entry["requests"][0]["url"], content=image)

            task = await client.post(
                f"{self.BASE}/s2s/v1.0/task/photo-{action}",
                headers=headers,
                json={"request_id": 0, "payload": {"file_sets": {"src_ids": [entry["file_id"]]}}},
            )
            task.raise_for_status()
            task_id = task.json()["result"]["task_id"]

            for _ in range(60):
                poll = await client.get(
                    f"{self.BASE}/s2s/v1.0/task/photo-{action}",
                    headers=headers,
                    params={"task_id": task_id},
                )
                poll.raise_for_status()
                result = poll.json()["result"]
                if result["status"] == "success":
                    out = await client.get(result["results"][0]["data"][0]["url"])
                    out.raise_for_status()
                    return out.content
                if result["status"] == "error":
                    raise RuntimeError(f"YouCam {action} 失敗: {result}")
                await asyncio.sleep(2)
            raise TimeoutError(f"YouCam {action} がタイムアウトしました")

    async def colorize(self, image: bytes) -> bytes:
        return await self._run(image, "colorize")

    async def enhance(self, image: bytes) -> bytes:
        return await self._run(image, "enhance")

    async def remove_defects(self, image: bytes) -> bytes:
        return await self._run(image, "object-removal")


def get_restorer() -> RestorePort:
    return LiveYouCam() if get_settings().youcam_mode == "live" else MockYouCam()
