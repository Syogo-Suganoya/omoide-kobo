"""Agent Development Kit へのブリッジ。

内製のエージェント（restore / estimate / story / itinerary）を ADK のツールとして公開し、
Gemini の live モード時は ADK の LlmAgent が自然文の指示からパイプラインを起動できるようにする。
mock モード（＝鍵なし）では ADK を読み込まず、Orchestrator が直接パイプラインを回す。
"""

from __future__ import annotations

from typing import Any

from app.agents.orchestrator import get_orchestrator
from app.config import get_settings
from app.models import Stamina, Trip
from app.repo import get_photo, list_family_photos, save_trip

INSTRUCTION = """あなたは家族の古写真をよみがえらせる「オモイデ工房」の進行役です。
写真の修復、場所と年代の推定、家族への確認質問、思い出の地を巡る旅程作成をツールで進めます。
推定は必ず候補・根拠・確度として伝え、断定はしません。場所の確定は常に家族の記憶を優先します。
親の体力に配慮し、休憩を織り込んだ旅程を提案してください。"""


async def restore_photo(photo_id: str) -> dict[str, Any]:
    """写真をカラー化・修復する。元画像は保全される。"""
    photo = await get_photo(photo_id)
    if photo is None:
        return {"error": "写真が見つかりません"}
    result = await get_orchestrator().restore.run(photo=photo)
    return {"summary": result.summary, **result.data}


async def estimate_photo(photo_id: str) -> dict[str, Any]:
    """写真の撮影地と年代を、根拠と確度つきの候補として推定する。確定はしない。"""
    photo = await get_photo(photo_id)
    if photo is None:
        return {"error": "写真が見つかりません"}
    result = await get_orchestrator().estimate.run(photo=photo)
    return {"summary": result.summary, **result.data}


async def capture_story(photo_id: str, transcript: str, narrator: str = "") -> dict[str, Any]:
    """家族の語り（書き起こし）を構造化して写真に紐付ける。人物関係は確定しない。"""
    photo = await get_photo(photo_id)
    if photo is None:
        return {"error": "写真が見つかりません"}
    result = await get_orchestrator().story.run(
        photo=photo, transcript=transcript, narrator=narrator or None
    )
    return {"summary": result.summary, **result.data}


async def plan_trip(family_id: str, photo_ids: list[str], origin: str, stamina: str = "low") -> dict[str, Any]:
    """確定した思い出の場所を巡る、休憩込みの旅程を作る。"""
    photos = [p for p in await list_family_photos(family_id) if p.id in photo_ids]
    trip = await save_trip(Trip(family_id=family_id, origin=origin, stamina=Stamina(stamina)))
    result = await get_orchestrator().itinerary.run(trip=trip, photos=photos)
    return {"summary": result.summary, **result.data}


TOOLS = [restore_photo, estimate_photo, capture_story, plan_trip]


def adk_status() -> dict[str, Any]:
    settings = get_settings()
    try:
        import google.adk  # noqa: F401
    except Exception as exc:  # pragma: no cover - 環境依存
        return {"available": False, "reason": f"google-adk 未導入: {exc}", "active": False}
    return {
        "available": True,
        "active": settings.gemini_mode == "live",
        "reason": None if settings.gemini_mode == "live" else "GEMINI_MODE=mock のため内製パイプラインで実行中",
        "tools": [t.__name__ for t in TOOLS],
    }


def build_root_agent() -> Any:
    """ADK の LlmAgent を組み立てる（GEMINI_MODE=live 時のみ利用）。"""
    from google.adk.agents import LlmAgent

    return LlmAgent(
        name="omoide_kobo_orchestrator",
        model=get_settings().gemini_model,
        description="古写真の修復・場所推定・語り・巡礼旅程を進めるオーケストレータ",
        instruction=INSTRUCTION,
        tools=list(TOOLS),
    )
