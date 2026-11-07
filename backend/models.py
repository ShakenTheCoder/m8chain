"""The public, versioned contract for one analyzed TikTok post."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from urllib.parse import urlsplit, urlunsplit
import re


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeRequest(Contract):
    url: str = Field(max_length=2048)

    @field_validator("url")
    @classmethod
    def tiktok_url(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or parts.username or parts.password or parts.port:
            raise ValueError("Paste an HTTPS TikTok video URL.")
        if host in {"www.tiktok.com", "tiktok.com", "m.tiktok.com"}:
            valid = re.fullmatch(r"/@[^/]+/video/\d+/?", parts.path) or re.fullmatch(r"/t/[\w-]+/?", parts.path)
        elif host in {"vm.tiktok.com", "vt.tiktok.com"}:
            valid = re.fullmatch(r"/[\w-]+/?", parts.path)
        else:
            valid = False
        if not valid:
            raise ValueError("Paste a TikTok video link, such as https://www.tiktok.com/@creator/video/123456789.")
        return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))


class Video(Contract):
    platform: Literal["tiktok"] = "tiktok"
    id: str
    url: str
    creator_id: str | None = None
    published_at: str | None = None
    duration_seconds: float | None = None


class Collection(Contract):
    run_id: str
    collected_at: str
    discovery_queries: list[str] = Field(default_factory=list)


class Language(Contract):
    code: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal["audio", "unavailable"] = "unavailable"
    supported: bool | None = None
    allowed: list[str] = Field(default_factory=lambda: ["en", "ro"])


class Segment(Contract):
    start_seconds: float
    end_seconds: float
    text: str


class Transcript(Contract):
    status: Literal["complete", "unavailable", "failed", "skipped"] = "unavailable"
    source: Literal["faster-whisper"] = "faster-whisper"
    model: str | None = None
    language: str | None = None
    text: str | None = None
    segments: list[Segment] = Field(default_factory=list)


class Sound(Contract):
    id: str | None = None
    title: str | None = None
    author: str | None = None
    is_original: bool | None = None


class TextSequence(Contract):
    source: Literal["transcript", "post_description", "on_screen_text"]
    text: str
    normalized: str
    folded: str
    tokens: list[str]
    start_seconds: float | None = None
    end_seconds: float | None = None


class NumericExpression(Contract):
    source: Literal["transcript", "post_description", "on_screen_text"]
    text: str
    compact_digits: str
    start_seconds: float | None = None
    match_hint_only: Literal[True] = True


class VisibleText(Contract):
    text: str
    frame_index: int | None = None
    timestamp_seconds: float | None = None


class OnScreenText(Contract):
    status: Literal["complete", "unavailable", "failed", "skipped"] = "skipped"
    source: str | None = None
    items: list[VisibleText] = Field(default_factory=list)


class Elements(Contract):
    post_description: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    transcript: Transcript = Field(default_factory=Transcript)
    sound: Sound = Field(default_factory=Sound)
    on_screen_text: OnScreenText = Field(default_factory=OnScreenText)
    text_sequences: list[TextSequence] = Field(default_factory=list)
    numeric_expressions: list[NumericExpression] = Field(default_factory=list)


class Frame(Contract):
    index: int
    timestamp_seconds: float
    description: str | None = None
    asset_path: str | None = None


class VisualAction(Contract):
    description: str
    frame_indices: list[int]
    start_seconds: float
    end_seconds: float


class VisualAnalysis(Contract):
    status: Literal["complete", "unavailable", "failed", "skipped"] = "skipped"
    model: str | None = None
    summary: str | None = None
    frames: list[Frame] = Field(default_factory=list)
    actions: list[VisualAction] = Field(default_factory=list)
    coverage: Literal["sampled_frames_only"] = "sampled_frames_only"
    audio_delivery: Literal["not_analyzed"] = "not_analyzed"
    action_localization: Literal["not_analyzed"] = "not_analyzed"


class MediaEvidence(Contract):
    status: Literal["retained", "not_retained"] = "not_retained"
    video_path: str | None = None
    video_sha256: str | None = None


class ContentDescription(Contract):
    text: str | None = None
    sources: list[str] = Field(default_factory=list)
    method: Literal["visual_summary_and_verbatim_text"] = "visual_summary_and_verbatim_text"


class Observation(Contract):
    observed_at: str
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    like_rate: float | None = None
    share_rate: float | None = None


class Decision(Contract):
    label: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]
    needs_review: bool


class Features(Contract):
    topic: Decision | None = None
    hook_type: Decision | None = None
    format: Decision | None = None
    call_to_action: Decision | None = None
    opening_text: str | None = None
    evidence_sources: list[str] = Field(default_factory=list)


class Classifier(Contract):
    name: Literal["laya"] = "laya"
    model: str
    status: Literal["complete", "skipped", "failed"] = "skipped"
    taxonomy_version: Literal["marketing-v1"] = "marketing-v1"
    input_truncated: bool = False
    min_confidence: float = Field(ge=0, le=1)


class Analysis(Contract):
    schema_version: Literal["1.2"] = "1.2"
    analysis_version: Literal["organ-mvp-2"] = "organ-mvp-2"
    id: str
    status: Literal["complete", "partial", "unsupported_language"] = "partial"
    video: Video
    collection: Collection
    language: Language = Field(default_factory=Language)
    elements: Elements
    description: ContentDescription = Field(default_factory=ContentDescription)
    visual: VisualAnalysis = Field(default_factory=VisualAnalysis)
    media_evidence: MediaEvidence = Field(default_factory=MediaEvidence)
    observation: Observation
    features: Features = Field(default_factory=Features)
    classifier: Classifier
    limitations: list[str] = Field(default_factory=list)
