"""Data contracts, schemas, and Pydantic models for the n8chain optimization engine.

Defines genotypes, phenotypes, persona definitions, budget allocations,
and generation lifecycle summaries for Part 3 (Optimization).
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PersonaType(str, Enum):
    """Target persona type operating the marketing campaign."""
    CONTENT_CREATOR = "content_creator"
    BUSINESS = "business"


class Platform(str, Enum):
    """Supported social media and advertising platforms."""
    INSTAGRAM = "Instagram"
    TIKTOK = "TikTok"
    LINKEDIN = "LinkedIn"
    X = "X"


class Persona(BaseModel):
    """User persona directing content style and fitness priorities."""
    type: PersonaType = Field(
        ...,
        description="Persona category: 'content_creator' or 'business'",
    )
    tone: str = Field(
        default="authentic and engaging",
        description="Brand voice / tone, e.g., 'casual', 'authoritative', 'edgy', 'humorous'",
    )
    target_audience: str = Field(
        default="digital natives and tech early adopters",
        description="Audience segment description",
    )
    risk_tolerance: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Appetite for bold/unorthodox creative angles vs proven formats",
    )
    primary_goal: Literal["reach", "conversions", "engagement", "roas"] = Field(
        default="engagement",
        description="Primary campaign optimization goal",
    )


class ValidationInput(BaseModel):
    """Handoff contract from Part 2 (Validation) to Part 3 (Optimization).

    Provides the selected trend, matched niche, validated persona, and campaign constraints.
    """
    trend_id: str = Field(
        default_factory=lambda: f"trend_{uuid.uuid4().hex[:8]}",
        description="Unique identifier of the validated trend",
    )
    trend_name: str = Field(
        ...,
        description="Human-readable title of the trend (e.g., 'Lo-Fi AI Productivity Hacks')",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Core keyword associations and semantic tags",
    )
    niche: str = Field(
        ...,
        description="Target industry niche (e.g., 'B2B SaaS', 'Personal Development')",
    )
    persona: Persona = Field(
        ...,
        description="Validated persona profile",
    )
    recommended_formats: List[str] = Field(
        default_factory=lambda: ["short_form_video", "carousel", "hook_text"],
        description="Recommended content formats from validation stage",
    )
    total_budget: float = Field(
        default=1000.0,
        gt=0.0,
        description="Total campaign budget in USD allocated for ad spend",
    )


class PostChromosome(BaseModel):
    """Genotype representing a structured marketing post creative."""
    hook: str = Field(
        ...,
        description="Opening hook angle (question, statistic, contrarian statement, etc.)",
    )
    caption_body: str = Field(
        ...,
        description="Core body copy and value proposition",
    )
    visual_asset_prompt: str = Field(
        ...,
        description="Suggested visual creative prompt or Adobe Express template styling",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="Optimized hashtags tailored to trend and niche",
    )
    call_to_action: str = Field(
        ...,
        description="Explicit user prompt (e.g., 'Comment DEMO below', 'Link in bio')",
    )
    target_platform: Platform = Field(
        default=Platform.INSTAGRAM,
        description="Social distribution network",
    )


class BudgetAllocation(BaseModel):
    """Spend and bidding parameters allocated to a candidate post."""
    spend_weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Normalized relative weight within population spend distribution",
    )
    daily_budget: float = Field(
        default=0.0,
        ge=0.0,
        description="Absolute daily currency budget allocated to this candidate",
    )
    bid_aggressiveness: float = Field(
        default=1.0,
        ge=0.2,
        le=3.0,
        description="Bidding multiplier (0.5=conservative, 1.0=standard, 2.0=aggressive)",
    )


class Candidate(BaseModel):
    """Individual candidate in the evolutionary population."""
    id: str = Field(
        default_factory=lambda: f"cand_{uuid.uuid4().hex[:8]}",
        description="Unique candidate identifier",
    )
    generation_index: int = Field(
        default=0,
        ge=0,
        description="Generation in which this candidate was created",
    )
    post: PostChromosome = Field(
        ...,
        description="Post creative chromosome (content genotype)",
    )
    budget: BudgetAllocation = Field(
        default_factory=BudgetAllocation,
        description="Associated budget allocation chromosome",
    )
    fitness_score: float = Field(
        default=0.0,
        description="Multi-objective fitness score evaluated for this candidate",
    )
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Observed or simulated performance indicators (CTR, ROAS, etc.)",
    )
    parent_ids: List[str] = Field(
        default_factory=list,
        description="Parent candidate IDs for evolutionary lineage tracking",
    )
    status: Literal["active", "survived", "eliminated", "recombined"] = Field(
        default="active",
        description="Lifecycle status in current generation",
    )


class PerformanceObservation(BaseModel):
    """Observed performance metrics for a candidate during an active cycle."""
    candidate_id: str
    impressions: int = Field(default=1000, ge=0)
    clicks: int = Field(default=30, ge=0)
    ctr: float = Field(default=0.03, ge=0.0)
    engagement_rate: float = Field(default=0.05, ge=0.0)
    conversions: int = Field(default=2, ge=0)
    conversion_rate: float = Field(default=0.067, ge=0.0)
    spend: float = Field(default=50.0, ge=0.0)
    cpc: float = Field(default=1.67, ge=0.0)
    cac: float = Field(default=25.0, ge=0.0)
    roas: float = Field(default=2.5, ge=0.0)


class GAConfig(BaseModel):
    """Hyperparameters governing genetic evolution and budget dynamics."""
    population_size: int = Field(default=12, ge=4, le=50)
    mutation_rate: float = Field(default=0.20, ge=0.01, le=1.0)
    elitism_ratio: float = Field(default=0.20, ge=0.05, le=0.5)
    tournament_size: int = Field(default=3, ge=2, le=10)
    crossover_rate: float = Field(default=0.80, ge=0.1, le=1.0)
    max_generations: int = Field(default=5, ge=1, le=100)
    budget_exploration_noise: float = Field(default=0.15, ge=0.0, le=0.5)


class GenerationSummary(BaseModel):
    """Telemetry and stats summarizing an evolution generation."""
    generation: int = Field(..., ge=0)
    best_candidate_id: str
    best_fitness: float
    avg_fitness: float
    diversity_score: float
    total_budget_allocated: float
    active_candidates: List[Candidate]
    eliminated_candidate_ids: List[str] = Field(default_factory=list)


class InitCampaignRequest(BaseModel):
    """Request payload to initialize a new evolutionary campaign."""
    validation_input: ValidationInput
    config: Optional[GAConfig] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "validation_input" not in data and "trend_name" in data:
                # Wrap direct ValidationInput provided at root level
                config = data.get("config")
                validation_data = {k: v for k, v in data.items() if k != "config"}
                return {"validation_input": validation_data, "config": config}
        return data


class InitCampaignResponse(BaseModel):
    """Response returned upon campaign initialization."""
    campaign_id: str
    generation: GenerationSummary
    message: str = "Generation 0 initialized successfully"


class StepCampaignRequest(BaseModel):
    """Request to step the evolutionary cycle to the next generation."""
    campaign_id: str
    uploaded_metrics: Optional[List[PerformanceObservation]] = Field(
        default=None,
        description="Optional live ad metrics. If omitted, mock simulator is used.",
    )


class StepCampaignResponse(BaseModel):
    """Response after stepping evolution."""
    campaign_id: str
    generation: GenerationSummary
    budget_reallocation: Dict[str, float]
    message: str


class CampaignStatusResponse(BaseModel):
    """Full campaign diagnostic state and Pareto-optimal candidates."""
    campaign_id: str
    trend_name: str
    niche: str
    persona_type: str
    current_generation: int
    convergence_curve: List[Dict[str, Any]]
    pareto_optimal_candidates: List[Candidate]
    current_budget_breakdown: Dict[str, float]
    history: List[GenerationSummary]
