"""経路探索ポート（スポンサー: 駅すぱあと API MCP サーバー）。

返すのは「区間の並び」だけで、休憩の挿入や体力配慮は旅程エージェント側の責務。
live は MCP サーバーへ JSON-RPC の tools/call を投げる。
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.utils import add_minutes


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


class LiveEkispert:
    """駅すぱあと MCP サーバー（JSON-RPC over HTTP）。"""

    name = "ekispert"

    def __init__(self) -> None:
        url = get_settings().ekispert_mcp_url
        if not url:
            raise RuntimeError("EKISPERT_MCP_URL が未設定です")
        self._url = url

    async def _call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(self._url, json=payload)
            res.raise_for_status()
            body = res.json()
        if "error" in body:
            raise RuntimeError(f"駅すぱあと MCP エラー: {body['error']}")
        return body["result"]

    async def search(self, origin: str, destination: str, depart: str) -> dict[str, Any]:
        result = await self._call_tool(
            "search_course_extreme",
            {"from": origin, "to": destination, "time": depart, "searchType": "departure"},
        )
        content = result.get("structuredContent") or result
        sections: list[dict[str, Any]] = []
        for point in content.get("sections", content.get("Route", {}).get("Line", [])):
            sections.append(
                {
                    "means": point.get("means") or point.get("Name", "移動"),
                    "from": point.get("from"),
                    "to": point.get("to"),
                    "depart": point.get("depart"),
                    "arrive": point.get("arrive"),
                    "minutes": int(point.get("minutes", 0)),
                    "note": point.get("note"),
                }
            )
        return {
            "sections": sections,
            "total_minutes": sum(s["minutes"] for s in sections),
            "walking_minutes": sum(s["minutes"] for s in sections if "徒歩" in str(s["means"])),
            "transfers": max(0, len(sections) - 1),
            "accessibility": content.get("accessibility", []),
            "provider": self.name,
        }


def get_router() -> RoutePort:
    return LiveEkispert() if get_settings().ekispert_mode == "live" else MockEkispert()
