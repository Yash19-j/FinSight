from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Scenario:
    """Validated assumptions describing one counterfactual scenario."""

    scenario_id: str
    name: str
    description: str
    revenue_growth_adjustment: float = 0.0
    expense_growth_adjustment: float = 0.0
    one_time_cash_adjustment: float = 0.0
    duration_months: int = 12
    expense_reduction: float = 0.0
    baseline: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string.")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")

        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")

        for field in (
            "revenue_growth_adjustment",
            "expense_growth_adjustment",
            "one_time_cash_adjustment",
            "expense_reduction",
        ):
            value = getattr(self, field)

            if isinstance(value, bool):
                raise ValueError(f"{field} must be numeric, not boolean.")

            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field} must be finite.") from exc

            if not math.isfinite(numeric):
                raise ValueError(f"{field} must be finite.")

        if isinstance(self.duration_months, bool):
            raise ValueError("duration_months must be an integer.")

        if not isinstance(self.duration_months, (int, np.integer)):
            raise ValueError("duration_months must be an integer.")

        if self.duration_months < 1:
            raise ValueError("duration_months must be at least 1.")

        if self.expense_reduction < 0.0 or self.expense_reduction > 1.0:
            raise ValueError("expense_reduction must be between 0 and 1.")

        if self.revenue_growth_adjustment <= -1.0:
            raise ValueError(
                "revenue_growth_adjustment must be greater than -1."
            )

        if self.expense_growth_adjustment <= -1.0:
            raise ValueError(
                "expense_growth_adjustment must be greater than -1."
            )


