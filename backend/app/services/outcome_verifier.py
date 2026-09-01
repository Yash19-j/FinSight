from __future__ import annotations

import copy
import math
from dataclasses import asdict
from numbers import Integral, Real
from typing import Dict, Mapping

from ..models.action import Action, ActionParameters


class OutcomeVerificationError(RuntimeError):
    """Raised when a dry-run execution result cannot be safely verified."""


class OutcomeVerifier:
    """Verify integrity of a FinSight dry-run execution result.

    This verifier does not evaluate merchant financial performance. It only
    confirms that a SIMULATED/DRY_RUN execution result faithfully preserves
    the exact policy-approved Action that crossed the execution boundary.
    """

    SUCCESS_STATUS = "EXECUTION_VERIFIED"
    FAILURE_STATUS = "VERIFICATION_FAILED"
    VERIFICATION_TYPE = "DRY_RUN_EXECUTION"

    _REQUIRED_EXECUTION_KEYS = (
        "status",
        "mode",
        "scenario_id",
        "policy_status",
        "parameters",
    )

    @classmethod
    def _failure(
        cls,
        scenario_id: str | None,
        reason: str,
    ) -> Dict[str, object]:
        return {
            "status": cls.FAILURE_STATUS,
            "verified": False,
            "verification_type": cls.VERIFICATION_TYPE,
            "scenario_id": scenario_id,
            "reason": reason,
            "outcome_available": False,
        }

    @classmethod
    def _success(cls, scenario_id: str) -> Dict[str, object]:
        return {
            "status": cls.SUCCESS_STATUS,
            "verified": True,
            "verification_type": cls.VERIFICATION_TYPE,
            "scenario_id": scenario_id,
            "reason": (
                "Dry-run execution matches the approved Action. "
                "No real-world financial outcome was evaluated."
            ),
            "outcome_available": False,
        }

    @staticmethod
    def _validate_finite_recursive(value: object, path: str) -> None:
        if value is None or isinstance(value, (str, bool)):
            return

        if isinstance(value, Real):
            if not math.isfinite(float(value)):
                raise OutcomeVerificationError(f"{path} must be finite.")
            return

        if isinstance(value, Mapping):
            for key, item in value.items():
                OutcomeVerifier._validate_finite_recursive(
                    item,
                    f"{path}.{key}",
                )
            return

        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                OutcomeVerifier._validate_finite_recursive(
                    item,
                    f"{path}[{index}]",
                )
            return

        raise OutcomeVerificationError(
            f"{path} contains unsupported value type "
            f"{type(value).__name__}."
        )

    @classmethod
    def _validate_parameters(
        cls,
        parameters: object,
    ) -> ActionParameters:
        if not isinstance(parameters, ActionParameters):
            raise OutcomeVerificationError(
                "Action parameters must be an ActionParameters instance."
            )

        for field_name in (
            "revenue_growth_adjustment",
            "expense_growth_adjustment",
            "one_time_cash_adjustment",
            "expense_reduction",
        ):
            value = getattr(parameters, field_name, None)

            if isinstance(value, bool) or not isinstance(value, Real):
                raise OutcomeVerificationError(
                    f"Action parameter '{field_name}' must be "
                    "finite numeric data."
                )

            if not math.isfinite(float(value)):
                raise OutcomeVerificationError(
                    f"Action parameter '{field_name}' must be finite."
                )

        duration = getattr(parameters, "duration_months", None)

        if isinstance(duration, bool) or not isinstance(
            duration,
            Integral,
        ):
            raise OutcomeVerificationError(
                "Action parameter 'duration_months' must be an integer."
            )

        if int(duration) < 1:
            raise OutcomeVerificationError(
                "Action parameter 'duration_months' must be at least 1."
            )

        expense_reduction = float(parameters.expense_reduction)

        if not 0.0 <= expense_reduction <= 1.0:
            raise OutcomeVerificationError(
                "Action parameter 'expense_reduction' must be "
                "between 0 and 1."
            )

        return parameters

    @classmethod
    def _validate_action(cls, action: object) -> Action:
        if action is None:
            raise OutcomeVerificationError(
                "Action cannot be None."
            )

        if not isinstance(action, Action):
            raise OutcomeVerificationError(
                "OutcomeVerifier accepts only an Action instance."
            )

        if (
            not isinstance(action.scenario_id, str)
            or not action.scenario_id.strip()
        ):
            raise OutcomeVerificationError(
                "Action scenario_id must be a non-empty string."
            )

        if action.scenario_id == "baseline":
            raise OutcomeVerificationError(
                "Baseline is a no-op and cannot have an "
                "executed Action outcome."
            )

        if (
            not isinstance(action.scenario_name, str)
            or not action.scenario_name.strip()
        ):
            raise OutcomeVerificationError(
                "Action scenario_name must be a non-empty string."
            )

        if action.policy_status not in {"APPROVE", "MODIFY"}:
            raise OutcomeVerificationError(
                "Action policy_status must be APPROVE or MODIFY; "
                "BLOCK cannot be verified as executed."
            )

        confidence = action.confidence

        if isinstance(confidence, bool) or not isinstance(
            confidence,
            Real,
        ):
            raise OutcomeVerificationError(
                "Action confidence must be finite numeric data."
            )

        confidence_value = float(confidence)

        if (
            not math.isfinite(confidence_value)
            or not 0.0 <= confidence_value <= 1.0
        ):
            raise OutcomeVerificationError(
                "Action confidence must be finite and between 0 and 1."
            )

        if not isinstance(action.reasoning, tuple) or not all(
            isinstance(item, str)
            for item in action.reasoning
        ):
            raise OutcomeVerificationError(
                "Action reasoning must be an immutable "
                "sequence of strings."
            )

        cls._validate_parameters(action.parameters)

        return action

    @classmethod
    def _validate_execution_result(
        cls,
        execution_result: object,
    ) -> Dict[str, object]:
        if execution_result is None:
            raise OutcomeVerificationError(
                "execution_result cannot be None."
            )

        if not isinstance(execution_result, Mapping):
            raise OutcomeVerificationError(
                "execution_result must be a Mapping."
            )

        missing = [
            key
            for key in cls._REQUIRED_EXECUTION_KEYS
            if key not in execution_result
        ]

        if missing:
            raise OutcomeVerificationError(
                f"execution_result is missing required keys: {missing}"
            )

        copied = copy.deepcopy(dict(execution_result))

        cls._validate_finite_recursive(
            copied,
            "execution_result",
        )

        for key in (
            "status",
            "mode",
            "scenario_id",
            "policy_status",
        ):
            if (
                not isinstance(copied[key], str)
                or not copied[key]
            ):
                raise OutcomeVerificationError(
                    f"execution_result.{key} must be "
                    "a non-empty string."
                )

        if not isinstance(copied["parameters"], Mapping):
            raise OutcomeVerificationError(
                "execution_result.parameters must be a Mapping."
            )

        return copied

    @classmethod
    def verify(
        cls,
        action: Action,
        execution_result: Mapping[str, object],
    ) -> Dict[str, object]:
        """Verify a dry-run result against the approved Action."""
        validated_action = cls._validate_action(action)

        execution = cls._validate_execution_result(
            execution_result
        )

        scenario_id = validated_action.scenario_id

        if execution["status"] != "SIMULATED":
            return cls._failure(
                scenario_id,
                "Execution status must be SIMULATED for dry-run "
                "verification. No real-world financial outcome "
                "was evaluated.",
            )

        if execution["mode"] != "DRY_RUN":
            return cls._failure(
                scenario_id,
                "Execution mode must be DRY_RUN. "
                "No real-world financial outcome was evaluated.",
            )

        if execution["scenario_id"] != validated_action.scenario_id:
            return cls._failure(
                scenario_id,
                "Execution scenario_id does not match the "
                "approved Action. No real-world financial "
                "outcome was evaluated.",
            )

        if (
            execution["policy_status"]
            != validated_action.policy_status
        ):
            return cls._failure(
                scenario_id,
                "Execution policy_status does not match the "
                "approved Action. No real-world financial "
                "outcome was evaluated.",
            )

        approved_parameters = asdict(
            validated_action.parameters
        )

        execution_parameters = dict(
            execution["parameters"]
        )

        if execution_parameters != approved_parameters:
            return cls._failure(
                scenario_id,
                "Execution parameters do not exactly match "
                "the approved Action parameters. "
                "No real-world financial outcome was evaluated.",
            )

        result = cls._success(scenario_id)

        cls._validate_finite_recursive(
            result,
            "verification_result",
        )

        return result