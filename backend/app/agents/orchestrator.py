"""オーケストレータ: 取り込み→修復→推定→（家族確認）→旅程 のパイプライン進行。

バッチは自律進行する（設計書 4章）。家族確認が要る段は awaiting_family で止め、
家族の回答が入った時点で後続（旅程・語り）を人が起動する。
"""

from __future__ import annotations

import logging

from app.agents.base import Agent, AgentResult
from app.agents.estimate import EstimateAgent
from app.agents.itinerary import ItineraryAgent
from app.agents.motion import MotionAgent
from app.agents.restore import RestoreAgent
from app.agents.story import StoryAgent
from app.models import Job, JobStatus, PhotoStatus
from app.repo import get_photo, save_job, save_photo

_logger = logging.getLogger("omoide.orchestrator")


class Orchestrator(Agent):
    name = "orchestrator"
    role = "取り込み→修復→推定→旅程のパイプライン進行"
    autonomy = "autonomous"

    def __init__(self) -> None:
        self.restore = RestoreAgent()
        self.estimate = EstimateAgent()
        self.story = StoryAgent()
        self.itinerary = ItineraryAgent()
        self.motion = MotionAgent()

    def roster(self) -> list[dict[str, str]]:
        return [
            a.describe()
            for a in (self, self.restore, self.estimate, self.story, self.itinerary, self.motion)
        ]

    async def run(self, *, job: Job) -> AgentResult:  # type: ignore[override]
        """アルバム一括取り込み。1枚が失敗しても残りは進める。"""
        job.status = JobStatus.running
        job.steps.append(f"取り込み開始（{job.total}枚）")
        await save_job(job)

        failures = 0
        for photo_id in list(job.photo_ids):
            photo = await get_photo(photo_id)
            if photo is None:
                continue
            try:
                restored = await self.restore.run(photo=photo)
                job.steps.append(f"[修復] {photo.filename}: {restored.summary}")
                await save_job(job)

                photo = await get_photo(photo_id) or photo
                estimated = await self.estimate.run(photo=photo)
                job.steps.append(f"[推定] {photo.filename}: {estimated.summary}（家族の確認待ち）")
            except Exception as exc:  # 1枚の失敗でバッチを止めない
                failures += 1
                _logger.exception("写真の処理に失敗: %s", photo_id)
                photo.status = PhotoStatus.failed
                photo.error = str(exc)
                await save_photo(photo)
                job.steps.append(f"[失敗] {photo.filename}: {exc}")
            finally:
                job.completed += 1
                await save_job(job)

        job.status = JobStatus.done if failures < job.total else JobStatus.failed
        job.steps.append(
            f"完了: {job.completed - failures}/{job.total} 枚を修復・推定。家族の確認をお待ちしています。"
        )
        if failures:
            job.error = f"{failures}件失敗"
        await save_job(job)
        return AgentResult(
            agent=self.name,
            summary=job.steps[-1],
            data={"job_id": job.id, "failures": failures},
        )


_orchestrator = Orchestrator()


def get_orchestrator() -> Orchestrator:
    return _orchestrator
