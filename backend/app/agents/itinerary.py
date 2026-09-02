"""旅程エージェント: 特定地点の現況確認（現存/廃止）→ 移動負荷の低い旅程生成。

提案まで（propose_only）。休憩の挿入と徒歩の警告は親の体力(stamina)で変わる。
"""

from __future__ import annotations

from app.adapters.ekispert import get_router
from app.adapters.gemini import get_llm
from app.agents.base import Agent, AgentResult
from app.models import (
    AuditAction,
    Itinerary,
    Leg,
    Photo,
    Spot,
    SpotStatus,
    Stamina,
    Trip,
)
from app.repo import save_trip
from app.services import audit
from app.utils import add_minutes

# stamina → (連続移動の上限分, 休憩の長さ, 昼食の長さ, 徒歩の警告しきい値)
_RULES: dict[Stamina, tuple[int, int, int, int]] = {
    Stamina.low: (45, 15, 60, 10),
    Stamina.normal: (90, 10, 45, 15),
    Stamina.high: (150, 0, 30, 25),
}


class ItineraryAgent(Agent):
    name = "itinerary"
    role = "特定地点の現況確認 → 移動負荷の低い旅程生成"
    autonomy = "propose_only"

    async def run(  # type: ignore[override]
        self,
        *,
        trip: Trip,
        photos: list[Photo],
        start_time: str = "09:00",
    ) -> AgentResult:
        llm = get_llm()
        router = get_router()
        max_move, break_len, lunch_len, walk_warn = _RULES[trip.stamina]

        # 1) 現況確認。場所は家族の記憶（confirmed）が優先される。
        spots: list[Spot] = []
        for photo in photos:
            place = photo.resolved_place
            if not place:
                continue
            status = await llm.spot_status(place)
            candidate = (photo.estimate.place_candidates[0] if photo.estimate and photo.estimate.place_candidates else None)
            spots.append(
                Spot(
                    photo_id=photo.id,
                    place=place,
                    current_status=SpotStatus(status.get("current_status", "unknown")),
                    current_note=status.get("note"),
                    stay_minutes=int(status.get("stay_minutes", 30)),
                    lat=candidate.lat if candidate else None,
                    lng=candidate.lng if candidate else None,
                )
            )

        visitable = [s for s in spots if s.current_status != SpotStatus.abolished]

        # 2) 経路をつないで旅程に組む
        legs: list[Leg] = []
        notes: list[str] = []
        breaks = 0
        cursor = start_time
        since_break = 0
        lunch_taken = False
        origin = trip.origin

        for spot in visitable:
            route = await router.search(origin, spot.place, cursor)
            for section in route["sections"]:
                # 休憩を挟むと以降が後ろにずれるため、時刻は経路の値ではなく手元の cursor で採番する
                arrive = add_minutes(cursor, section["minutes"])
                legs.append(
                    Leg(
                        kind="move",
                        **{"from": section["from"]},
                        to=section["to"],
                        depart=cursor,
                        arrive=arrive,
                        minutes=section["minutes"],
                        means=section["means"],
                        note=section.get("note"),
                    )
                )
                cursor = arrive
                since_break += section["minutes"]
                if "徒歩" in str(section["means"]) and section["minutes"] > walk_warn:
                    notes.append(
                        f"{section['from']}→{section['to']} は徒歩{section['minutes']}分。"
                        "タクシー利用に切り替えられます。"
                    )
                if break_len and since_break >= max_move:
                    legs.append(
                        Leg(
                            kind="break",
                            to=section["to"],
                            depart=cursor,
                            arrive=add_minutes(cursor, break_len),
                            minutes=break_len,
                            means="休憩",
                            note="移動が続いたため休憩を挟みます（座れる場所を想定）",
                        )
                    )
                    cursor = add_minutes(cursor, break_len)
                    since_break = 0
                    breaks += 1

            notes.extend(route.get("accessibility", []))

            if not lunch_taken and cursor >= "11:30":
                legs.append(
                    Leg(
                        kind="break",
                        to=spot.place,
                        depart=cursor,
                        arrive=add_minutes(cursor, lunch_len),
                        minutes=lunch_len,
                        means="昼食",
                        note="ゆっくり座れる店を想定",
                    )
                )
                cursor = add_minutes(cursor, lunch_len)
                since_break = 0
                lunch_taken = True
                breaks += 1

            legs.append(
                Leg(
                    kind="stay",
                    to=spot.place,
                    depart=cursor,
                    arrive=add_minutes(cursor, spot.stay_minutes),
                    minutes=spot.stay_minutes,
                    means="滞在",
                    note=spot.current_note,
                )
            )
            cursor = add_minutes(cursor, spot.stay_minutes)
            since_break = 0
            origin = spot.place

        for spot in spots:
            if spot.current_status == SpotStatus.abolished:
                notes.append(f"「{spot.place}」は現存しないため、跡地訪問の可否を家族で相談してください。")
            elif spot.current_status == SpotStatus.rebuilt:
                notes.append(f"「{spot.place}」は当時と姿が変わっています（{spot.current_note}）。")

        itinerary = Itinerary(
            date=trip.date,
            legs=legs,
            total_minutes=sum(leg.minutes for leg in legs),
            walking_minutes=sum(leg.minutes for leg in legs if leg.means == "徒歩"),
            breaks=breaks,
            accessibility_notes=list(dict.fromkeys(notes)),
        )
        trip.spots = spots
        trip.itinerary = itinerary
        await save_trip(trip)

        await audit.record_external_call(
            trip.family_id, router.name, "search_route", mode=router.name, target=trip.id
        )
        await audit.record(
            trip.family_id,
            AuditAction.trip_plan,
            actor=self.name,
            target=trip.id,
            detail={
                "spots": [s.place for s in spots],
                "stamina": trip.stamina.value,
                "breaks": breaks,
                "total_minutes": itinerary.total_minutes,
            },
        )
        return AgentResult(
            agent=self.name,
            summary=f"{len(visitable)}か所・所要{itinerary.total_minutes}分・休憩{breaks}回の旅程を作成",
            data={"trip_id": trip.id},
            proposal=True,
        )
