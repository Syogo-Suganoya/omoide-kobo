"""GMI Cloud（100+モデルの推論API）ポート。設計書 12章。

- restore / relight: bria-fibo 系。YouCam のカラー化と併用し、破れ・退色の復元と再照明で品質を底上げする
- animate: image-to-video。カラー化した写真を数秒だけ動かす「ウゴクアルバム」

mock は Pillow だけで完結する（restore/relight は別系統の絵作り、animate は寄りながら流れる GIF）。
生成物には必ず AI 生成の透かしを焼き込む。透かしは live/mock を問わず本実装側で入れるので、
モデルを差し替えても「実写真と混同させない」担保は外れない（設計書 12章）。
"""

from __future__ import annotations

import asyncio
import io
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.config import get_settings

WATERMARK = "AI GENERATED"


class GenerativePort(Protocol):
    name: str

    async def restore(self, image: bytes) -> bytes: ...

    async def relight(self, image: bytes) -> bytes: ...

    async def animate(self, image: bytes, prompt: str) -> tuple[bytes, str]: ...


def _load(image: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image)).convert("RGB")


def _dump(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def stamp_watermark(img: Image.Image) -> Image.Image:
    """AI 生成であることの透かし。実写真と並べても取り違えないよう、隅に常時表示する。"""
    out = img.copy()
    draw = ImageDraw.Draw(out, "RGBA")
    size = max(12, out.width // 32)
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:  # 古い Pillow はサイズ指定を取らない
        font = ImageFont.load_default()

    box = draw.textbbox((0, 0), WATERMARK, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = out.width - w - size, out.height - h - size
    draw.rectangle([x - 6, y - 5, x + w + 6, y + h + 6], fill=(0, 0, 0, 130))
    draw.text((x, y), WATERMARK, font=font, fill=(255, 255, 255, 235))
    return out


# --------------------------------------------------------------------------- mock


class MockGmi:
    name = "gmi-mock"

    async def restore(self, image: bytes) -> bytes:
        """破れ・粒状ノイズを均し、階調を伸ばす。YouCam 側とは違う絵作りにして比較が意味を持つようにする。"""
        img = _load(image)
        img = img.filter(ImageFilter.MedianFilter(size=5))
        img = ImageOps.autocontrast(img, cutoff=2)
        img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=140, threshold=2))
        return _dump(ImageEnhance.Color(img).enhance(1.08))

    async def relight(self, image: bytes) -> bytes:
        """再照明。斜め上からの光を足して、平板な古写真に立体感を戻す。"""
        img = _load(image)
        light = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(light)
        # 左上を明るく、右下へ落とす楕円グラデーション
        for i in range(24, 0, -1):
            k = i / 24
            box = [
                -img.width * 0.4 + img.width * 0.55 * (1 - k),
                -img.height * 0.5 + img.height * 0.6 * (1 - k),
                img.width * (0.5 + 0.9 * k),
                img.height * (0.5 + 1.0 * k),
            ]
            draw.ellipse(box, fill=int(60 * (1 - k)))
        glow = Image.merge("RGB", (light, light, light)).filter(ImageFilter.GaussianBlur(24))
        lit = Image.blend(img, Image.blend(img, glow, 0.35), 0.6)
        return _dump(ImageEnhance.Contrast(lit).enhance(1.06))

    async def animate(self, image: bytes, prompt: str) -> tuple[bytes, str]:
        """寄りながらわずかに流れる数秒のクリップ。

        人物を動かすのではなく、カメラ側だけを動かす（＝生成範囲を「その場の自然な動き」に留める）。
        mp4 のエンコーダを持ち込まずに済むよう GIF で返す。
        """
        base = _load(image)
        # GIF はフレームぶん重くなるので、長辺 720px に落としてから作る
        if base.width > 720:
            base = base.resize((720, int(base.height * 720 / base.width)), Image.LANCZOS)
        frames: list[Image.Image] = []
        steps = 16
        for i in range(steps):
            k = i / (steps - 1)
            zoom = 1.0 + 0.08 * k
            w, h = int(base.width / zoom), int(base.height / zoom)
            # ゆっくり右下へパン
            left = int((base.width - w) * (0.35 + 0.3 * k))
            top = int((base.height - h) * (0.35 + 0.3 * k))
            frame = base.crop((left, top, left + w, top + h)).resize(
                (base.width, base.height), Image.LANCZOS
            )
            frame = ImageEnhance.Brightness(frame).enhance(0.98 + 0.04 * k)
            frames.append(stamp_watermark(frame).convert("P", palette=Image.ADAPTIVE))

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:] + frames[-2:0:-1],  # 往復させて切れ目を目立たせない
            duration=110,
            loop=0,
            optimize=True,
        )
        return buf.getvalue(), "image/gif"


# --------------------------------------------------------------------------- live


class LiveGmi:
    """GMI Cloud の推論 API（OpenAI 互換のエンドポイント＋非同期タスク）。

    動画生成は投げっぱなしにできないので、タスク ID をポーリングして URL を取る。
    モデル名とパスは契約プランやモデルの世代で変わるため、実キー投入時に
    docs.gmicloud.ai と突き合わせて確認すること（未疎通）。
    """

    name = "gmi"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gmi_api_key:
            raise RuntimeError("GMI_API_KEY が未設定です")
        self._base = settings.gmi_base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {settings.gmi_api_key}"}
        self._image_model = settings.gmi_image_model
        self._video_model = settings.gmi_video_model

    async def _image_edit(self, image: bytes, model: str, prompt: str) -> bytes:
        async with httpx.AsyncClient(timeout=180) as client:
            res = await client.post(
                f"{self._base}/v1/images/edits",
                headers=self._headers,
                files={"image": ("src.jpg", image, "image/jpeg")},
                data={"model": model, "prompt": prompt, "response_format": "b64_json"},
            )
            res.raise_for_status()
            payload = res.json()["data"][0]
            if "b64_json" in payload:
                import base64

                return base64.b64decode(payload["b64_json"])
            out = await client.get(payload["url"])
            out.raise_for_status()
            return out.content

    async def restore(self, image: bytes) -> bytes:
        return await self._image_edit(
            image, f"{self._image_model}-restore", "破れ・退色・傷を復元する。構図と人物は変えない。"
        )

    async def relight(self, image: bytes) -> bytes:
        return await self._image_edit(
            image, f"{self._image_model}-relight", "自然光で撮り直したように再照明する。被写体は変えない。"
        )

    async def animate(self, image: bytes, prompt: str) -> tuple[bytes, str]:
        import base64

        async with httpx.AsyncClient(timeout=600) as client:
            task = await client.post(
                f"{self._base}/v1/videos/generations",
                headers=self._headers,
                json={
                    "model": self._video_model,
                    "prompt": prompt,
                    "image": base64.b64encode(image).decode(),
                    "duration": 4,
                },
            )
            task.raise_for_status()
            task_id = task.json()["id"]

            for _ in range(120):
                poll = await client.get(f"{self._base}/v1/videos/generations/{task_id}", headers=self._headers)
                poll.raise_for_status()
                body = poll.json()
                if body.get("status") in ("succeeded", "completed"):
                    video = await client.get(body["output"][0]["url"])
                    video.raise_for_status()
                    return video.content, "video/mp4"
                if body.get("status") in ("failed", "cancelled"):
                    raise RuntimeError(f"GMI 動画生成に失敗: {body}")
                await asyncio.sleep(5)
            raise TimeoutError("GMI 動画生成がタイムアウトしました")


def get_generative() -> GenerativePort:
    return LiveGmi() if get_settings().gmi_mode == "live" else MockGmi()
