"""語りエージェント: 会話音声から人物・出来事を抽出し写真に紐付ける。

抽出は自律、確定は家族（設計書 4章）。人物関係は confirmed_by_family=False のまま保持し、
家族が承認するまで確定情報として扱わない（設計書 7-3）。
"""

from __future__ import annotations

import anyio

from app.adapters.gemini import get_llm
from app.adapters.speech import get_speech
from app.agents.base import Agent, AgentResult
from app.infra.blobs import get_blobs, make_ref
from app.models import AuditAction, Photo
from app.repo import save_photo
from app.services import audit


class StoryAgent(Agent):
    name = "story"
    role = "会話音声から人物・出来事を抽出し写真に紐付け"
    autonomy = "propose_only"

    async def run(  # type: ignore[override]
        self,
        *,
        photo: Photo,
        audio: bytes | None = None,
        filename: str = "",
        transcript: str | None = None,
        narrator: str | None = None,
    ) -> AgentResult:
        llm = get_llm()
        audio_ref = None

        if transcript is None:
            if audio is None:
                raise ValueError("audio か transcript のいずれかが必要です")
            speech = get_speech()
            blobs = get_blobs()
            audio_ref = make_ref(photo.family_id, photo.album_id, "voice", f"{photo.id}.bin")
            await anyio.to_thread.run_sync(lambda: blobs.write(audio_ref, audio, "audio/webm"))
            transcript = await speech.transcribe(audio, filename or photo.filename)
            await audit.record_external_call(
                photo.family_id, speech.name, "speech_to_text", mode=speech.name, target=photo.id
            )

        story = await llm.structure_story(transcript, photo.resolved_place)
        story.narrator = narrator
        story.audio_ref = audio_ref
        photo.story = story
        await save_photo(photo)

        await audit.record_external_call(
            photo.family_id, llm.name, "structure_story", mode=llm.name, target=photo.id
        )
        await audit.record(
            photo.family_id,
            AuditAction.story_capture,
            actor=self.name,
            target=photo.id,
            detail={
                "narrator": narrator,
                "people_extracted": len(story.people),
                "relations_confirmed_by_ai": False,
            },
        )
        return AgentResult(
            agent=self.name,
            summary=story.summary or "語りを記録しました",
            data={"people": [p.label for p in story.people]},
            proposal=True,
        )
