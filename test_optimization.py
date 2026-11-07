"""Unit and integration test suite for m8chain Evolutionary Optimization Engine."""

import pytest
from fastapi.testclient import TestClient

from budget import BudgetReallocator
from engine import EvolutionaryOptimizationEngine
from main import app
from schemas import (
    GAConfig,
    InputAdOrPost,
    Persona,
    PersonaType,
    Platform,
    PostMetrics,
    ValidationInput,
)
from simulator import MarketingPerformanceSimulator

client = TestClient(app)


@pytest.fixture
def sample_validation_input() -> ValidationInput:
    """Fixture providing a standard ValidationInput contract."""
    return ValidationInput(
        trend_name="AI Agent Driven Marketing Workflows",
        keywords=["AI Agent", "Workflow", "Automation", "ROAS"],
        niche="B2B SaaS",
        persona=Persona(
            type=PersonaType.BUSINESS,
            tone="authoritative",
            target_audience="Founders and Growth Directors",
            risk_tolerance="medium",
            primary_goal="roas",
        ),
        recommended_formats=["short_form_video", "carousel"],
        total_budget=1000.0,
    )


def test_health_endpoint():
    """Verify health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "m8chain-optimization-engine"


def test_population_initialization(sample_validation_input):
    """Verify Generation 0 initialization and candidate chromosome structure."""
    config = GAConfig(population_size=8)
    engine = EvolutionaryOptimizationEngine(config=config)
    population = engine.initialize_population(sample_validation_input)

    assert len(population) == 8
    for cand in population:
        assert cand.generation_index == 0
        assert cand.post.hook
        assert cand.post.caption_body
        assert cand.post.call_to_action
        assert cand.post.target_platform in list(Platform)
        assert cand.budget.daily_budget > 0.0

    # Test budget conservation in Gen 0
    total_allocated = sum(c.budget.daily_budget for c in population)
    assert abs(total_allocated - sample_validation_input.total_budget) < 0.50


def test_budget_reallocator_conservation(sample_validation_input):
    """Verify strict budget conservation across reallocation algorithms."""
    config = GAConfig(population_size=6)
    engine = EvolutionaryOptimizationEngine(config=config)
    population = engine.initialize_population(sample_validation_input)

    # Assign dummy fitness
    for idx, c in enumerate(population):
        c.fitness_score = float(idx + 1) * 0.5

    reallocator = BudgetReallocator()
    reallocated = reallocator.reallocate_budget(
        population,
        total_budget=sample_validation_input.total_budget,
        method="softmax",
    )

    total_allocated = sum(c.budget.daily_budget for c in reallocated)
    assert abs(total_allocated - sample_validation_input.total_budget) < 0.50

    # Ensure higher fitness candidate gets higher daily budget
    sorted_by_fit = sorted(reallocated, key=lambda c: c.fitness_score, reverse=True)
    assert sorted_by_fit[0].budget.daily_budget > sorted_by_fit[-1].budget.daily_budget


def test_simulator_feedback(sample_validation_input):
    """Verify simulator generates valid realistic metrics."""
    config = GAConfig(population_size=4)
    engine = EvolutionaryOptimizationEngine(config=config)
    population = engine.initialize_population(sample_validation_input)

    simulator = MarketingPerformanceSimulator(random_seed=123)
    observations = simulator.evaluate_population(population, sample_validation_input)

    assert len(observations) == 4
    for obs in observations:
        assert obs.impressions > 0
        assert obs.clicks > 0
        assert 0.0 < obs.ctr < 1.0
        assert 0.0 < obs.engagement_rate < 1.0
        assert obs.spend > 0.0
        assert obs.cpc > 0.0


def test_genetic_step(sample_validation_input):
    """Verify one generation step produces valid offspring and advances index."""
    config = GAConfig(population_size=6, elitism_ratio=0.33)
    engine = EvolutionaryOptimizationEngine(config=config)
    gen0 = engine.initialize_population(sample_validation_input)

    gen1_summary = engine.step(gen0, sample_validation_input, generation_idx=1)

    assert gen1_summary.generation == 1
    assert len(gen1_summary.active_candidates) == 6
    assert gen1_summary.best_fitness > 0.0
    assert abs(gen1_summary.total_budget_allocated - sample_validation_input.total_budget) < 0.50

    # Check that surviving elites retain status
    survivors = [c for c in gen1_summary.active_candidates if c.status == "survived"]
    assert len(survivors) >= 1


def test_fastapi_lifecycle_workflow(sample_validation_input):
    """Verify full end-to-end API lifecycle: init -> step -> status."""
    # 1. Init
    init_payload = {
        "validation_input": sample_validation_input.model_dump(),
        "config": {"population_size": 6, "mutation_rate": 0.20},
    }
    init_res = client.post("/api/v1/optimize/init", json=init_payload)
    assert init_res.status_code == 200
    init_data = init_res.json()
    campaign_id = init_data["campaign_id"]
    assert campaign_id.startswith("camp_")
    assert init_data["generation"]["generation"] == 0

    # 2. Step
    step_payload = {"campaign_id": campaign_id}
    step_res = client.post("/api/v1/optimize/step", json=step_payload)
    assert step_res.status_code == 200
    step_data = step_res.json()
    assert step_data["generation"]["generation"] == 1
    assert len(step_data["budget_reallocation"]) == 6

    # 3. Status
    status_res = client.get(f"/api/v1/optimize/status/{campaign_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["current_generation"] == 1
    assert len(status_data["convergence_curve"]) == 2  # Gen 0 and Gen 1
    assert len(status_data["pareto_optimal_candidates"]) > 0


def test_client_seed_posts_initialization():
    """Verify initialization directly from incoming client TikToks and ads with real metrics."""
    seed_posts = [
        {
            "id": "tiktok_client_01",
            "source": "tiktok",
            "hook": "How our AI agents booked 50 demo calls this week",
            "caption_body": "Full breakdown of our multi-agent automation funnel.",
            "call_to_action": "Comment DEMO for full blueprint",
            "visual_asset_prompt": "Vertical screen capture of analytics dashboard",
            "hashtags": ["#marketing", "#aiagent"],
            "target_platform": "TikTok",
            "metrics": {
                "impressions": 50000,
                "clicks": 2500,
                "ctr": 0.05,
                "engagement_rate": 0.12,
                "conversions": 45,
                "spend": 400.0,
                "cpc": 0.16,
                "cac": 8.89,
                "roas": 5.5,
            },
        },
        {
            "id": "ad_meta_02",
            "source": "ad_meta",
            "hook": "Why traditional marketing agencies are becoming obsolete",
            "caption_body": "Cut your CAC in half using automated genetic ad evolution.",
            "call_to_action": "Claim free audit",
            "visual_asset_prompt": "Editorial studio layout with clean contrast",
            "hashtags": ["#growth", "#martech"],
            "target_platform": "Instagram",
            "metrics": {
                "impressions": 20000,
                "clicks": 600,
                "ctr": 0.03,
                "engagement_rate": 0.05,
                "conversions": 15,
                "spend": 250.0,
                "cpc": 0.42,
                "cac": 16.67,
                "roas": 3.2,
            },
        },
    ]

    payload = {
        "campaign_name": "Q4 TikTok Scaling",
        "niche": "B2B MarTech",
        "persona": {
            "type": "business",
            "tone": "authoritative",
            "primary_goal": "roas",
        },
        "total_budget": 1200.0,
        "seed_posts": seed_posts,
    }

    res = client.post("/api/v1/optimize/init", json=payload)
    assert res.status_code == 200
    data = res.json()
    cands = data["generation"]["active_candidates"]

    # Verify seed candidates exist
    seed_cands = [c for c in cands if c["origin"] == "client_seed"]
    assert len(seed_cands) >= 2
    top_seed = seed_cands[0]
    assert top_seed["original_seed_id"] in ("tiktok_client_01", "ad_meta_02")

    # High-performing seed gets higher budget
    assert seed_cands[0]["budget"]["daily_budget"] > 0.0
    total_allocated = sum(c["budget"]["daily_budget"] for c in cands)
    assert abs(total_allocated - 1200.0) <= 0.01
