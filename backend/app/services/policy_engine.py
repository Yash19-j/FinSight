from __future__ import annotations

import copy
import math
from numbers import Integral, Real
from typing import Dict, List, Mapping, Optional


class PolicyEngine:
    """Deterministic safety gate for an optimizer-selected scenario.

    The policy engine validates an optimizer recommendation against
    execution-safety rules.

    Possible outcomes:

        APPROVE
        MODIFY
        BLOCK

    The engine does not perform simulation or optimization.

    Financial safety is evaluated only when an authoritative baseline
    scenario result is supplied by DecisionPipeline.
    """

    MAX_REVENUE_GROWTH_ADJUSTMENT = 0.20
    MAX_EXPENSE_REDUCTION_APPROVE = 0.30
    MAX_EXPENSE_REDUCTION_MODIFY = 0.50

    DEFAULT_MAX_CAPITAL_REQUIRED = 0.0

    CONFIDENCE_VALUES = {
        "HIGH": 1.0,
        "MEDIUM": 0.9,
        "LOW": 0.75,
    }

    SUPPORTED_SCENARIO_TYPES = {
        "BASELINE",
        "REVENUE_GROWTH",
        "EXPENSE_REDUCTION",
        "COMBINED",
    }

    def __init__(
        self,
        decision: Mapping[str, object],
        data_confidence: Optional[str] = None,
        max_capital_required: float = DEFAULT_MAX_CAPITAL_REQUIRED,
    ) -> None:
        if not isinstance(decision, dict):
            raise ValueError("decision must be a dictionary.")

        self.decision = copy.deepcopy(decision)

        self.data_confidence = self._resolve_confidence(
            data_confidence
        )

        self.max_capital_required = self._finite_float(
            max_capital_required,
            "max_capital_required",
        )

        if self.max_capital_required < 0.0:
            raise ValueError(
                "max_capital_required cannot be negative."
            )

        self.baseline_result = self._resolve_baseline_result()

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _resolve_confidence(
        self,
        explicit_confidence: Optional[str],
    ) -> str:
        value = explicit_confidence

        if value is None:
            value = self._find_decision_confidence(
                self.decision
            )

        if value is None:
            raise ValueError(
                "data_confidence must be supplied as HIGH, MEDIUM, or LOW."
            )

        confidence = str(value).upper()

        if confidence not in self.CONFIDENCE_VALUES:
            raise ValueError(
                "data_confidence must be one of HIGH, MEDIUM, or LOW."
            )

        return confidence

    @staticmethod
    def _find_decision_confidence(
        decision: Optional[Mapping[str, object]],
    ) -> Optional[str]:
        if decision is None:
            return None

        containers = (
            decision,
            decision.get("baseline"),
            decision.get("baseline_result"),
        )

        for container in containers:
            if isinstance(container, dict):
                value = container.get("data_confidence")

                if value is not None:
                    return str(value)

        return None

    # ------------------------------------------------------------------
    # Numeric validation
    # ------------------------------------------------------------------

    @staticmethod
    def _finite_float(
        value: object,
        field: str,
    ) -> float:
        if isinstance(value, bool):
            raise ValueError(
                f"{field} must be a finite numeric value."
            )

        if not isinstance(value, Real):
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{field} must be a finite numeric value."
                ) from exc

        numeric = float(value)

        if not math.isfinite(numeric):
            raise ValueError(
                f"{field} must be finite."
            )

        return numeric

    @classmethod
    def _validate_finite_recursive(
        cls,
        value: object,
        path: str,
    ) -> None:
        if value is None:
            return

        if isinstance(value, bool):
            return

        if isinstance(value, Real):
            numeric = float(value)

            if not math.isfinite(numeric):
                raise RuntimeError(
                    f"Policy output '{path}' contains a non-finite value."
                )

            return

        if isinstance(value, Mapping):
            for key, item in value.items():
                cls._validate_finite_recursive(
                    item,
                    f"{path}.{key}",
                )

            return

        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                cls._validate_finite_recursive(
                    item,
                    f"{path}[{index}]",
                )

            return

    # ------------------------------------------------------------------
    # Baseline resolution
    # ------------------------------------------------------------------

    def _resolve_baseline_result(
        self,
    ) -> Optional[Dict[str, object]]:
        """Resolve authoritative baseline information.

        DecisionPipeline supplies the authoritative ScenarioEngine result
        using ``baseline_result``.

        Direct PolicyEngine callers may omit it. In that case the financial
        safety gate is skipped because there is no authoritative baseline
        against which to compare the selected scenario.
        """

        baseline = self.decision.get(
            "baseline_result"
        )

        if isinstance(baseline, dict):
            return baseline

        baseline = self.decision.get(
            "baseline"
        )

        if isinstance(baseline, dict):
            return baseline

        return None

    # ------------------------------------------------------------------
    # Scenario helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_scenario_type(
        action: Mapping[str, object],
    ) -> str:
        """Infer the supported scenario type."""

        explicit_type = action.get(
            "scenario_type"
        )

        if explicit_type is not None:
            scenario_type = str(
                explicit_type
            ).upper()

            if scenario_type in PolicyEngine.SUPPORTED_SCENARIO_TYPES:
                return scenario_type

            raise ValueError(
                f"Unsupported scenario type '{explicit_type}'."
            )

        scenario_id = str(
            action.get(
                "scenario_id",
                "",
            )
        ).lower()

        scenario_name = str(
            action.get(
                "scenario_name",
                "",
            )
        ).lower()

        identifier = (
            f"{scenario_id} {scenario_name}"
        )

        if scenario_id == "baseline":
            return "BASELINE"

        if (
            "combined" in identifier
            or (
                "revenue" in identifier
                and "expense" in identifier
            )
        ):
            return "COMBINED"

        if (
            "expense_reduction" in identifier
            or "expense reduction" in identifier
        ):
            return "EXPENSE_REDUCTION"

        if (
            "revenue_growth" in identifier
            or "revenue growth" in identifier
        ):
            return "REVENUE_GROWTH"

        raise ValueError(
            "Unable to determine a supported scenario type."
        )

    @staticmethod
    def _rule(
        rule: str,
        status: str,
        requested: object = None,
        limit: object = None,
    ) -> Dict[str, object]:
        result: Dict[str, object] = {
            "rule": rule,
            "status": status,
        }

        if requested is not None:
            result["requested"] = requested

        if limit is not None:
            result["limit"] = limit

        return result

    # ------------------------------------------------------------------
    # Policy limits
    # ------------------------------------------------------------------

    def _policy_limits(self) -> Dict[str, object]:
        return {
            "max_revenue_growth_adjustment": float(
                self.MAX_REVENUE_GROWTH_ADJUSTMENT
            ),
            "max_expense_reduction_approve": float(
                self.MAX_EXPENSE_REDUCTION_APPROVE
            ),
            "max_expense_reduction_modify": float(
                self.MAX_EXPENSE_REDUCTION_MODIFY
            ),
            "max_capital_required": float(
                self.max_capital_required
            ),
        }

    # ------------------------------------------------------------------
    # Financial safety gate
    # ------------------------------------------------------------------

    def _financial_safety_gate(
        self,
        action: Mapping[str, object],
    ) -> Optional[str]:
        """Block risky interventions that do not reduce shortfall risk.

        This gate only activates when DecisionPipeline supplies an
        authoritative baseline result.

        Standalone PolicyEngine tests/callers do not have that baseline,
        so the existing policy rules continue to operate unchanged.
        """

        if self.baseline_result is None:
            return None

        baseline_shortfall_value = self.baseline_result.get(
            "probability_of_cash_shortfall"
        )

        scenario_shortfall_value = action.get(
            "probability_of_cash_shortfall"
        )

        # The financial-safety metric is authoritative only when supplied
        # by ScenarioEngine. Do not invent a value for direct callers.
        if (
            baseline_shortfall_value is None
            or scenario_shortfall_value is None
        ):
            return None

        baseline_shortfall = self._finite_float(
            baseline_shortfall_value,
            "baseline_result.probability_of_cash_shortfall",
        )

        scenario_shortfall = self._finite_float(
            scenario_shortfall_value,
            "recommended_scenario.probability_of_cash_shortfall",
        )

        # If baseline is already safe, an intervention does not need to
        # reduce shortfall probability further.
        if baseline_shortfall <= 1e-12:
            return None

        # If the company is exposed to shortfall and the selected
        # intervention does not reduce that risk, automatic execution
        # must be blocked.
        if scenario_shortfall >= baseline_shortfall - 1e-12:
            return (
                "Selected intervention does not reduce the probability of "
                "cash shortfall relative to baseline."
            )

        return None

    # ------------------------------------------------------------------
    # Main evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> Dict[str, object]:
        recommended = self.decision.get(
            "recommended_scenario"
        )

        if not isinstance(recommended, dict):
            raise ValueError(
                "recommended_scenario must be a dictionary."
            )

        action = copy.deepcopy(
            recommended
        )

        scenario_id = action.get(
            "scenario_id"
        )

        if (
            not isinstance(scenario_id, str)
            or not scenario_id.strip()
        ):
            raise ValueError(
                "recommended_scenario.scenario_id must be a "
                "non-empty string."
            )

        scenario_name = action.get(
            "scenario_name"
        )

        if (
            not isinstance(scenario_name, str)
            or not scenario_name.strip()
        ):
            raise ValueError(
                "recommended_scenario.scenario_name must be a "
                "non-empty string."
            )

        assumptions = action.get(
            "assumptions"
        )

        if not isinstance(assumptions, dict):
            raise ValueError(
                "recommended_scenario.assumptions must be a dictionary."
            )

        scenario_type = self._infer_scenario_type(
            action
        )

        rules: List[Dict[str, object]] = []
        violations: List[str] = []
        warnings: List[str] = []
        reasoning: List[str] = []

        # --------------------------------------------------------------
        # BASELINE
        # --------------------------------------------------------------

        if scenario_type == "BASELINE":
            rules.append(
                self._rule(
                    "BASELINE_NO_ACTION",
                    "PASS",
                )
            )

            reasoning.append(
                "Baseline is a valid no-action outcome."
            )

            confidence = self.CONFIDENCE_VALUES[
                self.data_confidence
            ]

            if self.data_confidence == "LOW":
                rules.append(
                    self._rule(
                        "DATA_CONFIDENCE",
                        "BLOCK",
                        self.data_confidence,
                    )
                )

                violations.append(
                    "Automatic execution is blocked because "
                    "data confidence is LOW."
                )

                reasoning.append(
                    "Recommendation may still be presented to the user, "
                    "but automatic execution is blocked because data "
                    "confidence is LOW."
                )

            elif self.data_confidence == "MEDIUM":
                rules.append(
                    self._rule(
                        "DATA_CONFIDENCE",
                        "PASS",
                        self.data_confidence,
                    )
                )

                warnings.append(
                    "Data confidence is MEDIUM."
                )

                reasoning.append(
                    "Data confidence is MEDIUM; the recommendation remains "
                    "eligible under policy."
                )

            else:
                rules.append(
                    self._rule(
                        "DATA_CONFIDENCE",
                        "PASS",
                        self.data_confidence,
                    )
                )

                reasoning.append(
                    "Data confidence is HIGH."
                )

            if violations:
                status = "BLOCK"
                approved_action = None

                reasoning.extend(
                    violations
                )

                reasoning.append(
                    "Automatic execution is blocked under the configured "
                    "policy."
                )
            else:
                status = "APPROVE"
                approved_action = copy.deepcopy(
                    action
                )

            result = {
                "status": status,
                "original_action": action,
                "approved_action": approved_action,
                "policy": {
                    "rules_evaluated": rules,
                    "violations": violations,
                    "warnings": warnings,
                },
                "reasoning": reasoning,
                "confidence": float(
                    confidence
                ),
                "policy_limits": self._policy_limits(),
                "capital_required": 0.0,
                "capital_limit": float(
                    self.max_capital_required
                ),
            }

            self._validate_output(
                result
            )

            return result

        # --------------------------------------------------------------
        # INTERVENTION ASSUMPTIONS
        # --------------------------------------------------------------

        revenue_growth = self._finite_float(
            assumptions.get(
                "revenue_growth_adjustment",
                0.0,
            ),
            "assumptions.revenue_growth_adjustment",
        )

        if scenario_type in {
            "EXPENSE_REDUCTION",
            "COMBINED",
        } and "expense_reduction" not in assumptions:
            raise ValueError(
                "assumptions.expense_reduction is required."
            )

        expense_reduction = self._finite_float(
            assumptions.get(
                "expense_reduction",
                0.0,
            ),
            "assumptions.expense_reduction",
        )

        capital_required = max(
            0.0,
            self._finite_float(
                assumptions.get(
                    "one_time_cash_adjustment",
                    0.0,
                ),
                "assumptions.one_time_cash_adjustment",
            ),
        )

        duration_months = assumptions.get(
            "duration_months"
        )

        if duration_months is None:
            raise ValueError(
                "assumptions.duration_months is required."
            )

        if isinstance(
            duration_months,
            bool,
        ):
            raise ValueError(
                "assumptions.duration_months must be an integer."
            )

        if not isinstance(
            duration_months,
            Integral,
        ):
            try:
                duration_numeric = float(
                    duration_months
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "assumptions.duration_months must be an integer."
                ) from exc

            if not duration_numeric.is_integer():
                raise ValueError(
                    "assumptions.duration_months must be an integer."
                )

            duration_months = int(
                duration_numeric
            )

        duration_months = int(
            duration_months
        )

        if duration_months <= 0:
            raise ValueError(
                "assumptions.duration_months must be positive."
            )

        # --------------------------------------------------------------
        # CAPITAL POLICY
        # --------------------------------------------------------------

        if capital_required > self.max_capital_required:
            rules.append(
                self._rule(
                    "MAX_CAPITAL_REQUIRED",
                    "BLOCK",
                    capital_required,
                    self.max_capital_required,
                )
            )

            violations.append(
                "Required capital exceeds the configured capital limit."
            )

        else:
            rules.append(
                self._rule(
                    "MAX_CAPITAL_REQUIRED",
                    "PASS",
                    capital_required,
                    self.max_capital_required,
                )
            )

            reasoning.append(
                "Required capital is within the configured policy limit."
            )

        # --------------------------------------------------------------
        # EXPENSE REDUCTION POLICY
        # --------------------------------------------------------------

        expense_requires_modify = False

        if scenario_type in {
            "EXPENSE_REDUCTION",
            "COMBINED",
        }:
            if not (
                0.0
                <= expense_reduction
                <= 1.0
            ):
                raise ValueError(
                    "expense_reduction must be between 0 and 1."
                )

            if (
                expense_reduction
                > self.MAX_EXPENSE_REDUCTION_MODIFY
            ):
                rules.append(
                    self._rule(
                        "MAX_EXPENSE_REDUCTION",
                        "BLOCK",
                        expense_reduction,
                        self.MAX_EXPENSE_REDUCTION_MODIFY,
                    )
                )

                violations.append(
                    "Expense reduction exceeds the maximum policy "
                    "limit of 50%."
                )

            elif (
                expense_reduction
                > self.MAX_EXPENSE_REDUCTION_APPROVE
            ):
                expense_requires_modify = True

                rules.append(
                    self._rule(
                        "MAX_EXPENSE_REDUCTION",
                        "MODIFY",
                        expense_reduction,
                        self.MAX_EXPENSE_REDUCTION_APPROVE,
                    )
                )

            else:
                rules.append(
                    self._rule(
                        "MAX_EXPENSE_REDUCTION",
                        "PASS",
                        expense_reduction,
                        self.MAX_EXPENSE_REDUCTION_APPROVE,
                    )
                )

                reasoning.append(
                    "Expense reduction is within the approved 30% "
                    "policy limit."
                )

        # --------------------------------------------------------------
        # REVENUE GROWTH POLICY
        # --------------------------------------------------------------

        revenue_requires_modify = False

        if scenario_type in {
            "REVENUE_GROWTH",
            "COMBINED",
        }:
            if revenue_growth > (
                self.MAX_REVENUE_GROWTH_ADJUSTMENT
            ):
                revenue_requires_modify = True

                rules.append(
                    self._rule(
                        "MAX_REVENUE_GROWTH_ADJUSTMENT",
                        "MODIFY",
                        revenue_growth,
                        self.MAX_REVENUE_GROWTH_ADJUSTMENT,
                    )
                )

            else:
                rules.append(
                    self._rule(
                        "MAX_REVENUE_GROWTH_ADJUSTMENT",
                        "PASS",
                        revenue_growth,
                        self.MAX_REVENUE_GROWTH_ADJUSTMENT,
                    )
                )

                reasoning.append(
                    "Revenue growth assumption is within the approved "
                    "20% policy limit."
                )

        # --------------------------------------------------------------
        # FINANCIAL SAFETY
        # --------------------------------------------------------------

        financial_safety_violation = (
            self._financial_safety_gate(
                action
            )
        )

        if financial_safety_violation is not None:
            rules.append(
                self._rule(
                    "FINANCIAL_SAFETY",
                    "BLOCK",
                    action.get(
                        "probability_of_cash_shortfall"
                    ),
                    (
                        None
                        if self.baseline_result is None
                        else self.baseline_result.get(
                            "probability_of_cash_shortfall"
                        )
                    ),
                )
            )

            violations.append(
                financial_safety_violation
            )

        elif self.baseline_result is not None:
            baseline_shortfall_value = (
                self.baseline_result.get(
                    "probability_of_cash_shortfall"
                )
            )

            scenario_shortfall_value = action.get(
                "probability_of_cash_shortfall"
            )

            # Only expose the financial-safety PASS rule when the
            # authoritative metrics actually exist.
            if (
                baseline_shortfall_value is not None
                and scenario_shortfall_value is not None
            ):
                baseline_shortfall = self._finite_float(
                    baseline_shortfall_value,
                    "baseline_result.probability_of_cash_shortfall",
                )

                if baseline_shortfall > 0.0:
                    rules.append(
                        self._rule(
                            "FINANCIAL_SAFETY",
                            "PASS",
                        )
                    )

                    reasoning.append(
                        "Selected intervention reduces the probability of "
                        "cash shortfall relative to baseline."
                    )

                else:
                    rules.append(
                        self._rule(
                            "FINANCIAL_SAFETY",
                            "PASS",
                        )
                    )

                    reasoning.append(
                        "Baseline cash-shortfall probability is zero; "
                        "financial-safety reduction is not required."
                    )

        # --------------------------------------------------------------
        # DATA CONFIDENCE
        # --------------------------------------------------------------

        confidence = self.CONFIDENCE_VALUES[
            self.data_confidence
        ]

        if self.data_confidence == "LOW":
            rules.append(
                self._rule(
                    "DATA_CONFIDENCE",
                    "BLOCK",
                    self.data_confidence,
                )
            )

            violations.append(
                "Automatic execution is blocked because data "
                "confidence is LOW."
            )

            reasoning.append(
                "Recommendation may still be presented to the user, "
                "but automatic execution is blocked because data "
                "confidence is LOW."
            )

        elif self.data_confidence == "MEDIUM":
            rules.append(
                self._rule(
                    "DATA_CONFIDENCE",
                    "PASS",
                    self.data_confidence,
                )
            )

            warnings.append(
                "Data confidence is MEDIUM."
            )

            reasoning.append(
                "Data confidence is MEDIUM; the recommendation remains "
                "eligible under policy."
            )

        else:
            rules.append(
                self._rule(
                    "DATA_CONFIDENCE",
                    "PASS",
                    self.data_confidence,
                )
            )

            reasoning.append(
                "Data confidence is HIGH."
            )

        # --------------------------------------------------------------
        # FINAL POLICY DECISION
        # --------------------------------------------------------------

        if violations:
            status = "BLOCK"
            approved_action = None

            reasoning.extend(
                violations
            )

            reasoning.append(
                "Automatic execution is blocked under the configured "
                "policy."
            )

        elif (
            expense_requires_modify
            or revenue_requires_modify
        ):
            status = "MODIFY"

            approved_action = copy.deepcopy(
                action
            )

            approved_assumptions = approved_action[
                "assumptions"
            ]

            if expense_requires_modify:
                approved_assumptions[
                    "expense_reduction"
                ] = float(
                    self.MAX_EXPENSE_REDUCTION_APPROVE
                )

                reasoning.append(
                    "Action was modified to the maximum permitted "
                    "expense reduction of 30%."
                )

            if revenue_requires_modify:
                approved_assumptions[
                    "revenue_growth_adjustment"
                ] = float(
                    self.MAX_REVENUE_GROWTH_ADJUSTMENT
                )

                reasoning.append(
                    "Action was modified to the maximum permitted "
                    "revenue growth assumption of 20%."
                )

        else:
            status = "APPROVE"

            approved_action = copy.deepcopy(
                action
            )

            reasoning.append(
                "All applicable policy rules passed."
            )

        result = {
            "status": status,
            "original_action": action,
            "approved_action": approved_action,
            "policy": {
                "rules_evaluated": rules,
                "violations": violations,
                "warnings": warnings,
            },
            "reasoning": reasoning,
            "confidence": float(
                confidence
            ),
            "policy_limits": self._policy_limits(),
            "capital_required": float(
                capital_required
            ),
            "capital_limit": float(
                self.max_capital_required
            ),
        }

        self._validate_output(
            result
        )

        return result

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    @classmethod
    def _validate_output(
        cls,
        result: Mapping[str, object],
    ) -> None:
        status = result.get(
            "status"
        )

        if status not in {
            "APPROVE",
            "MODIFY",
            "BLOCK",
        }:
            raise RuntimeError(
                "Policy output contains an invalid status."
            )

        confidence = float(
            result["confidence"]
        )

        if (
            not math.isfinite(confidence)
            or not 0.0 <= confidence <= 1.0
        ):
            raise RuntimeError(
                "Policy confidence must be between 0 and 1 and finite."
            )

        cls._validate_finite_recursive(
            result,
            "policy_output",
        )