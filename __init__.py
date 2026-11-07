"""n8chain Evolutionary Optimization Package."""

try:
    from .schemas import (
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
    from .engine import EvolutionaryOptimizationEngine
    from .budget import BudgetReallocator
    from .simulator import MarketingPerformanceSimulator
except ImportError:
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
    from engine import EvolutionaryOptimizationEngine
    from budget import BudgetReallocator
    from simulator import MarketingPerformanceSimulator

__all__ = [
    "BudgetAllocation",
    "Candidate",
    "GAConfig",
    "GenerationSummary",
    "PerformanceObservation",
    "Persona",
    "PersonaType",
    "Platform",
    "PostChromosome",
    "ValidationInput",
    "EvolutionaryOptimizationEngine",
    "BudgetReallocator",
    "MarketingPerformanceSimulator",
]
