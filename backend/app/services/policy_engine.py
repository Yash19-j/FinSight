from __future__ import annotations

import copy
import math
from numbers import Integral, Real
from typing import Any, Dict, List, Mapping, Optional


class PolicyEngine:
    """Deterministic safety gate for an optimizer-selected scenario.

    The policy engine does not recalculate financial scores, simulate
    scenarios, or execute actions. It validates the optimizer recommendation
    against configurable execution-safety rules and returns one of APPROVE,
    MODIFY, or BLOCK.

    For intervention scenarios, the supported policy types are the scenario
    types produced by the current ScenarioEngine: REVENUE_GROWTH,
    EXPENSE_REDUCTION, and COMBINED. BASELINE is treated as no action and is
    therefore always approved.
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
        self.data_confidence = self._resolve_confidence(data_confidence)
        self.max_capital_required = self._finite_float(
            max_capital_required,
            "max_capital_required",
        )
        if self.max_capital_required < 0.0:
            raise ValueError("max_capital_required cannot be negative.")

    def _resolve_confidence(
        self,
        explicit_confidence: Optional[str],
    ) -> str:
        value = explicit_confidence
        if value is None:
            value = self._find_decision_confidence(self.decision)
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
    def _find_decision_confidence(decision: Optional[Mapping[str, object]]) -> Optional[str]:
        """Read an optional string confidence from a decision structure."""
        if decision is None:
            return None
        for container in (decision, decision.get("baseline")):
            if isinstance(container, dict):
                value = container.get("data_confidence")
                if value is not None:
                    return str(value)
        return None

    @staticmethod
    def _finite_float(value: object, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field} must be a finite numeric value.") from exc
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"{field} must be finite.")
        return numeric

    @classmethod
    def _validate_finite_recursive(cls, value: object, path: str) -> None:
        """Reject non-finite numeric values in an action or decision tree."""
        if value is None or isinstance(value, (str, bool)):
            return
        if isinstance(value, Real):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"{path} must be finite.")
            return
        if isinstance(value, Integral):
            return
        if isinstance(value, dict):
            for key, item in value.items():
                cls._validate_finite_recursive(item, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                cls._validate_finite_recursive(item, f"{path}[{index}]")
            return
        raise ValueError(
            f"{path} contains unsupported value type {type(value).__name__}."
        )

    @staticmethod
    def _scenario_type(action: Mapping[str, object]) -> str:
        explicit = action.get("scenario_type")
        if explicit is not None:
            scenario_type = str(explicit).upper()
        else:
            scenario_id = action.get("scenario_id")
            if not isinstance(scenario_id, str) or not scenario_id:
                raise ValueError("recommended_scenario.scenario_id must be a non-empty string.")
            if scenario_id == "baseline":
                scenario_type = "BASELINE"
            elif scenario_id.startswith("revenue_growth_"):
                scenario_type = "REVENUE_GROWTH"
            elif scenario_id.startswith("expense_reduction_"):
                scenario_type = "EXPENSE_REDUCTION"
            elif scenario_id.startswith("combined_revenue_"):
                scenario_type = "COMBINED"
            else:
                raise ValueError(
                    "Unsupported scenario type; provide a supported scenario_type."
                )

        if scenario_type not in PolicyEngine.SUPPORTED_SCENARIO_TYPES:
            raise ValueError(f"Unsupported scenario type: {scenario_type}")

        if scenario_type == "BASELINE":
            scenario_id = action.get("scenario_id")
            if scenario_id != "baseline" and action.get("baseline") is not True:
                raise ValueError(
                    "BASELINE scenario_type requires a baseline recommendation."
                )
        return scenario_type

    @staticmethod
    def _require_action_fields(action: Mapping[str, object]) -> None:
        for field in ("scenario_id", "scenario_name"):
            if field not in action:
                raise ValueError(f"recommended_scenario is missing required field '{field}'.")
            if not isinstance(action[field], str) or not action[field]:
                raise ValueError(
                    f"recommended_scenario.{field} must be a non-empty string."
                )

    @classmethod
    def _assumptions(cls, action: Mapping[str, object]) -> Dict[str, object]:
        assumptions = action.get("assumptions")
        if not isinstance(assumptions, dict):
            raise ValueError(
                "recommended_scenario.assumptions must be a dictionary."
            )
        return assumptions

    @classmethod
    def _require_numeric_assumption(
        cls,
        assumptions: Mapping[str, object],
        field: str,
    ) -> float:
        if field not in assumptions:
            raise ValueError(
                f"recommended_scenario.assumptions is missing required field '{field}'."
            )
        return cls._finite_float(
            assumptions[field],
            f"recommended_scenario.assumptions.{field}",
        )

    @classmethod
    def _validate_duration(cls, assumptions: Mapping[str, object]) -> int:
        value = cls._require_numeric_assumption(assumptions, "duration_months")
        if not float(value).is_integer() or value <= 0:
            raise ValueError(
                "recommended_scenario.assumptions.duration_months must be a positive integer."
            )
        return int(value)

    def _validate_decision(self) -> Dict[str, object]:
        if "recommended_scenario" not in self.decision:
            raise ValueError("decision is missing 'recommended_scenario'.")

        action = self.decision["recommended_scenario"]
        if not isinstance(action, dict):
            raise ValueError("decision.recommended_scenario must be a dictionary.")

        self._validate_finite_recursive(action, "decision.recommended_scenario")
        self._require_action_fields(action)
        return action

    def _validate_intervention_assumptions(
        self,
        action: Mapping[str, object],
        scenario_type: str,
    ) -> Dict[str, float]:
        assumptions = self._assumptions(action)
        duration = self._validate_duration(assumptions)
        capital = self._require_numeric_assumption(
            assumptions,
            "one_time_cash_adjustment",
        )

        revenue_growth = 0.0
        expense_reduction = 0.0

        if scenario_type in {"REVENUE_GROWTH", "COMBINED"}:
            revenue_growth = self._require_numeric_assumption(
                assumptions,
                "revenue_growth_adjustment",
            )

        if scenario_type in {"EXPENSE_REDUCTION", "COMBINED"}:
            expense_reduction = self._require_numeric_assumption(
                assumptions,
                "expense_reduction",
            )
            if not 0.0 <= expense_reduction <= 1.0:
                raise ValueError(
                    "recommended_scenario.assumptions.expense_reduction must be between 0 and 1."
                )

        # Validate optional ScenarioEngine fields when present, without
        # inventing missing values for scenario types that do not need them.
        if "expense_growth_adjustment" in assumptions:
            self._finite_float(
                assumptions["expense_growth_adjustment"],
                "recommended_scenario.assumptions.expense_growth_adjustment",
            )

        return {
            "duration_months": float(duration),
            "capital_required": max(0.0, capital),
            "revenue_growth_adjustment": revenue_growth,
            "expense_reduction": expense_reduction,
        }

    def _rule(
        self,
        rule: str,
        status: str,
        requested: object = None,
        limit: object = None,
    ) -> Dict[str, object]:
        result: Dict[str, object] = {"rule": rule, "status": status}
        if requested is not None:
            result["requested"] = requested
        if limit is not None:
            result["limit"] = limit
        return result

    def _policy_limits(self) -> Dict[str, float]:
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
            "max_capital_required": float(self.max_capital_required),
        }

    def evaluate(self) -> Dict[str, object]:
        """Evaluate the optimizer recommendation against execution policy."""
        action = self._validate_decision()
        scenario_type = self._scenario_type(action)

        rules: List[Dict[str, object]] = [
            self._rule("SCENARIO_TYPE", "PASS", scenario_type),
        ]
        violations: List[str] = []
        warnings: List[str] = []
        reasoning: List[str] = []

        original_action = copy.deepcopy(action)

        # BASELINE is a no-action recommendation. It is safe from intervention
        # restrictions and does not require intervention assumptions.
        if scenario_type == "BASELINE":
            rules.append(self._rule("BASELINE_ACTION", "PASS"))
            confidence = self.CONFIDENCE_VALUES[self.data_confidence]
            if self.data_confidence == "MEDIUM":
                warnings.append("Data confidence is MEDIUM.")
                reasoning.append("Data confidence is MEDIUM; no intervention is being executed.")
            elif self.data_confidence == "LOW":
                warnings.append("Data confidence is LOW.")
                reasoning.append(
                    "Data confidence is LOW; the baseline requires no intervention, "
                    "so no automatic action is executed."
                )
            else:
                reasoning.append("BASELINE requires no intervention and is approved.")

            result: Dict[str, object] = {
                "status": "APPROVE",
                "original_action": original_action,
                "approved_action": copy.deepcopy(action),
                "policy": {
                    "rules_evaluated": rules,
                    "violations": violations,
                    "warnings": warnings,
                },
                "reasoning": reasoning,
                "confidence": float(confidence),
                "policy_limits": self._policy_limits(),
            }
            self._validate_output(result)
            return result

        values = self._validate_intervention_assumptions(action, scenario_type)
        capital_required = values["capital_required"]
        revenue_growth = values["revenue_growth_adjustment"]
        expense_reduction = values["expense_reduction"]

        # Hard limits are evaluated before soft modification rules.
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
                "Requested capital requirement exceeds the configured capital limit."
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
                "Capital requirement is within the configured capital limit."
            )

        expense_requires_modify = False
        if scenario_type in {"EXPENSE_REDUCTION", "COMBINED"}:
            if expense_reduction > self.MAX_EXPENSE_REDUCTION_MODIFY:
                rules.append(
                    self._rule(
                        "MAX_EXPENSE_REDUCTION",
                        "BLOCK",
                        expense_reduction,
                        self.MAX_EXPENSE_REDUCTION_MODIFY,
                    )
                )
                violations.append(
                    "Requested expense reduction exceeds the absolute 50% policy limit."
                )
            elif expense_reduction > self.MAX_EXPENSE_REDUCTION_APPROVE:
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
                    "Expense reduction is within the approved 30% policy limit."
                )

        revenue_requires_modify = False
        if scenario_type in {"REVENUE_GROWTH", "COMBINED"}:
            if revenue_growth > self.MAX_REVENUE_GROWTH_ADJUSTMENT:
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
                    "Revenue growth assumption is within the approved 20% policy limit."
                )

        confidence = self.CONFIDENCE_VALUES[self.data_confidence]
        if self.data_confidence == "MEDIUM":
            warnings.append("Data confidence is MEDIUM.")
            reasoning.append("Data confidence is MEDIUM; the recommendation remains eligible under policy.")
        elif self.data_confidence == "LOW":
            rules.append(self._rule("DATA_CONFIDENCE", "BLOCK", self.data_confidence))
            violations.append(
                "Automatic execution is blocked because data confidence is LOW."
            )
            reasoning.append(
                "Recommendation may still be presented to the user, but automatic execution is blocked because data confidence is LOW."
            )
        else:
            rules.append(self._rule("DATA_CONFIDENCE", "PASS", self.data_confidence))
            reasoning.append("Data confidence is HIGH.")

        if self.data_confidence == "MEDIUM":
            rules.append(self._rule("DATA_CONFIDENCE", "PASS", self.data_confidence))

        if violations:
            status = "BLOCK"
            approved_action = None
            reasoning.extend(violations)
            reasoning.append("Automatic execution is blocked under the configured policy.")
        elif expense_requires_modify or revenue_requires_modify:
            status = "MODIFY"
            approved_action = copy.deepcopy(action)
            assumptions = approved_action["assumptions"]

            if expense_requires_modify:
                assumptions["expense_reduction"] = float(
                    self.MAX_EXPENSE_REDUCTION_APPROVE
                )
                reasoning.append(
                    "Action was modified to the maximum permitted expense reduction of 30%."
                )

            if revenue_requires_modify:
                assumptions["revenue_growth_adjustment"] = float(
                    self.MAX_REVENUE_GROWTH_ADJUSTMENT
                )
                reasoning.append(
                    "Action was modified to the maximum permitted revenue growth assumption of 20%."
                )
        else:
            status = "APPROVE"
            approved_action = copy.deepcopy(action)
            reasoning.append("All applicable policy rules passed.")

        result = {
            "status": status,
            "original_action": original_action,
            "approved_action": approved_action,
            "policy": {
                "rules_evaluated": rules,
                "violations": violations,
                "warnings": warnings,
            },
            "reasoning": reasoning,
            "confidence": float(confidence),
            "policy_limits": self._policy_limits(),
            "capital_required": float(capital_required),
            "capital_limit": float(self.max_capital_required),
        }
        self._validate_output(result)
        return result

    @classmethod
    def _validate_output(cls, result: Mapping[str, object]) -> None:
        status = result.get("status")
        if status not in {"APPROVE", "MODIFY", "BLOCK"}:
            raise RuntimeError("Policy output contains an invalid status.")
        confidence = float(result["confidence"])
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise RuntimeError("Policy confidence must be between 0 and 1 and finite.")
        cls._validate_finite_recursive(result, "policy_output")
