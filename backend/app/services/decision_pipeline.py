from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .decision_optimizer import DecisionOptimizer
from .financial_state import FinancialStateEngine
from .risk_detector import RiskDetector
from .root_cause import RootCauseEngine
from .scenario_engine import Scenario, ScenarioEngine


class DecisionPipeline:
    """Orchestrate FinSight's existing financial decision engines.

    The pipeline coordinates state construction, deterministic risk/root-cause
    analysis, scenario simulation, and decision optimization. It intentionally
    contains no duplicated financial logic and performs no external I/O.
    """

    DEFAULT_SIMULATION_RUNS = 5_000
    DEFAULT_HORIZON_MONTHS = 12
    DEFAULT_RANDOM_SEED = 42

    DEFAULT_SCENARIO_DURATION_MONTHS = 6
    DEFAULT_REVENUE_GROWTH_ADJUSTMENT = 0.10
    DEFAULT_EXPENSE_REDUCTION = 0.10

    def __init__(
        self,
        df: pd.DataFrame,
        simulation_runs: int = DEFAULT_SIMULATION_RUNS,
        horizon_months: int = DEFAULT_HORIZON_MONTHS,
        random_seed: Optional[int] = DEFAULT_RANDOM_SEED,
        data_confidence: Optional[str] = None,
        scenario_duration_months: Optional[int] = None,
        revenue_growth_adjustment: float = DEFAULT_REVENUE_GROWTH_ADJUSTMENT,
        expense_reduction: float = DEFAULT_EXPENSE_REDUCTION,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("DecisionPipeline expects a pandas DataFrame.")

        self.df = df.copy(deep=True)
        self.simulation_runs = simulation_runs
        self.horizon_months = horizon_months
        self.random_seed = random_seed
        self.data_confidence = data_confidence
        self.scenario_duration_months = scenario_duration_months
        self.revenue_growth_adjustment = revenue_growth_adjustment
        self.expense_reduction = expense_reduction

    @staticmethod
    def _validate_output_numbers(value: object, path: str) -> None:
        """Reject non-finite numeric values recursively in public output."""
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return
        if isinstance(value, (int, float, np.integer, np.floating)):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise RuntimeError(
                    f"Decision pipeline output '{path}' became non-finite."
                )
            return
        if isinstance(value, dict):
            for key, item in value.items():
                DecisionPipeline._validate_output_numbers(
                    item, f"{path}.{key}"
                )
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                DecisionPipeline._validate_output_numbers(
                    item, f"{path}[{index}]"
                )
            return
        raise RuntimeError(
            f"Decision pipeline output '{path}' contains unsupported type "
            f"{type(value).__name__}."
        )

    @staticmethod
    def _validate_config_value(value: object, name: str) -> None:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be numeric, not boolean.")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric.") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"{name} must be finite.")

    def _validate_configuration(self) -> None:
        # Reuse ScenarioEngine's existing validators rather than reproducing
        # its simulation-count, horizon, and seed rules here.
        ScenarioEngine._validate_simulation_runs(self.simulation_runs)
        ScenarioEngine._validate_horizon(self.horizon_months)
        ScenarioEngine._validate_seed(self.random_seed)

        if self.scenario_duration_months is not None:
            if isinstance(self.scenario_duration_months, bool) or not isinstance(
                self.scenario_duration_months, (int, np.integer)
            ):
                raise ValueError("scenario_duration_months must be an integer.")
            if not 1 <= int(self.scenario_duration_months) <= self.horizon_months:
                raise ValueError(
                    "scenario_duration_months must be between 1 and horizon_months."
                )

        self._validate_config_value(
            self.revenue_growth_adjustment,
            "revenue_growth_adjustment",
        )
        self._validate_config_value(self.expense_reduction, "expense_reduction")
        if not 0.0 <= float(self.expense_reduction) <= 1.0:
            raise ValueError("expense_reduction must be between 0 and 1.")

    def _build_scenarios(self) -> List[Scenario]:
        duration = (
            min(self.DEFAULT_SCENARIO_DURATION_MONTHS, int(self.horizon_months))
            if self.scenario_duration_months is None
            else int(self.scenario_duration_months)
        )
        return [
            ScenarioEngine.baseline(duration_months=self.horizon_months),
            ScenarioEngine.revenue_growth(
                float(self.revenue_growth_adjustment),
                duration_months=duration,
            ),
            ScenarioEngine.expense_reduction(
                float(self.expense_reduction),
                duration_months=duration,
            ),
            ScenarioEngine.combined(
                float(self.revenue_growth_adjustment),
                float(self.expense_reduction),
                duration_months=duration,
            ),
        ]

    def _simulate_scenarios(
        self,
        engine: ScenarioEngine,
        scenarios: Sequence[Scenario],
    ) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []

        for index, scenario in enumerate(scenarios):
            seed = None if self.random_seed is None else self.random_seed + index
            try:
                result = engine.simulate(
                    scenario,
                    simulation_runs=self.simulation_runs,
                    horizon_months=self.horizon_months,
                    seed=seed,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Decision pipeline failed during scenario simulation "
                    f"for '{scenario.scenario_id}': {exc}"
                ) from exc

            if not isinstance(result, dict):
                raise RuntimeError(
                    f"Decision pipeline received a non-dictionary result "
                    f"from scenario '{scenario.scenario_id}'."
                )
            self._validate_output_numbers(
                result,
                f"scenarios[{index}]",
            )
            results.append(dict(result))

        return results

    @staticmethod
    def _split_baseline(
        scenario_results: Sequence[Dict[str, object]],
    ) -> tuple[Dict[str, object], List[Dict[str, object]]]:
        baselines = [
            result for result in scenario_results if result.get("baseline") is True
        ]
        interventions = [
            result for result in scenario_results if result.get("baseline") is not True
        ]

        if len(baselines) != 1:
            raise RuntimeError(
                f"Decision pipeline expected exactly one baseline scenario, "
                f"found {len(baselines)}."
            )
        return baselines[0], interventions

    def run(self) -> Dict[str, object]:
        """Run the complete FinSight decision pipeline and return one result."""
        self._validate_configuration()

        try:
            state = FinancialStateEngine(self.df).build_state()
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during financial-state construction: {exc}"
            ) from exc

        try:
            risks = RiskDetector(state).detect()
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during risk detection: {exc}"
            ) from exc

        try:
            root_causes = RootCauseEngine(state, risks).analyze()
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during root-cause analysis: {exc}"
            ) from exc

        scenarios = self._build_scenarios()
        scenario_engine = ScenarioEngine(state)
        scenario_results = self._simulate_scenarios(
            scenario_engine,
            scenarios,
        )
        baseline_result, intervention_results = self._split_baseline(
            scenario_results
        )

        confidence = self.data_confidence or str(state["data_confidence"])
        try:
            decision = DecisionOptimizer(
                baseline_result=baseline_result,
                scenario_results=intervention_results,
                data_confidence=confidence,
            ).optimize()
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during decision optimization: {exc}"
            ) from exc

        result: Dict[str, object] = {
            "financial_state": state,
            "risks": risks,
            "root_causes": root_causes,
            "scenarios": scenario_results,
            "decision": decision,
            "metadata": {
                "simulation_runs": int(self.simulation_runs),
                "horizon_months": int(self.horizon_months),
                "random_seed": (
                    None if self.random_seed is None else int(self.random_seed)
                ),
            },
        }

        self._validate_output_numbers(result, "result")
        return result
