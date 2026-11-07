"""Genetic Algorithm and Evolutionary Programming Engine for marketing campaigns.

Implements post chromosome representation, multi-objective fitness evaluation,
tournament selection with elitism, crossover, mutation operators, and population lifecycle.
"""

from __future__ import annotations

import copy
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from budget import BudgetReallocator
from schemas import (
    BudgetAllocation,
    Candidate,
    GAConfig,
    GenerationSummary,
    PerformanceObservation,
    Persona,
    PersonaType,
    Platform,
    PostChromosome,
    ValidationInput,
)
from simulator import MarketingPerformanceSimulator


class EvolutionaryOptimizationEngine:
    """Evolutionary Engine driving content mutation, crossover, and budget optimization."""

    # Curated templates for gene recombination and mutations
    HOOK_TEMPLATES = [
        "Why is nobody in {niche} talking about {trend_name}?",
        "91% of {niche} teams are making this critical {keyword} mistake.",
        "Stop doing {keyword} the old way. Here is the contrarian blueprint:",
        "The 3-step {trend_name} framework that actually scales in 2026.",
        "How top performers in {niche} turned {trend_name} into an unfair advantage.",
        "Unpopular opinion: your current approach to {keyword} is burning your budget.",
        "What happens when you combine {trend_name} with automated workflows? See the data:",
        "The exact {keyword} strategy we used to 4x efficiency without extra headcount.",
    ]

    CAPTION_TEMPLATES = [
        "In {niche}, the rules just shifted. {trend_name} is no longer optional—it's the differentiator. "
        "Here are 3 core pillars to master right now:\n1. Focus on high-leverage {keyword}.\n"
        "2. Automate repetitive distribution.\n3. Double down on verified audience resonance.",
        "Most people overcomplicate {trend_name}. The real secret isn't more hours—it's smarter systems. "
        "We dissected the top {keyword} campaigns and found a common pattern: clear hooks, low friction, and ruthless execution.",
        "If you want better ROI on {keyword}, you need to evolve with the market. "
        "Here's the breakdown of how {trend_name} bridges the gap between attention and conversion.",
        "Break through the noise in {niche}. While competitors chase yesterday's algorithms, "
        "early adopters of {trend_name} are capturing market share at half the acquisition cost.",
    ]

    VISUAL_PROMPT_TEMPLATES = [
        "Adobe Express kinetic typography with bold neon accents, split-screen UI highlight, 9:16 vertical ratio.",
        "Adobe Firefly studio editorial shot, clean minimalist workspace, ambient lighting, cinematic depth of field.",
        "High-contrast Bento-box grid displaying 3 actionable stats for {keyword}, modern glassmorphic card styling.",
        "Split-screen Before vs After comparison in {niche}, vibrant Adobe Illustrator vector badges.",
        "Dynamic 3D isometric infographic showing exponential growth curve driven by {trend_name}.",
    ]

    CTA_CREATOR_TEMPLATES = [
        "Save this post for your next campaign brainstorm 📌",
        "Comment 'GROWTH' below and I'll DM you the free breakdown link 🚀",
        "Share this with a colleague who needs to see this shift 💡",
        "Tap follow for weekly tactical breakdowns in {niche} 🔔",
    ]

    CTA_BUSINESS_TEMPLATES = [
        "Claim your complimentary {trend_name} audit today (link in bio) 📊",
        "Book a 15-minute product walkthrough to unlock higher ROAS 🎯",
        "Download the complete enterprise {keyword} implementation playbook 📥",
        "Start your 14-day free trial—no credit card required ⚡",
    ]

    def __init__(
        self,
        config: Optional[GAConfig] = None,
        simulator: Optional[MarketingPerformanceSimulator] = None,
        budget_reallocator: Optional[BudgetReallocator] = None,
    ) -> None:
        """Initialize evolutionary engine with config and sub-modules."""
        self.config = config or GAConfig()
        self.simulator = simulator or MarketingPerformanceSimulator()
        self.reallocator = budget_reallocator or BudgetReallocator()

    def initialize_population(self, validation_input: ValidationInput) -> List[Candidate]:
        """Seed the Generation 0 population of candidate posts and budget allocations.

        Combines trend keywords with randomized structural angles and platforms.
        """
        population: List[Candidate] = []
        platforms = [Platform.INSTAGRAM, Platform.TIKTOK, Platform.LINKEDIN, Platform.X]
        niche = validation_input.niche
        trend = validation_input.trend_name
        keywords = validation_input.keywords or [niche, "growth", "automation"]
        persona = validation_input.persona

        for i in range(self.config.population_size):
            kw = keywords[i % len(keywords)]
            platform = platforms[i % len(platforms)]

            hook = random.choice(self.HOOK_TEMPLATES).format(niche=niche, trend_name=trend, keyword=kw)
            caption = random.choice(self.CAPTION_TEMPLATES).format(niche=niche, trend_name=trend, keyword=kw)
            visual = random.choice(self.VISUAL_PROMPT_TEMPLATES).format(niche=niche, trend_name=trend, keyword=kw)

            cta_pool = (
                self.CTA_CREATOR_TEMPLATES
                if persona.type == PersonaType.CONTENT_CREATOR
                else self.CTA_BUSINESS_TEMPLATES
            )
            cta = random.choice(cta_pool).format(niche=niche, trend_name=trend, keyword=kw)

            hashtags = [
                f"#{kw.replace(' ', '').lower()}",
                f"#{niche.replace(' ', '').lower()}",
                f"#{trend.split()[0].replace(' ', '').lower()}",
                "#marketing",
                "#growth",
            ]

            chromosome = PostChromosome(
                hook=hook,
                caption_body=caption,
                visual_asset_prompt=visual,
                hashtags=hashtags,
                call_to_action=cta,
                target_platform=platform,
            )

            candidate = Candidate(
                id=f"cand_g0_{i+1:02d}",
                generation_index=0,
                post=chromosome,
                budget=BudgetAllocation(spend_weight=1.0, daily_budget=0.0, bid_aggressiveness=1.0),
                status="active",
            )
            population.append(candidate)

        # Distribute initial budget equally
        self.reallocator.allocate_initial_budget(population, validation_input.total_budget)
        return population

    def evaluate_fitness(
        self,
        candidates: List[Candidate],
        persona: Persona,
        observations: Optional[List[PerformanceObservation]] = None,
    ) -> None:
        """Calculate multi-objective fitness tailored to persona priorities.

        For Content Creator: Heavily weights CTR, Engagement Rate, and Reach per dollar.
            Fitness = w1 * CTR_norm + w2 * Eng_norm - w3 * CPC_penalty
        For Business: Heavily weights Conversion Rate, ROAS, and CAC efficiency.
            Fitness = w1 * CVR_norm + w2 * ROAS_norm - w3 * CAC_penalty
        """
        obs_map = {obs.candidate_id: obs for obs in observations} if observations else {}

        for candidate in candidates:
            obs = obs_map.get(candidate.id)
            metrics = candidate.metrics if obs is None else {
                "ctr": obs.ctr,
                "engagement_rate": obs.engagement_rate,
                "conversions": float(obs.conversions),
                "conversion_rate": obs.conversion_rate,
                "cpc": obs.cpc,
                "cac": obs.cac,
                "roas": obs.roas,
            }

            ctr = metrics.get("ctr", 0.03)
            eng = metrics.get("engagement_rate", 0.05)
            cvr = metrics.get("conversion_rate", 0.04)
            cpc = metrics.get("cpc", 1.50)
            cac = metrics.get("cac", 25.0)
            roas = metrics.get("roas", 2.0)

            if persona.type == PersonaType.CONTENT_CREATOR:
                # Goal: High attention, viral sharing, low impression cost
                raw_score = (
                    (ctr / 0.03) * 0.40
                    + (eng / 0.05) * 0.50
                    - min(1.0, (cpc / 3.0)) * 0.15
                    + (1.0 if persona.primary_goal == "reach" and eng > 0.06 else 0.0)
                )
            else:  # PersonaType.BUSINESS
                # Goal: Pipeline conversions, high ROAS, efficient CAC
                raw_score = (
                    (cvr / 0.04) * 0.35
                    + (roas / 2.5) * 0.45
                    - min(1.0, (cac / 40.0)) * 0.20
                    + (0.20 if roas >= 3.0 else 0.0)
                )

            # Keep fitness strictly positive and rounded for stability
            candidate.fitness_score = round(float(max(0.05, raw_score)), 4)

    def select_parent(self, population: List[Candidate]) -> Candidate:
        """Select a single parent candidate using Tournament Selection."""
        k = min(self.config.tournament_size, len(population))
        tournament_sample = random.sample(population, k)
        return max(tournament_sample, key=lambda c: c.fitness_score)

    def crossover(
        self,
        parent1: Candidate,
        parent2: Candidate,
        generation: int,
        idx: int,
    ) -> Candidate:
        """Perform genetic recombination between two high-performing parent candidates.

        Swaps text chromosomes (hook, CTA, visuals) and arithmetically blends budget parameters.
        """
        p1 = parent1.post
        p2 = parent2.post

        # Single-point / uniform feature crossover for content
        child_hook = p1.hook if random.random() < 0.5 else p2.hook
        child_caption = p1.caption_body if random.random() < 0.5 else p2.caption_body
        child_visual = p1.visual_asset_prompt if random.random() < 0.5 else p2.visual_asset_prompt
        child_cta = p1.call_to_action if random.random() < 0.5 else p2.call_to_action
        child_platform = p1.target_platform if random.random() < 0.5 else p2.target_platform

        # Combine and deduplicate hashtags
        merged_tags = list(dict.fromkeys(p1.hashtags + p2.hashtags))
        random.shuffle(merged_tags)
        child_hashtags = merged_tags[:5]

        # Arithmetic crossover for continuous budget parameters (alpha-blending)
        alpha = random.uniform(0.3, 0.7)
        blended_bid = alpha * parent1.budget.bid_aggressiveness + (1 - alpha) * parent2.budget.bid_aggressiveness
        blended_weight = alpha * parent1.budget.spend_weight + (1 - alpha) * parent2.budget.spend_weight

        child_chromosome = PostChromosome(
            hook=child_hook,
            caption_body=child_caption,
            visual_asset_prompt=child_visual,
            hashtags=child_hashtags,
            call_to_action=child_cta,
            target_platform=child_platform,
        )

        return Candidate(
            id=f"cand_g{generation}_{idx:02d}",
            generation_index=generation,
            post=child_chromosome,
            budget=BudgetAllocation(
                spend_weight=blended_weight,
                daily_budget=0.0,
                bid_aggressiveness=round(blended_bid, 2),
            ),
            parent_ids=[parent1.id, parent2.id],
            status="recombined",
        )

    def mutate(
        self,
        candidate: Candidate,
        validation_input: ValidationInput,
    ) -> Candidate:
        """Apply mutation operators with configurable mutation rate.

        Mutates hook angle, swaps CTA or platform, and perturbs budget bidding parameters.
        """
        post = candidate.post
        rate = self.config.mutation_rate
        niche = validation_input.niche
        trend = validation_input.trend_name
        kw = random.choice(validation_input.keywords) if validation_input.keywords else niche

        # 1. Hook Mutation
        if random.random() < rate:
            post.hook = random.choice(self.HOOK_TEMPLATES).format(niche=niche, trend_name=trend, keyword=kw)

        # 2. Visual Style Mutation
        if random.random() < rate:
            post.visual_asset_prompt = random.choice(self.VISUAL_PROMPT_TEMPLATES).format(
                niche=niche, trend_name=trend, keyword=kw
            )

        # 3. CTA Mutation
        if random.random() < rate:
            cta_pool = (
                self.CTA_CREATOR_TEMPLATES
                if validation_input.persona.type == PersonaType.CONTENT_CREATOR
                else self.CTA_BUSINESS_TEMPLATES
            )
            post.call_to_action = random.choice(cta_pool).format(niche=niche, trend_name=trend, keyword=kw)

        # 4. Platform Mutation (explores alternative social distribution)
        if random.random() < (rate * 0.75):
            available = [p for p in Platform if p != post.target_platform]
            post.target_platform = random.choice(available)

        # 5. Budget Bidding Mutation (Gaussian perturbation)
        if random.random() < rate:
            perturbation = np.random.normal(0.0, self.config.budget_exploration_noise)
            candidate.budget.bid_aggressiveness = float(
                np.clip(candidate.budget.bid_aggressiveness + perturbation, 0.4, 2.5)
            )

        return candidate

    def step(
        self,
        population: List[Candidate],
        validation_input: ValidationInput,
        generation_idx: int,
        uploaded_metrics: Optional[List[PerformanceObservation]] = None,
    ) -> GenerationSummary:
        """Advance evolutionary cycle by 1 generation: evaluate, select, evolve, and reallocate budget.

        Args:
            population: Current generation candidate pool.
            validation_input: Target trend, niche, and persona constraints.
            generation_idx: Target index of the new generation being generated.
            uploaded_metrics: Optional actual metrics from live network; if None, simulated.

        Returns:
            GenerationSummary describing the outcome and newly formed population.
        """
        # 1. Obtain performance observations (simulated or real)
        if uploaded_metrics:
            observations = uploaded_metrics
            for obs in observations:
                cand = next((c for c in population if c.id == obs.candidate_id), None)
                if cand:
                    cand.metrics = {
                        "ctr": obs.ctr,
                        "engagement_rate": obs.engagement_rate,
                        "conversions": float(obs.conversions),
                        "conversion_rate": obs.conversion_rate,
                        "cpc": obs.cpc,
                        "cac": obs.cac,
                        "roas": obs.roas,
                        "spend": obs.spend,
                    }
        else:
            observations = self.simulator.evaluate_population(population, validation_input)

        # 2. Fitness Evaluation
        self.evaluate_fitness(population, validation_input.persona, observations)

        # Sort population descending by fitness
        population.sort(key=lambda c: c.fitness_score, reverse=True)

        # 3. Elitism: Preserve top performers directly
        num_elites = max(1, int(len(population) * self.config.elitism_ratio))
        elites: List[Candidate] = []
        for i in range(num_elites):
            elite_copy = copy.deepcopy(population[i])
            elite_copy.status = "survived"
            elites.append(elite_copy)

        # 4. Elimination tracking
        eliminated_candidates = population[num_elites:]
        eliminated_ids = [c.id for c in eliminated_candidates]

        # 5. Breeding new generation via Crossover and Mutation
        new_population: List[Candidate] = list(elites)
        needed = self.config.population_size - len(new_population)

        for i in range(needed):
            parent1 = self.select_parent(population)
            parent2 = self.select_parent(population)
            child = self.crossover(parent1, parent2, generation=generation_idx, idx=len(new_population) + 1)
            child = self.mutate(child, validation_input)
            new_population.append(child)

        # 6. Evaluate performance of the newly formed generation
        new_observations = self.simulator.evaluate_population(new_population, validation_input)
        self.evaluate_fitness(new_population, validation_input.persona, new_observations)

        # 7. Dynamic Budget Reallocation across the new population
        self.reallocator.reallocate_budget(
            new_population,
            total_budget=validation_input.total_budget,
            method="softmax",
            temperature=0.75,
            exploration_ratio=0.20,
        )

        # 8. Summary metrics
        best_candidate = max(new_population, key=lambda c: c.fitness_score)
        avg_fitness = float(np.mean([c.fitness_score for c in new_population]))
        diversity = self.compute_diversity_score(new_population)

        return GenerationSummary(
            generation=generation_idx,
            best_candidate_id=best_candidate.id,
            best_fitness=best_candidate.fitness_score,
            avg_fitness=round(avg_fitness, 4),
            diversity_score=round(diversity, 4),
            total_budget_allocated=validation_input.total_budget,
            active_candidates=new_population,
            eliminated_candidate_ids=eliminated_ids,
        )

    def compute_diversity_score(self, population: List[Candidate]) -> float:
        """Compute structural population diversity based on unique platforms, hooks, and CTAs."""
        if not population:
            return 0.0

        n = len(population)
        unique_platforms = len(set(c.post.target_platform for c in population)) / min(4, n)
        unique_ctas = len(set(c.post.call_to_action for c in population)) / n
        unique_hooks = len(set(c.post.hook for c in population)) / n

        return float((unique_platforms + unique_ctas + unique_hooks) / 3.0)

    def get_pareto_front(self, candidates: List[Candidate]) -> List[Candidate]:
        """Extract Pareto-optimal candidates balancing Attention (CTR) vs Conversion (ROAS/Conversions)."""
        pareto: List[Candidate] = []
        for cand in candidates:
            cand_ctr = cand.metrics.get("ctr", cand.fitness_score)
            cand_roas = cand.metrics.get("roas", cand.fitness_score)
            dominated = False

            for other in candidates:
                if other.id == cand.id:
                    continue
                other_ctr = other.metrics.get("ctr", other.fitness_score)
                other_roas = other.metrics.get("roas", other.fitness_score)

                if (other_ctr >= cand_ctr and other_roas >= cand_roas) and (
                    other_ctr > cand_ctr or other_roas > cand_roas
                ):
                    dominated = True
                    break

            if not dominated:
                pareto.append(cand)
        return pareto or candidates[:3]
