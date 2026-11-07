"""m8chain Evolutionary Optimization Package."""

try:
    from .schemas import (
        BudgetAllocation,
        CampaignInitPayload,
        Candidate,
        GAConfig,
        GenerationSummary,
        InputAdOrPost,
        PerformanceObservation,
        Persona,
        PersonaType,
        Platform,
        PostChromosome,
        PostMetrics,
        ValidationInput,
    )
    from .engine import EvolutionaryOptimizationEngine
    from .budget import BudgetReallocator
    from .simulator import MarketingPerformanceSimulator
except ImportError:
    from schemas import (
        BudgetAllocation,
        CampaignInitPayload,
        Candidate,
        GAConfig,
        GenerationSummary,
        InputAdOrPost,
        PerformanceObservation,
        Persona,
        PersonaType,
        Platform,
        PostChromosome,
        PostMetrics,
        ValidationInput,
    )
    from engine import EvolutionaryOptimizationEngine
    from budget import BudgetReallocator
    from simulator import MarketingPerformanceSimulator

__all__ = [
    "BudgetAllocation",
    "CampaignInitPayload",
    "Candidate",
    "GAConfig",
    "GenerationSummary",
    "InputAdOrPost",
    "PerformanceObservation",
    "Persona",
    "PersonaType",
    "Platform",
    "PostChromosome",
    "PostMetrics",
    "ValidationInput",
    "EvolutionaryOptimizationEngine",
    "BudgetReallocator",
    "MarketingPerformanceSimulator",
]
