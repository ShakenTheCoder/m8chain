#!/usr/bin/env python3
"""End-to-end demonstration and verification CLI script for n8chain Evolutionary Optimization.

Simulates a full multi-generation campaign run, showcasing post chromosome evolution,
elitism, tournament selection, stochastic simulation feedback, and dynamic budget reallocation
with rich terminal diagnostics.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from budget import BudgetReallocator
from engine import EvolutionaryOptimizationEngine
from schemas import (
    GAConfig,
    GenerationSummary,
    Persona,
    PersonaType,
    Platform,
    ValidationInput,
)
from simulator import MarketingPerformanceSimulator

console = Console()


def render_banner() -> None:
    """Print branded ASCII banner for n8chain."""
    banner_text = Text()
    banner_text.append("⚡ n8chain — Part 3: Evolutionary Optimization Engine\n", style="bold cyan")
    banner_text.append("   Genetic Algorithm & Dynamic Budget Allocation Pipeline (Hackathon Demo)", style="dim white")
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def display_generation_summary(
    summary: GenerationSummary,
    total_budget: float,
) -> None:
    """Display rich tables for a single generation's active candidates and budget breakdown."""
    console.print(
        f"\n[bold yellow]▶ Generation {summary.generation}[/bold yellow] "
        f"— [green]Best Fitness: {summary.best_fitness:.4f}[/green] | "
        f"[cyan]Avg Fitness: {summary.avg_fitness:.4f}[/cyan] | "
        f"[magenta]Diversity: {summary.diversity_score:.2f}[/magenta] | "
        f"[white]Eliminated: {len(summary.eliminated_candidate_ids)} candidates[/white]"
    )

    table = Table(
        title=f"Generation {summary.generation} Candidate Allocations & Creatives",
        box=box.ROUNDED,
        header_style="bold magenta",
        expand=True,
    )
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Platform", style="green", width=10)
    table.add_column("Status", style="bold", width=11)
    table.add_column("Fitness", justify="right", style="yellow", width=9)
    table.add_column("Daily Spend", justify="right", style="green", width=12)
    table.add_column("Bid Mult", justify="right", style="white", width=9)
    table.add_column("Hook Angle / Headline", style="white", overflow="ellipsis")
    table.add_column("CTR / ROAS", justify="right", style="blue", width=14)

    # Sort candidates by fitness descending
    sorted_candidates = sorted(summary.active_candidates, key=lambda c: c.fitness_score, reverse=True)

    for c in sorted_candidates:
        status_style = "green" if c.status == "survived" else ("yellow" if c.status == "recombined" else "cyan")
        metrics = c.metrics
        ctr_val = metrics.get("ctr", 0.0)
        roas_val = metrics.get("roas", 0.0)
        perf_str = f"{ctr_val*100:.1f}% / {roas_val:.1f}x"

        table.add_row(
            c.id,
            c.post.target_platform.value,
            f"[{status_style}]{c.status}[/{status_style}]",
            f"{c.fitness_score:.3f}",
            f"${c.budget.daily_budget:.2f}",
            f"{c.budget.bid_aggressiveness:.2f}x",
            c.post.hook[:50] + "..." if len(c.post.hook) > 50 else c.post.hook,
            perf_str,
        )

    console.print(table)

    # Conservation verification check
    is_conserved = BudgetReallocator.verify_budget_conservation(summary.active_candidates, total_budget)
    allocated_sum = sum(c.budget.daily_budget for c in summary.active_candidates)
    if is_conserved:
        console.print(
            f"  [bold green]✓ Budget Conservation Verified:[/bold green] "
            f"Sum(${allocated_sum:.2f}) == Target(${total_budget:.2f})"
        )
    else:
        console.print(
            f"  [bold red]✗ Budget Conservation Warning:[/bold red] "
            f"Sum(${allocated_sum:.2f}) != Target(${total_budget:.2f})"
        )


def display_winning_creative(candidate) -> None:
    """Print the final top-performing evolved post creative."""
    post = candidate.post
    win_text = Text()
    win_text.append(f"Candidate ID: {candidate.id} (Fitness: {candidate.fitness_score:.4f})\n", style="bold green")
    win_text.append(f"Target Platform: {post.target_platform.value}\n", style="bold cyan")
    win_text.append(f"Allocated Daily Budget: ${candidate.budget.daily_budget:.2f} (Bid: {candidate.budget.bid_aggressiveness:.2f}x)\n\n", style="bold yellow")
    win_text.append("🎯 Hook:\n", style="bold magenta")
    win_text.append(f"\"{post.hook}\"\n\n", style="white")
    win_text.append("📝 Caption Body:\n", style="bold magenta")
    win_text.append(f"{post.caption_body}\n\n", style="dim white")
    win_text.append("🎨 Visual Asset Prompt (Adobe Express / Firefly):\n", style="bold magenta")
    win_text.append(f"{post.visual_asset_prompt}\n\n", style="italic cyan")
    win_text.append("🏷️ Hashtags:\n", style="bold magenta")
    win_text.append(f"{' '.join(post.hashtags)}\n\n", style="blue")
    win_text.append("📣 Call to Action:\n", style="bold magenta")
    win_text.append(f"\"{post.call_to_action}\"\n", style="bold white")

    console.print(Panel(win_text, title="🏆 Champion Evolved Post Creative", border_style="gold1", expand=False))


