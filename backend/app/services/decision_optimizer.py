from __future__ import annotations

import math
from typing import Dict, List, Mapping, Optional, Sequence


class DecisionOptimizer:
    """
    Deterministically rank already-simulated financial scenarios.

    This class does not simulate, forecast, or alter ScenarioEngine results.
    It compares each intervention against an explicit baseline, normalizes
    baseline-relative improvements, applies a bounded capital penalty, then
    applies the supplied financial-state confidence multiplier.

    Base score:
        raw_score =
            0.40 * normalized_survival
          + 0.25 * normalized_downside
          + 0.20 * normalized_ending_cash
          + 0.15 * normalized_horizon

        decision_score = clamp(50 + 50 * raw_score, 0, 100)

    Capital adjustment:
        capital_penalty =
            0, if capital_required <= 0
            min(
                capital_required /
                max(abs(ending_cash_improvement), 1.0),
                1.0
            ), otherwise

        risk_adjusted_score =
            decision_score * (1 - 0.20 * capital_penalty)

    Confidence adjustment:
        confidence_adjusted_score =
            risk_adjusted_score * confidence_multiplier

    The capital penalty is deliberately bounded at a 20% maximum reduction.
    It is not an additional weighted scoring dimension, preserving the stated
    40/25/20/15 decision-score model.

    Material improvement for recommendation:
        normalized survival improvement >= 0.05
        OR
        normalized downside improvement >= 0.05

    Recommendation thresholds are applied to the confidence-adjusted score:
        >= 70 -> RECOMMEND
        >= 50 -> CONSIDER
        < 50  -> NO_ACTION
    """

    EPSILON = 1e-12
    CAPITAL_PENALTY_MAX = 0.20
    MATERIAL_IMPROVEMENT_THRESHOLD = 0.05

    CONFIDENCE_MULTIPLIERS = {
        "HIGH": 1.00,
        "MEDIUM": 0.90,
        "LOW": 0.75,
    }

    REQUIRED_RESULT_FIELDS = (
        "scenario_id",
        "scenario_name",
        "horizon_months",
        "simulation_runs",
        "survival_probability",
        "mean_ending_cash",
        "median_ending_cash",
        "p10_ending_cash",
        "p90_ending_cash",
        "mean_survival_month",
        "probability_of_cash_shortfall",
        "baseline",
        "assumptions",
    )

    REQUIRED_ASSUMPTION_FIELDS = (
        "revenue_growth_adjustment",
        "expense_growth_adjustment",
        "one_time_cash_adjustment",
        "duration_months",
    )

    def __init__(
        self,
        baseline_result: Mapping[str, object],
        scenario_results: Sequence[Mapping[str, object]],
        data_confidence: Optional[str] = None,
    ) -> None:
        if not isinstance(baseline_result, dict):
            raise ValueError("baseline_result must be a dictionary.")

        if not isinstance(scenario_results, list):
            raise ValueError("scenario_results must be a list.")

        self.baseline_result = dict(baseline_result)
        self.scenario_results = [dict(result) for result in scenario_results]

        self._validate_result(
            self.baseline_result,
            result_label="baseline_result",
        )

        if self.baseline_result["baseline"] is not True:
            raise ValueError("baseline_result must have baseline=True.")

        self.data_confidence = self._resolve_confidence(data_confidence)

        self._validate_scenarios()

    def _resolve_confidence(
        self,
        explicit_confidence: Optional[str],
    ) -> str:
        confidence_value = explicit_confidence
        if confidence_value is None and "data_confidence" in self.baseline_result:
            confidence_value = str(self.baseline_result["data_confidence"])
        if confidence_value is None:
            # ScenarioEngine results do not currently expose data confidence.
            # MEDIUM is the conservative neutral default when the caller does
            # not provide FinancialState confidence separately.
            return "MEDIUM"

        confidence = str(confidence_value).upper()
        if confidence not in self.CONFIDENCE_MULTIPLIERS:
            raise ValueError(
                "data_confidence must be one of HIGH, MEDIUM, or LOW."
            )
        return confidence

    @staticmethod
    def _finite_float(value: object, field: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{field} must be a finite numeric value.")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be a finite numeric value.") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"{field} must be finite.")
        return numeric

    def _validate_result(
        self,
        result: Mapping[str, object],
        *,
        result_label: str,
    ) -> None:
        if not isinstance(result, dict):
            raise ValueError(f"{result_label} must be a dictionary.")

        missing = [
            field for field in self.REQUIRED_RESULT_FIELDS if field not in result
        ]
        if missing:
            raise ValueError(
                f"{result_label} is missing required fields: {missing}"
            )

        if not isinstance(result["scenario_id"], str) or not result["scenario_id"]:
            raise ValueError(f"{result_label}.scenario_id must be a non-empty string.")

        if not isinstance(result["scenario_name"], str):
            raise ValueError(f"{result_label}.scenario_name must be a string.")

        horizon = result["horizon_months"]
        if isinstance(horizon, bool):
            raise ValueError(f"{result_label}.horizon_months must be positive.")
        try:
            horizon_int = int(horizon)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{result_label}.horizon_months must be positive."
            ) from exc
        if horizon_int != horizon or horizon_int <= 0:
            raise ValueError(f"{result_label}.horizon_months must be positive.")

        runs = result["simulation_runs"]
        if isinstance(runs, bool):
            raise ValueError(f"{result_label}.simulation_runs must be positive.")
        try:
            runs_int = int(runs)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{result_label}.simulation_runs must be positive."
            ) from exc
        if runs_int != runs or runs_int <= 0:
            raise ValueError(f"{result_label}.simulation_runs must be positive.")

        for field in (
            "survival_probability",
            "probability_of_cash_shortfall",
        ):
            value = self._finite_float(result[field], f"{result_label}.{field}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{result_label}.{field} must be between 0 and 1."
                )

        for field in (
            "mean_ending_cash",
            "median_ending_cash",
            "p10_ending_cash",
            "p90_ending_cash",
            "mean_survival_month",
        ):
            self._finite_float(result[field], f"{result_label}.{field}")

        if not isinstance(result["baseline"], bool):
            raise ValueError(f"{result_label}.baseline must be boolean.")

        assumptions = result["assumptions"]
        if not isinstance(assumptions, dict):
            raise ValueError(f"{result_label}.assumptions must be a dictionary.")

        missing_assumptions = [
            field
            for field in self.REQUIRED_ASSUMPTION_FIELDS
            if field not in assumptions
        ]
        if missing_assumptions:
            raise ValueError(
                f"{result_label}.assumptions is missing required fields: "
                f"{missing_assumptions}"
            )

        for field in self.REQUIRED_ASSUMPTION_FIELDS:
            self._finite_float(
                assumptions[field],
                f"{result_label}.assumptions.{field}",
            )

        duration = assumptions["duration_months"]
        if isinstance(duration, bool):
            raise ValueError(
                f"{result_label}.assumptions.duration_months must be positive."
            )
        try:
            duration_int = int(duration)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{result_label}.assumptions.duration_months must be positive."
            ) from exc
        if duration_int != duration or duration_int <= 0:
            raise ValueError(
                f"{result_label}.assumptions.duration_months must be positive."
            )

    def _validate_scenarios(self) -> None:
        seen_ids = set()

        for index, scenario in enumerate(self.scenario_results):
            label = f"scenario_results[{index}]"
            self._validate_result(scenario, result_label=label)

            scenario_id = scenario["scenario_id"]
            if scenario_id == self.baseline_result["scenario_id"]:
                if scenario["baseline"] is True:
                    continue
                raise ValueError(
                    "A scenario using the baseline scenario_id must have baseline=True."
                )

            if scenario_id in seen_ids:
                raise ValueError(
                    f"Duplicate intervention scenario_id: {scenario_id}"
                )
            seen_ids.add(scenario_id)

            if scenario["baseline"] is True:
                # A baseline result supplied under a different ID is not an
                # intervention and is safely excluded from ranking.
                continue

            if scenario["horizon_months"] != self.baseline_result["horizon_months"]:
                raise ValueError(
                    f"Scenario '{scenario_id}' horizon_months must match "
                    "baseline_result.horizon_months for a valid comparison."
                )

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _normalize_probability_improvement(
        self,
        improvement: float,
        baseline_probability: float,
    ) -> float:
        denominator = max(1.0 - baseline_probability, self.EPSILON)
        return self._clamp(improvement / denominator, -1.0, 1.0)

    def _normalize_horizon_improvement(
        self,
        improvement: float,
        horizon: float,
        baseline_mean_survival_month: float,
    ) -> float:
        denominator = max(
            horizon - baseline_mean_survival_month,
            self.EPSILON,
        )
        return self._clamp(improvement / denominator, -1.0, 1.0)

    def _normalize_financial_improvement(
        self,
        improvement: float,
        baseline_value: float,
    ) -> float:
        denominator = max(abs(baseline_value), 1.0)
        return self._clamp(improvement / denominator, -1.0, 1.0)

    def _capital_penalty(
        self,
        capital_required: float,
        ending_cash_improvement: float,
    ) -> float:
        if capital_required <= 0.0:
            return 0.0

        denominator = max(abs(ending_cash_improvement), 1.0)
        return self._clamp(
            capital_required / denominator,
            0.0,
            1.0,
        )

    def _classification(self, score: float) -> str:
        if score >= 70.0:
            return "RECOMMEND"
        if score >= 50.0:
            return "CONSIDER"
        return "NO_ACTION"

    def _build_reasoning(
        self,
        scenario: Mapping[str, object],
        *,
        survival_improvement: float,
        downside_improvement: float,
        ending_cash_improvement: float,
        horizon_improvement: float,
        capital_required: float,
        capital_penalty: float,
        confidence: str,
        classification: str,
    ) -> List[str]:
        reasoning: List[str] = []

        if survival_improvement > 0:
            reasoning.append(
                f"Survival probability improves by "
                f"{survival_improvement * 100:.2f} percentage points "
                "relative to baseline."
            )
        elif survival_improvement < 0:
            reasoning.append(
                f"Survival probability declines by "
                f"{abs(survival_improvement) * 100:.2f} percentage points "
                "relative to baseline."
            )
        else:
            reasoning.append("Survival probability is unchanged from baseline.")

        if downside_improvement > 0:
            reasoning.append(
                f"P10 ending cash improves by ₹{downside_improvement:,.2f} "
                "relative to baseline."
            )
        elif downside_improvement < 0:
            reasoning.append(
                f"P10 ending cash worsens by ₹{abs(downside_improvement):,.2f} "
                "relative to baseline."
            )
        else:
            reasoning.append("P10 ending cash is unchanged from baseline.")

        if ending_cash_improvement > 0:
            reasoning.append(
                f"Mean ending cash improves by ₹{ending_cash_improvement:,.2f} "
                "relative to baseline."
            )
        elif ending_cash_improvement < 0:
            reasoning.append(
                f"Mean ending cash declines by ₹{abs(ending_cash_improvement):,.2f} "
                "relative to baseline."
            )
        else:
            reasoning.append("Mean ending cash is unchanged from baseline.")

        if horizon_improvement > 0:
            reasoning.append(
                f"Mean survival horizon improves by "
                f"{horizon_improvement:.2f} months."
            )
        elif horizon_improvement < 0:
            reasoning.append(
                f"Mean survival horizon declines by "
                f"{abs(horizon_improvement):.2f} months."
            )
        else:
            reasoning.append("Mean survival horizon is unchanged from baseline.")

        if capital_required > 0:
            reasoning.append(
                f"The intervention requires ₹{capital_required:,.2f} of "
                f"additional capital; the bounded capital penalty is "
                f"{capital_penalty * 100:.2f}%."
            )
        else:
            reasoning.append("The intervention requires no additional capital.")

        reasoning.append(
            f"The scenario uses {confidence} data confidence."
        )

        if classification == "RECOMMEND":
            reasoning.append(
                "Under the tested scenario assumptions, this option produces "
                "the strongest risk-adjusted outcome."
            )
        elif classification == "CONSIDER":
            reasoning.append(
                "Under the tested scenario assumptions, this option shows "
                "useful but not decisive risk-adjusted improvement."
            )
        else:
            reasoning.append(
                "The scenario does not provide sufficient risk-adjusted "
                "improvement over baseline."
            )

        return reasoning

    def _score_scenario(self, scenario: Mapping[str, object]) -> Dict[str, object]:
        baseline = self.baseline_result

        survival_improvement = (
            float(scenario["survival_probability"])
            - float(baseline["survival_probability"])
        )
        downside_improvement = (
            float(scenario["p10_ending_cash"])
            - float(baseline["p10_ending_cash"])
        )
        ending_cash_improvement = (
            float(scenario["mean_ending_cash"])
            - float(baseline["mean_ending_cash"])
        )
        survival_horizon_improvement = (
            float(scenario["mean_survival_month"])
            - float(baseline["mean_survival_month"])
        )

        horizon = float(baseline["horizon_months"])

        normalized_survival = self._normalize_probability_improvement(
            survival_improvement,
            float(baseline["survival_probability"]),
        )
        normalized_downside = self._normalize_financial_improvement(
            downside_improvement,
            float(baseline["p10_ending_cash"]),
        )
        normalized_ending_cash = self._normalize_financial_improvement(
            ending_cash_improvement,
            float(baseline["mean_ending_cash"]),
        )
        normalized_horizon = self._normalize_horizon_improvement(
            survival_horizon_improvement,
            horizon,
            float(baseline["mean_survival_month"]),
        )

        raw_score = (
            0.40 * normalized_survival
            + 0.25 * normalized_downside
            + 0.20 * normalized_ending_cash
            + 0.15 * normalized_horizon
        )
        raw_score = self._clamp(raw_score, -1.0, 1.0)

        decision_score = self._clamp(
            50.0 + 50.0 * raw_score,
            0.0,
            100.0,
        )

        assumptions = scenario["assumptions"]
        capital_required = max(
            0.0,
            float(assumptions["one_time_cash_adjustment"]),
        )

        capital_penalty = self._capital_penalty(
            capital_required,
            ending_cash_improvement,
        )

        # Keep the specified 40/25/20/15 score intact. The separate bounded
        # capital penalty affects the risk-adjusted score used for ranking.
        risk_adjusted_score = decision_score * (
            1.0 - self.CAPITAL_PENALTY_MAX * capital_penalty
        )

        confidence_multiplier = self.CONFIDENCE_MULTIPLIERS[
            self.data_confidence
        ]
        confidence_adjusted_score = (
            risk_adjusted_score * confidence_multiplier
        )
        confidence_adjusted_score = self._clamp(
            confidence_adjusted_score,
            0.0,
            100.0,
        )

        classification = self._classification(confidence_adjusted_score)

        reasoning = self._build_reasoning(
            scenario,
            survival_improvement=survival_improvement,
            downside_improvement=downside_improvement,
            ending_cash_improvement=ending_cash_improvement,
            horizon_improvement=survival_horizon_improvement,
            capital_required=capital_required,
            capital_penalty=capital_penalty,
            confidence=self.data_confidence,
            classification=classification,
        )

        item: Dict[str, object] = {
            "scenario_id": str(scenario["scenario_id"]),
            "scenario_name": str(scenario["scenario_name"]),
            "decision_score": float(decision_score),
            "raw_score": float(raw_score),
            "confidence_adjusted_score": float(confidence_adjusted_score),
            "classification": classification,
            "survival_improvement": float(survival_improvement),
            "downside_improvement": float(downside_improvement),
            "ending_cash_improvement": float(ending_cash_improvement),
            "survival_horizon_improvement": float(
                survival_horizon_improvement
            ),
            "capital_required": float(capital_required),
            "capital_penalty": float(capital_penalty),
            "confidence": float(confidence_multiplier),
            "reasoning": reasoning,
        }

        self._validate_ranking_item(item)
        return item

    @staticmethod
    def _validate_ranking_item(item: Mapping[str, object]) -> None:
        for field in (
            "decision_score",
            "raw_score",
            "confidence_adjusted_score",
            "survival_improvement",
            "downside_improvement",
            "ending_cash_improvement",
            "survival_horizon_improvement",
            "capital_required",
            "capital_penalty",
            "confidence",
        ):
            value = float(item[field])
            if not math.isfinite(value):
                raise RuntimeError(
                    f"Decision optimizer output '{field}' became non-finite."
                )

        if not 0.0 <= float(item["decision_score"]) <= 100.0:
            raise RuntimeError("Decision score must be between 0 and 100.")
        if not -1.0 <= float(item["raw_score"]) <= 1.0:
            raise RuntimeError("Raw score must be between -1 and 1.")
        if not 0.0 <= float(item["confidence_adjusted_score"]) <= 100.0:
            raise RuntimeError(
                "Confidence-adjusted score must be between 0 and 100."
            )
        if not 0.0 <= float(item["capital_penalty"]) <= 1.0:
            raise RuntimeError("Capital penalty must be between 0 and 1.")
        if not 0.0 <= float(item["confidence"]) <= 1.0:
            raise RuntimeError("Confidence must be between 0 and 1.")

    def _materially_improves(self, item: Mapping[str, object]) -> bool:
        normalized_survival = self._normalize_probability_improvement(
            float(item["survival_improvement"]),
            float(self.baseline_result["survival_probability"]),
        )
        normalized_downside = self._normalize_financial_improvement(
            float(item["downside_improvement"]),
            float(self.baseline_result["p10_ending_cash"]),
        )

        return (
            normalized_survival >= self.MATERIAL_IMPROVEMENT_THRESHOLD
            or normalized_downside >= self.MATERIAL_IMPROVEMENT_THRESHOLD
        )

    @staticmethod
    def _sort_key(item: Mapping[str, object]):
        # Python sorts tuples lexicographically. Negative values make the
        # first three metrics descending while scenario_id remains ascending.
        return (
            -float(item["confidence_adjusted_score"]),
            -float(item["_survival_probability"]),
            -float(item["_p10_ending_cash"]),
            -float(item["_mean_ending_cash"]),
            str(item["scenario_id"]),
        )

    def _build_baseline_output(self) -> Dict[str, object]:
        return dict(self.baseline_result)

    def _validate_final_output(self, result: Mapping[str, object]) -> None:
        decision = result["decision"]
        if not isinstance(decision, dict):
            raise RuntimeError("Decision output must be a dictionary.")

        for field in ("score", "confidence"):
            value = float(decision[field])
            if not math.isfinite(value):
                raise RuntimeError(
                    f"Final decision '{field}' became non-finite."
                )

        if not 0.0 <= float(decision["score"]) <= 100.0:
            raise RuntimeError("Final decision score must be between 0 and 100.")
        if not 0.0 <= float(decision["confidence"]) <= 1.0:
            raise RuntimeError(
                "Final decision confidence must be between 0 and 1."
            )

    def optimize(self) -> Dict[str, object]:
        """
        Compare all interventions against baseline and return a deterministic
        ranking plus the risk-adjusted recommendation.
        """
        ranking: List[Dict[str, object]] = []

        for scenario in self.scenario_results:
            if scenario["baseline"] is True:
                continue

            item = self._score_scenario(scenario)

            # Private sorting fields are removed before returning the contract.
            item["_survival_probability"] = float(
                scenario["survival_probability"]
            )
            item["_p10_ending_cash"] = float(scenario["p10_ending_cash"])
            item["_mean_ending_cash"] = float(scenario["mean_ending_cash"])
            ranking.append(item)

        ranking.sort(key=self._sort_key)

        for item in ranking:
            item.pop("_survival_probability", None)
            item.pop("_p10_ending_cash", None)
            item.pop("_mean_ending_cash", None)

        winner = ranking[0] if ranking else None
        winner_is_material = (
            winner is not None and self._materially_improves(winner)
        )

        if winner is not None and winner_is_material:
            decision = {
                "score": float(winner["confidence_adjusted_score"]),
                "confidence": float(winner["confidence"]),
                "classification": str(winner["classification"]),
            }

            if winner["classification"] == "NO_ACTION":
                recommended_scenario: Dict[str, object] = self._build_baseline_output()
                decision_reasoning = [
                    "No tested intervention reached the recommendation threshold "
                    "after capital and confidence adjustments."
                ]
            else:
                recommended_scenario = dict(winner)
                decision_reasoning = list(winner["reasoning"])
        else:
            recommended_scenario = self._build_baseline_output()
            decision = {
                "score": 50.0,
                "confidence": float(
                    self.CONFIDENCE_MULTIPLIERS[self.data_confidence]
                ),
                "classification": "NO_ACTION",
            }
            decision_reasoning = [
                "No tested intervention produced sufficient risk-adjusted "
                "improvement over doing nothing."
            ]

        result: Dict[str, object] = {
            "recommended_scenario": recommended_scenario,
            "ranking": ranking,
            "baseline": self._build_baseline_output(),
            "decision": decision,
            "reasoning": decision_reasoning,
        }

        self._validate_final_output(result)
        return result
