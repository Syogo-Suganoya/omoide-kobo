"""修復エージェント: カラー化・退色/折れ修復・ノイズ除去の一括処理。

自律で進むが、original_ref は決して上書きしない（設計書 4章）。
YouCam のカラー化に加えて GMI Cloud の restore/relight でもう一系統を作り、
どちらを採るかは家族が見比べて決める（設計書 12章）。AI は勝手に選ばない。
"""

from __future__ import annotations

import logging

import anyio

from app.adapters.gmi import get_generative
from app.adapters.youcam import get_restorer
from app.agents.base import Agent, AgentResult
from app.infra.blobs import get_blobs, make_ref
from app.models import AuditAction, Photo, PhotoStatus
from app.repo import save_photo
from app.services import audit

_logger = logging.getLogger("omoide.restore")


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

        # もう一系統（GMI Cloud）。失敗しても本流は止めない
        try:
            generative = get_generative()
            alt = await generative.restore(original)
            alt = await generative.relight(alt)
            alt_ref = make_ref(photo.family_id, photo.album_id, "restored-alt", f"{photo.id}.jpg")
            await anyio.to_thread.run_sync(lambda: blobs.write(alt_ref, alt, "image/jpeg"))
            photo.alt_restored_ref = alt_ref
            photo.alt_restore_steps = ["破れ・退色の復元（restore）", "再照明（relight）"]
            photo.alt_restored_provider = generative.name
            await audit.record_external_call(
                photo.family_id, generative.name, "restore+relight", mode=generative.name, target=photo.id
            )
        except Exception as exc:  # 比較用の系統なので、落ちても修復自体は成立させる
            photo.alt_restore_steps = []
            _logger.warning("GMI の修復に失敗（本流は継続）: %s", exc)

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
                "providers": [p for p in (photo.restored_provider, photo.alt_restored_provider) if p],
            },
        )
        summary = "／".join(steps)
        if photo.alt_restored_ref:
            summary += "（比較用にもう一系統も生成）"
        return AgentResult(
            agent=self.name,
            summary=summary,
            data={"restored_ref": ref, "alt_restored_ref": photo.alt_restored_ref},
        )
