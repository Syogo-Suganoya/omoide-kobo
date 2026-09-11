"""YouCam(Perfect Corp) S2S API への疎通確認。

    docker compose run --rm api python -m scripts.check_youcam          # 認証だけ
    docker compose run --rm api python -m scripts.check_youcam colorize # 画像1枚を通す

YOUCAM_API_KEY と YOUCAM_SECRET_KEY が要る（.env に書けば compose が渡す）。
YOUCAM_MODE は見ていないので、mock 運用のままでも live 接続だけを試せる。
"""

from __future__ import annotations

import asyncio
import io
import sys

import httpx
from PIL import Image

from app.adapters.youcam import LiveYouCam
from app.config import get_settings


def _sample_photo() -> bytes:
    """通しの確認用。灰色の階調だけの小さな画像。"""
    img = Image.new("RGB", (512, 384))
    pixels = img.load()
    for x in range(512):
        tone = 40 + int(170 * x / 512)
        for y in range(384):
            pixels[x, y] = (tone, tone, tone)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


async def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    settings = get_settings()

    print(f"接続先     : {LiveYouCam.BASE}")
    print(f"APIキー    : {'設定あり' if settings.youcam_api_key else '未設定'}")
    print(f"シークレット: {'設定あり' if settings.youcam_secret_key else '未設定'}\n")

    try:
        youcam = LiveYouCam()
    except Exception as exc:
        print(f"失敗: {exc}")
        return 1

    # 1) 認証だけ先に試す。ここで落ちるならキーか id_token の作り方が違う
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            token = await youcam._auth(client)
        print(f"認証 OK（アクセストークン {len(token)} 文字）")
    except httpx.HTTPStatusError as exc:
        print(f"認証 NG: HTTP {exc.response.status_code}")
        print(f"  応答: {exc.response.text[:500]}")
        if exc.response.status_code == 401:
            print(
                "\n  確認すること:\n"
                "   - コンソール（yce.makeupar.com の API Key タブ）でキーが有効か・期限切れでないか\n"
                "   - YOUCAM_API_KEY に API キー、YOUCAM_SECRET_KEY にシークレットキーが入っているか\n"
                "   - ユニット（クレジット）が残っているか"
            )
        return 1
    except Exception as exc:
        print(f"認証 NG: {type(exc).__name__}: {exc}")
        return 1

    if not action:
        print("\n画像まで通すなら: ... python -m scripts.check_youcam colorize")
        return 0

    # 2) 画像を1枚通す。アップロード先の取得・タスク作成・ポーリングまで踏む
    try:
        result = await getattr(youcam, action.replace("-", "_"))(_sample_photo())
    except httpx.HTTPStatusError as exc:
        print(f"{action} NG: HTTP {exc.response.status_code} {exc.request.url}")
        print(f"  応答: {exc.response.text[:500]}")
        return 1
    except Exception as exc:
        print(f"{action} NG: {type(exc).__name__}: {exc}")
        return 1

    print(f"{action} OK（{len(result)} バイト受信）")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
