"""推定・語り構造化を担う LLM ポート（Gemini）。

live モードは google-genai を使い、mock モードは決定的なフィクスチャを返す。
どちらも「候補・根拠・確度」を必ず返す契約にしてあり、確定は行わない（設計書 7-2）。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings
from app.models import (
    EraEstimate,
    Estimate,
    EventMention,
    FamilyQuestion,
    PersonMention,
    PlaceCandidate,
    Story,
)


@dataclass
class EstimateContext:
    """家族の訂正が後続推定に効く（設計書 4章 パイプライン 4）。"""

    album_title: str = ""
    family_corrections: list[str] = field(default_factory=list)
    confirmed_places: list[str] = field(default_factory=list)


class LlmPort(Protocol):
    name: str

    async def estimate_photo(self, image: bytes, filename: str, ctx: EstimateContext) -> Estimate: ...

    async def generate_questions(self, estimate: Estimate) -> list[FamilyQuestion]: ...

    async def structure_story(self, transcript: str, place: str | None) -> Story: ...

    async def spot_status(self, place: str) -> dict[str, Any]: ...


# --------------------------------------------------------------------------- mock

_FIXTURES: list[dict[str, Any]] = [
    {
        "features": [
            "木造駅舎の切妻屋根と改札ラッチ",
            "ホーム上の縦書き駅名標（右書き併記なし）",
            "停車中の車両は初期型の電車で前面2枚窓",
            "背後になだらかな山稜と棚田",
        ],
        "places": [
            {
                "name": "JR只見線 会津柳津駅",
                "address": "福島県河沼郡柳津町",
                "lat": 37.5238,
                "lng": 139.7326,
                "confidence": 0.62,
                "evidence": ["木造駅舎の妻面意匠が只見線の同型駅舎と一致", "背後の山稜線の形状が一致"],
            },
            {
                "name": "JR磐越西線 山都駅",
                "address": "福島県喜多方市",
                "confidence": 0.24,
                "evidence": ["同時期の同型駅舎が存在", "ホーム構造が類似"],
            },
        ],
        "era": {
            "label": "昭和40年代前半",
            "year_from": 1965,
            "year_to": 1970,
            "confidence": 0.71,
            "evidence": ["前面2枚窓の車両形式の運用期間", "女性の服装（膝丈スカート）の流行期"],
        },
    },
    {
        "features": [
            "商店街のアーケードと日除けテント",
            "看板の文字は右から左ではなく左書き",
            "路上に丸型ポストと三輪トラック",
            "半袖シャツと日傘",
        ],
        "places": [
            {
                "name": "尾道本通り商店街",
                "address": "広島県尾道市",
                "lat": 34.4090,
                "lng": 133.1955,
                "confidence": 0.55,
                "evidence": ["アーケード柱の断面形状が一致", "背後の山手の傾斜と石段"],
            },
            {
                "name": "高松丸亀町商店街",
                "address": "香川県高松市",
                "confidence": 0.21,
                "evidence": ["同時期のアーケード形式が類似"],
            },
        ],
        "era": {
            "label": "昭和30年代後半",
            "year_from": 1960,
            "year_to": 1965,
            "confidence": 0.64,
            "evidence": ["丸型ポストの設置期間", "三輪トラックの流通期"],
        },
    },
    {
        "features": [
            "砂浜と防波堤、木造の海の家",
            "浮き輪とゴムボート",
            "遠景に岬と灯台",
            "水着の意匠",
        ],
        "places": [
            {
                "name": "由比ヶ浜海岸",
                "address": "神奈川県鎌倉市",
                "lat": 35.3080,
                "lng": 139.5390,
                "confidence": 0.48,
                "evidence": ["遠景の岬の稜線が稲村ヶ崎と一致", "防波堤の護岸形式"],
            },
            {
                "name": "白浜海岸",
                "address": "静岡県下田市",
                "confidence": 0.27,
                "evidence": ["砂質と岩礁の分布が類似"],
            },
        ],
        "era": {
            "label": "昭和45年前後",
            "year_from": 1968,
            "year_to": 1973,
            "confidence": 0.58,
            "evidence": ["水着の意匠の流行期", "海の家の建築様式"],
        },
    },
    {
        "features": [
            "神社の石段と杉並木",
            "幟旗の文字",
            "紋付羽織と晴れ着",
            "手前に七五三の千歳飴袋",
        ],
        "places": [
            {
                "name": "諏訪大社 下社秋宮",
                "address": "長野県諏訪郡下諏訪町",
                "lat": 36.0752,
                "lng": 138.0810,
                "confidence": 0.51,
                "evidence": ["御柱の位置関係", "神楽殿の注連縄の形状"],
            },
            {
                "name": "生島足島神社",
                "address": "長野県上田市",
                "confidence": 0.18,
                "evidence": ["同地域の社殿形式が類似"],
            },
        ],
        "era": {
            "label": "昭和50年代前半",
            "year_from": 1975,
            "year_to": 1980,
            "confidence": 0.66,
            "evidence": ["晴れ着の柄行きの流行期", "印画紙の縁取り様式"],
        },
    },
]

_SPOT_STATUS = {
    "駅": {
        "current_status": "rebuilt",
        "note": "駅舎は改築済み。旧駅舎の一部の意匠が待合室に保存されています。",
        "stay_minutes": 40,
    },
    "商店街": {
        "current_status": "existing",
        "note": "アーケードは現存。一部の店舗は代替わりしています。",
        "stay_minutes": 60,
    },
    "海岸": {
        "current_status": "existing",
        "note": "海岸線は現存。海の家は季節営業です。",
        "stay_minutes": 45,
    },
    "神社": {
        "current_status": "existing",
        "note": "社殿は現存。石段は手すりありの参道に迂回できます。",
        "stay_minutes": 50,
    },
}


def _pick(filename: str) -> dict[str, Any]:
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()
    return _FIXTURES[int(digest[:8], 16) % len(_FIXTURES)]


class MockGemini:
    name = "gemini-mock"

    async def estimate_photo(self, image: bytes, filename: str, ctx: EstimateContext) -> Estimate:
        fixture = _pick(filename)
        candidates = [PlaceCandidate(**c) for c in fixture["places"]]

        # 家族の訂正は後続の推定に効く。訂正で名前が出た土地は候補として引き上げる。
        hints = " ".join(ctx.family_corrections + ctx.confirmed_places)
        if hints:
            for cand in candidates:
                key = cand.name.split()[-1].replace("駅", "").replace("海岸", "")
                if key and key in hints:
                    cand.confidence = min(0.95, cand.confidence + 0.25)
                    cand.evidence.append(f"家族の確定・訂正内容と一致（{key}）")
            candidates.sort(key=lambda c: c.confidence, reverse=True)

        return Estimate(
            place_candidates=candidates,
            era=EraEstimate(**fixture["era"]),
            features=list(fixture["features"]),
            model=self.name,
        )

    async def generate_questions(self, estimate: Estimate) -> list[FamilyQuestion]:
        questions: list[FamilyQuestion] = []
        if estimate.place_candidates:
            top = estimate.place_candidates[0]
            questions.append(
                FamilyQuestion(
                    text=f"この場所は「{top.name}」でしょうか。駅名や地名を覚えていますか？",
                    reason=f"場所の第一候補（確度 {top.confidence:.0%}）を確かめたい",
                )
            )
        if estimate.era:
            questions.append(
                FamilyQuestion(
                    text=f"撮影は{estimate.era.label}ごろだと思われますが、何かの行事の日でしたか？",
                    reason=f"年代の推定（確度 {estimate.era.confidence:.0%}）を確かめたい",
                )
            )
        if estimate.features:
            questions.append(
                FamilyQuestion(
                    text=f"写真に「{estimate.features[0]}」が写っています。これに覚えはありますか？",
                    reason="推定の決め手になった特徴の裏取り",
                )
            )
        return questions

    async def structure_story(self, transcript: str, place: str | None) -> Story:
        text = transcript.strip()
        sentences = [s for s in re.split(r"[。\n]", text) if s.strip()]
        people = [
            PersonMention(label=m, note="語りに登場（家族の確定待ち）")
            for m in dict.fromkeys(re.findall(r"(祖母|祖父|母|父|兄|姉|弟|妹|叔父|叔母|近所の[^\s、。]+)", text))
        ]
        events = [EventMention(summary=s.strip(), when_hint=None) for s in sentences[:3]]
        head = sentences[0].strip() if sentences else "語りの記録"
        summary = f"{place or '撮影地'}での思い出。{head}。"
        return Story(transcript=text, summary=summary, people=people, events=events)

    async def spot_status(self, place: str) -> dict[str, Any]:
        for key, value in _SPOT_STATUS.items():
            if key in place:
                return value
        return {"current_status": "unknown", "note": "現況は未確認です。", "stay_minutes": 30}


# --------------------------------------------------------------------------- live

_ESTIMATE_SCHEMA = """
{
  "features": ["視覚特徴"],
  "place_candidates": [
    {"name": "", "address": "", "lat": 0, "lng": 0, "confidence": 0.0, "evidence": ["根拠"]}
  ],
  "era": {"label": "", "year_from": 0, "year_to": 0, "confidence": 0.0, "evidence": ["根拠"]}
}
"""


class LiveGemini:
    """google-genai 経由の実装。GEMINI_MODE=live かつ GEMINI_API_KEY 必須。"""

    name = "gemini"

    def __init__(self) -> None:
        from google import genai  # 遅延 import

        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY が未設定です")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self.name = settings.gemini_model

    async def _json(self, parts: list[Any]) -> dict[str, Any]:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=parts,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)

    async def estimate_photo(self, image: bytes, filename: str, ctx: EstimateContext) -> Estimate:
        from google.genai import types

        prompt = (
            "あなたは古写真の鑑定家です。白黒写真から撮影地と年代を推定します。\n"
            "駅舎・看板文字・車両型式・服装・地形・建築様式を手がかりに、"
            "必ず根拠を列挙し、確度(0.0-1.0)を付けてください。断定はしないでください。\n"
            f"アルバム名: {ctx.album_title}\n"
            f"同じアルバムで家族が確定済みの場所: {', '.join(ctx.confirmed_places) or 'なし'}\n"
            f"家族からの訂正: {'; '.join(ctx.family_corrections) or 'なし'}\n"
            f"次のJSON形式のみで出力: {_ESTIMATE_SCHEMA}"
        )
        data = await self._json(
            [types.Part.from_bytes(data=image, mime_type="image/jpeg"), prompt]
        )
        return Estimate(
            place_candidates=[PlaceCandidate(**c) for c in data.get("place_candidates", [])],
            era=EraEstimate(**data["era"]) if data.get("era") else None,
            features=data.get("features", []),
            model=self.name,
        )

    async def generate_questions(self, estimate: Estimate) -> list[FamilyQuestion]:
        prompt = (
            "次の推定結果について、家族に事実確認するための質問を最大3件作ってください。"
            "高齢の親が答えやすい、平易で具体的な聞き方にしてください。\n"
            f"推定: {estimate.model_dump_json()}\n"
            '出力: {"questions":[{"text":"","reason":""}]}'
        )
        data = await self._json([prompt])
        return [FamilyQuestion(**q) for q in data.get("questions", [])]

    async def structure_story(self, transcript: str, place: str | None) -> Story:
        prompt = (
            "家族の語りの書き起こしを構造化してください。"
            "人物と出来事は「語りに現れた候補」として抽出し、関係の断定はしないでください。\n"
            f"撮影地: {place or '不明'}\n書き起こし: {transcript}\n"
            '出力: {"summary":"","people":[{"label":"","note":""}],"events":[{"summary":"","when_hint":""}]}'
        )
        data = await self._json([prompt])
        return Story(
            transcript=transcript,
            summary=data.get("summary"),
            people=[PersonMention(**p) for p in data.get("people", [])],
            events=[EventMention(**e) for e in data.get("events", [])],
        )

    async def spot_status(self, place: str) -> dict[str, Any]:
        prompt = (
            f"「{place}」の現況を推定してください。"
            "existing(現存) / rebuilt(建替え・改称) / abolished(廃止・消失) / unknown のいずれかと、"
            "高齢者を連れて訪ねる場合の滞在目安(分)を返してください。\n"
            '出力: {"current_status":"","note":"","stay_minutes":0}'
        )
        return await self._json([prompt])


def get_llm() -> LlmPort:
    return LiveGemini() if get_settings().gemini_mode == "live" else MockGemini()
