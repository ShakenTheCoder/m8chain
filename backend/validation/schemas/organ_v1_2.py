"""Runtime input contracts for data received from the `organ` branch (schema v1.2 / organ-mvp-2).

Supports both:
1. Colleague's Trend Description JSON containing trend metadata + supporting v1.2 video records.
2. Standalone or batch v1.2 video records (automatically grouped into synthetic trend descriptions).
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


RecordStatus = Literal["complete", "partial", "unsupported_language"]


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    platform: str = "tiktok"
    id: str
    url: str = ""
    creator_id: str = ""
    published_at: str = ""
    duration_seconds: float = Field(default=0.0, ge=0.0)


class CollectionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str = ""
    collected_at: str = ""
    discovery_queries: list[str] = Field(default_factory=list)


class LanguageInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str = "en"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "detector"
    supported: bool = True
    allowed: list[str] = Field(default_factory=lambda: ["en"])


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    start_seconds: float = Field(default=0.0, ge=0.0)
    end_seconds: float = Field(default=0.0, ge=0.0)
    text: str = ""


class TranscriptInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "complete"
    source: str = "asr"
    model: str = ""
    language: str = "en"
    text: str = ""
    segments: list[TranscriptSegment] = Field(default_factory=list)


class SoundInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str = ""
    author: str = ""
    is_original: bool = True


class OnScreenTextItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = ""
    frame_index: int = 0
    timestamp_seconds: float = Field(default=0.0, ge=0.0)


class OnScreenTextInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "complete"
    source: str = "ocr"
    items: list[OnScreenTextItem] = Field(default_factory=list)


class TextSequenceItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = ""
    text: str = ""
    normalized: str = ""
    folded: str = ""
    tokens: list[str] = Field(default_factory=list)
    start_seconds: float = Field(default=0.0, ge=0.0)
    end_seconds: float = Field(default=0.0, ge=0.0)


class NumericExpressionItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = ""
    text: str = ""
    compact_digits: str = ""
    start_seconds: float = Field(default=0.0, ge=0.0)
    match_hint_only: bool = True


class ElementsInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    post_description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    transcript: TranscriptInfo = Field(default_factory=TranscriptInfo)
    sound: SoundInfo = Field(default_factory=SoundInfo)
    on_screen_text: OnScreenTextInfo = Field(default_factory=OnScreenTextInfo)
    text_sequences: list[TextSequenceItem] = Field(default_factory=list)
    numeric_expressions: list[NumericExpressionItem] = Field(default_factory=list)


class SynthesizedDescription(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = ""
    sources: list[str] = Field(default_factory=list)
    method: str = ""


class VisualFrame(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = 0
    timestamp_seconds: float = Field(default=0.0, ge=0.0)
    description: str = ""
    asset_path: str = ""


class VisualAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str = ""
    frame_indices: list[int] = Field(default_factory=list)
    start_seconds: float = Field(default=0.0, ge=0.0)
    end_seconds: float = Field(default=0.0, ge=0.0)


class VisualInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "complete"
    model: str = ""
    summary: str = ""
    frames: list[VisualFrame] = Field(default_factory=list)
    actions: list[VisualAction] = Field(default_factory=list)
    coverage: str = "full"
    audio_delivery: str = ""
    action_localization: str = ""


class MediaEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "verified"
    video_path: str = ""
    video_sha256: str = ""


class ObservationMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    observed_at: str = ""
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    like_rate: float = Field(default=0.0, ge=0.0)
    share_rate: float = Field(default=0.0, ge=0.0)


class ExtractedFeatures(BaseModel):
    model_config = ConfigDict(extra="allow")

    topic: str = ""
    hook_type: str = ""
    format: str = ""
    call_to_action: str = ""
    opening_text: str = ""
    evidence_sources: list[str] = Field(default_factory=list)


class ClassifierMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    model: str = ""
    status: str = "complete"
    taxonomy_version: str = ""
    input_truncated: bool = False
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OrganVideoRecordV1_2(BaseModel):
    """Exact runtime contract for an analyzed video record produced by `organ` (schema 1.2)."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.2"
    analysis_version: str = "organ-mvp-2"
    id: str
    status: RecordStatus = "complete"

    video: VideoMetadata
    collection: CollectionMetadata = Field(default_factory=CollectionMetadata)
    language: LanguageInfo = Field(default_factory=LanguageInfo)
    elements: ElementsInfo = Field(default_factory=ElementsInfo)
    description: SynthesizedDescription = Field(default_factory=SynthesizedDescription)
    visual: VisualInfo = Field(default_factory=VisualInfo)
    media_evidence: MediaEvidence = Field(default_factory=MediaEvidence)
    observation: ObservationMetrics = Field(default_factory=ObservationMetrics)
    features: ExtractedFeatures = Field(default_factory=ExtractedFeatures)
    classifier: ClassifierMetadata = Field(default_factory=ClassifierMetadata)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> "OrganVideoRecordV1_2":
        if not self.schema_version.startswith("1."):
            raise ValueError(
                f"Unsupported organ record schema_version '{self.schema_version}'. Expected '1.2'."
            )
        return self


class TrendDominantFeatures(BaseModel):
    model_config = ConfigDict(extra="allow")

    topic: str = ""
    hook_type: str = ""
    format: str = ""
    call_to_action: str = ""
    common_hashtags: list[str] = Field(default_factory=list)
    sound_motif: str = ""


class TrendBenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_count: int = 0
    usable_record_count: int = 0
    complete_count: int = 0
    partial_count: int = 0
    unsupported_language_count: int = 0
    total_views: int = 0
    avg_views: float = 0.0
    avg_like_rate: float = 0.0
    avg_share_rate: float = 0.0
    avg_save_rate: float = 0.0
    avg_comment_rate: float = 0.0


class OrganTrendDescription(BaseModel):
    """Trend Description JSON received from the `organ` colleague.

    Accepts flexible field aliases (`trend_id`/`id`, `title`/`name`/`label`,
    `summary`/`description`, `records`/`videos`/`posts`/`supporting_records`)
    so integration across branches works seamlessly without brittle renames.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    trend_id: str = Field(
        validation_alias=AliasChoices("trend_id", "id", "cluster_id")
    )
    title: str = Field(
        default="Untitled Trend",
        validation_alias=AliasChoices("title", "name", "label", "trend_name"),
    )
    summary: str = Field(
        default="",
        validation_alias=AliasChoices("summary", "description", "trend_description", "overview"),
    )
    discovered_at: str = Field(
        default="",
        validation_alias=AliasChoices("discovered_at", "created_at", "collected_at"),
    )
    shared_elements: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("shared_elements", "motifs", "key_signals", "tags"),
    )
    dominant_features: TrendDominantFeatures | None = None
    records: list[OrganVideoRecordV1_2] = Field(
        default_factory=list,
        validation_alias=AliasChoices("records", "videos", "posts", "supporting_records", "items"),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
