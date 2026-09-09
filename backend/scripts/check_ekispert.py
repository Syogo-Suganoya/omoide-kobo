"""駅すぱあと API MCP サーバーへの疎通確認。

キーを入れたあと、アプリを立ち上げずに接続だけ試すためのもの。

    docker compose run --rm api python -m scripts.check_ekispert 東京 京都

EKISPERT_API_KEY が要る（.env に書けば compose が渡す）。EKISPERT_MODE は見ていないので、
mock 運用のままでも live 接続だけを試せる。
"""

from __future__ import annotations

import asyncio
import sys

from app.adapters.ekispert import LiveEkispert
from app.config import get_settings


async def main() -> int:
    origin = sys.argv[1] if len(sys.argv) > 1 else "東京"
    destination = sys.argv[2] if len(sys.argv) > 2 else "京都"
    depart = sys.argv[3] if len(sys.argv) > 3 else "09:00"

    settings = get_settings()
    print(f"接続先 : {settings.ekispert_mcp_url}")
    print(f"キー   : {'設定あり' if settings.ekispert_api_key else '未設定'}")
    print(f"種別   : {settings.ekispert_search_type}", end="")
    if settings.ekispert_search_type == "plain":
        # 平均待ち時間探索なので時刻表は見ない。時刻は旅程エージェントが積み上げる
        print("（平均待ち時間探索・時刻指定なし）")
    else:
        print(f"（ダイヤ探索・{depart} 発）")
    print(f"探索   : {origin} → {destination}\n")

    try:
        router = LiveEkispert()
        result = await router.search(origin, destination, depart)
    except Exception as exc:
        print(f"失敗: {type(exc).__name__}: {exc}")
        return 1

    for section in result["sections"]:
        print(
            f"  {section['depart'] or '--:--'} {section['from']}"
            f" --[{section['means']} {section['minutes']}分]-->"
            f" {section['to']} {section['arrive'] or '--:--'}"
        )
    print(
        f"\n所要 {result['total_minutes']}分 ／ 徒歩 {result['walking_minutes']}分"
        f" ／ 乗換 {result['transfers']}回"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
