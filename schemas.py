"""Data contracts, schemas, and Pydantic models for the m8chain optimization engine.

Defines genotypes, phenotypes, persona definitions, client seed ad contracts,
Step 2 Validation handoff bundle schemas, budget allocations, and generation lifecycle summaries.
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


class PostMetrics(BaseModel):
    """Historical or observed performance metrics for a seed ad or post."""
    impressions: float = Field(default=1000.0, ge=0.0, description="Total impressions or views")
    views: Optional[float] = Field(default=None, description="Alias for impressions")
    clicks: int = Field(default=30, ge=0, description="Total clicks")
    ctr: float = Field(default=0.03, ge=0.0, description="Click-through rate (e.g. 0.03 = 3%)")
    engagement_rate: float = Field(default=0.05, ge=0.0, description="Engagement rate (likes+shares+comments / views)")
    conversions: Optional[int] = Field(default=2, ge=0, description="Direct conversions")
    spend: Optional[float] = Field(default=50.0, ge=0.0, description="Observed ad spend in USD")
    cpc: Optional[float] = Field(default=1.67, ge=0.0, description="Cost per click")
    cac: Optional[float] = Field(default=25.0, ge=0.0, description="Customer acquisition cost")
    roas: Optional[float] = Field(default=2.5, ge=0.0, description="Return on ad spend")

    @model_validator(mode="before")
    @classmethod
    def sync_views(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "views" in data and ("impressions" not in data or data["impressions"] is None):
                data["impressions"] = float(data["views"])
            elif "impressions" in data and ("views" not in data or data["views"] is None):
                data["views"] = float(data["impressions"])
        return data


class InputAdOrPost(BaseModel):
    """Incoming seed post or running ad (e.g. from TikTok, Meta, organic)."""
    id: str = Field(
        default_factory=lambda: f"post_{uuid.uuid4().hex[:6]}",
        description="Unique identifier (e.g., 'tiktok_001', 'ad_meta_04')",
    )
    source: str = Field(
        default="tiktok",
        description="Traffic origin: 'tiktok' | 'ad_meta' | 'ad_tiktok' | 'organic'",
    )
    hook: str = Field(
        ...,
        description="The hook text or hook description",
    )
    caption_body: str = Field(
        default="",
        description="Caption body / value proposition",
    )
    call_to_action: str = Field(
        default="Link in bio",
        description="Action prompt (link in bio, share, shop now, demo)",
    )
    visual_asset_prompt: str = Field(
        default="Dynamic vertical short-form video clip, high tempo, kinetic captions",
        description="Description or prompt of visual elements / Adobe template style",
    )
    visual_style: Optional[str] = Field(
        default=None,
        description="Alias for visual_asset_prompt",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="List of hashtags",
    )
    target_platform: Platform = Field(
        default=Platform.TIKTOK,
        description="Platform: TikTok, Instagram, LinkedIn, or X",
    )
    metrics: PostMetrics = Field(
        default_factory=PostMetrics,
        description="Historical observed metrics",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "visual_style" in data and ("visual_asset_prompt" not in data or not data["visual_asset_prompt"]):
                data["visual_asset_prompt"] = data["visual_style"]
            if "target_platform" in data and isinstance(data["target_platform"], str):
                norm = data["target_platform"].strip().lower()
                mapping = {
                    "tiktok": Platform.TIKTOK,
                    "instagram": Platform.INSTAGRAM,
                    "linkedin": Platform.LINKEDIN,
                    "x": Platform.X,
                    "twitter": Platform.X,
                }
                if norm in mapping:
                    data["target_platform"] = mapping[norm]
        return data


class TrendElementGroup(BaseModel):
    """Group of trend elements identified in Part 1 (Organ) and validated in Part 2."""
    trend_id: str = Field(
        default_factory=lambda: f"trend_{uuid.uuid4().hex[:8]}",
        description="Unique trend identifier",
    )
    trend_name: str = Field(
        ...,
        description="Title of the validated trend (e.g. 'POV Office Satire', 'Autonomous AI Workflows')",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Short summary or overview of the trend pattern",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Key semantic keywords and topics associated with the trend",
    )
    recommended_hooks: List[str] = Field(
        default_factory=list,
        description="High-performing opening hooks recommended by validation stage",
    )
    recommended_formats: List[str] = Field(
        default_factory=lambda: ["short_form_video", "carousel", "hook_text"],
        description="Content formats suited for this trend",
    )
    hashtags: List[str] = Field(
        default_factory=list,
        description="Recommended hashtag collection",
    )
    supporting_posts: Optional[List[InputAdOrPost]] = Field(
        default_factory=list,
        description="Sample posts or TikToks supporting the trend (with or without historical metrics)",
    )


class ValidationVerdict(BaseModel):
    """Validation stage verdict on persona suitability and positioning guidance."""
    verdict_status: str = Field(
        default="approved",
        description="Suitability verdict status: 'approved', 'strong_match', 'caution', etc.",
    )
    suitability_score: float = Field(
        default=0.92,
        description="Numerical suitability score (0.0 to 1.0 or 0 to 100)",
    )
    reasoning: str = Field(
        default="Trend exhibits strong engagement affinity with the persona audience and brand tone.",
        description="Explanation for why this trend matches the user persona and niche",
    )
    strategic_angle: Optional[str] = Field(
        default=None,
        description="Actionable strategic direction (e.g., 'Focus on relatable burnout humor and quick-fix hacks')",
    )


class ValidationHandoffBundle(BaseModel):
    """Official Step 2 (Validation) handoff bundle passed to Step 3 (Optimization)."""
    campaign_id: Optional[str] = Field(
        default=None,
        description="Optional campaign ID from validation stage",
    )
    selected_trend: TrendElementGroup = Field(
        ...,
        description="User-selected winning trend and constituent elements",
    )
    niche: str = Field(
        ...,
        description="Industry niche (e.g., 'B2B MarTech & SaaS', 'Creator Economy')",
    )
    persona: Persona = Field(
        ...,
        description="Content creator or Business persona profile",
    )
    verdict: ValidationVerdict = Field(
        default_factory=ValidationVerdict,
        description="Suitability verdict and strategic positioning direction",
    )
    total_budget: float = Field(
        default=1000.0,
        gt=0.0,
        description="Total campaign budget in USD allocated for ad spend",
    )
    seed_posts: Optional[List[InputAdOrPost]] = Field(
        default_factory=list,
        description="Optional supporting TikToks or ads with metrics passed forward from upstream stages",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_supporting_posts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync seed_posts from selected_trend.supporting_posts if not explicitly set
            selected_trend = data.get("selected_trend")
            if isinstance(selected_trend, dict):
                supp = selected_trend.get("supporting_posts")
                if supp and not data.get("seed_posts"):
                    data["seed_posts"] = supp
        return data


class ValidationInput(BaseModel):
    """Unified internal contract for Part 3 (Optimization).

    Accepts validated trend/niche parameters alongside incoming client TikTok posts,
    running ads, and the official Step 2 ValidationHandoffBundle.
    """
    trend_id: str = Field(
        default_factory=lambda: f"trend_{uuid.uuid4().hex[:8]}",
        description="Unique identifier of the validated trend or campaign",
    )
    trend_name: str = Field(
        default="Viral Marketing Campaign",
        description="Human-readable title of the trend or campaign name",
    )
    campaign_name: Optional[str] = Field(
        default=None,
        description="Alias for trend_name",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Core keyword associations and semantic tags",
    )
    niche: str = Field(
        default="Creator Economy & Digital Marketing",
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
    recommended_hooks: List[str] = Field(
        default_factory=list,
        description="Recommended hooks provided in trend element group",
    )
    total_budget: float = Field(
        default=1000.0,
        gt=0.0,
        description="Total campaign budget in USD allocated for ad spend",
    )
    seed_posts: List[InputAdOrPost] = Field(
        default_factory=list,
        description="Incoming client TikTok posts and running ads with historical performance",
    )
    selected_trend: Optional[TrendElementGroup] = Field(
        default=None,
        description="Full trend element group if passed from validation bundle",
    )
    verdict: Optional[ValidationVerdict] = Field(
        default=None,
        description="Validation stage verdict and strategic angle",
    )
    strategic_angle: Optional[str] = Field(
        default=None,
        description="Strategic positioning direction for creative generation",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_from_bundle_or_trend(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Check if this is a ValidationHandoffBundle or has selected_trend
            trend_obj = data.get("selected_trend")
            if isinstance(trend_obj, dict):
                data.setdefault("trend_id", trend_obj.get("trend_id") or f"trend_{uuid.uuid4().hex[:8]}")
                data.setdefault("trend_name", trend_obj.get("trend_name"))
                data.setdefault("campaign_name", trend_obj.get("trend_name"))
                if "keywords" in trend_obj and not data.get("keywords"):
                    data["keywords"] = trend_obj["keywords"]
                if "recommended_formats" in trend_obj and not data.get("recommended_formats"):
                    data["recommended_formats"] = trend_obj["recommended_formats"]
                if "recommended_hooks" in trend_obj and not data.get("recommended_hooks"):
                    data["recommended_hooks"] = trend_obj["recommended_hooks"]
                if "supporting_posts" in trend_obj and not data.get("seed_posts"):
                    data["seed_posts"] = trend_obj["supporting_posts"]

            # Sync verdict
            verdict_obj = data.get("verdict")
            if isinstance(verdict_obj, dict):
                if "strategic_angle" in verdict_obj and not data.get("strategic_angle"):
                    data["strategic_angle"] = verdict_obj["strategic_angle"]

            # Sync campaign_name and trend_name
            if "campaign_name" in data and ("trend_name" not in data or not data["trend_name"]):
                data["trend_name"] = data["campaign_name"]
            elif "trend_name" in data and ("campaign_name" not in data or not data["campaign_name"]):
                data["campaign_name"] = data["trend_name"]
        return data


class CampaignInitPayload(BaseModel):
    """Dedicated initialization payload for incoming TikToks and ads."""
    campaign_name: str = Field(..., description="Campaign name or trend label")
    persona: Persona = Field(..., description="Content creator vs Business persona")
    total_budget: float = Field(default=1000.0, gt=0.0, description="Campaign total spend limit")
    seed_posts: List[InputAdOrPost] = Field(
        default_factory=list,
        description="Incoming TikTok posts, Meta ads, or organic creatives with historical metrics",
    )
    niche: Optional[str] = Field(default="Creator Economy & Digital Marketing")
    keywords: Optional[List[str]] = Field(default_factory=list)
    recommended_formats: Optional[List[str]] = Field(default_factory=lambda: ["short_form_video", "carousel"])


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
    origin: Literal["client_seed", "survived_elite", "recombined", "evolved_offspring", "seed_variation"] = Field(
        default="evolved_offspring",
        description="Origin tracking: client seed ad vs evolved generation offspring",
    )
    original_seed_id: Optional[str] = Field(
        default=None,
        description="Client post ID if originated directly from an incoming TikTok or ad",
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
            if "validation_input" in data:
                return data

            # Direct ValidationHandoffBundle or wrapped validation_handoff
            if "validation_handoff" in data:
                return {"validation_input": data["validation_handoff"], "config": data.get("config")}

            # Direct fields (e.g. selected_trend, trend_name, campaign_name, or seed_posts)
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
