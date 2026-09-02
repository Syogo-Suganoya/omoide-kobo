"""語りエージェント用の音声ポート（Speech-to-Text / Text-to-Speech）。

mock は決定的な語りフィクスチャを返し、TTS は無音 WAV を返す（UI の疎通確認用）。
"""

from __future__ import annotations

import hashlib
import struct
from typing import Protocol

from app.config import get_settings

_TRANSCRIPTS = [
    "この駅はね、母さんが女学校に通ってたときに毎朝使ってた駅なの。"
    "改札のおじさんが顔を覚えててくれてね、雨の日は傘を貸してくれたのよ。"
    "写真を撮ったのは、叔母さんが東京へ出る日の見送りだったと思う。",
    "この商店街は日曜になると人でいっぱいでね。"
    "父さんが自転車の後ろに乗せてくれて、角の店でアイスキャンデーを買うのが楽しみだった。"
    "近所の田中さんの店が向かいにあって、よく声をかけてもらったの。",
    "海はね、夏になると親戚みんなで行ったの。"
    "祖父が浮き輪をふくらませるのが下手で、いつも兄が代わりにやってた。"
    "この日は波が高くて、あんまり泳げなかったのを覚えてる。",
    "七五三のときの写真ね。祖母が仕立ててくれた着物なの。"
    "石段が長くて、途中で泣いてしまって、父さんに抱っこしてもらって登ったの。"
    "写真のあと、千歳飴をもらってご機嫌になったのよ。",
]


class SpeechPort(Protocol):
    name: str

    async def transcribe(self, audio: bytes, filename: str = "") -> str: ...

    async def synthesize(self, text: str) -> bytes: ...


def _silent_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    frames = int(seconds * rate)
    data = b"\x00\x00" * frames
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE", b"fmt ", 16, 1, 1, rate, rate * 2, 2, 16,
        b"data", len(data),
    )
    return header + data


class MockSpeech:
    name = "speech-mock"

    async def transcribe(self, audio: bytes, filename: str = "") -> str:
        seed = hashlib.sha256(filename.encode("utf-8") or audio[:256]).hexdigest()
        return _TRANSCRIPTS[int(seed[:8], 16) % len(_TRANSCRIPTS)]

    async def synthesize(self, text: str) -> bytes:
        return _silent_wav(min(6.0, max(1.0, len(text) / 20)))


class LiveSpeech:
    name = "google-speech"

    async def transcribe(self, audio: bytes, filename: str = "") -> str:
        from google.cloud import speech

        client = speech.SpeechAsyncClient()
        config = speech.RecognitionConfig(
            language_code="ja-JP",
            enable_automatic_punctuation=True,
            model="latest_long",
        )
        response = await client.recognize(
            config=config, audio=speech.RecognitionAudio(content=audio)
        )
        return "".join(r.alternatives[0].transcript for r in response.results)

    async def synthesize(self, text: str) -> bytes:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechAsyncClient()
        response = await client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(language_code="ja-JP"),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            ),
        )
        return response.audio_content


def get_speech() -> SpeechPort:
    return LiveSpeech() if get_settings().speech_mode == "live" else MockSpeech()
