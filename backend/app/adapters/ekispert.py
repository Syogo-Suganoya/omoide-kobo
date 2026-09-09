"""経路探索ポート（スポンサー: 駅すぱあと API MCP サーバー）。

返すのは「区間の並び」だけで、休憩の挿入や体力配慮は旅程エージェント側の責務。
live は MCP サーバーへ JSON-RPC の tools/call を投げる。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.utils import add_minutes, diff_minutes


class RoutePort(Protocol):
    name: str

    async def search(self, origin: str, destination: str, depart: str) -> dict[str, Any]: ...


def _minutes(seed: str, low: int, high: int) -> int:
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6], 16)
    return low + digest % max(1, high - low)


def _station(place: str) -> str:
    """地名から最寄駅の呼び名を作る。「◯◯駅駅」にならないようにする。"""
    return place if place.endswith(("駅", "駅前")) else f"{place}駅"


class MockEkispert:
    name = "ekispert-mock"

    async def search(self, origin: str, destination: str, depart: str) -> dict[str, Any]:
        seed = f"{origin}->{destination}"
        walk_out = _minutes(seed + "w1", 4, 10)
        express = _minutes(seed + "e", 55, 140)
        transfer = _minutes(seed + "t", 6, 18)
        local = _minutes(seed + "l", 20, 55)
        walk_in = _minutes(seed + "w2", 5, 14)

        cursor = depart
        sections: list[dict[str, Any]] = []

        def push(means: str, to: str, minutes: int, note: str | None = None) -> None:
            nonlocal cursor
            arrive = add_minutes(cursor, minutes)
            sections.append(
                {
                    "means": means,
                    "from": sections[-1]["to"] if sections else origin,
                    "to": to,
                    "depart": cursor,
                    "arrive": arrive,
                    "minutes": minutes,
                    "note": note,
                }
            )
            cursor = arrive

        if _station(origin) != origin:
            push("徒歩", _station(origin), walk_out, "改札まで平坦")
        push("特急・新幹線", "乗換駅", express, "指定席／車内トイレあり")
        push("乗換", "在来線ホーム", transfer, "エレベーター利用可")
        push("在来線", _station(destination), local, "ワンマン運転・段差あり")
        # 目的地そのものが駅なら、駅から歩く区間は要らない
        if _station(destination) != destination:
            push("徒歩", destination, walk_in, "緩やかな上り坂")

        total = sum(s["minutes"] for s in sections)
        walking = sum(s["minutes"] for s in sections if s["means"] == "徒歩")
        return {
            "sections": sections,
            "total_minutes": total,
            "walking_minutes": walking,
            "transfers": 2,
            "accessibility": [
                "乗換駅はエレベーターで移動できます",
                f"{_station(destination)}のホームは段差があります（駅員へ声かけ推奨）",
            ],
            "provider": self.name,
        }


def _as_list(value: Any) -> list[Any]:
    """駅すぱあとの JSON は要素が1つだと配列にならないので、常に配列にそろえる。"""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _hhmm(datetime_text: str | None) -> str | None:
    """"2026-09-09T09:12:00+09:00" → "09:12"。"""
    if not datetime_text or len(datetime_text) < 16:
        return None
    return datetime_text[11:16]


class _McpSession:
    """Streamable HTTP の MCP クライアント。

    素の JSON-RPC を投げるだけでは通らない。initialize で握手してセッション ID を受け取り、
    notifications/initialized を送ってから tools/call する。応答は JSON か SSE のどちらでも返る。
    """

    PROTOCOL = "2025-06-18"

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self._url = url
        self._headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **headers,
        }
        self._session_id: str | None = None

    @staticmethod
    def _decode(res: httpx.Response) -> dict[str, Any] | None:
        if res.status_code == 202 or not res.content:
            return None
        if res.headers.get("content-type", "").startswith("text/event-stream"):
            # SSE の data 行から、結果を含むものを拾う
            for line in res.text.splitlines():
                if not line.startswith("data:"):
                    continue
                body = json.loads(line[5:].strip())
                if "result" in body or "error" in body:
                    return body
            return None
        return res.json()

    async def _post(self, client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any] | None:
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        res = await client.post(self._url, json=body, headers=headers)
        if res.status_code >= 400:
            raise RuntimeError(f"駅すぱあと MCP が {res.status_code} を返しました: {res.text[:300]}")
        session_id = res.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        decoded = self._decode(res)
        if decoded and "error" in decoded:
            raise RuntimeError(f"駅すぱあと MCP エラー: {decoded['error']}")
        return decoded

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": self.PROTOCOL,
                        "capabilities": {},
                        "clientInfo": {"name": "omoide-kobo", "version": "0.1.0"},
                    },
                },
            )
            await self._post(client, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            body = await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
        if not body:
            raise RuntimeError("駅すぱあと MCP から応答がありませんでした")
        return body["result"]


class LiveEkispert:
    """駅すぱあと API MCP サーバー（https://api-mcp.ekispert.jp/mcp）。

    経路探索ツールは ekispert_api_search_routes で、中身は /search/course/extreme。
    出発・経由・目的地はコロン区切りの viaList 1本で渡す（駅名・駅コード・住所・座標のいずれも可）。
    """

    name = "ekispert"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.ekispert_mcp_url:
            raise RuntimeError("EKISPERT_MCP_URL が未設定です")
        if not settings.ekispert_api_key:
            raise RuntimeError("EKISPERT_API_KEY が未設定です")
        self._search_type = settings.ekispert_search_type
        self._session = _McpSession(
            settings.ekispert_mcp_url,
            {
                "ekispert-api-access-key": settings.ekispert_api_key,
                "ekispert-api-response-format": settings.ekispert_response_format,
            },
        )

    @staticmethod
    def _payload(result: dict[str, Any]) -> dict[str, Any]:
        """ツール結果から駅すぱあとの JSON を取り出す。"""
        if result.get("isError"):
            detail = str(result.get("content"))
            if "searchType" in detail or "time" in detail:
                # ダイヤ探索は専用アクセスキーが要る。既定の plain なら通る
                raise RuntimeError(
                    "駅すぱあとがダイヤ探索を受け付けませんでした（専用アクセスキーが必要です）。"
                    f"EKISPERT_SEARCH_TYPE=plain に戻してください: {detail}"
                )
            raise RuntimeError(f"駅すぱあと MCP がエラーを返しました: {detail}")
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured:
            return structured
        for item in _as_list(result.get("content")):
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except (json.JSONDecodeError, KeyError):
                    continue
        raise RuntimeError("駅すぱあと MCP の応答を解釈できませんでした")

    async def search(self, origin: str, destination: str, depart: str) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            # 経由地を挟むときも、この1本にコロンで足す
            "viaList": f"{origin}:{destination}",
            "searchType": self._search_type,
            "answerCount": 1,
        }
        # plain（平均待ち時間探索）に time は渡せない。ダイヤ探索のときだけ付ける
        if self._search_type != "plain":
            arguments["time"] = depart.replace(":", "")  # "09:00" → "0900"

        result = await self._session.call_tool("ekispert_api_search_routes", arguments)
        payload = self._payload(result)
        courses = _as_list(payload.get("ResultSet", {}).get("Course"))
        if not courses:
            raise RuntimeError(f"経路が見つかりませんでした（{origin} → {destination}）")
        return self._to_sections(courses[0])

    @staticmethod
    def _to_sections(course: dict[str, Any]) -> dict[str, Any]:
        """Course を、旅程エージェントが読む区間の並びに直す。

        Point と Line は交互に並ぶ（Point[i] --Line[i]--> Point[i+1]）。
        休憩の挿入と体力配慮はこちらではやらない（旅程エージェントの責務）。
        """
        route = course.get("Route", {})
        lines = _as_list(route.get("Line"))
        points = _as_list(route.get("Point"))

        def point_name(index: int) -> str:
            if index >= len(points):
                return ""
            point = points[index]
            station = point.get("Station") or {}
            return station.get("Name") or point.get("Name") or ""

        sections: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            depart_at = _hhmm((line.get("DepartureState") or {}).get("Datetime", {}).get("text"))
            arrive_at = _hhmm((line.get("ArrivalState") or {}).get("Datetime", {}).get("text"))
            if depart_at and arrive_at:
                minutes = diff_minutes(depart_at, arrive_at)
            else:
                minutes = int(line.get("timeOnBoard") or line.get("timeWalk") or 0)
            means = line.get("Name") or ("徒歩" if line.get("Type") == "walk" else "移動")
            sections.append(
                {
                    "means": means,
                    "from": point_name(i),
                    "to": point_name(i + 1),
                    "depart": depart_at,
                    "arrive": arrive_at,
                    "minutes": minutes,
                    "note": None,
                }
            )

        walking = int(route.get("timeWalk") or 0) or sum(
            s["minutes"] for s in sections if "徒歩" in str(s["means"])
        )
        return {
            "sections": sections,
            "total_minutes": sum(s["minutes"] for s in sections),
            "walking_minutes": walking,
            "transfers": int(route.get("transferCount") or max(0, len(sections) - 1)),
            # 駅すぱあとは段差・エレベーターの情報を返さないので、ここでは付けない
            "accessibility": [],
            "provider": LiveEkispert.name,
        }


def get_router() -> RoutePort:
    return LiveEkispert() if get_settings().ekispert_mode == "live" else MockEkispert()
