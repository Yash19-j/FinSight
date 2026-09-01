from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..models.action import Action, ActionParameters
from .action_executor import ActionExecutor
from .decision_optimizer import DecisionOptimizer
from .outcome_verifier import OutcomeVerifier
from .policy_engine import PolicyEngine
from .financial_state import FinancialStateEngine
from .risk_detector import RiskDetector
from .root_cause import RootCauseEngine
from .scenario_engine import Scenario, ScenarioEngine


class DecisionPipeline:
    """Orchestrate FinSight's complete financial decision workflow.

    The pipeline coordinates state construction, deterministic risk/root-cause
    analysis, scenario simulation, decision optimization, policy evaluation,
    approved-action construction, dry-run execution, and execution
    verification. It contains no duplicated financial logic and performs no
    external I/O itself.
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
        # Reuse ScenarioEngine's established validators.
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
        self._validate_config_value(
            self.expense_reduction,
            "expense_reduction",
        )

        if not 0.0 <= float(self.expense_reduction) <= 1.0:
            raise ValueError("expense_reduction must be between 0 and 1.")

    def _build_scenarios(self) -> List[Scenario]:
        duration = (
            min(
                self.DEFAULT_SCENARIO_DURATION_MONTHS,
                int(self.horizon_months),
            )
            if self.scenario_duration_months is None
            else int(self.scenario_duration_months)
        )

        return [
            ScenarioEngine.baseline(
                duration_months=self.horizon_months
            ),
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
            seed = (
                None
                if self.random_seed is None
                else self.random_seed + index
            )

            try:
                result = engine.simulate(
                    scenario,
                    simulation_runs=self.simulation_runs,
                    horizon_months=self.horizon_months,
                    seed=seed,
                )
            except Exception as exc:
                raise RuntimeError(
                    "Decision pipeline failed during scenario simulation "
                    f"for '{scenario.scenario_id}': {exc}"
                ) from exc

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Decision pipeline received a non-dictionary result "
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
            result
            for result in scenario_results
            if result.get("baseline") is True
        ]
        interventions = [
            result
            for result in scenario_results
            if result.get("baseline") is not True
        ]

        if len(baselines) != 1:
            raise RuntimeError(
                "Decision pipeline expected exactly one baseline scenario, "
                f"found {len(baselines)}."
            )

        return baselines[0], interventions

    @staticmethod
    def _resolve_recommended_scenario(
        decision: Dict[str, object],
        scenario_results: Sequence[Dict[str, object]],
    ) -> Dict[str, object]:
        """Resolve the optimizer's selected ID to an authoritative result."""
        recommended = decision.get("recommended_scenario")

        if not isinstance(recommended, dict):
            raise RuntimeError(
                "Decision pipeline cannot resolve the recommended scenario: "
                "recommended_scenario must be a dictionary."
            )

        scenario_id = recommended.get("scenario_id")

        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise RuntimeError(
                "Decision pipeline cannot resolve the recommended scenario: "
                "recommended_scenario.scenario_id is missing or invalid."
            )

        matches = [
            result
            for result in scenario_results
            if result.get("scenario_id") == scenario_id
        ]

        if not matches:
            raise RuntimeError(
                "Decision pipeline could not resolve recommended scenario_id "
                f"'{scenario_id}' from ScenarioEngine results."
            )

        if len(matches) > 1:
            raise RuntimeError(
                "Decision pipeline found multiple ScenarioEngine results for "
                f"recommended scenario_id '{scenario_id}'."
            )

        # Shallow copy is sufficient here because PolicyEngine deep-copies
        # its decision input before applying any MODIFY changes.
        return dict(matches[0])

    def _evaluate_policy(
        self,
        decision: Dict[str, object],
        scenario_results: Sequence[Dict[str, object]],
        data_confidence: str,
    ) -> Dict[str, object]:
        """Evaluate the selected authoritative scenario under policy."""
        authoritative_scenario = self._resolve_recommended_scenario(
            decision,
            scenario_results,
        )

        policy_decision = dict(decision)
        policy_decision["recommended_scenario"] = authoritative_scenario

        try:
            result = PolicyEngine(
                decision=policy_decision,
                data_confidence=data_confidence,
            ).evaluate()
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during policy evaluation: {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Decision pipeline received a non-dictionary policy result."
            )

        return result

    @staticmethod
    def _build_action_from_policy(
        policy: Dict[str, object],
    ) -> Optional[Action]:
        """Build Action strictly from PolicyEngine's approved_action."""
        try:
            status = policy["status"]

            if status == "BLOCK":
                return None

            approved_action = policy["approved_action"]

            if not isinstance(approved_action, dict):
                raise ValueError(
                    "policy.approved_action must be a dictionary for "
                    "APPROVE/MODIFY."
                )

            scenario_id = approved_action["scenario_id"]

            # Baseline is a valid policy outcome but is explicitly a no-op,
            # so it must never cross the execution boundary.
            if scenario_id == "baseline":
                return None

            assumptions = approved_action["assumptions"]

            if not isinstance(assumptions, dict):
                raise ValueError(
                    "policy.approved_action.assumptions must be a dictionary."
                )

            parameters = ActionParameters(
                revenue_growth_adjustment=assumptions[
                    "revenue_growth_adjustment"
                ],
                expense_growth_adjustment=assumptions[
                    "expense_growth_adjustment"
                ],
                one_time_cash_adjustment=assumptions[
                    "one_time_cash_adjustment"
                ],
                duration_months=assumptions["duration_months"],
                expense_reduction=assumptions["expense_reduction"],
            )

            return Action(
                scenario_id=scenario_id,
                scenario_name=approved_action["scenario_name"],
                parameters=parameters,
                policy_status=status,
                confidence=policy["confidence"],
                reasoning=policy["reasoning"],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during action construction: {exc}"
            ) from exc

    @staticmethod
    def _execute_action(action: Action) -> Dict[str, object]:
        try:
            result = ActionExecutor().execute(action)
        except Exception as exc:
            raise RuntimeError(
                f"Decision pipeline failed during action execution: {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Decision pipeline failed during action execution: "
                "executor returned a non-dictionary result."
            )

        return result

    @staticmethod
    def _verify_execution(
        action: Action,
        execution: Dict[str, object],
    ) -> Dict[str, object]:
        try:
            result = OutcomeVerifier().verify(action, execution)
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during outcome verification: "
                f"{exc}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Decision pipeline failed during outcome verification: "
                "verifier returned a non-dictionary result."
            )

        return result

    def run(self) -> Dict[str, object]:
        """Run the complete FinSight decision pipeline."""
        self._validate_configuration()

        try:
            state = FinancialStateEngine(self.df).build_state()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during financial-state "
                f"construction: {exc}"
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

        confidence = (
            self.data_confidence
            or str(state["data_confidence"])
        )

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

        if not isinstance(decision, dict):
            raise RuntimeError(
                "Decision pipeline received a non-dictionary decision result."
            )

        policy = self._evaluate_policy(
            decision,
            scenario_results,
            confidence,
        )

        action = self._build_action_from_policy(policy)

        if action is None:
            execution = None
            verification = None
        else:
            execution = self._execute_action(action)
            verification = self._verify_execution(
                action,
                execution,
            )

        result: Dict[str, object] = {
            "financial_state": state,
            "risks": risks,
            "root_causes": root_causes,
            "scenarios": scenario_results,
            "decision": decision,
            "policy": policy,
            "action": None if action is None else action.to_dict(),
            "execution": execution,
            "verification": verification,
            "metadata": {
                "simulation_runs": int(self.simulation_runs),
                "horizon_months": int(self.horizon_months),
                "random_seed": (
                    None
                    if self.random_seed is None
                    else int(self.random_seed)
                ),
            },
        }

        self._validate_output_numbers(result, "result")
        return result
