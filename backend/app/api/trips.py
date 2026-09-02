from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import repo
from app.agents.orchestrator import get_orchestrator
from app.models import Stamina, Trip

router = APIRouter(tags=["trips"])


class TripCreate(BaseModel):
    family_id: str
    photo_ids: list[str]
    origin: str = "東京"
    date: str | None = None
    title: str = "思い出巡礼旅"
    stamina: Stamina = Stamina.low
    start_time: str = "09:00"


@router.post("/trips", response_model=Trip)
async def create_trip(payload: TripCreate) -> Trip:
    photos = [p for p in await repo.list_family_photos(payload.family_id) if p.id in payload.photo_ids]
    if not photos:
        raise HTTPException(400, "旅程に含める写真を選んでください")
    missing = [p.filename for p in photos if not p.resolved_place]
    if len(missing) == len(photos):
        raise HTTPException(400, "場所が未確定です。家族の確認を先に済ませてください")

    trip = await repo.save_trip(
        Trip(
            family_id=payload.family_id,
            title=payload.title,
            origin=payload.origin,
            date=payload.date,
            stamina=payload.stamina,
        )
    )
    # 選択順ではなく写真の並び順で巡る
    ordered = [p for p in photos if p.resolved_place]
    await get_orchestrator().itinerary.run(trip=trip, photos=ordered, start_time=payload.start_time)
    result = await repo.get_trip(trip.id)
    assert result is not None
    return result


@router.get("/families/{family_id}/trips", response_model=list[Trip])
async def list_trips(family_id: str) -> list[Trip]:
    return await repo.list_trips(family_id)


@router.get("/trips/{trip_id}", response_model=Trip)
async def get_trip(trip_id: str) -> Trip:
    trip = await repo.get_trip(trip_id)
    if trip is None:
        raise HTTPException(404, "旅程が見つかりません")
    return trip
