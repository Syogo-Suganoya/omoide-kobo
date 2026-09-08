"""修復エージェント: カラー化・退色/折れ修復・ノイズ除去の一括処理。

自律で進むが、original_ref は決して上書きしない（設計書 4章）。
"""

from __future__ import annotations

import anyio

from app.adapters.youcam import get_restorer
from app.agents.base import Agent, AgentResult
from app.infra.blobs import get_blobs, make_ref
from app.models import AuditAction, Photo, PhotoStatus
from app.repo import save_photo
from app.services import audit


class RestoreAgent(Agent):
    name = "restore"
    role = "カラー化・退色/折れ修復・ノイズ除去の一括処理"
    autonomy = "autonomous"

    async def run(self, *, photo: Photo) -> AgentResult:  # type: ignore[override]
        restorer = get_restorer()
        blobs = get_blobs()

        photo.status = PhotoStatus.restoring
        await save_photo(photo)

        original = await anyio.to_thread.run_sync(blobs.read, photo.original_ref)

        steps: list[str] = []
        image = await restorer.remove_defects(original)
        steps.append("ノイズ・折れ跡の除去")
        image = await restorer.enhance(image)
        steps.append("退色補正・精細化")
        image = await restorer.colorize(image)
        steps.append("カラー化")

        ref = make_ref(photo.family_id, photo.album_id, "restored", f"{photo.id}.jpg")
        await anyio.to_thread.run_sync(lambda: blobs.write(ref, image, "image/jpeg"))

        photo.restored_ref = ref
        photo.restore_steps = steps
        photo.restored_provider = restorer.name
        await save_photo(photo)

        photo.status = PhotoStatus.restored
        await save_photo(photo)

        await audit.record_external_call(
            photo.family_id, restorer.name, "colorize+enhance+cleanup", mode=restorer.name, target=photo.id
        )
        await audit.record(
            photo.family_id,
            AuditAction.restore,
            actor=self.name,
            target=photo.id,
            detail={
                "steps": steps,
                "original_preserved": True,
                "providers": [photo.restored_provider],
            },
        )
        return AgentResult(
            agent=self.name,
            summary="／".join(steps),
            data={"restored_ref": ref},
        )