def display_convergence_history(history: List[GenerationSummary]) -> None:
    """Print a concise convergence telemetry table across all generations."""
    table = Table(
        title="📈 Campaign Convergence & Evolution Progression",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
    )
    table.add_column("Gen", justify="center", style="yellow")
    table.add_column("Best Fitness", justify="right", style="green")
    table.add_column("Avg Fitness", justify="right", style="cyan")
    table.add_column("Diversity", justify="right", style="magenta")
    table.add_column("Top Performer ID", style="white")
    table.add_column("Spend on Top Performer", justify="right", style="green")

    for summary in history:
        best_cand = next(c for c in summary.active_candidates if c.id == summary.best_candidate_id)
        table.add_row(
            str(summary.generation),
            f"{summary.best_fitness:.4f}",
            f"{summary.avg_fitness:.4f}",
            f"{summary.diversity_score:.2f}",
            summary.best_candidate_id,
            f"${best_cand.budget.daily_budget:.2f}",
        )

    console.print(table)


def run_demo(
    generations: int = 5,
    population_size: int = 10,
    total_budget: float = 1200.0,
    persona_type: str = "business",
) -> None:
    """Execute full end-to-end simulation run."""
    render_banner()

    # Step 1: Mock input representing Part 2 (Validation) handoff
    persona_enum = PersonaType.BUSINESS if persona_type == "business" else PersonaType.CONTENT_CREATOR
    validation_input = ValidationInput(
        trend_name="Autonomous Multi-Agent Marketing Workflows",
        keywords=["AI Agent", "Workflow Automation", "Ad Optimization", "Content Engine"],
        niche="B2B MarTech & SaaS",
        persona=Persona(
            type=persona_enum,
            tone="authoritative and cutting-edge",
            target_audience="VP of Growth, Performance Marketers, and Tech Founders",
            risk_tolerance="medium",
            primary_goal="roas" if persona_enum == PersonaType.BUSINESS else "engagement",
        ),
        recommended_formats=["short_form_video", "carousel_infographic", "high_contrast_post"],
        total_budget=total_budget,
    )

    console.print(
        Panel(
            f"[bold]Selected Trend:[/bold] {validation_input.trend_name}\n"
            f"[bold]Target Niche:[/bold] {validation_input.niche}\n"
            f"[bold]Persona:[/bold] {validation_input.persona.type.value.upper()} (Goal: {validation_input.persona.primary_goal})\n"
            f"[bold]Total Budget:[/bold] ${validation_input.total_budget:,.2f} USD\n"
            f"[bold]Evolution Hyperparameters:[/bold] Pop={population_size}, Generations={generations}, Elitism=20%",
            title="📥 Part 2 (Validation) → Part 3 (Optimization) Handoff Contract",
            border_style="blue",
            expand=False,
        )
    )

    # Initialize Engine & Simulator
    config = GAConfig(
        population_size=population_size,
        mutation_rate=0.20,
        elitism_ratio=0.20,
        tournament_size=3,
        crossover_rate=0.80,
    )
    simulator = MarketingPerformanceSimulator(random_seed=42)
    engine = EvolutionaryOptimizationEngine(config=config, simulator=simulator)

    history: List[GenerationSummary] = []

    # --- Generation 0 ---
    with console.status("[bold green]Seeding Generation 0 population & calculating baseline metrics..."):
        population = engine.initialize_population(validation_input)
        obs0 = simulator.evaluate_population(population, validation_input)
        engine.evaluate_fitness(population, validation_input.persona, obs0)

        best_cand0 = max(population, key=lambda c: c.fitness_score)
        avg_fit0 = float(sum(c.fitness_score for c in population) / len(population))
        gen0_summary = GenerationSummary(
            generation=0,
            best_candidate_id=best_cand0.id,
            best_fitness=best_cand0.fitness_score,
            avg_fitness=round(avg_fit0, 4),
            diversity_score=round(engine.compute_diversity_score(population), 4),
            total_budget_allocated=total_budget,
            active_candidates=population,
            eliminated_candidate_ids=[],
        )
        history.append(gen0_summary)

    display_generation_summary(gen0_summary, total_budget)

    # --- Generations 1..N ---
    current_population = population
    for gen in range(1, generations):
        with console.status(f"[bold cyan]Evolving Generation {gen} (Selection → Crossover → Mutation → Reallocation)..."):
            gen_summary = engine.step(
                population=current_population,
                validation_input=validation_input,
                generation_idx=gen,
            )
            history.append(gen_summary)
            current_population = gen_summary.active_candidates

        display_generation_summary(gen_summary, total_budget)

    # Final Summaries
    console.print("\n" + "=" * 80 + "\n")
    display_convergence_history(history)

    # Champion Post
    champion = max(current_population, key=lambda c: c.fitness_score)
    console.print()
    display_winning_creative(champion)

    console.print("\n[bold green]✓ Demo execution completed successfully![/bold green]\n")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="n8chain Evolutionary Optimization CLI Demo")
    parser.add_argument("--generations", type=int, default=5, help="Number of generations to evolve (default: 5)")
    parser.add_argument("--population", type=int, default=10, help="Population size (default: 10)")
    parser.add_argument("--budget", type=float, default=1000.0, help="Total campaign budget in USD (default: 1000.0)")
    parser.add_argument(
        "--persona",
        type=str,
        choices=["business", "content_creator"],
        default="business",
        help="Target persona (business or content_creator)",
    )
    args = parser.parse_args()

    run_demo(
        generations=args.generations,
        population_size=args.population,
        total_budget=args.budget,
        persona_type=args.persona,
    )


if __name__ == "__main__":
    main()
