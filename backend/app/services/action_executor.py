from __future__ import annotations

import math
from dataclasses import asdict
from numbers import Integral, Real
from typing import Dict

from ..models.action import Action, ActionParameters


class ActionExecutionError(RuntimeError):
    """Raised when an approved Action cannot be safely dry-run."""


class ActionExecutor:
    """Deterministic dry-run executor for policy-approved FinSight Actions.

    The executor performs no financial calculations and has no external side
    effects. It accepts only the immutable Action contract, validates that the
    action remains executable, and returns a JSON-safe dry-run record using the
    approved parameters already present on the Action.
    """

    STATUS = "SIMULATED"
    MODE = "DRY_RUN"

    _SUPPORTED_PREFIXES = (
        "revenue_growth_",
        "expense_reduction_",
        "combined_revenue_",
    )

    @classmethod
    def _validate_parameters(cls, parameters: object) -> ActionParameters:
        if not isinstance(parameters, ActionParameters):
            raise ActionExecutionError(
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
                raise ActionExecutionError(
                    f"Action parameter '{field_name}' must be finite numeric data."
                )
            if not math.isfinite(float(value)):
                raise ActionExecutionError(
                    f"Action parameter '{field_name}' must be finite."
                )

        duration = getattr(parameters, "duration_months", None)
        if isinstance(duration, bool) or not isinstance(duration, Integral):
            raise ActionExecutionError(
                "Action parameter 'duration_months' must be an integer."
            )
        if int(duration) < 1:
            raise ActionExecutionError(
                "Action parameter 'duration_months' must be at least 1."
            )

        expense_reduction = float(parameters.expense_reduction)
        if not 0.0 <= expense_reduction <= 1.0:
            raise ActionExecutionError(
                "Action parameter 'expense_reduction' must be between 0 and 1."
            )

        return parameters

    @classmethod
    def _validate_action(cls, action: object) -> Action:
        if action is None:
            raise ActionExecutionError("Action cannot be None.")
        if not isinstance(action, Action):
            raise ActionExecutionError(
                "ActionExecutor accepts only an Action instance."
            )

        if not isinstance(action.scenario_id, str) or not action.scenario_id.strip():
            raise ActionExecutionError("Action scenario_id must be a non-empty string.")
        if not isinstance(action.scenario_name, str) or not action.scenario_name.strip():
            raise ActionExecutionError(
                "Action scenario_name must be a non-empty string."
            )

        if action.policy_status not in {"APPROVE", "MODIFY"}:
            raise ActionExecutionError(
                "Action policy_status must be APPROVE or MODIFY; blocked actions cannot execute."
            )

        confidence = action.confidence
        if isinstance(confidence, bool) or not isinstance(confidence, Real):
            raise ActionExecutionError("Action confidence must be finite numeric data.")
        confidence_value = float(confidence)
        if not math.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
            raise ActionExecutionError(
                "Action confidence must be finite and between 0 and 1."
            )

        if not isinstance(action.reasoning, tuple) or not all(
            isinstance(item, str) for item in action.reasoning
        ):
            raise ActionExecutionError(
                "Action reasoning must be an immutable sequence of strings."
            )

        cls._validate_parameters(action.parameters)

        if action.scenario_id == "baseline":
            raise ActionExecutionError(
                "Baseline is a no-op and is not an executable intervention."
            )

        if not action.scenario_id.startswith(cls._SUPPORTED_PREFIXES):
            raise ActionExecutionError(
                f"Unsupported executable scenario_id: {action.scenario_id}"
            )

        return action

    @classmethod
    def _build_dry_run_result(cls, action: Action) -> Dict[str, object]:
        # Parameters are copied directly from the approved Action contract.
        # scenario_id is used only to select supported dispatch families; no
        # parameter value is ever reconstructed from it.
        return {
            "status": cls.STATUS,
            "mode": cls.MODE,
            "scenario_id": action.scenario_id,
            "policy_status": action.policy_status,
            "parameters": asdict(action.parameters),
            "message": (
                "Approved intervention validated in dry-run mode; "
                "no external system was modified."
            ),
        }

    @classmethod
    def execute(cls, action: Action) -> Dict[str, object]:
        """Validate and deterministically dry-run one approved Action."""
        validated_action = cls._validate_action(action)

        try:
            result = cls._build_dry_run_result(validated_action)
        except ActionExecutionError:
            raise
        except Exception as exc:
            raise ActionExecutionError(
                f"Dry-run execution failed explicitly: {exc}"
            ) from exc

        return result