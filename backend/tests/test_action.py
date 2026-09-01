import json
import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.action import Action, ActionParameters


def make_parameters(**overrides):
    values = {
        "revenue_growth_adjustment": 0.10,
        "expense_growth_adjustment": 0.02,
        "one_time_cash_adjustment": 0.0,
        "duration_months": 6,
        "expense_reduction": 0.10,
    }
    values.update(overrides)
    return ActionParameters(**values)


def make_action(**overrides):
    values = {
        "scenario_id": "expense_reduction_0.1",
        "scenario_name": "Expense Reduction",
        "parameters": make_parameters(),
        "policy_status": "APPROVE",
        "confidence": 1.0,
        "reasoning": ["Expense reduction is within policy limits."],
    }
    values.update(overrides)
    return Action(**values)


def test_valid_action_parameters():
    parameters = make_parameters()

    assert parameters.revenue_growth_adjustment == pytest.approx(0.10)
    assert parameters.expense_growth_adjustment == pytest.approx(0.02)
    assert parameters.one_time_cash_adjustment == pytest.approx(0.0)
    assert parameters.duration_months == 6
    assert parameters.expense_reduction == pytest.approx(0.10)


def test_valid_action():
    action = make_action()

    assert action.scenario_id == "expense_reduction_0.1"
    assert action.scenario_name == "Expense Reduction"
    assert action.parameters == make_parameters()
    assert action.policy_status == "APPROVE"
    assert action.confidence == pytest.approx(1.0)
    assert action.reasoning == ("Expense reduction is within policy limits.",)


def test_approve_action():
    action = make_action(policy_status="APPROVE")
    assert action.policy_status == "APPROVE"


def test_modify_action():
    action = make_action(
        policy_status="MODIFY",
        parameters=make_parameters(expense_reduction=0.30),
        reasoning=["Action was modified to the permitted expense reduction."],
    )

    assert action.policy_status == "MODIFY"
    assert action.parameters.expense_reduction == pytest.approx(0.30)


def test_empty_scenario_id_rejected():
    with pytest.raises(ValueError, match="scenario_id must be a non-empty string"):
        make_action(scenario_id="")


def test_whitespace_scenario_id_rejected():
    with pytest.raises(ValueError, match="scenario_id must be a non-empty string"):
        make_action(scenario_id="   ")


def test_empty_scenario_name_rejected():
    with pytest.raises(ValueError, match="scenario_name must be a non-empty string"):
        make_action(scenario_name="")


def test_whitespace_scenario_name_rejected():
    with pytest.raises(ValueError, match="scenario_name must be a non-empty string"):
        make_action(scenario_name="   ")


@pytest.mark.parametrize("policy_status", ["BLOCK", "", "approve", "MODIFY ", 1, None])
def test_invalid_policy_status_rejected(policy_status):
    with pytest.raises(ValueError, match="policy_status must be APPROVE or MODIFY"):
        make_action(policy_status=policy_status)


def test_block_status_is_rejected():
    with pytest.raises(ValueError, match="policy_status must be APPROVE or MODIFY"):
        make_action(policy_status="BLOCK")


@pytest.mark.parametrize("confidence", [-0.0001, -1.0])
def test_confidence_below_zero_rejected(confidence):
    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        make_action(confidence=confidence)


@pytest.mark.parametrize("confidence", [1.0001, 2.0])
def test_confidence_above_one_rejected(confidence):
    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        make_action(confidence=confidence)


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -math.inf])
def test_non_finite_confidence_rejected(confidence):
    with pytest.raises(ValueError, match="confidence must be finite"):
        make_action(confidence=confidence)


@pytest.mark.parametrize("duration", [0, -1, -6])
def test_duration_less_than_one_rejected(duration):
    with pytest.raises(ValueError, match="duration_months must be at least 1"):
        make_parameters(duration_months=duration)


@pytest.mark.parametrize("duration", [1.0, 1.5, "6", True, None])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError, match="duration_months must be an integer"):
        make_parameters(duration_months=duration)


@pytest.mark.parametrize(
    "field",
    [
        "revenue_growth_adjustment",
        "expense_growth_adjustment",
        "one_time_cash_adjustment",
        "expense_reduction",
    ],
)
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_parameters_rejected(field, value):
    with pytest.raises(ValueError, match=f"{field} must be"):
        make_parameters(**{field: value})


@pytest.mark.parametrize("expense_reduction", [-0.0001, -1.0])
def test_expense_reduction_below_zero_rejected(expense_reduction):
    with pytest.raises(ValueError, match="expense_reduction must be between 0 and 1"):
        make_parameters(expense_reduction=expense_reduction)


@pytest.mark.parametrize("expense_reduction", [1.0001, 2.0])
def test_expense_reduction_above_one_rejected(expense_reduction):
    with pytest.raises(ValueError, match="expense_reduction must be between 0 and 1"):
        make_parameters(expense_reduction=expense_reduction)


def test_action_parameters_are_immutable():
    parameters = make_parameters()

    with pytest.raises((AttributeError, TypeError)):
        parameters.expense_reduction = 0.30


def test_action_is_immutable():
    action = make_action()

    with pytest.raises((AttributeError, TypeError)):
        action.policy_status = "MODIFY"

    with pytest.raises((AttributeError, TypeError)):
        action.parameters = make_parameters(expense_reduction=0.30)

    with pytest.raises(AttributeError):
        action.reasoning.append("another reason")


def test_reasoning_requires_a_sequence_of_strings():
    assert make_action(reasoning=[]).reasoning == ()
    assert make_action(reasoning=("first", "second")).reasoning == (
        "first",
        "second",
    )

    with pytest.raises(ValueError, match="reasoning must be a sequence of strings"):
        make_action(reasoning="not a list")

    with pytest.raises(ValueError, match="reasoning must contain only strings"):
        make_action(reasoning=["valid", 123])


def test_approved_parameters_can_represent_policy_modify_without_unsafe_original():
    unsafe_original = make_parameters(expense_reduction=0.40)
    approved = make_action(
        policy_status="MODIFY",
        parameters=make_parameters(expense_reduction=0.30),
    )

    assert unsafe_original.expense_reduction == pytest.approx(0.40)
    assert approved.parameters.expense_reduction == pytest.approx(0.30)
    assert approved.parameters.expense_reduction != unsafe_original.expense_reduction


def test_to_dict_serializes_nested_parameters_and_reasoning():
    action = make_action()
    result = action.to_dict()

    assert result == {
        "scenario_id": "expense_reduction_0.1",
        "scenario_name": "Expense Reduction",
        "parameters": {
            "revenue_growth_adjustment": pytest.approx(0.10),
            "expense_growth_adjustment": pytest.approx(0.02),
            "one_time_cash_adjustment": pytest.approx(0.0),
            "duration_months": 6,
            "expense_reduction": pytest.approx(0.10),
        },
        "policy_status": "APPROVE",
        "confidence": pytest.approx(1.0),
        "reasoning": ["Expense reduction is within policy limits."],
    }
    assert json.dumps(result)