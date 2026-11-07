"""Sanity, Invariant, and Integration Test Suite for Part 3: Optimization.

Validates:
1. Strict Budget Conservation (sum <= total across >= 5 generations with zero budget leaks)
2. Persona-Specific Multi-Objective Fitness (Creator vs Business priorities)
3. Reproduction Mechanics (Elitism preservation, Crossover gene-blending, Mutation validity)
4. Chromosome Integrity (No empty strings, valid platforms, non-negative budget)
5. FastAPI Endpoints (Init HTTP 200, Step with simulated & uploaded metrics, Status & Pareto, 422 & 404 errors)
"""

import copy
import pytest
from fastapi.testclient import TestClient

from budget import BudgetReallocator
from engine import EvolutionaryOptimizationEngine
from main import CAMPAIGNS, app
from schemas import (
    BudgetAllocation,
    Candidate,
    GAConfig,
    PerformanceObservation,
    Persona,
    PersonaType,
    Platform,
    PostChromosome,
    TrendElementGroup,
    ValidationHandoffBundle,
    ValidationInput,
    ValidationVerdict,
)
from simulator import MarketingPerformanceSimulator

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def creator_validation_input() -> ValidationInput:
    """Fixture for Content Creator persona."""
    return ValidationInput(
        trend_name="Lo-Fi AI Productivity Hacks",
        keywords=["AI hacks", "Productivity", "Workflow", "Notion AI"],
        niche="Personal Development",
        persona=Persona(
            type=PersonaType.CONTENT_CREATOR,
            tone="casual and inspiring",
            target_audience="Creators and Solopreneurs",
            risk_tolerance="high",
            primary_goal="engagement",
        ),
        recommended_formats=["short_form_video", "carousel"],
        total_budget=850.0,
    )


@pytest.fixture
def business_validation_input() -> ValidationInput:
    """Fixture for Business persona."""
    return ValidationInput(
        trend_name="Autonomous B2B Pipeline Agents",
        keywords=["Pipeline", "B2B SaaS", "LeadGen", "Outbound AI"],
        niche="Enterprise Software",
        persona=Persona(
            type=PersonaType.BUSINESS,
            tone="authoritative and analytical",
            target_audience="VP Sales & Marketing Directors",
            risk_tolerance="low",
            primary_goal="roas",
        ),
        recommended_formats=["high_contrast_post", "infographic"],
        total_budget=1500.0,
    )


# ---------------------------------------------------------------------------
# 1. Mathematical & Algorithmic Invariants
# ---------------------------------------------------------------------------

