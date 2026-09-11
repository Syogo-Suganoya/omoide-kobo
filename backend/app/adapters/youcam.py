"""修復エージェントが使う画像処理ポート（スポンサー: YouCam API）。

mock は Pillow でカラー化相当の見た目（輝度→肌・空・草の色域へのグラデーションマップ）と
退色補正・ノイズ除去・折れ跡の緩和をローカル実行する。デモは鍵なしで最後まで通る。
live は YouCam(Perfect Corp) S2S API を叩く。
"""

from __future__ import annotations

import asyncio
import base64
import io
import time
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


def _id_token(client_id: str, client_secret: str) -> str:
    """S2S v1 の id_token を作る。

    公式仕様: `client_id=<client_id>&timestamp=<ミリ秒>` を、X.509 形式を Base64 にした
    client_secret（＝公開鍵）で RSA 暗号化し、その結果を Base64 にしたもの。
    生のシークレットをそのまま渡しても 401 になる。
    """
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    public_key = load_der_public_key(base64.b64decode(client_secret))
    plain = f"client_id={client_id}&timestamp={int(time.time() * 1000)}".encode()
    return base64.b64encode(public_key.encrypt(plain, padding.PKCS1v15())).decode()


class LiveYouCam:
    """YouCam(Perfect Corp) S2S v1 API 実装。

    フロー: client/auth でアクセストークン取得（2時間有効）→ file/{機能} でアップロード先を
    もらって PUT → task/{機能} を作成 → ポーリングで結果 URL を取得。
    ポーリングを 10 秒空けるとタスクが破棄されるので、返ってくる polling_interval に従う。
    """

    name = "youcam"
    BASE = "https://yce-api-01.perfectcorp.com"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.youcam_api_key:
            raise RuntimeError("YOUCAM_API_KEY が未設定です")
        if not settings.youcam_secret_key:
            raise RuntimeError("YOUCAM_SECRET_KEY が未設定です（id_token の生成に要ります）")
        self._api_key = settings.youcam_api_key
        self._secret = settings.youcam_secret_key
        self._token: str | None = None
        # 同じ request_id は再実行されない（課金の二重取りを防ぐ仕様）。タスクごとに進める
        self._request_id = 0

    async def _auth(self, client: httpx.AsyncClient) -> str:
        if self._token:
            return self._token
        res = await client.post(
            f"{self.BASE}/s2s/v1.0/client/auth",
            json={"client_id": self._api_key, "id_token": _id_token(self._api_key, self._secret)},
        )
        res.raise_for_status()
        self._token = res.json()["result"]["access_token"]
        return self._token

    async def _run(self, image: bytes, action: str, params: dict | None = None) -> bytes:
        async with httpx.AsyncClient(timeout=120) as client:
            token = await self._auth(client)
            headers = {"Authorization": f"Bearer {token}"}

            upload = await client.post(
                f"{self.BASE}/s2s/v1.0/file/{action}",
                headers=headers,
                json={"files": [{"content_type": "image/jpeg", "file_name": "src.jpg"}]},
            )
            upload.raise_for_status()
            entry = upload.json()["result"]["files"][0]
            request = entry["requests"][0]
            put = await client.request(
                request.get("method", "PUT"),
                request["url"],
                content=image,
                headers=request.get("headers") or {"Content-Type": "image/jpeg"},
            )
            put.raise_for_status()

            self._request_id += 1
            act: dict[str, object] = {"id": 0}
            if params:
                act["params"] = params
            task = await client.post(
                f"{self.BASE}/s2s/v1.0/task/{action}",
                headers=headers,
                json={
                    "request_id": self._request_id,
                    "payload": {
                        "file_sets": {"src_ids": [entry["file_id"]]},
                        "actions": [act],
                    },
                },
            )
            task.raise_for_status()
            task_id = task.json()["result"]["task_id"]

            for _ in range(120):
                poll = await client.get(
                    f"{self.BASE}/s2s/v1.0/task/{action}",
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
                # 10 秒空けるとタスクが捨てられる。サーバーの指示に従い、上限も 5 秒に抑える
                await asyncio.sleep(min(result.get("polling_interval", 500) / 1000, 5))
            raise TimeoutError(f"YouCam {action} がタイムアウトしました")

    async def colorize(self, image: bytes) -> bytes:
        return await self._run(image, "colorize")

    async def enhance(self, image: bytes) -> bytes:
        # scale は拡大率。元の大きさのまま精細化したいので 1
        return await self._run(image, "enhance", {"scale": 1})

    async def remove_defects(self, image: bytes) -> bytes:
        """YouCam に折れ跡・粒状ノイズ向けの機能が無いので、ここだけローカルで処理する。

        obj-removal は消したい範囲のマスクを渡す機能で、用途が違う。
        この後段の enhance（ノイズ除去を含む）と colorize が API 側の仕事。
        """
        return await MockYouCam().remove_defects(image)


def get_restorer() -> RestorePort:
    return LiveYouCam() if get_settings().youcam_mode == "live" else MockYouCam()
