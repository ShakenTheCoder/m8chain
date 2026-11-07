"""Dynamic Budget Reallocator for evolutionary marketing campaigns.

Implements budget reallocation algorithms including Softmax-weighted allocation,
Upper Confidence Bound (UCB) exploration-exploitation, and strict budget conservation
guarantees across generations.
"""

from __future__ import annotations

import math
from typing import Dict, List, Literal, Optional
import numpy as np

from schemas import BudgetAllocation, Candidate


class BudgetReallocator:
    """Manages spend distribution and dynamic resource reallocation.

    Shifts advertising spend from eliminated or underperforming candidates
    to elite performers while maintaining an exploration budget floor for
    newly recombined/mutated variations.
    """

    def __init__(
        self,
        min_allocation_pct: float = 0.03,
        max_allocation_pct: float = 0.40,
        default_bid_aggressiveness: float = 1.0,
    ) -> None:
        """Initialize the reallocator.

        Args:
            min_allocation_pct: Minimum budget fraction guaranteed to any active candidate
                to prevent starving exploratory variations.
            max_allocation_pct: Maximum budget cap for any single candidate to prevent
                over-concentration risk.
            default_bid_aggressiveness: Base bidding multiplier.
        """
        self.min_allocation_pct = min_allocation_pct
        self.max_allocation_pct = max_allocation_pct
        self.default_bid_aggressiveness = default_bid_aggressiveness

    def allocate_initial_budget(
        self,
        candidates: List[Candidate],
        total_budget: float,
    ) -> List[Candidate]:
        """Equally distribute budget across Generation 0 candidates with slight diversity perturbation.

        Args:
            candidates: Newly initialized Generation 0 candidates.
            total_budget: Total campaign budget in currency units.

        Returns:
            Updated candidates with initialized BudgetAllocation.
        """
        if not candidates:
            return candidates

        n = len(candidates)
        base_share = total_budget / n

        for candidate in candidates:
            candidate.budget = BudgetAllocation(
                spend_weight=1.0 / n,
                daily_budget=round(base_share, 2),
                bid_aggressiveness=self.default_bid_aggressiveness,
            )

        self._normalize_and_enforce_cap(candidates, total_budget)
        return candidates

    def reallocate_budget(
        self,
        candidates: List[Candidate],
        total_budget: float,
        method: Literal["softmax", "ucb", "thompson"] = "softmax",
        temperature: float = 0.8,
        exploration_ratio: float = 0.20,
    ) -> List[Candidate]:
        """Reallocate campaign budget based on fitness scores and observed metrics.

        Args:
            candidates: Active candidate pool to receive budget.
            total_budget: Total campaign budget to allocate.
            method: Reallocation strategy ('softmax', 'ucb', 'thompson').
            temperature: Softmax temperature parameter (lower = greedier exploitation).
            exploration_ratio: Fraction of budget reserved strictly for exploratory distribution.

        Returns:
            Candidates with updated budget allocations strictly summing to total_budget.
        """
        active_candidates = [c for c in candidates if c.status != "eliminated"]
        for c in candidates:
            if c.status == "eliminated":
                c.budget.daily_budget = 0.0
                c.budget.spend_weight = 0.0
                c.budget.bid_aggressiveness = 0.0

        if not active_candidates:
            return candidates

        n = len(active_candidates)
        if n == 1:
            active_candidates[0].budget.spend_weight = 1.0
            active_candidates[0].budget.daily_budget = total_budget
            active_candidates[0].budget.bid_aggressiveness = 1.5
            return candidates

        fitness_scores = np.array([max(0.0, c.fitness_score) for c in active_candidates], dtype=float)

        if method == "ucb":
            weights = self._compute_ucb_weights(active_candidates, exploration_ratio)
        elif method == "thompson":
            weights = self._compute_thompson_weights(active_candidates)
        else:  # softmax with exploration floor
            weights = self._compute_softmax_weights(fitness_scores, temperature, exploration_ratio)

        # Distribute raw daily budgets
        for candidate, weight in zip(active_candidates, weights):
            candidate.budget.spend_weight = float(weight)
            candidate.budget.daily_budget = float(weight * total_budget)

            # High fitness candidates bid more aggressively to capture high-value inventory
            relative_rank = weight / (1.0 / n)
            candidate.budget.bid_aggressiveness = float(
                np.clip(self.default_bid_aggressiveness * math.sqrt(max(0.2, relative_rank)), 0.5, 2.5)
            )

        self._normalize_and_enforce_cap(active_candidates, total_budget)
        return candidates

    def _compute_softmax_weights(
        self,
        scores: np.ndarray,
        temperature: float,
        exploration_ratio: float,
    ) -> np.ndarray:
        """Compute Softmax allocation with temperature and an exploration floor."""
        temp = max(1e-3, temperature)
        # Normalize scores to [0, 1] range to prevent exp overflow/underflow
        score_span = scores.max() - scores.min()
        norm_scores = (scores - scores.min()) / score_span if score_span > 1e-6 else np.zeros_like(scores)

        exp_scores = np.exp(norm_scores / temp)
        softmax_probs = exp_scores / exp_scores.sum()

        n = len(scores)
        uniform_floor = np.ones(n) / n
        combined_weights = (1.0 - exploration_ratio) * softmax_probs + exploration_ratio * uniform_floor
        return combined_weights / combined_weights.sum()

    def _compute_ucb_weights(
        self,
        candidates: List[Candidate],
        exploration_c: float = 0.5,
    ) -> np.ndarray:
        """Upper Confidence Bound scoring to balance exploitation of winners and testing of new variants."""
        total_pulls = sum(max(1, int(c.metrics.get("clicks", 1))) for c in candidates)
        ucb_scores = []

        for c in candidates:
            pulls = max(1, int(c.metrics.get("clicks", 1)))
            mean_reward = max(0.0, c.fitness_score)
            bonus = exploration_c * math.sqrt(2.0 * math.log(max(2, total_pulls)) / pulls)
            ucb_scores.append(mean_reward + bonus)

        arr = np.array(ucb_scores, dtype=float)
        arr = np.maximum(arr, 1e-4)
        return arr / arr.sum()

    def _compute_thompson_weights(
        self,
        candidates: List[Candidate],
    ) -> np.ndarray:
        """Thompson Sampling-like probabilistic weight sampling using Beta priors."""
        samples = []
        for c in candidates:
            clicks = max(1, int(c.metrics.get("clicks", 1)))
            conversions = max(0, int(c.metrics.get("conversions", 0)))
            # Beta distribution parameters for conversion success
            alpha = 1.0 + conversions
            beta_param = 1.0 + max(0, clicks - conversions)
            sample = np.random.beta(alpha, beta_param) * max(0.1, c.fitness_score)
            samples.append(sample)

        arr = np.array(samples, dtype=float)
        arr = np.maximum(arr, 1e-4)
        return arr / arr.sum()

    def _normalize_and_enforce_cap(
        self,
        candidates: List[Candidate],
        total_budget: float,
    ) -> None:
        """Enforces min/max allocation caps and strict conservation: sum(budgets) == total_budget."""
        n = len(candidates)
        if n == 0 or total_budget <= 0:
            return

        min_budget = total_budget * self.min_allocation_pct
        max_budget = total_budget * self.max_allocation_pct

        # Initial clamp
        budgets = np.array([c.budget.daily_budget for c in candidates], dtype=float)
        budgets = np.clip(budgets, min_budget, max_budget)

        # Iteratively scale to match total_budget exactly
        for _ in range(5):
            current_sum = budgets.sum()
            if current_sum <= 1e-6:
                budgets = np.full(n, total_budget / n)
                break
            budgets = (budgets / current_sum) * total_budget
            budgets = np.clip(budgets, min_budget, max_budget)

        # Distribute any remaining residual due to continuous clipping
        residual = total_budget - float(budgets.sum())
        budgets[np.argmax(budgets)] += residual

        # Round budgets to 2 decimal places (exact cents)
        rounded_budgets = [round(float(b), 2) for b in budgets]
        cent_diff = round(total_budget - sum(rounded_budgets), 2)

        # Distribute cent discrepancy to ensure sum(budgets) <= total_budget exactly with zero leak
        if cent_diff != 0:
            top_idx = int(np.argmax(budgets))
            rounded_budgets[top_idx] = round(rounded_budgets[top_idx] + cent_diff, 2)

        # Assign back to candidates and recompute normalized spend weights
        for c, b in zip(candidates, rounded_budgets):
            c.budget.daily_budget = b
            c.budget.spend_weight = float(b / total_budget) if total_budget > 0 else 0.0

    @staticmethod
    def get_budget_breakdown(candidates: List[Candidate]) -> Dict[str, float]:
        """Return a mapping of candidate ID to daily allocated budget."""
        return {c.id: c.budget.daily_budget for c in candidates}

    @staticmethod
    def verify_budget_conservation(
        candidates: List[Candidate],
        total_budget: float,
        tolerance: float = 0.05,
    ) -> bool:
        """Check if sum of active budgets matches total budget within cent precision."""
        active_sum = round(sum(c.budget.daily_budget for c in candidates if c.status != "eliminated"), 2)
        return (active_sum <= total_budget + 1e-4) and (abs(active_sum - total_budget) <= tolerance)
