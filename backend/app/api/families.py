from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import repo
from app.infra.blobs import get_blobs
from app.models import AuditAction, Family, InviteStatus, Member
from app.services import audit

router = APIRouter(tags=["families"])


class FamilyCreate(BaseModel):
    name: str
    members: list[Member] = []


class FamilyRename(BaseModel):
    name: str
    actor: str = "owner"


class MemberInvite(BaseModel):
    name: str
    relation: str
    actor: str = "owner"


class InviteDecision(BaseModel):
    status: InviteStatus
    actor: str = "owner"


@router.post("/families", response_model=Family)
async def create_family(payload: FamilyCreate) -> Family:
    family = await repo.save_family(Family(name=payload.name, members=payload.members))
    await audit.record(
        family.id,
        AuditAction.share_scope_change,
        actor=payload.name,
        target=family.id,
        detail={"event": "family_created", "members": len(family.members)},
    )
    return family


@router.get("/families", response_model=list[Family])
async def list_families() -> list[Family]:
    return await repo.list_families()


@router.get("/families/{family_id}", response_model=Family)
async def get_family(family_id: str) -> Family:
    family = await repo.get_family(family_id)
    if family is None:
        raise HTTPException(404, "家族が見つかりません")
    return family


@router.patch("/families/{family_id}", response_model=Family)
async def rename_family(family_id: str, payload: FamilyRename) -> Family:
    """入口で名前を聞かずに始められるようにした分、あとから変えられる口を用意する。"""
    family = await get_family(family_id)
    before = family.name
    family.name = payload.name.strip() or family.name
    await repo.save_family(family)
    await audit.record(
        family_id,
        AuditAction.share_scope_change,
        actor=payload.actor,
        target=family_id,
        detail={"event": "family_renamed", "before": before, "after": family.name},
    )
    return family


@router.post("/families/{family_id}/members", response_model=Family)
async def invite_member(family_id: str, payload: MemberInvite) -> Family:
    """共有は家族の明示招待制（設計書 7-3）。"""
    family = await get_family(family_id)
    member = Member(name=payload.name, relation=payload.relation)
    family.members.append(member)
    await repo.save_family(family)
    await audit.record(
        family_id,
        AuditAction.share_scope_change,
        actor=payload.actor,
        target=member.uid,
        detail={"event": "member_invited", "name": member.name, "relation": member.relation},
    )
    return family


@router.post("/families/{family_id}/members/{uid}", response_model=Family)
async def update_invite(family_id: str, uid: str, payload: InviteDecision) -> Family:
    family = await get_family(family_id)
    for member in family.members:
        if member.uid == uid:
            member.invite_status = payload.status
            break
    else:
        raise HTTPException(404, "メンバーが見つかりません")
    await repo.save_family(family)
    await audit.record(
        family_id,
        AuditAction.share_scope_change,
        actor=payload.actor,
        target=uid,
        detail={"event": "invite_status_changed", "status": payload.status.value},
    )
    return family


@router.delete("/families/{family_id}")
async def delete_family(family_id: str, actor: str = "owner") -> dict[str, object]:
    """削除権（設計書 7-4）: 写真・音声・旅程を一括削除し、実行証跡だけ残す。"""
    family = await get_family(family_id)
    photos = await repo.list_family_photos(family_id)
    blob_count = get_blobs().delete_prefix(f"family/{family_id}")
    removed = await repo.purge_family(family_id)
    await audit.record(
        family_id,
        AuditAction.delete,
        actor=actor,
        target=family_id,
        detail={
            "family_name": family.name,
            "documents_removed": removed,
            "blobs_removed": blob_count,
            "photos_removed": len(photos),
            "irreversible": True,
        },
    )
    return {"deleted": True, "documents": removed, "blobs": blob_count}
