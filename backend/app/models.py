"""設計書 6章 のデータモデル（Firestore + Cloud Storage）。

推定（estimate）と家族の記憶（confirmed）を必ず別フィールドで保持する。
AI は confirmed を書き換えない ＝ 設計書 7-2「推定は記憶を上書きしない」の型レベルの担保。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# --------------------------------------------------------------------------- 家族

class InviteStatus(str, Enum):
    invited = "invited"
    joined = "joined"
    revoked = "revoked"


class Member(BaseModel):
    uid: str = Field(default_factory=lambda: new_id("uid"))
    name: str
    relation: str  # 続柄（母 / 父 / 長男 …）
    invite_status: InviteStatus = InviteStatus.invited


class Family(BaseModel):
    id: str = Field(default_factory=lambda: new_id("fam"))
    name: str
    members: list[Member] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- 写真

class PhotoStatus(str, Enum):
    uploaded = "uploaded"
    estimating = "estimating"
    awaiting_family = "awaiting_family"  # 家族確認待ち（AI は確定しない）
    confirmed = "confirmed"
    failed = "failed"


class PlaceCandidate(BaseModel):
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    confidence: float = 0.0  # 0.0 - 1.0
    evidence: list[str] = Field(default_factory=list)  # 根拠（看板/車両型式/服装/地形）


class EraEstimate(BaseModel):
    label: str  # 「昭和40年代前半」など
    year_from: int | None = None
    year_to: int | None = None
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class Estimate(BaseModel):
    """AI の推定結果。常に候補・根拠・確度つきで、確定値ではない。"""

    place_candidates: list[PlaceCandidate] = Field(default_factory=list)
    era: EraEstimate | None = None
    features: list[str] = Field(default_factory=list)  # 抽出された視覚特徴
    model: str = ""
    created_at: datetime = Field(default_factory=now)


class FamilyQuestion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("q"))
    text: str
    reason: str = ""  # なぜ聞くのか（どの推定を確かめたいか）
    answered: bool = False
    answer: str | None = None


class Confirmed(BaseModel):
    """家族の記憶。AI 側からは書き込まない。"""

    place: str | None = None
    era: str | None = None
    confirmed_by: str | None = None  # uid / 名前
    family_correction: str | None = None  # AI 推定への訂正コメント
    confirmed_at: datetime | None = None


class PersonMention(BaseModel):
    label: str  # 「祖母」「近所の◯◯さん」
    note: str | None = None
    # 設計書 7-3: 人物関係は AI が確定しない。家族が確定するまで False。
    confirmed_by_family: bool = False


class EventMention(BaseModel):
    summary: str
    when_hint: str | None = None
    confirmed_by_family: bool = False


class Story(BaseModel):
    narrator: str | None = None
    transcript: str | None = None
    summary: str | None = None
    people: list[PersonMention] = Field(default_factory=list)
    events: list[EventMention] = Field(default_factory=list)
    audio_ref: str | None = None
    created_at: datetime = Field(default_factory=now)


class Photo(BaseModel):
    id: str = Field(default_factory=lambda: new_id("pho"))
    album_id: str
    family_id: str
    filename: str
    status: PhotoStatus = PhotoStatus.uploaded
    original_ref: str | None = None  # 家族限定バケットの参照。常に保全（上書きしない）
    estimate: Estimate | None = None
    questions: list[FamilyQuestion] = Field(default_factory=list)
    confirmed: Confirmed = Field(default_factory=Confirmed)
    story: Story | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @property
    def resolved_place(self) -> str | None:
        """家族の記憶が常に優先。無ければ第一候補にフォールバック。"""
        if self.confirmed.place:
            return self.confirmed.place
        if self.estimate and self.estimate.place_candidates:
            return self.estimate.place_candidates[0].name
        return None


class Album(BaseModel):
    id: str = Field(default_factory=lambda: new_id("alb"))
    family_id: str
    title: str
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- 旅程

class SpotStatus(str, Enum):
    existing = "existing"  # 現存
    rebuilt = "rebuilt"  # 建替え・改称
    abolished = "abolished"  # 廃止・消失
    unknown = "unknown"


class Spot(BaseModel):
    photo_id: str
    place: str
    current_status: SpotStatus = SpotStatus.unknown
    current_note: str | None = None
    stay_minutes: int = 30
    lat: float | None = None
    lng: float | None = None


class Leg(BaseModel):
    kind: Literal["move", "stay", "break"] = "move"
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    depart: str | None = None
    arrive: str | None = None
    minutes: int = 0
    means: str | None = None  # 徒歩 / JR / バス …
    note: str | None = None

    model_config = {"populate_by_name": True}


class Itinerary(BaseModel):
    date: str | None = None
    legs: list[Leg] = Field(default_factory=list)
    total_minutes: int = 0
    walking_minutes: int = 0
    breaks: int = 0
    accessibility_notes: list[str] = Field(default_factory=list)


class Stamina(str, Enum):
    low = "low"  # 親の体力を最優先（休憩多め・乗換少なめ）
    normal = "normal"
    high = "high"


class Trip(BaseModel):
    id: str = Field(default_factory=lambda: new_id("trp"))
    family_id: str
    title: str = "思い出巡礼旅"
    origin: str = "東京"
    date: str | None = None
    stamina: Stamina = Stamina.low
    spots: list[Spot] = Field(default_factory=list)
    itinerary: Itinerary | None = None
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- 共有

class ShareTarget(str, Enum):
    photo = "photo"
    album = "album"


class ShareLink(BaseModel):
    """期限付きの閲覧リンク。

    外部サービスに家族の写真を預けず、家族が好きな手段（LINE でもメールでも）でリンクを渡せる。
    トークンを知っていれば閲覧できる代わりに、必ず期限を持ち、いつでも失効できる。
    """

    id: str = Field(default_factory=lambda: new_id("shr"))
    token: str
    family_id: str
    target_type: ShareTarget
    target_id: str
    created_by: str
    expires_at: datetime
    revoked: bool = False
    view_count: int = 0
    created_at: datetime = Field(default_factory=now)

    @property
    def alive(self) -> bool:
        return not self.revoked and self.expires_at > now()


# --------------------------------------------------------------------------- 監査

class AuditAction(str, Enum):
    upload = "upload"
    estimate = "estimate"
    family_confirm = "family_confirm"
    story_capture = "story_capture"
    trip_plan = "trip_plan"
    share = "share"
    share_view = "share_view"
    variant_select = "variant_select"
    share_revoke = "share_revoke"
    share_scope_change = "share_scope_change"
    delete = "delete"
    external_call = "external_call"


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aud"))
    family_id: str
    actor: str = "system"  # uid または agent 名
    action: AuditAction
    target: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    policy: str = ""  # 非学習ポリシーの証跡
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- ジョブ

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    family_id: str
    album_id: str | None = None
    kind: str = "ingest"
    status: JobStatus = JobStatus.queued
    total: int = 0
    completed: int = 0
    photo_ids: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)  # オーケストレータの進行ログ
    error: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
