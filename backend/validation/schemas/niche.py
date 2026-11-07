"""Niche taxonomy, hybrid emergent niche synthesis, and Laya decision trace schemas."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


NicheOrigin = Literal["seed_taxonomy", "emergent_cluster", "custom_user"]
LayaBackendStatus = Literal[
    "laya_sdk_local",
    "laya_transformers_local",
    "laya_hf_inference_api",
    "laya_calibrated_fallback",
]


class SeedNicheDefinition(BaseModel):
    """Curated seed niche definition evaluated by Laya's `choice` primitive."""

    niche_id: str
    name: str
    description: str
    criteria_prompt: str
    keywords: list[str] = Field(default_factory=list)
    typical_hooks: list[str] = Field(default_factory=list)
    typical_formats: list[str] = Field(default_factory=list)
    commercial_categories: list[str] = Field(default_factory=list)


class LayaTypedDecisionTrace(BaseModel):
    """Structured output trace from `convaiinnovations/laya` (ModernBERT-large, 421M, 512 ctx, EN)."""

    model_id: str = "convaiinnovations/laya"
    backbone: str = "ModernBERT-large (421M params, 512 context, English)"
    execution_mode: LayaBackendStatus = "laya_calibrated_fallback"
    estimated_input_tokens: int = 0
    max_context_tokens: int = 512
    input_truncated: bool = False
    english_compatible: bool = True
    temperature: float = 1.35

    # 1. `choice` primitive: probability distribution across candidate seed niches
    choice_probabilities: dict[str, float] = Field(default_factory=dict)
    top_choice_id: str = ""
    top_choice_confidence: float = 0.0

    # 2. `score` primitive: ordinal rubric scores normalized to [0.0, 1.0]
    virality_rubric_score: float = 0.0
    virality_rubric_label: str = "moderate"
    commercial_rubric_score: float = 0.0
    commercial_rubric_label: str = "moderate"
    production_effort_label: Literal["low", "medium", "high"] = "medium"

    # 3. `noul` (yes/no calibrated P(true)) primitives
    brand_safe_probability: float = 0.85
    clear_cta_probability: float = 0.5
    emergent_niche_triggered: bool = False

    compact_state_preview: str = ""
    notes: list[str] = Field(default_factory=list)


class NicheCluster(BaseModel):
    """Matched or dynamically synthesized niche in Hybrid mode."""

    niche_id: str
    name: str
    origin: NicheOrigin = "seed_taxonomy"
    description: str
    taxonomy_source: str = "convaiinnovations/laya-hybrid-v1"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    cohesion_score: float = Field(default=0.0, ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)
    matched_trend_ids: list[str] = Field(default_factory=list)
    commercial_categories: list[str] = Field(default_factory=list)
