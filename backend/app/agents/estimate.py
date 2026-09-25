"""推定エージェント: 場所・年代を根拠と確度つきで提示し、家族への確認質問を作る。

確定は行わない（propose_only）。同じアルバムで家族が確定・訂正した内容は、
次の写真の推定コンテキストへ反映される。
"""

from __future__ import annotations

import anyio

from app.adapters.gemini import EstimateContext, get_llm
from app.agents.base import Agent, AgentResult
from app.infra.blobs import get_blobs
from app.models import AuditAction, Photo, PhotoStatus
from app.repo import get_album, list_photos, save_photo
from app.services import audit


async def build_context(photo: Photo) -> EstimateContext:
    album = await get_album(photo.album_id)
    siblings = [p for p in await list_photos(photo.album_id) if p.id != photo.id]
    return EstimateContext(
        album_title=album.title if album else "",
        family_corrections=[
            p.confirmed.family_correction for p in siblings if p.confirmed.family_correction
        ],
        confirmed_places=[p.confirmed.place for p in siblings if p.confirmed.place],
    )


class EstimateAgent(Agent):
    name = "estimate"
    role = "場所・年代を根拠と確度つきで提示（確定は家族）"
    autonomy = "propose_only"

    async def run(self, *, photo: Photo) -> AgentResult:  # type: ignore[override]
        llm = get_llm()
        blobs = get_blobs()

        photo.status = PhotoStatus.estimating
        await save_photo(photo)

        ref = photo.original_ref
        image = await anyio.to_thread.run_sync(blobs.read, ref)

        ctx = await build_context(photo)
        estimate = await llm.estimate_photo(image, photo.filename, ctx)
        questions = await llm.generate_questions(estimate)

        photo.estimate = estimate
        # 既に家族が答えた質問は残し、新規ぶんだけ足す
        answered = {q.text for q in photo.questions if q.answered}
        photo.questions = [q for q in photo.questions if q.answered] + [
            q for q in questions if q.text not in answered
        ]
        photo.status = PhotoStatus.awaiting_family
        await save_photo(photo)

        await audit.record_external_call(
            photo.family_id, llm.name, "estimate_place_and_era", mode=llm.name, target=photo.id
        )
        top = estimate.place_candidates[0] if estimate.place_candidates else None
        await audit.record(
            photo.family_id,
            AuditAction.estimate,
            actor=self.name,
            target=photo.id,
            detail={
                "top_candidate": top.name if top else None,
                "confidence": top.confidence if top else None,
                "era": estimate.era.label if estimate.era else None,
                "is_proposal_only": True,
            },
        )
        summary = (
            f"候補「{top.name}」確度{top.confidence:.0%}／{estimate.era.label if estimate.era else '年代不明'}"
            if top
            else "候補を特定できませんでした"
        )
        return AgentResult(
            agent=self.name,
            summary=summary,
            data={"questions": [q.text for q in questions]},
            proposal=True,
        )
