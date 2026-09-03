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

    The pipeline coordinates:

        FinancialStateEngine
        -> RiskDetector
        -> RootCauseEngine
        -> ScenarioEngine
        -> DecisionOptimizer
        -> PolicyEngine
        -> Action
        -> ActionExecutor
        -> OutcomeVerifier

    The pipeline itself contains no duplicated financial logic and performs
    no external I/O.
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
        revenue_growth_adjustment: float = (
            DEFAULT_REVENUE_GROWTH_ADJUSTMENT
        ),
        expense_reduction: float = DEFAULT_EXPENSE_REDUCTION,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                "DecisionPipeline expects a pandas DataFrame."
            )

        self.df = df.copy(deep=True)

        self.simulation_runs = simulation_runs
        self.horizon_months = horizon_months
        self.random_seed = random_seed

        self.data_confidence = data_confidence

        self.scenario_duration_months = (
            scenario_duration_months
        )

        self.revenue_growth_adjustment = (
            revenue_growth_adjustment
        )

        self.expense_reduction = expense_reduction

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_output_numbers(
        value: object,
        path: str,
    ) -> None:
        """Reject non-finite numeric values recursively."""
        if (
            isinstance(value, bool)
            or value is None
            or isinstance(value, str)
        ):
            return

        if isinstance(
            value,
            (int, float, np.integer, np.floating),
        ):
            numeric = float(value)

            if not math.isfinite(numeric):
                raise RuntimeError(
                    f"Decision pipeline output '{path}' "
                    "became non-finite."
                )

            return

        if isinstance(value, dict):
            for key, item in value.items():
                DecisionPipeline._validate_output_numbers(
                    item,
                    f"{path}.{key}",
                )

            return

        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                DecisionPipeline._validate_output_numbers(
                    item,
                    f"{path}[{index}]",
                )

            return

        raise RuntimeError(
            f"Decision pipeline output '{path}' contains "
            f"unsupported type {type(value).__name__}."
        )

    @staticmethod
    def _validate_config_value(
        value: object,
        name: str,
    ) -> None:
        if isinstance(value, bool):
            raise ValueError(
                f"{name} must be numeric, not boolean."
            )

        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name} must be numeric."
            ) from exc

        if not math.isfinite(numeric):
            raise ValueError(
                f"{name} must be finite."
            )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _validate_configuration(self) -> None:
        """Validate pipeline configuration using existing engine rules."""
        ScenarioEngine._validate_simulation_runs(
            self.simulation_runs
        )

        ScenarioEngine._validate_horizon(
            self.horizon_months
        )

        ScenarioEngine._validate_seed(
            self.random_seed
        )

        if self.scenario_duration_months is not None:
            if (
                isinstance(
                    self.scenario_duration_months,
                    bool,
                )
                or not isinstance(
                    self.scenario_duration_months,
                    (int, np.integer),
                )
            ):
                raise ValueError(
                    "scenario_duration_months must be an integer."
                )

            if not (
                1
                <= int(self.scenario_duration_months)
                <= self.horizon_months
            ):
                raise ValueError(
                    "scenario_duration_months must be between "
                    "1 and horizon_months."
                )

        self._validate_config_value(
            self.revenue_growth_adjustment,
            "revenue_growth_adjustment",
        )

        self._validate_config_value(
            self.expense_reduction,
            "expense_reduction",
        )

        if not (
            0.0
            <= float(self.expense_reduction)
            <= 1.0
        ):
            raise ValueError(
                "expense_reduction must be between 0 and 1."
            )

    # ------------------------------------------------------------------
    # Scenario construction
    # ------------------------------------------------------------------

    def _build_scenarios(self) -> List[Scenario]:
        """Construct the baseline and bounded intervention scenarios."""
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
                float(
                    self.revenue_growth_adjustment
                ),
                duration_months=duration,
            ),
            ScenarioEngine.expense_reduction(
                float(self.expense_reduction),
                duration_months=duration,
            ),
            ScenarioEngine.combined(
                float(
                    self.revenue_growth_adjustment
                ),
                float(self.expense_reduction),
                duration_months=duration,
            ),
        ]

    # ------------------------------------------------------------------
    # Scenario simulation
    # ------------------------------------------------------------------

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
                    "Decision pipeline failed during scenario "
                    f"simulation for '{scenario.scenario_id}': "
                    f"{exc}"
                ) from exc

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Decision pipeline received a non-dictionary "
                    "result from scenario "
                    f"'{scenario.scenario_id}'."
                )

            self._validate_output_numbers(
                result,
                f"scenarios[{index}]",
            )

            results.append(
                dict(result)
            )

        return results

    # ------------------------------------------------------------------
    # Baseline handling
    # ------------------------------------------------------------------

    @staticmethod
    def _split_baseline(
        scenario_results: Sequence[
            Dict[str, object]
        ],
    ) -> tuple[
        Dict[str, object],
        List[Dict[str, object]],
    ]:
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
                "Decision pipeline expected exactly one "
                "baseline scenario, "
                f"found {len(baselines)}."
            )

        return (
            baselines[0],
            interventions,
        )

    # ------------------------------------------------------------------
    # Recommendation resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_recommended_scenario(
        decision: Dict[str, object],
        scenario_results: Sequence[
            Dict[str, object]
        ],
    ) -> Dict[str, object]:
        """Resolve optimizer ID to the authoritative ScenarioEngine result."""
        recommended = decision.get(
            "recommended_scenario"
        )

        if not isinstance(recommended, dict):
            raise RuntimeError(
                "Decision pipeline cannot resolve the "
                "recommended scenario: "
                "recommended_scenario must be a dictionary."
            )

        scenario_id = recommended.get(
            "scenario_id"
        )

        if (
            not isinstance(scenario_id, str)
            or not scenario_id.strip()
        ):
            raise RuntimeError(
                "Decision pipeline cannot resolve the "
                "recommended scenario: "
                "recommended_scenario.scenario_id is missing "
                "or invalid."
            )

        matches = [
            result
            for result in scenario_results
            if result.get("scenario_id") == scenario_id
        ]

        if not matches:
            raise RuntimeError(
                "Decision pipeline could not resolve recommended "
                "scenario_id "
                f"'{scenario_id}' from ScenarioEngine results."
            )

        if len(matches) > 1:
            raise RuntimeError(
                "Decision pipeline found multiple ScenarioEngine "
                "results for recommended scenario_id "
                f"'{scenario_id}'."
            )

        # PolicyEngine deep-copies its input before applying MODIFY,
        # therefore this outer copy protects the pipeline's scenario
        # collection while preserving authoritative nested values.
        return dict(matches[0])

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------

    def _evaluate_policy(
        self,
        decision: Dict[str, object],
        scenario_results: Sequence[
            Dict[str, object]
        ],
        baseline_result: Dict[str, object],
        data_confidence: str,
    ) -> Dict[str, object]:
        """Evaluate the selected authoritative scenario under policy."""
        authoritative_scenario = (
            self._resolve_recommended_scenario(
                decision,
                scenario_results,
            )
        )

        policy_decision = dict(decision)

        # The optimizer only selects a scenario ID/name.
        #
        # The complete authoritative ScenarioEngine result is supplied
        # here so PolicyEngine never reconstructs assumptions from IDs.
        policy_decision[
            "recommended_scenario"
        ] = authoritative_scenario

        # Supply the authoritative baseline separately.
        #
        # This is intentionally placed into the decision envelope instead
        # of changing PolicyEngine's constructor, preserving compatibility
        # with existing PolicyEngine test doubles and direct callers.
        policy_decision[
            "baseline_result"
        ] = baseline_result

        try:
            result = PolicyEngine(
                decision=policy_decision,
                data_confidence=data_confidence,
            ).evaluate()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during policy evaluation: "
                f"{exc}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Decision pipeline received a non-dictionary "
                "policy result."
            )

        return result

    # ------------------------------------------------------------------
    # Action construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_action_from_policy(
        policy: Dict[str, object],
    ) -> Optional[Action]:
        """Build an Action strictly from PolicyEngine approval."""
        try:
            status = policy["status"]

            # BLOCK is never executable.
            if status == "BLOCK":
                return None

            approved_action = policy[
                "approved_action"
            ]

            if not isinstance(
                approved_action,
                dict,
            ):
                raise ValueError(
                    "policy.approved_action must be a dictionary "
                    "for APPROVE/MODIFY."
                )

            scenario_id = approved_action[
                "scenario_id"
            ]

            # Baseline is a valid policy outcome but is explicitly
            # a no-op and must never cross the execution boundary.
            if scenario_id == "baseline":
                return None

            assumptions = approved_action[
                "assumptions"
            ]

            if not isinstance(
                assumptions,
                dict,
            ):
                raise ValueError(
                    "policy.approved_action.assumptions must "
                    "be a dictionary."
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
                duration_months=assumptions[
                    "duration_months"
                ],
                expense_reduction=assumptions[
                    "expense_reduction"
                ],
            )

            return Action(
                scenario_id=scenario_id,
                scenario_name=approved_action[
                    "scenario_name"
                ],
                parameters=parameters,
                policy_status=status,
                confidence=policy[
                    "confidence"
                ],
                reasoning=policy[
                    "reasoning"
                ],
            )

        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during action "
                f"construction: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_action(
        action: Action,
    ) -> Dict[str, object]:
        try:
            result = ActionExecutor().execute(
                action
            )
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during action execution: "
                f"{exc}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Decision pipeline failed during action execution: "
                "executor returned a non-dictionary result."
            )

        return result

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_execution(
        action: Action,
        execution: Dict[str, object],
    ) -> Dict[str, object]:
        try:
            result = OutcomeVerifier().verify(
                action,
                execution,
            )
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

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, object]:
        """Run the complete FinSight decision pipeline."""
        self._validate_configuration()

        # --------------------------------------------------------------
        # 1. Financial state
        # --------------------------------------------------------------

        try:
            state = FinancialStateEngine(
                self.df
            ).build_state()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during financial-state "
                f"construction: {exc}"
            ) from exc

        # --------------------------------------------------------------
        # 2. Risk detection
        # --------------------------------------------------------------

        try:
            risks = RiskDetector(
                state
            ).detect()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during risk detection: "
                f"{exc}"
            ) from exc

        # --------------------------------------------------------------
        # 3. Root-cause / driver analysis
        # --------------------------------------------------------------

        try:
            root_causes = RootCauseEngine(
                state,
                risks,
            ).analyze()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during root-cause "
                f"analysis: {exc}"
            ) from exc

        # --------------------------------------------------------------
        # 4. Scenario construction
        # --------------------------------------------------------------

        scenarios = self._build_scenarios()

        scenario_engine = ScenarioEngine(
            state
        )

        # --------------------------------------------------------------
        # 5. Scenario simulation
        # --------------------------------------------------------------

        scenario_results = self._simulate_scenarios(
            scenario_engine,
            scenarios,
        )

        # --------------------------------------------------------------
        # 6. Baseline / interventions
        # --------------------------------------------------------------

        (
            baseline_result,
            intervention_results,
        ) = self._split_baseline(
            scenario_results
        )

        # --------------------------------------------------------------
        # 7. Confidence
        # --------------------------------------------------------------

        confidence = (
            self.data_confidence
            or str(
                state["data_confidence"]
            )
        )

        # --------------------------------------------------------------
        # 8. Decision optimization
        # --------------------------------------------------------------

        try:
            decision = DecisionOptimizer(
                baseline_result=baseline_result,
                scenario_results=intervention_results,
                data_confidence=confidence,
            ).optimize()
        except Exception as exc:
            raise RuntimeError(
                "Decision pipeline failed during decision "
                f"optimization: {exc}"
            ) from exc

        if not isinstance(decision, dict):
            raise RuntimeError(
                "Decision pipeline received a non-dictionary "
                "decision result."
            )

        # --------------------------------------------------------------
        # 9. Policy / financial safety gate
        # --------------------------------------------------------------

        policy = self._evaluate_policy(
            decision=decision,
            scenario_results=scenario_results,
            baseline_result=baseline_result,
            data_confidence=confidence,
        )

        # --------------------------------------------------------------
        # 10. Action construction
        # --------------------------------------------------------------

        action = self._build_action_from_policy(
            policy
        )

        # --------------------------------------------------------------
        # 11. Execution + verification
        # --------------------------------------------------------------

        if action is None:
            execution = None
            verification = None

        else:
            execution = self._execute_action(
                action
            )

            verification = self._verify_execution(
                action,
                execution,
            )

        # --------------------------------------------------------------
        # 12. Public result
        # --------------------------------------------------------------

        result: Dict[str, object] = {
            "financial_state": state,
            "risks": risks,
            "root_causes": root_causes,
            "scenarios": scenario_results,
            "decision": decision,
            "policy": policy,
            "action": (
                None
                if action is None
                else action.to_dict()
            ),
            "execution": execution,
            "verification": verification,
            "metadata": {
                "simulation_runs": int(
                    self.simulation_runs
                ),
                "horizon_months": int(
                    self.horizon_months
                ),
                "random_seed": (
                    None
                    if self.random_seed is None
                    else int(self.random_seed)
                ),
            },
        }

        # Final public-contract validation.
        self._validate_output_numbers(
            result,
            "result",
        )

        return result