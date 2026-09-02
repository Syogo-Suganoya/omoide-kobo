"""ウゴクアルバム（設計書 12章）: カラー化した写真を数秒だけ動かす。

このエージェントだけは consent_gated で、次の3つを型と手順で担保する。

1. 故人が写る写真では、家族全員（参加済みメンバー）の同意が揃うまで生成を始めない
2. 生成範囲は「その場の自然な動き」に限る。発話や新規の行動は作らない
3. 生成物には必ず AI 生成の透かしを入れ、実写真と混同させない

同意の記録と生成範囲は監査ログに残す。
"""

from __future__ import annotations

import anyio

from app.adapters.gmi import get_generative
from app.agents.base import Agent, AgentResult
from app.infra.blobs import get_blobs, make_ref
from app.models import (
    MOTION_SCOPE,
    AuditAction,
    ConsentStatus,
    Family,
    InviteStatus,
    MotionClip,
    MotionConsent,
    MotionStatus,
    Photo,
    now,
)
from app.repo import save_motion
from app.services import audit

# 生成モデルに渡す指示。カメラの動きと空気の揺らぎだけに限定する。
PROMPT = (
    "写真の中の空気だけをわずかに動かす。"
    "光の揺らぎ、風、ごく小さな身じろぎまで。"
    "人物に喋らせない。新しい動作・表情の変化・構図の変更をしない。数秒で止める。"
)


class ConsentRequired(RuntimeError):
    """同意が揃っていないのに生成しようとしたときに投げる。"""


class MotionAgent(Agent):
    name = "motion"
    role = "カラー化写真を数秒動かす（ウゴクアルバム）"
    autonomy = "consent_gated"

    def prepare(self, *, photo: Photo, family: Family, requested_by: str, includes_deceased: bool) -> MotionClip:
        """依頼を受け取り、必要なら同意待ちの状態を作る。ここでは生成しない。"""
        clip = MotionClip(
            photo_id=photo.id,
            family_id=photo.family_id,
            requested_by=requested_by,
            includes_deceased=includes_deceased,
            scope=MOTION_SCOPE,
        )
        if includes_deceased:
            # 故人が写るなら、参加済みの家族全員に諾否を聞く
            clip.consents = [
                MotionConsent(uid=m.uid, name=m.name)
                for m in family.members
                if m.invite_status is InviteStatus.joined
            ]
            clip.status = MotionStatus.pending_consent
        else:
            clip.status = MotionStatus.generating
        return clip

    async def run(self, *, clip: MotionClip, photo: Photo) -> AgentResult:  # type: ignore[override]
        if clip.includes_deceased and not clip.consent_complete:
            raise ConsentRequired("家族全員の同意が揃っていません")
        if clip.consent_denied:
            raise ConsentRequired("同意しない家族がいるため生成しません")

        generative = get_generative()
        blobs = get_blobs()

        clip.status = MotionStatus.generating
        await save_motion(clip)

        try:
            # 動かすのは家族が選んだ修復結果。無ければ既定の修復結果
            ref = photo.preferred_ref or photo.restored_ref or photo.original_ref
            source = await anyio.to_thread.run_sync(blobs.read, ref)
            video, media_type = await generative.animate(source, PROMPT)

            suffix = "gif" if "gif" in media_type else "mp4"
            video_ref = make_ref(photo.family_id, photo.album_id, "motion", f"{clip.id}.{suffix}")
            await anyio.to_thread.run_sync(lambda: blobs.write(video_ref, video, media_type))

            clip.video_ref = video_ref
            clip.media_type = media_type
            clip.model = generative.name
            clip.status = MotionStatus.ready
            clip.generated_at = now()
        except Exception as exc:
            clip.status = MotionStatus.failed
            clip.error = str(exc)
            await save_motion(clip)
            raise

        await save_motion(clip)
        await audit.record_external_call(
            photo.family_id, generative.name, "image_to_video", mode=generative.name, target=clip.id
        )
        await audit.record(
            photo.family_id,
            AuditAction.motion_generate,
            actor=self.name,
            target=clip.id,
            detail={
                "photo_id": photo.id,
                "scope": clip.scope,
                "watermarked": clip.watermarked,
                "includes_deceased": clip.includes_deceased,
                "consents": [
                    {"name": c.name, "status": c.status.value} for c in clip.consents
                ],
            },
        )
        return AgentResult(
            agent=self.name,
            summary="ウゴクアルバムを作りました（AI 生成の透かし入り）",
            data={"motion_id": clip.id, "media_type": clip.media_type},
        )


def consent_summary(clip: MotionClip) -> str:
    if not clip.consents:
        return "同意の確認は不要（故人は写っていないと申告）"
    granted = sum(1 for c in clip.consents if c.status is ConsentStatus.granted)
    return f"同意 {granted}/{len(clip.consents)}"
