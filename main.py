"""FastAPI service exposing RESTful endpoints for the n8chain evolutionary engine.

Provides endpoints to initialize campaigns from Part 2 validation contracts,
step generational evolution with real or simulated telemetry, and query
convergence curves and Pareto-optimal post candidates.
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from budget import BudgetReallocator
from engine import EvolutionaryOptimizationEngine
from schemas import (
    CampaignStatusResponse,
    Candidate,
    GAConfig,
    GenerationSummary,
    InitCampaignRequest,
    InitCampaignResponse,
    PerformanceObservation,
    StepCampaignRequest,
    StepCampaignResponse,
    ValidationInput,
)
from simulator import MarketingPerformanceSimulator

app = FastAPI(
    title="n8chain Evolutionary Optimization API",
    version="1.0.0",
    description="Evolutionary Programming & Genetic Algorithm service for marketing content & budget optimization.",
)

# Enable CORS for Next.js frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CampaignState(BaseModel):
    """In-memory state container for an active campaign."""
    campaign_id: str
    validation_input: ValidationInput
    config: GAConfig
    current_generation: int = 0
    population: List[Candidate] = Field(default_factory=list)
    history: List[GenerationSummary] = Field(default_factory=list)
    convergence_curve: List[Dict[str, float]] = Field(default_factory=list)


# In-memory storage for hackathon runtime
CAMPAIGNS: Dict[str, CampaignState] = {}


def get_engine(config: Optional[GAConfig] = None) -> EvolutionaryOptimizationEngine:
    """Factory creating an engine instance."""
    return EvolutionaryOptimizationEngine(config=config)


@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
@app.get("/ui", response_class=HTMLResponse, tags=["Web UI"])
def get_dashboard() -> HTMLResponse:
    """Serve the Notion-style interactive Web UI dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>n8chain Optimization UI Not Found</h1>", status_code=404)


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """Health check endpoint confirming API service readiness."""
    return {
        "status": "online",
        "service": "n8chain-optimization-engine",
        "version": "1.0.0",
        "stage": "Part 3: Optimization",
    }


@app.post(
    "/api/v1/optimize/init",
    response_model=InitCampaignResponse,
    status_code=status.HTTP_200_OK,
    tags=["Optimization"],
)
def initialize_campaign(request: InitCampaignRequest) -> InitCampaignResponse:
    """Initialize Generation 0 from Part 2 ValidationInput contract.

    Seeds candidate creatives across platforms and equally distributes total budget.
    """
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    ga_config = request.config or GAConfig()
    engine = get_engine(ga_config)

    # 1. Initialize candidate population
    gen0_population = engine.initialize_population(request.validation_input)

    # 2. Evaluate Generation 0 baseline with simulated feedback
    simulator = MarketingPerformanceSimulator()
    obs = simulator.evaluate_population(gen0_population, request.validation_input)
    engine.evaluate_fitness(gen0_population, request.validation_input.persona, obs)

    # 3. Create Generation 0 summary
    best_candidate = max(gen0_population, key=lambda c: c.fitness_score)
    avg_fitness = float(sum(c.fitness_score for c in gen0_population) / len(gen0_population))
    diversity = engine.compute_diversity_score(gen0_population)

    gen0_summary = GenerationSummary(
        generation=0,
        best_candidate_id=best_candidate.id,
        best_fitness=best_candidate.fitness_score,
        avg_fitness=round(avg_fitness, 4),
        diversity_score=round(diversity, 4),
        total_budget_allocated=request.validation_input.total_budget,
        active_candidates=gen0_population,
        eliminated_candidate_ids=[],
    )

    # 4. Persist state
    state = CampaignState(
        campaign_id=campaign_id,
        validation_input=request.validation_input,
        config=ga_config,
        current_generation=0,
        population=gen0_population,
        history=[gen0_summary],
        convergence_curve=[
            {
                "generation": 0,
                "best_fitness": gen0_summary.best_fitness,
                "avg_fitness": gen0_summary.avg_fitness,
            }
        ],
    )
    CAMPAIGNS[campaign_id] = state

    return InitCampaignResponse(
        campaign_id=campaign_id,
        generation=gen0_summary,
        message=f"Initialized campaign '{request.validation_input.trend_name}' with {len(gen0_population)} candidates.",
    )


@app.post(
    "/api/v1/optimize/step",
    response_model=StepCampaignResponse,
    tags=["Optimization"],
)
def step_evolution(request: StepCampaignRequest) -> StepCampaignResponse:
    """Advance campaign to the next generation.

    Eliminates weak candidates, breeds top performers, perturbs budget allocations,
    and shifts spend toward winners using either live ad metrics or simulated feedback.
    """
    state = CAMPAIGNS.get(request.campaign_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{request.campaign_id}' not found.",
        )

    engine = get_engine(state.config)
    next_gen_idx = state.current_generation + 1

    # Advance one generation
    gen_summary = engine.step(
        population=state.population,
        validation_input=state.validation_input,
        generation_idx=next_gen_idx,
        uploaded_metrics=request.uploaded_metrics,
    )

    # Update state
    state.current_generation = next_gen_idx
    state.population = gen_summary.active_candidates
    state.history.append(gen_summary)
    state.convergence_curve.append(
        {
            "generation": next_gen_idx,
            "best_fitness": gen_summary.best_fitness,
            "avg_fitness": gen_summary.avg_fitness,
        }
    )

    budget_breakdown = BudgetReallocator.get_budget_breakdown(state.population)

    return StepCampaignResponse(
        campaign_id=state.campaign_id,
        generation=gen_summary,
        budget_reallocation=budget_breakdown,
        message=f"Successfully evolved to Generation {next_gen_idx}. Best fitness: {gen_summary.best_fitness}",
    )


@app.get(
    "/api/v1/optimize/status/{campaign_id}",
    response_model=CampaignStatusResponse,
    tags=["Optimization"],
)
def get_campaign_status(campaign_id: str) -> CampaignStatusResponse:
    """Retrieve campaign convergence history, Pareto-optimal creatives, and budget distribution."""
    state = CAMPAIGNS.get(campaign_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )

    engine = get_engine(state.config)
    pareto_candidates = engine.get_pareto_front(state.population)
    budget_breakdown = BudgetReallocator.get_budget_breakdown(state.population)

    return CampaignStatusResponse(
        campaign_id=state.campaign_id,
        trend_name=state.validation_input.trend_name,
        niche=state.validation_input.niche,
        persona_type=state.validation_input.persona.type.value,
        current_generation=state.current_generation,
        convergence_curve=state.convergence_curve,
        pareto_optimal_candidates=pareto_candidates,
        current_budget_breakdown=budget_breakdown,
        history=state.history,
    )
