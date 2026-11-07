"""Persona modeling contracts for Content Creator and Business personas."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


PersonaType = Literal["content_creator", "business"]
ProductionEffort = Literal["low", "medium", "high"]
CreatorGrowthGoal = Literal["virality", "engagement", "community"]
AudioPreference = Literal["any", "trending_sound", "original_only"]
BrandSafetyStrictness = Literal["standard", "strict"]
BusinessObjective = Literal["awareness", "lead_gen", "direct_conversion"]


class ContentCreatorParams(BaseModel):
    """Profile parameters specific to the Content Creator persona."""

    preferred_formats: list[str] = Field(
        default_factory=lambda: ["talking_head", "tutorial", "pov", "demo", "storytime"]
    )
    max_production_effort: ProductionEffort = "medium"
    growth_goal: CreatorGrowthGoal = "virality"
    original_audio_preference: AudioPreference = "any"


class BusinessParams(BaseModel):
    """Profile parameters specific to the Business marketing persona."""

    brand_safety_strictness: BrandSafetyStrictness = "strict"
    campaign_objective: BusinessObjective = "direct_conversion"
    commercial_fit_required: bool = True


class PersonaProfile(BaseModel):
    """Active user persona evaluated by the Suitability Verdict Engine."""

    type: PersonaType = "content_creator"
    display_name: str = "Solo Creator Studio"
    target_domain: str = "Skincare & Everyday Wellness"
    domain_keywords: list[str] = Field(
        default_factory=lambda: ["skincare", "routine", "glow", "wellness", "serum", "hydration"]
    )
    target_audience: str = "Gen Z & Millennial short-form video viewers (18-34)"
    allowed_languages: list[str] = Field(default_factory=lambda: ["en"])

    creator_params: ContentCreatorParams = Field(default_factory=ContentCreatorParams)
    business_params: BusinessParams = Field(default_factory=BusinessParams)


DEFAULT_CREATOR_PERSONA = PersonaProfile(
    type="content_creator",
    display_name="Creator Growth Studio",
    target_domain="Skincare, Wellness & Lifestyle Tech",
    domain_keywords=[
        "skincare",
        "barrier",
        "routine",
        "productivity",
        "ai",
        "workflow",
        "wellness",
        "creator",
    ],
    target_audience="Short-form discovery audience seeking relatable demos & fast hooks",
    allowed_languages=["en"],
    creator_params=ContentCreatorParams(
        preferred_formats=["talking_head", "tutorial", "split_screen_demo", "pov"],
        max_production_effort="medium",
        growth_goal="virality",
        original_audio_preference="any",
    ),
)

DEFAULT_BUSINESS_PERSONA = PersonaProfile(
    type="business",
    display_name="Brand Performance Marketing",
    target_domain="DTC Skincare & SaaS Productivity",
    domain_keywords=[
        "skincare",
        "serum",
        "clinical",
        "saas",
        "automation",
        "productivity",
        "offer",
        "trial",
    ],
    target_audience="High-intent shoppers & B2B/prosumer decision makers",
    allowed_languages=["en"],
    business_params=BusinessParams(
        brand_safety_strictness="strict",
        campaign_objective="direct_conversion",
        commercial_fit_required=True,
    ),
)