class ScenarioEngine:
    """
    Monte Carlo scenario simulator for the normalized financial state.

    Revenue and expenses are modeled with multiplicative log-normal shocks.

    Scenario adjustments are assumptions, not predictions:
      * revenue_growth_adjustment changes the revenue growth rate while active.
      * expense_reduction changes the simulated expense level while active.
      * expense_growth_adjustment changes the expense growth rate while active.
      * one_time_cash_adjustment is applied exactly once at simulation start.

    Important metric semantics:
      * ending_cash = cash at the actual end of the simulation horizon.
      * survival_month = first month in which cash becomes <= 0.
      * survival_probability = probability that cash remains > 0 for the
        entire simulation horizon.

    A path that becomes insolvent is still simulated through the full horizon.
    This prevents ending_cash from becoming a disguised "cash at failure"
    metric.
    """

    DEFAULT_SIMULATION_RUNS = 5_000
    MIN_SIMULATION_RUNS = 100
    MAX_SIMULATION_RUNS = 50_000

    DEFAULT_HORIZON_MONTHS = 12
    MIN_HORIZON_MONTHS = 3
    MAX_HORIZON_MONTHS = 60

    STATE_NUMERIC_FIELDS = (
        "cash",
        "monthly_revenue",
        "monthly_expenses",
        "net_burn",
        "average_net_burn",
        "runway_months",
        "revenue_growth",
        "expense_growth",
        "revenue_volatility",
        "expense_volatility",
        "revenue_expense_ratio",
        "burn_multiple",
    )

    def __init__(self, financial_state: Dict[str, object]):
        if not isinstance(financial_state, dict):
            raise TypeError("financial_state must be a dictionary.")

        required = {
            "cash",
            "monthly_revenue",
            "monthly_expenses",
            "revenue_growth",
            "expense_growth",
            "revenue_volatility",
            "expense_volatility",
        }

        missing = sorted(required - set(financial_state))

        if missing:
            raise ValueError(
                f"Financial state is missing required fields: {missing}"
            )

        self.state = dict(financial_state)
        self._validate_state()

    @staticmethod
    def _finite(value: object, field: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field} must be finite numeric data."
            ) from exc

        if not math.isfinite(result):
            raise ValueError(f"{field} must be finite.")

        return result

    def _validate_state(self) -> None:
        for field in self.STATE_NUMERIC_FIELDS:
            value = self.state.get(field)

            if value is None:
                continue

            self._finite(value, field)

        for field in ("monthly_revenue", "monthly_expenses"):
            value = self._finite(self.state[field], field)

            if value < 0:
                raise ValueError(f"{field} cannot be negative.")

        for field in ("revenue_volatility", "expense_volatility"):
            value = self._finite(self.state[field], field)

            if value < 0:
                raise ValueError(f"{field} cannot be negative.")

    @staticmethod
    def _validate_simulation_runs(simulation_runs: int) -> int:
        if isinstance(simulation_runs, bool) or not isinstance(
            simulation_runs,
            (int, np.integer),
        ):
            raise ValueError("simulation_runs must be an integer.")

        if not (
            ScenarioEngine.MIN_SIMULATION_RUNS
            <= int(simulation_runs)
            <= ScenarioEngine.MAX_SIMULATION_RUNS
        ):
            raise ValueError(
                "simulation_runs must be between 100 and 50000."
            )

        return int(simulation_runs)

    @staticmethod
    def _validate_horizon(horizon_months: int) -> int:
        if isinstance(horizon_months, bool) or not isinstance(
            horizon_months,
            (int, np.integer),
        ):
            raise ValueError("horizon_months must be an integer.")

        if not (
            ScenarioEngine.MIN_HORIZON_MONTHS
            <= int(horizon_months)
            <= ScenarioEngine.MAX_HORIZON_MONTHS
        ):
            raise ValueError(
                "horizon_months must be between 3 and 60."
            )

        return int(horizon_months)

    @staticmethod
    def _validate_seed(seed: Optional[int]) -> Optional[int]:
        if seed is None:
            return None

        if isinstance(seed, bool) or not isinstance(
            seed,
            (int, np.integer),
        ):
            raise ValueError("seed must be an integer or None.")

        return int(seed)

    @staticmethod
    def _validate_scenario(scenario: Scenario) -> None:
        if not isinstance(scenario, Scenario):
            raise TypeError("scenario must be a Scenario instance.")

    @classmethod
    def baseline(cls, duration_months: int = 12) -> Scenario:
        """Create the no-intervention scenario."""
        return Scenario(
            scenario_id="baseline",
            name="Baseline",
            description=(
                "No intervention; baseline financial dynamics continue."
            ),
            duration_months=duration_months,
            baseline=True,
        )

    @classmethod
    def revenue_growth(
        cls,
        growth: float,
        duration_months: int = 12,
    ) -> Scenario:
        """Create a scenario with an explicit temporary revenue-growth lift."""
        return Scenario(
            scenario_id=f"revenue_growth_{growth:g}",
            name="Revenue Growth",
            description=(
                "Scenario assumption: revenue growth is increased by the "
                "specified amount while the intervention is active."
            ),
            revenue_growth_adjustment=growth,
            duration_months=duration_months,
            baseline=False,
        )

    @classmethod
    def expense_reduction(
        cls,
        reduction: float,
        duration_months: int = 12,
    ) -> Scenario:
        """Create a scenario with a temporary expense-level reduction."""
        return Scenario(
            scenario_id=f"expense_reduction_{reduction:g}",
            name="Expense Reduction",
            description=(
                "Scenario assumption: simulated expenses are multiplied by "
                "one minus the specified reduction while active."
            ),
            expense_reduction=reduction,
            duration_months=duration_months,
            baseline=False,
        )

    @classmethod
    def combined(
        cls,
        revenue_growth: float,
        expense_reduction: float,
        duration_months: int = 12,
    ) -> Scenario:
        """Create a scenario combining revenue growth and expense reduction."""
        return Scenario(
            scenario_id=(
                f"combined_revenue_{revenue_growth:g}_"
                f"expense_reduction_{expense_reduction:g}"
            ),
            name="Combined",
            description=(
                "Scenario assumption: revenue growth is increased and "
                "expenses are reduced while active."
            ),
            revenue_growth_adjustment=revenue_growth,
            expense_reduction=expense_reduction,
            duration_months=duration_months,
            baseline=False,
        )

    def _active_growth(
        self,
        baseline_growth: float,
        adjustment: float,
        month: int,
        duration: int,
    ) -> float:
        if month <= duration:
            return baseline_growth + adjustment

        return baseline_growth

    @staticmethod
    def _growth_multiplier(
        growth: float,
        volatility: float,
        rng: np.random.Generator,
        size: int,
    ) -> np.ndarray:
        """
        Produce a non-negative multiplicative factor.

        With zero volatility, the multiplier is exactly 1 + growth.
        With stochastic volatility, the expected multiplicative factor is
        centered around 1 + growth.
        """
        if growth <= -1.0:
            raise ValueError(
                "Effective growth must be greater than -100% per month."
            )

        if volatility < 0:
            raise ValueError("Volatility cannot be negative.")

        drift = math.log1p(growth)

        shocks = rng.normal(
            0.0,
            volatility,
            size=size,
        )

        log_multiplier = (
            drift
            - 0.5 * volatility**2
            + shocks
        )

        return np.exp(log_multiplier)

    def _simulate_paths(
        self,
        scenario: Scenario,
        simulation_runs: int,
        horizon_months: int,
        seed: Optional[int],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)

        initial_revenue = self._finite(
            self.state["monthly_revenue"],
            "monthly_revenue",
        )

        initial_expenses = self._finite(
            self.state["monthly_expenses"],
            "monthly_expenses",
        )

        initial_cash = self._finite(
            self.state["cash"],
            "cash",
        )

        baseline_revenue_growth = self._finite(
            self.state["revenue_growth"],
            "revenue_growth",
        )

        baseline_expense_growth = self._finite(
            self.state["expense_growth"],
            "expense_growth",
        )

        revenue_volatility = self._finite(
            self.state["revenue_volatility"],
            "revenue_volatility",
        )

        expense_volatility = self._finite(
            self.state["expense_volatility"],
            "expense_volatility",
        )

        revenue = np.full(
            simulation_runs,
            initial_revenue,
            dtype=float,
        )

        baseline_expenses = np.full(
            simulation_runs,
            initial_expenses,
            dtype=float,
        )

        starting_cash = (
            initial_cash
            + scenario.one_time_cash_adjustment
        )

        cash = np.full(
            simulation_runs,
            starting_cash,
            dtype=float,
        )

        # Track the first insolvency month independently from cash.
        #
        # A path may become negative in month 2 and continue evolving through
        # month 12. This allows ending_cash to remain a true horizon-end
        # metric while survival_month records the first failure.
        survival_month = np.full(
            simulation_runs,
            horizon_months,
            dtype=int,
        )

        failed = np.zeros(
            simulation_runs,
            dtype=bool,
        )

        if starting_cash <= 0.0:
            survival_month[:] = 0
            failed[:] = True

        for month in range(1, horizon_months + 1):
            revenue_growth = self._active_growth(
                baseline_revenue_growth,
                scenario.revenue_growth_adjustment,
                month,
                scenario.duration_months,
            )

            expense_growth = self._active_growth(
                baseline_expense_growth,
                scenario.expense_growth_adjustment,
                month,
                scenario.duration_months,
            )

            revenue_multiplier = self._growth_multiplier(
                revenue_growth,
                revenue_volatility,
                rng,
                simulation_runs,
            )

            expense_multiplier = self._growth_multiplier(
                expense_growth,
                expense_volatility,
                rng,
                simulation_runs,
            )

            revenue = np.maximum(
                0.0,
                revenue * revenue_multiplier,
            )

            baseline_expenses = np.maximum(
                0.0,
                baseline_expenses * expense_multiplier,
            )

            if month <= scenario.duration_months:
                expenses = baseline_expenses * (
                    1.0 - scenario.expense_reduction
                )
            else:
                expenses = baseline_expenses.copy()

            expenses = np.maximum(
                0.0,
                expenses,
            )

            # IMPORTANT:
            # Cash is always updated through the complete horizon.
            #
            # We deliberately do not freeze an insolvent path.
            cash = cash + revenue - expenses

            # Record only the FIRST month of insolvency.
            newly_failed = (
                (~failed)
                & (cash <= 0.0)
            )

            survival_month[newly_failed] = month
            failed[newly_failed] = True

        ending_cash = cash.copy()

        self._validate_simulation_outputs(
            ending_cash=ending_cash,
            survival_month=survival_month,
            revenue=revenue,
            expenses=expenses,
            cash=cash,
        )

        return (
            ending_cash,
            survival_month,
            revenue,
            expenses,
        )

    def simulate(
        self,
        scenario: Scenario,
        simulation_runs: int = DEFAULT_SIMULATION_RUNS,
        horizon_months: int = DEFAULT_HORIZON_MONTHS,
        seed: Optional[int] = None,
    ) -> Dict[str, object]:
        """
        Run a Monte Carlo scenario.

        The returned result is a probabilistic scenario estimate conditional
        on the supplied financial state and explicit scenario assumptions.

        It is not a guaranteed forecast or recommendation.
        """
        self._validate_scenario(scenario)

        simulation_runs = self._validate_simulation_runs(
            simulation_runs
        )

        horizon_months = self._validate_horizon(
            horizon_months
        )

        seed = self._validate_seed(seed)

        if scenario.duration_months > horizon_months:
            raise ValueError(
                "scenario duration_months cannot exceed horizon_months."
            )

        effective_revenue_growth = (
            self._finite(
                self.state["revenue_growth"],
                "revenue_growth",
            )
            + scenario.revenue_growth_adjustment
        )

        effective_expense_growth = (
            self._finite(
                self.state["expense_growth"],
                "expense_growth",
            )
            + scenario.expense_growth_adjustment
        )

        if effective_revenue_growth <= -1.0:
            raise ValueError(
                "Effective revenue growth must be greater than -100% per month."
            )

        if effective_expense_growth <= -1.0:
            raise ValueError(
                "Effective expense growth must be greater than -100% per month."
            )

        (
            ending_cash,
            survival_month,
            revenue,
            expenses,
        ) = self._simulate_paths(
            scenario,
            simulation_runs,
            horizon_months,
            seed,
        )

        self._validate_simulation_outputs(
            ending_cash=ending_cash,
            survival_month=survival_month,
            revenue=revenue,
            expenses=expenses,
        )

        survival_month = np.clip(
            survival_month,
            0,
            horizon_months,
        )

        # A path survives only if it never crossed <= 0 during the horizon.
        survived = (
            (survival_month == horizon_months)
            & (ending_cash > 0.0)
        )

        survival_probability = float(
            np.mean(survived)
        )

        shortfall_probability = (
            1.0 - survival_probability
        )

        p10, median, p90 = np.percentile(
            ending_cash,
            [10, 50, 90],
        )

        result: Dict[str, object] = {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "horizon_months": horizon_months,
            "simulation_runs": simulation_runs,
            "survival_probability": survival_probability,
            "mean_ending_cash": float(
                np.mean(ending_cash)
            ),
            "median_ending_cash": float(
                median
            ),
            "p10_ending_cash": float(
                p10
            ),
            "p90_ending_cash": float(
                p90
            ),
            "mean_survival_month": float(
                np.mean(survival_month)
            ),
            "probability_of_cash_shortfall": shortfall_probability,
            "baseline": bool(scenario.baseline),
            "assumptions": {
                "revenue_growth_adjustment": float(
                    scenario.revenue_growth_adjustment
                ),
                "expense_growth_adjustment": float(
                    scenario.expense_growth_adjustment
                ),
                "one_time_cash_adjustment": float(
                    scenario.one_time_cash_adjustment
                ),
                "duration_months": int(
                    scenario.duration_months
                ),
                "expense_reduction": float(
                    scenario.expense_reduction
                ),
            },
        }

        self._validate_output(result)

        return result

    @staticmethod
    def _validate_simulation_outputs(
        *,
        ending_cash: np.ndarray,
        survival_month: np.ndarray,
        revenue: np.ndarray,
        expenses: np.ndarray,
        cash: Optional[np.ndarray] = None,
    ) -> None:
        """Fail loudly if any internal simulation output is non-finite."""

        outputs = {
            "ending_cash": ending_cash,
            "survival_month": survival_month,
            "simulated revenue paths": revenue,
            "simulated expense paths": expenses,
        }

        if cash is not None:
            outputs["cash paths"] = cash

        for name, values in outputs.items():
            try:
                finite = np.isfinite(values)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Simulation output '{name}' became non-finite "
                    "or non-numeric."
                ) from exc

            if not np.all(finite):
                raise RuntimeError(
                    f"Simulation output '{name}' contains NaN or infinity."
                )

    @staticmethod
    def _validate_output(
        result: Dict[str, object],
    ) -> None:
        probability_fields = (
            "survival_probability",
            "probability_of_cash_shortfall",
        )

        for field in probability_fields:
            value = float(result[field])

            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise AssertionError(
                    f"{field} must be between 0 and 1."
                )

        for field in (
            "mean_ending_cash",
            "median_ending_cash",
            "p10_ending_cash",
            "p90_ending_cash",
            "mean_survival_month",
        ):
            value = float(result[field])

            if not math.isfinite(value):
                raise AssertionError(
                    f"{field} must be finite."
                )

        if (
            float(result["p10_ending_cash"])
            > float(result["median_ending_cash"])
        ):
            raise AssertionError(
                "P10 ending cash cannot exceed P50."
            )

        if (
            float(result["median_ending_cash"])
            > float(result["p90_ending_cash"])
        ):
            raise AssertionError(
                "P50 ending cash cannot exceed P90."
            )