class TestMathematicalAndAlgorithmicInvariants:
    """Test mathematical and genetic invariants across generations."""

    def test_strict_budget_conservation_across_5_generations(self, business_validation_input):
        """Invariant: For any generation N, sum(candidate_budgets) <= total_budget with zero leaks."""
        total_budget = business_validation_input.total_budget
        config = GAConfig(population_size=10, elitism_ratio=0.20, mutation_rate=0.25)
        engine = EvolutionaryOptimizationEngine(config=config)

        # Gen 0
        population = engine.initialize_population(business_validation_input)
        gen0_sum = round(sum(c.budget.daily_budget for c in population), 2)
        assert gen0_sum <= total_budget, f"Gen 0 exceeded budget: {gen0_sum} > {total_budget}"
        assert abs(gen0_sum - total_budget) <= 0.01, f"Gen 0 budget leak: {total_budget - gen0_sum}"

        current_population = population
        for gen in range(1, 6):
            summary = engine.step(
                population=current_population,
                validation_input=business_validation_input,
                generation_idx=gen,
            )
            active_cands = [c for c in summary.active_candidates if c.status != "eliminated"]
            gen_sum = round(sum(c.budget.daily_budget for c in active_cands), 2)

            # Invariant 1: Strictly <= total_budget
            assert gen_sum <= total_budget + 1e-6, f"Gen {gen} budget violated: {gen_sum} > {total_budget}"
            # Invariant 2: Zero budget leak (must equal total_budget down to cent precision)
            assert abs(gen_sum - total_budget) <= 0.01, (
                f"Gen {gen} had budget leak: Allocated ${gen_sum:.2f} of ${total_budget:.2f}"
            )
            # Invariant 3: Reallocator built-in conservation verification check
            assert BudgetReallocator.verify_budget_conservation(summary.active_candidates, total_budget)

            current_population = summary.active_candidates

    @pytest.mark.parametrize("odd_budget", [333.33, 777.77, 1250.50, 99.99])
    @pytest.mark.parametrize("method", ["softmax", "ucb", "thompson"])
    def test_budget_reallocation_methods_and_odd_budgets(self, business_validation_input, odd_budget, method):
        """Invariant: Exact budget conservation under odd budget numbers and all allocation algorithms."""
        reallocator = BudgetReallocator()
        candidates = [
            Candidate(
                id=f"cand_{i}",
                generation_index=0,
                post=PostChromosome(
                    hook=f"Hook {i}",
                    caption_body=f"Body {i}",
                    visual_asset_prompt=f"Prompt {i}",
                    hashtags=["#tag"],
                    call_to_action=f"CTA {i}",
                    target_platform=Platform.LINKEDIN,
                ),
                budget=BudgetAllocation(spend_weight=1.0, daily_budget=odd_budget / 7),
                fitness_score=float(i + 1) * 0.4,
                metrics={"clicks": (i + 1) * 20, "conversions": i * 3},
                status="active" if i < 6 else "eliminated",
            )
            for i in range(7)
        ]

        reallocated = reallocator.reallocate_budget(
            candidates,
            total_budget=odd_budget,
            method=method,
        )

        active = [c for c in reallocated if c.status != "eliminated"]
        eliminated = [c for c in reallocated if c.status == "eliminated"]

        # Eliminated candidates must have zero budget
        for elim in eliminated:
            assert elim.budget.daily_budget == 0.0
            assert elim.budget.spend_weight == 0.0

        # Active sum must strictly equal odd_budget
        active_sum = round(sum(c.budget.daily_budget for c in active), 2)
        assert active_sum <= odd_budget + 1e-4
        assert abs(active_sum - odd_budget) <= 0.01

    def test_persona_specific_fitness_priorities(self):
        """Invariant: Creator fitness prioritizes CTR/Eng; Business fitness prioritizes ROAS/Conversions."""
        engine = EvolutionaryOptimizationEngine()

        creator_persona = Persona(
            type=PersonaType.CONTENT_CREATOR,
            tone="casual",
            target_audience="Creators",
            risk_tolerance="high",
            primary_goal="engagement",
        )
        business_persona = Persona(
            type=PersonaType.BUSINESS,
            tone="professional",
            target_audience="B2B Executives",
            risk_tolerance="low",
            primary_goal="roas",
        )

        dummy_post = PostChromosome(
            hook="Test Hook",
            caption_body="Test Body",
            visual_asset_prompt="Test Visual",
            hashtags=["#test"],
            call_to_action="Test CTA",
            target_platform=Platform.INSTAGRAM,
        )

        # Candidate A: Viral Creator Style (High CTR, High Eng, Low ROAS, Moderate CPC)
        cand_a_creator_tuned = Candidate(
            id="cand_a",
            generation_index=0,
            post=dummy_post,
            metrics={
                "ctr": 0.085,           # 8.5% CTR (very high)
                "engagement_rate": 0.16, # 16% Engagement (very high)
                "conversions": 1.0,
                "conversion_rate": 0.01,
                "cpc": 0.80,
                "cac": 60.0,
                "roas": 0.9,            # Low ROAS
            },
        )

        # Candidate B: Direct-Response Business Style (Low CTR, Low Eng, High ROAS, Efficient CAC)
        cand_b_business_tuned = Candidate(
            id="cand_b",
            generation_index=0,
            post=dummy_post,
            metrics={
                "ctr": 0.019,           # 1.9% CTR (low attention)
                "engagement_rate": 0.025, # 2.5% Engagement (low attention)
                "conversions": 25.0,
                "conversion_rate": 0.09, # 9% CVR
                "cpc": 3.80,
                "cac": 18.0,            # Efficient CAC
                "roas": 4.8,            # 4.8x ROAS (very high)
            },
        )

        # Test Creator Evaluation
        pop_creator = [copy.deepcopy(cand_a_creator_tuned), copy.deepcopy(cand_b_business_tuned)]
        engine.evaluate_fitness(pop_creator, creator_persona)
        score_a_for_creator = pop_creator[0].fitness_score
        score_b_for_creator = pop_creator[1].fitness_score

        assert score_a_for_creator > score_b_for_creator, (
            f"Content Creator persona must favor high engagement/CTR (A: {score_a_for_creator} vs B: {score_b_for_creator})"
        )

        # Test Business Evaluation
        pop_business = [copy.deepcopy(cand_a_creator_tuned), copy.deepcopy(cand_b_business_tuned)]
        engine.evaluate_fitness(pop_business, business_persona)
        score_a_for_business = pop_business[0].fitness_score
        score_b_for_business = pop_business[1].fitness_score

        assert score_b_for_business > score_a_for_business, (
            f"Business persona must favor high ROAS/Conversions (B: {score_b_for_business} vs A: {score_a_for_business})"
        )

    def test_reproduction_mechanics_elitism_crossover_mutation(self, creator_validation_input):
        """Invariant: Elitism preserves top candidates, crossover blends genes, mutation creates valid changes."""
        config = GAConfig(
            population_size=10,
            elitism_ratio=0.20,  # Exactly 2 elites
            mutation_rate=0.30,
            tournament_size=3,
        )
        engine = EvolutionaryOptimizationEngine(config=config)
        gen0 = engine.initialize_population(creator_validation_input)

        # Assign deliberate distinct fitness scores
        for i, c in enumerate(gen0):
            c.fitness_score = float(i + 1) * 1.5

        top_candidates = sorted(gen0, key=lambda c: c.fitness_score, reverse=True)[:2]
        top_ids = [c.id for c in top_candidates]
        top_fitnesses = [c.fitness_score for c in top_candidates]

        # Step to Generation 1
        summary_g1 = engine.step(gen0, creator_validation_input, generation_idx=1)
        gen1_cands = summary_g1.active_candidates

        # 1. Elitism verification: top candidates must survive
        survivors = [c for c in gen1_cands if c.status == "survived"]
        assert len(survivors) == 2, f"Expected 2 survived elites, got {len(survivors)}"
        survivor_ids = [c.id for c in survivors]
        assert set(survivor_ids) == set(top_ids), "Elites in Gen 1 do not match top performers from Gen 0"

        # 2. Crossover verification: offspring must record parents
        recombined = [c for c in gen1_cands if c.status == "recombined"]
        assert len(recombined) == 8, f"Expected 8 recombined offspring, got {len(recombined)}"
        for child in recombined:
            assert len(child.parent_ids) == 2, f"Child {child.id} missing 2 parent IDs"
            assert child.parent_ids[0].startswith("cand_")
            assert child.parent_ids[1].startswith("cand_")

        # 3. Test individual crossover blending directly
        p1 = gen0[0]
        p2 = gen0[1]
        child = engine.crossover(p1, p2, generation=1, idx=99)
        assert child.post.hook in (p1.post.hook, p2.post.hook)
        assert child.post.caption_body in (p1.post.caption_body, p2.post.caption_body)
        assert child.post.call_to_action in (p1.post.call_to_action, p2.post.call_to_action)
        assert child.post.target_platform in (p1.post.target_platform, p2.post.target_platform)

        # 4. Test mutation validity across 100 iterations
        for _ in range(100):
            sample_child = copy.deepcopy(child)
            mutated = engine.mutate(sample_child, creator_validation_input)
            assert mutated.post.hook.strip() != ""
            assert mutated.post.caption_body.strip() != ""
            assert mutated.post.visual_asset_prompt.strip() != ""
            assert mutated.post.call_to_action.strip() != ""
            assert mutated.post.target_platform in list(Platform)
            assert mutated.budget.bid_aggressiveness >= 0.4

    def test_chromosome_integrity_no_empty_fields(self, business_validation_input):
        """Invariant: All candidates across multiple generations have complete, valid chromosome fields."""
        config = GAConfig(population_size=12, mutation_rate=0.25)
        engine = EvolutionaryOptimizationEngine(config=config)
        population = engine.initialize_population(business_validation_input)

        for gen in range(1, 4):
            summary = engine.step(population, business_validation_input, generation_idx=gen)
            for c in summary.active_candidates:
                # String fields non-empty
                assert isinstance(c.post.hook, str) and len(c.post.hook.strip()) > 5
                assert isinstance(c.post.caption_body, str) and len(c.post.caption_body.strip()) > 15
                assert isinstance(c.post.visual_asset_prompt, str) and len(c.post.visual_asset_prompt.strip()) > 10
                assert isinstance(c.post.call_to_action, str) and len(c.post.call_to_action.strip()) > 5

                # Hashtags valid list
                assert isinstance(c.post.hashtags, list)
                assert len(c.post.hashtags) >= 1
                for tag in c.post.hashtags:
                    assert tag.startswith("#")

                # Platform enum
                assert c.post.target_platform in [Platform.INSTAGRAM, Platform.TIKTOK, Platform.LINKEDIN, Platform.X]

                # Budget ranges
                assert c.budget.daily_budget >= 0.0
                assert 0.0 <= c.budget.spend_weight <= 1.0
                assert 0.2 <= c.budget.bid_aggressiveness <= 3.0

            population = summary.active_candidates


