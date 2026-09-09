"""駅すぱあと MCP の応答の読み方を固定する。

live は鍵がないと踏めないので、公式ドキュメントの形をなぞった応答で解析だけを検証する。
Point と Line が交互に並ぶこと、要素が1つだと配列にならないことが要点。
"""

from __future__ import annotations

import json

import pytest

from app.adapters.ekispert import LiveEkispert, MockEkispert


def _line(name: str, kind: str, depart: str, arrive: str) -> dict:
    return {
        "Name": name,
        "Type": kind,
        "DepartureState": {"Datetime": {"text": f"2026-09-09T{depart}:00+09:00"}},
        "ArrivalState": {"Datetime": {"text": f"2026-09-09T{arrive}:00+09:00"}},
    }


COURSE = {
    "Route": {
        "timeWalk": 12,
        "transferCount": 1,
        "Point": [
            {"Station": {"Name": "東京", "code": "22828"}},
            {"Station": {"Name": "郡山", "code": "24312"}},
            {"Station": {"Name": "会津柳津", "code": "21083"}},
        ],
        "Line": [
            _line("東北新幹線やまびこ", "train", "09:00", "10:20"),
            _line("徒歩", "walk", "10:20", "10:32"),
        ],
    }
}


def test_course_becomes_sections_in_order() -> None:
    result = LiveEkispert._to_sections(COURSE)

    assert [s["from"] for s in result["sections"]] == ["東京", "郡山"]
    assert [s["to"] for s in result["sections"]] == ["郡山", "会津柳津"]
    assert [s["minutes"] for s in result["sections"]] == [80, 12]
    assert result["sections"][0]["depart"] == "09:00"
    assert result["total_minutes"] == 92
    assert result["walking_minutes"] == 12
    assert result["transfers"] == 1


def test_single_element_is_not_a_list() -> None:
    """区間が1つだけの経路。駅すぱあとは配列にせず単体で返してくる。"""
    single = {
        "Route": {
            "Point": [{"Station": {"Name": "東京"}}, {"Station": {"Name": "有楽町"}}],
            "Line": _line("JR山手線", "train", "09:00", "09:02"),
        }
    }
    result = LiveEkispert._to_sections(single)
    assert len(result["sections"]) == 1
    assert result["sections"][0]["means"] == "JR山手線"


def test_payload_reads_text_content() -> None:
    """MCP のツール結果は content[].text に JSON 文字列で入ってくることがある。"""
    payload = LiveEkispert._payload(
        {"content": [{"type": "text", "text": json.dumps({"ResultSet": {"Course": [COURSE]}})}]}
    )
    assert payload["ResultSet"]["Course"][0] is not None


def test_payload_raises_on_tool_error() -> None:
    with pytest.raises(RuntimeError):
        LiveEkispert._payload({"isError": True, "content": [{"type": "text", "text": "駅が見つかりません"}]})


@pytest.mark.anyio
async def test_mock_keeps_the_same_shape() -> None:
    """mock と live で、旅程エージェントから見える形が変わらないこと。"""
    result = await MockEkispert().search("東京", "会津柳津駅", "09:00")
    assert set(result) == {
        "sections",
        "total_minutes",
        "walking_minutes",
        "transfers",
        "accessibility",
        "provider",
    }
