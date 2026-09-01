from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Literal, Sequence


PolicyStatus = Literal["APPROVE", "MODIFY"]


@dataclass(frozen=True)
class ActionParameters:
    """Immutable parameters for an approved FinSight intervention."""

    revenue_growth_adjustment: float
    expense_growth_adjustment: float
    one_time_cash_adjustment: float
    duration_months: int
    expense_reduction: float

    def __post_init__(self) -> None:
        for field_name in (
            "revenue_growth_adjustment",
            "expense_growth_adjustment",
            "one_time_cash_adjustment",
            "expense_reduction",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{field_name} must be a finite numeric value.")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"{field_name} must be finite.")
            object.__setattr__(self, field_name, numeric)

        if isinstance(self.duration_months, bool) or not isinstance(
            self.duration_months, Integral
        ):
            raise ValueError("duration_months must be an integer.")
        if self.duration_months < 1:
            raise ValueError("duration_months must be at least 1.")
        object.__setattr__(self, "duration_months", int(self.duration_months))

        if not 0.0 <= self.expense_reduction <= 1.0:
            raise ValueError("expense_reduction must be between 0 and 1.")


@dataclass(frozen=True)
class Action:
    """Immutable executable action approved by the FinSight policy layer."""

    scenario_id: str
    scenario_name: str
    parameters: ActionParameters
    policy_status: PolicyStatus
    confidence: float
    reasoning: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string.")
        if not isinstance(self.scenario_name, str) or not self.scenario_name.strip():
            raise ValueError("scenario_name must be a non-empty string.")
        if not isinstance(self.parameters, ActionParameters):
            raise ValueError("parameters must be an ActionParameters instance.")
        if not isinstance(self.policy_status, str) or self.policy_status not in {
            "APPROVE",
            "MODIFY",
        }:
            raise ValueError("policy_status must be APPROVE or MODIFY.")

        if isinstance(self.confidence, bool) or not isinstance(self.confidence, Real):
            raise ValueError("confidence must be a finite numeric value.")
        confidence = float(self.confidence)
        if not math.isfinite(confidence):
            raise ValueError("confidence must be finite.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")
        object.__setattr__(self, "confidence", confidence)

        if isinstance(self.reasoning, (str, bytes)) or not isinstance(
            self.reasoning, Sequence
        ):
            raise ValueError("reasoning must be a sequence of strings.")
        if not all(isinstance(item, str) for item in self.reasoning):
            raise ValueError("reasoning must contain only strings.")
        object.__setattr__(self, "reasoning", tuple(self.reasoning))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary representation."""
        result = asdict(self)
        result["reasoning"] = list(self.reasoning)
        return result