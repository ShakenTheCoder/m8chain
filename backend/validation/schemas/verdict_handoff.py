"""Suitability Verdict and Optimization Handoff contracts (Validation -> Optimization)."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

from .niche import LayaTypedDecisionTrace, NicheCluster
from .organ_v1_2 import (
    OrganVideoRecordV1_2,
    TrendBenchmarkMetrics,
    TrendDominantFeatures,
)
from .persona import PersonaProfile


FitStatus = Literal["strong_fit", "conditional_fit", "weak_fit", "disqualified"]


class EvidenceReference(BaseModel):
    record_id: str
    platform: str = "tiktok"
    record_status: str = "complete"
    signal_type: str
    excerpt: str
    timestamp_range: str | None = None


class DimensionBreakdown(BaseModel):
    domain_relevance: float = Field(default=0.0, ge=0.0, le=100.0)
    persona_alignment: float = Field(default=0.0, ge=0.0, le=100.0)
    engagement_momentum: float = Field(default=0.0, ge=0.0, le=100.0)
    execution_or_brand_safety: float = Field(default=0.0, ge=0.0, le=100.0)
    cta_and_conversion_fit: float = Field(default=0.0, ge=0.0, le=100.0)
    data_completeness: float = Field(default=0.0, ge=0.0, le=100.0)


class SuitabilityVerdict(BaseModel):
    """Structured verdict for a (Trend, Niche) pair evaluated under an active Persona."""

    trend_id: str
    niche_id: str
    persona_type: str
    fit_status: FitStatus
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)
    dimension_scores: DimensionBreakdown
    headline: str
    rationale: str
    strengths: list[str] = Field(default_factory=list)
    risks_and_limitations: list[str] = Field(default_factory=list)
    recommended_angles: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)


class ValidatedTrendView(BaseModel):
    """Enriched trend card returned to the Next.js Validation dashboard."""

    trend_id: str
    title: str
    summary: str
    discovered_at: str = ""
    shared_elements: list[str] = Field(default_factory=list)
    dominant_features: TrendDominantFeatures
    benchmark_metrics: TrendBenchmarkMetrics
    matched_niche: NicheCluster
    laya_trace: LayaTypedDecisionTrace
    suitability_verdict: SuitabilityVerdict
    ingestion_warnings: list[str] = Field(default_factory=list)
    records: list[OrganVideoRecordV1_2] = Field(default_factory=list)


class OptimizationSeedHints(BaseModel):
    """Actionable seed parameters extracted from Validation to warm-start Part 3 GA/EP."""

    recommended_hook_type: str
    recommended_format: str
    recommended_cta: str
    seed_hashtags: list[str] = Field(default_factory=list)
    opening_hook_templates: list[str] = Field(default_factory=list)
    target_duration_seconds_range: tuple[int, int] = (15, 45)
    budget_allocation_posture: Literal["aggressive_scale", "controlled_test", "micro_experiment"] = (
        "controlled_test"
    )
    suggested_initial_population_size: int = 12


class SelectedTrendBundle(BaseModel):
    trend_id: str
    title: str
    summary: str
    shared_elements: list[str] = Field(default_factory=list)
    dominant_features: TrendDominantFeatures
    benchmark_metrics: TrendBenchmarkMetrics
    supporting_records: list[OrganVideoRecordV1_2]


class HandoffDeliveryStatus(BaseModel):
    persisted_path: str
    webhook_configured: bool = False
    webhook_url: str | None = None
    webhook_forwarded: bool = False
    webhook_status_code: int | None = None
    webhook_message: str = "Ready for Optimization stage consumption via REST endpoint or JSON bundle."


class OptimizationHandoffBundle(BaseModel):
    """Clean handoff bundle passed from Part 2 (`validation`) -> Part 3 (`optimization`)."""

    handoff_version: str = "1.0"
    handoff_id: str
    confirmed_at: str
    source_branch: str = "validation"
    target_branch: str = "optimization"

    persona: PersonaProfile
    niche: NicheCluster
    selected_trend: SelectedTrendBundle
    suitability_verdict: SuitabilityVerdict
    laya_decision_trace: LayaTypedDecisionTrace
    optimization_seed_hints: OptimizationSeedHints
    user_notes: str = ""
    delivery: HandoffDeliveryStatus | None = None
