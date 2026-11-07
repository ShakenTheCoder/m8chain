"""Performance simulator generating realistic ad metrics and market feedback.

Simulates social platform audience dynamics, hook and creative affinities,
diminishing returns with budget saturation, and stochastic market noise.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional
import numpy as np

from schemas import Candidate, PerformanceObservation, Persona, Platform, ValidationInput


class MarketingPerformanceSimulator:
    """Stochastic simulator mimicking live social ad network performance.

    Models platform-hook affinity, creative resonance, audience saturation,
    and cost dynamics with non-linear diminishing returns.
    """

    def __init__(self, random_seed: Optional[int] = None) -> None:
        """Initialize simulator with optional deterministic seed."""
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)

    def evaluate_candidate(
        self,
        candidate: Candidate,
        validation_input: ValidationInput,
    ) -> PerformanceObservation:
        """Generate simulated performance observation for a single candidate.

        Args:
            candidate: Candidate post and budget to evaluate.
            validation_input: Contextual trend, niche, and persona constraints.

        Returns:
            PerformanceObservation with clicks, CTR, conversions, CPC, CAC, and ROAS.
        """
        post = candidate.post
        persona = validation_input.persona
        allocated_spend = max(5.0, candidate.budget.daily_budget)

        # 1. Base platform dynamics
        platform_base = {
            Platform.INSTAGRAM: {"ctr": 0.032, "eng": 0.055, "cpc": 1.40, "cvr": 0.045},
            Platform.TIKTOK: {"ctr": 0.042, "eng": 0.082, "cpc": 0.95, "cvr": 0.038},
            Platform.LINKEDIN: {"ctr": 0.021, "eng": 0.035, "cpc": 4.50, "cvr": 0.085},
            Platform.X: {"ctr": 0.028, "eng": 0.048, "cpc": 1.10, "cvr": 0.032},
        }[post.target_platform]

        # 2. Hook and Angle Resonance Multiplier
        hook_multiplier = 1.0
        hook_lower = post.hook.lower()
        if any(w in hook_lower for w in ["secret", "stop", "never", "why", "truth", "mistake", "hack"]):
            hook_multiplier += 0.25  # Curiosity / contrarian hook bonus
        if any(char.isdigit() for char in post.hook):
            hook_multiplier += 0.15  # Specific numbers/statistics bonus
        if "?" in post.hook:
            hook_multiplier += 0.10  # Interrogative engagement bonus

        # 3. Persona & Platform Alignment Multiplier
        alignment_multiplier = 1.0
        if persona.type.value == "business":
            if post.target_platform == Platform.LINKEDIN:
                alignment_multiplier += 0.35
            elif post.target_platform == Platform.TIKTOK:
                alignment_multiplier -= 0.10
        elif persona.type.value == "content_creator":
            if post.target_platform in (Platform.TIKTOK, Platform.INSTAGRAM):
                alignment_multiplier += 0.30
            elif post.target_platform == Platform.LINKEDIN:
                alignment_multiplier -= 0.15

        # 4. CTA and Visual Prompt Quality heuristic
        cta_lower = post.call_to_action.lower()
        cvr_multiplier = 1.0
        if any(term in cta_lower for term in ["shop", "buy", "demo", "claim", "book", "get"]):
            cvr_multiplier += 0.25
        elif any(term in cta_lower for term in ["save", "comment", "share"]):
            hook_multiplier += 0.10  # boosts engagement instead of direct conversion

        # 5. Diminishing returns & audience saturation with higher budget
        # Higher spend increases CPM/CPC due to audience ad fatigue (logarithmic decay)
        saturation_factor = 1.0 / (1.0 + 0.15 * math.log1p(allocated_spend / 30.0))

        # 6. Add Gaussian noise to simulate volatile auction dynamics
        ctr_noise = max(0.6, np.random.normal(1.0, 0.12))
        cvr_noise = max(0.6, np.random.normal(1.0, 0.15))

        # Calculate final rates
        simulated_ctr = float(
            np.clip(
                platform_base["ctr"] * hook_multiplier * alignment_multiplier * saturation_factor * ctr_noise,
                0.005,
                0.14,
            )
        )
        simulated_eng = float(
            np.clip(
                platform_base["eng"] * hook_multiplier * alignment_multiplier * saturation_factor * ctr_noise,
                0.01,
                0.25,
            )
        )
        simulated_cvr = float(
            np.clip(
                platform_base["cvr"] * cvr_multiplier * alignment_multiplier * cvr_noise,
                0.008,
                0.20,
            )
        )

        # Effective CPC adjusted by bid aggressiveness
        bid_factor = candidate.budget.bid_aggressiveness
        effective_cpc = float(
            max(0.30, platform_base["cpc"] * (0.8 + 0.4 * bid_factor) / saturation_factor)
        )

        # Derive counts based on spend
        clicks = max(1, int(allocated_spend / effective_cpc))
        impressions = max(clicks, int(clicks / simulated_ctr))
        conversions = max(0, int(clicks * simulated_cvr))

        # CAC & ROAS calculation
        cac = float(allocated_spend / conversions) if conversions > 0 else float(allocated_spend * 1.5)
        avg_order_value = 85.0 if persona.type.value == "business" else 28.0
        total_revenue = conversions * avg_order_value
        roas = float(round(total_revenue / allocated_spend, 2)) if allocated_spend > 0 else 0.0

        return PerformanceObservation(
            candidate_id=candidate.id,
            impressions=impressions,
            clicks=clicks,
            ctr=round(simulated_ctr, 4),
            engagement_rate=round(simulated_eng, 4),
            conversions=conversions,
            conversion_rate=round(simulated_cvr, 4),
            spend=round(allocated_spend, 2),
            cpc=round(effective_cpc, 2),
            cac=round(cac, 2),
            roas=round(roas, 2),
        )

    def evaluate_population(
        self,
        candidates: List[Candidate],
        validation_input: ValidationInput,
    ) -> List[PerformanceObservation]:
        """Batch evaluate all active candidates in the population.

        Args:
            candidates: Population of candidate posts.
            validation_input: Campaign validation parameters.

        Returns:
            List of PerformanceObservation results corresponding to candidates.
        """
        observations = []
        for c in candidates:
            if c.status == "eliminated":
                continue
            obs = self.evaluate_candidate(c, validation_input)
            # Inject metrics into candidate state
            c.metrics = {
                "impressions": float(obs.impressions),
                "clicks": float(obs.clicks),
                "ctr": obs.ctr,
                "engagement_rate": obs.engagement_rate,
                "conversions": float(obs.conversions),
                "conversion_rate": obs.conversion_rate,
                "spend": obs.spend,
                "cpc": obs.cpc,
                "cac": obs.cac,
                "roas": obs.roas,
            }
            observations.append(obs)
        return observations