# ---------------------------------------------------------------------------
# 2. FastAPI Route Testing
# ---------------------------------------------------------------------------

class TestFastAPIRoutes:
    """Test all REST API endpoints, response contracts, and error handlers."""

    def test_init_endpoint_with_direct_validation_input(self, creator_validation_input):
        """Test POST /api/v1/optimize/init with direct root payload returns HTTP 200."""
        payload = creator_validation_input.model_dump()
        response = client.post("/api/v1/optimize/init", json=payload)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "campaign_id" in data
        assert data["campaign_id"].startswith("camp_")

        gen0 = data["generation"]
        assert gen0["generation"] == 0
        assert len(gen0["active_candidates"]) == 12  # default pop size
        assert gen0["best_fitness"] > 0.0
        assert gen0["total_budget_allocated"] == creator_validation_input.total_budget

    def test_init_endpoint_with_wrapped_payload(self, business_validation_input):
        """Test POST /api/v1/optimize/init with wrapped validation_input and custom config."""
        payload = {
            "validation_input": business_validation_input.model_dump(),
            "config": {"population_size": 8, "mutation_rate": 0.15},
        }
        response = client.post("/api/v1/optimize/init", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["generation"]["active_candidates"]) == 8

    def test_step_endpoint_with_simulated_feedback(self, business_validation_input):
        """Test POST /api/v1/optimize/step using default simulated feedback."""
        # 1. Initialize campaign
        init_res = client.post("/api/v1/optimize/init", json=business_validation_input.model_dump())
        assert init_res.status_code == 200
        camp_id = init_res.json()["campaign_id"]

        # 2. Step with simulated metrics (uploaded_metrics=None)
        step_res = client.post("/api/v1/optimize/step", json={"campaign_id": camp_id})
        assert step_res.status_code == 200
        step_data = step_res.json()

        assert step_data["campaign_id"] == camp_id
        assert step_data["generation"]["generation"] == 1
        assert len(step_data["budget_reallocation"]) > 0

        # Verify budget reallocated sums to total_budget
        total_reallocated = round(sum(step_data["budget_reallocation"].values()), 2)
        assert abs(total_reallocated - business_validation_input.total_budget) <= 0.01

    def test_step_endpoint_with_uploaded_metrics(self, creator_validation_input):
        """Test POST /api/v1/optimize/step using custom uploaded metric observations."""
        init_res = client.post("/api/v1/optimize/init", json=creator_validation_input.model_dump())
        assert init_res.status_code == 200
        init_data = init_res.json()
        camp_id = init_data["campaign_id"]
        cands = init_data["generation"]["active_candidates"]

        # Mock custom ad network observations for these candidates
        mock_observations = [
            {
                "candidate_id": c["id"],
                "impressions": 5000,
                "clicks": 150 + i * 20,
                "ctr": 0.04 + (i * 0.005),
                "engagement_rate": 0.07 + (i * 0.01),
                "conversions": 5 + i,
                "conversion_rate": 0.05,
                "spend": c["budget"]["daily_budget"],
                "cpc": 1.20,
                "cac": 20.0,
                "roas": 2.2 + (i * 0.2),
            }
            for i, c in enumerate(cands)
        ]

        step_res = client.post(
            "/api/v1/optimize/step",
            json={"campaign_id": camp_id, "uploaded_metrics": mock_observations},
        )
        assert step_res.status_code == 200
        data = step_res.json()
        assert data["generation"]["generation"] == 1
        assert data["generation"]["best_fitness"] > 0.0

    def test_get_status_and_pareto_curve(self, business_validation_input):
        """Test GET /api/v1/optimize/status/{campaign_id} returns convergence and Pareto front."""
        init_res = client.post("/api/v1/optimize/init", json=business_validation_input.model_dump())
        camp_id = init_res.json()["campaign_id"]

        # Advance 2 steps
        client.post("/api/v1/optimize/step", json={"campaign_id": camp_id})
        client.post("/api/v1/optimize/step", json={"campaign_id": camp_id})

        # Fetch status
        status_res = client.get(f"/api/v1/optimize/status/{camp_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()

        assert status_data["campaign_id"] == camp_id
        assert status_data["trend_name"] == business_validation_input.trend_name
        assert status_data["niche"] == business_validation_input.niche
        assert status_data["current_generation"] == 2
        assert len(status_data["convergence_curve"]) == 3  # Gen 0, 1, 2
        assert len(status_data["pareto_optimal_candidates"]) >= 1
        assert len(status_data["history"]) == 3

    def test_error_handling_malformed_input_returns_422(self):
        """Test that malformed/invalid payloads return HTTP 422 Unprocessable Entity."""
        # 1. Completely empty payload
        res1 = client.post("/api/v1/optimize/init", json={})
        assert res1.status_code == 422

        # 2. Missing required 'persona'
        res2 = client.post(
            "/api/v1/optimize/init",
            json={"trend_name": "Test Trend", "niche": "Tech"},
        )
        assert res2.status_code == 422

        # 3. Invalid persona type (not 'content_creator' or 'business')
        res3 = client.post(
            "/api/v1/optimize/init",
            json={
                "trend_name": "Test Trend",
                "niche": "Tech",
                "persona": {"type": "invalid_type", "primary_goal": "reach"},
            },
        )
        assert res3.status_code == 422

        # 4. Negative total budget
        res4 = client.post(
            "/api/v1/optimize/init",
            json={
                "trend_name": "Test Trend",
                "niche": "Tech",
                "persona": {"type": "business"},
                "total_budget": -500.0,
            },
        )
        assert res4.status_code == 422

    def test_error_handling_nonexistent_campaign_returns_404(self):
        """Test that requests for non-existent campaigns return HTTP 404 Not Found."""
        res_step = client.post("/api/v1/optimize/step", json={"campaign_id": "camp_fake999"})
        assert res_step.status_code == 404
        assert "not found" in res_step.json()["detail"].lower()

        res_status = client.get("/api/v1/optimize/status/camp_fake999")
        assert res_status.status_code == 404
        assert "not found" in res_status.json()["detail"].lower()

    def test_web_dashboard_endpoints_serve_html(self):
        """Test that GET / and GET /ui serve the spacious Notion-style dashboard HTML."""
        res_root = client.get("/")
        assert res_root.status_code == 200
        assert "text/html" in res_root.headers.get("content-type", "")
        assert "m8chain Campaign Optimization Engine" in res_root.text
        assert "Creative Graveyard & Elimination Log" in res_root.text
        assert "Survived Creatives" in res_root.text
        assert "Pruned / Killed" in res_root.text
        assert "Selection Pressure" in res_root.text
        assert "max-width: 1280px" in res_root.text

        res_ui = client.get("/ui")
        assert res_ui.status_code == 200
        assert "text/html" in res_ui.headers.get("content-type", "")
        assert "m8chain Campaign Optimization Engine" in res_ui.text
        assert "Creative Graveyard & Elimination Log" in res_ui.text

    def test_metric_driven_seed_posts_evolution_cycle(self):
        """Test full evolutionary pipeline seeded directly from incoming client TikToks and ads."""
        seed_posts = [
            {
                "id": "tiktok_top_performer",
                "source": "tiktok",
                "hook": "Stop writing manual emails: here is our AI agent blueprint",
                "caption_body": "Automate outbound pipeline in 3 clicks.",
                "call_to_action": "Book demo in bio",
                "visual_asset_prompt": "Screen recording of automated calendar booking",
                "hashtags": ["#aiagent", "#b2b"],
                "target_platform": "TikTok",
                "metrics": {
                    "impressions": 75000,
                    "clicks": 3375,
                    "ctr": 0.045,
                    "engagement_rate": 0.10,
                    "conversions": 60,
                    "spend": 500.0,
                    "cpc": 0.15,
                    "cac": 8.33,
                    "roas": 6.2,
                },
            },
            {
                "id": "tiktok_mediocre",
                "source": "tiktok",
                "hook": "Why you need better marketing tools",
                "caption_body": "Tools help you scale.",
                "call_to_action": "Link in bio",
                "visual_asset_prompt": "Generic product shot",
                "hashtags": ["#tools"],
                "target_platform": "TikTok",
                "metrics": {
                    "impressions": 10000,
                    "clicks": 150,
                    "ctr": 0.015,
                    "engagement_rate": 0.02,
                    "conversions": 2,
                    "spend": 100.0,
                    "cpc": 0.67,
                    "cac": 50.0,
                    "roas": 1.1,
                },
            },
        ]

        payload = {
            "campaign_name": "High-ROAS Client Push",
            "niche": "MarTech SaaS",
            "persona": {
                "type": "business",
                "tone": "cutting-edge",
                "primary_goal": "roas",
            },
            "total_budget": 1000.0,
            "seed_posts": seed_posts,
            "config": {"population_size": 8, "elitism_ratio": 0.25},
        }

        # 1. Initialize
        init_res = client.post("/api/v1/optimize/init", json=payload)
        assert init_res.status_code == 200
        init_data = init_res.json()
        camp_id = init_data["campaign_id"]
        gen0 = init_data["generation"]

        # 2. Check Generation 0 Candidate Origins and Budget Allocation
        active = gen0["active_candidates"]
        assert len(active) == 8

        seed_cands = [c for c in active if c["origin"] == "client_seed"]
        assert len(seed_cands) >= 2

        # Winner seed gets significantly higher budget allocation than mediocre seed
        winner = next(c for c in active if c["original_seed_id"] == "tiktok_top_performer")
        mediocre = next(c for c in active if c["original_seed_id"] == "tiktok_mediocre")
        assert winner["fitness_score"] > mediocre["fitness_score"]
        assert winner["budget"]["daily_budget"] > mediocre["budget"]["daily_budget"]

        # Budget conservation
        assert BudgetReallocator.verify_budget_conservation(
            [Candidate(**c) for c in active],
            total_budget=1000.0,
        )

        # 3. Evolve to Generation 1
        step_res = client.post("/api/v1/optimize/step", json={"campaign_id": camp_id})
        assert step_res.status_code == 200
        step_data = step_res.json()
        gen1 = step_data["generation"]
        assert gen1["generation"] == 1

        # Elites preserved from winning seed
        survivors = [c for c in gen1["active_candidates"] if c["status"] == "survived"]
        assert len(survivors) >= 1
        assert any(c["original_seed_id"] == "tiktok_top_performer" for c in survivors)

    def test_validation_handoff_bundle_initialization(self):
        """Test POST /api/v1/optimize/init with official Step 2 ValidationHandoffBundle."""
        bundle_payload = {
            "campaign_id": "camp_val_step2_deepseek",
            "selected_trend": {
                "trend_id": "trend_deepseek_r1",
                "trend_name": "DeepSeek R1 Cost Arbitrage",
                "summary": "Engineering teams migrating high-volume queries to open weights for 90% savings",
                "keywords": ["DeepSeek R1", "Cost Arbitrage", "AI Reasoning", "Cloud Savings"],
                "recommended_hooks": [
                    "We cut our OpenAI bill by 87% in 48 hours without losing model reasoning power",
                    "Why tech leads are quietly moving enterprise agents to DeepSeek R1 this week",
                    "The $50,000 monthly AWS savings checklist for autonomous AI pipelines",
                ],
                "recommended_formats": ["short_form_video", "carousel"],
                "hashtags": ["#DeepSeek", "#EnterpriseAI", "#CloudSavings"],
                "supporting_posts": [],
            },
            "niche": "Enterprise AI & Cloud Infrastructure",
            "persona": {
                "type": "business",
                "tone": "authoritative and data-driven",
                "target_audience": "CTOs and VP Engineering",
                "risk_tolerance": "medium",
                "primary_goal": "roas",
            },
            "verdict": {
                "verdict_status": "approved",
                "suitability_score": 96.5,
                "reasoning": "High-intent B2B audience seeking immediate cloud margin optimization.",
                "strategic_angle": "Focus on audited invoice screenshots and latency benchmarks",
            },
            "total_budget": 1500.0,
        }

        # 1. Initialize with pure ValidationHandoffBundle
        init_res = client.post("/api/v1/optimize/init", json=bundle_payload)
        assert init_res.status_code == 200
        init_data = init_res.json()
        camp_id = init_data["campaign_id"]
        gen0 = init_data["generation"]
        candidates = gen0["active_candidates"]

        assert len(candidates) == 12  # default population size
        assert gen0["generation"] == 0

        # Verify recommended hooks are utilized in candidate posts
        rec_hooks = bundle_payload["selected_trend"]["recommended_hooks"]
        candidate_hooks = [c["post"]["hook"] for c in candidates]
        assert any(h in rec_hooks for h in candidate_hooks), "At least one candidate must use a recommended hook"

        # Verify strategic angle is incorporated in visual asset prompts
        strategic_angle = bundle_payload["verdict"]["strategic_angle"]
        visual_prompts = [c["post"]["visual_asset_prompt"] for c in candidates]
        assert any(strategic_angle in vp for vp in visual_prompts), "Strategic angle must appear in visual prompts"

        # Verify budget conservation in Gen 0
        total_allocated_gen0 = sum(c["budget"]["daily_budget"] for c in candidates)
        assert total_allocated_gen0 <= 1500.0
        assert abs(total_allocated_gen0 - 1500.0) <= 0.01

        # 2. Step to Generation 1
        step_res = client.post("/api/v1/optimize/step", json={"campaign_id": camp_id})
        assert step_res.status_code == 200
        step_data = step_res.json()
        gen1 = step_data["generation"]
        assert gen1["generation"] == 1
        gen1_cands = gen1["active_candidates"]

        # Budget conservation in Gen 1
        total_allocated_gen1 = sum(c["budget"]["daily_budget"] for c in gen1_cands)
        assert total_allocated_gen1 <= 1500.0
        assert abs(total_allocated_gen1 - 1500.0) <= 0.01

        # 3. Status check confirms trend and niche metadata
        status_res = client.get(f"/api/v1/optimize/status/{camp_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["trend_name"] == "DeepSeek R1 Cost Arbitrage"
        assert status_data["niche"] == "Enterprise AI & Cloud Infrastructure"
        assert len(status_data["pareto_optimal_candidates"]) >= 1

    def test_wrapped_validation_handoff_with_supporting_posts(self):
        """Test POST /api/v1/optimize/init with wrapped validation_handoff and supporting posts."""
        wrapped_payload = {
            "validation_handoff": {
                "selected_trend": {
                    "trend_id": "trend_creator_burnout",
                    "trend_name": "Solopreneur Burnout Confessions",
                    "summary": "Founders sharing raw vulnerability about work hours",
                    "keywords": ["Burnout", "Solopreneur", "Work Life Balance"],
                    "recommended_hooks": ["I worked 80 hours a week for 2 years until this happened"],
                    "recommended_formats": ["short_form_video"],
                    "hashtags": ["#burnout", "#solopreneur"],
                    "supporting_posts": [
                        {
                            "id": "tiktok_burnout_viral",
                            "source": "tiktok",
                            "hook": "Why I deleted my 100k follower account",
                            "caption_body": "Mental health over metrics.",
                            "call_to_action": "Read full essay in bio",
                            "visual_asset_prompt": "Talking head, natural sunlight",
                            "hashtags": ["#burnout"],
                            "target_platform": "TikTok",
                            "metrics": {
                                "impressions": 100000,
                                "clicks": 8000,
                                "ctr": 0.08,
                                "engagement_rate": 0.15,
                                "conversions": 120,
                                "spend": 300.0,
                                "cpc": 0.04,
                                "cac": 2.50,
                                "roas": 8.0,
                            },
                        }
                    ],
                },
                "niche": "Creator Economy",
                "persona": {
                    "type": "content_creator",
                    "tone": "raw and candid",
                    "target_audience": "Digital creators",
                    "primary_goal": "engagement",
                },
                "verdict": {
                    "verdict_status": "strong_match",
                    "suitability_score": 98.0,
                    "reasoning": "Direct alignment with creator vulnerability trends.",
                    "strategic_angle": "Use raw iPhone selfie video style",
                },
                "total_budget": 800.0,
            },
            "config": {"population_size": 6, "mutation_rate": 0.20},
        }

        res = client.post("/api/v1/optimize/init", json=wrapped_payload)
        assert res.status_code == 200
        data = res.json()
        cands = data["generation"]["active_candidates"]
        assert len(cands) == 6

        # Supporting post should be ingested as seed candidate
        seed_cands = [c for c in cands if c["origin"] == "client_seed"]
        assert len(seed_cands) >= 1
        assert seed_cands[0]["original_seed_id"] == "tiktok_burnout_viral"

        # Check total budget
        total_alloc = sum(c["budget"]["daily_budget"] for c in cands)
        assert abs(total_alloc - 800.0) <= 0.01
