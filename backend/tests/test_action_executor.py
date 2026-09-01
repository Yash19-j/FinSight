import json
import math
import socket
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.action import Action, ActionParameters
from backend.app.services.action_executor import ActionExecutionError, ActionExecutor
from backend.app.services.policy_engine import PolicyEngine
from backend.app.services.scenario_engine import Scenario, ScenarioEngine


def make_parameters(**overrides):
    values = {
        "revenue_growth_adjustment": 0.10,
        "expense_growth_adjustment": 0.0,
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
        "reasoning": ["Approved by policy."],
    }
    values.update(overrides)
    return Action(**values)


def forge_action(**overrides):
    """Create an Action bypassing dataclass validation for executor safety tests."""
    action = object.__new__(Action)
    values = {
        "scenario_id": "expense_reduction_0.1",
        "scenario_name": "Expense Reduction",
        "parameters": make_parameters(),
        "policy_status": "APPROVE",
        "confidence": 1.0,
        "reasoning": ("Approved by policy.",),
    }
    values.update(overrides)
    for field, value in values.items():
        object.__setattr__(action, field, value)
    return action


def assert_finite_recursive(value):
    if isinstance(value, dict):
        return all(assert_finite_recursive(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(assert_finite_recursive(item) for item in value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


def test_valid_approve_action_is_simulated():
    result = ActionExecutor.execute(make_action(policy_status="APPROVE"))

    assert result["status"] == "SIMULATED"
    assert result["mode"] == "DRY_RUN"
    assert result["policy_status"] == "APPROVE"
    assert "no external system was modified" in result["message"]


def test_valid_modify_action_is_simulated():
    result = ActionExecutor.execute(
        make_action(
            policy_status="MODIFY",
            parameters=make_parameters(expense_reduction=0.30),
        )
    )

    assert result["status"] == "SIMULATED"
    assert result["policy_status"] == "MODIFY"


def test_modify_uses_only_approved_modified_parameters():
    unsafe_original = make_parameters(expense_reduction=0.40)
    approved_action = make_action(
        scenario_id="expense_reduction_0.4",
        policy_status="MODIFY",
        parameters=make_parameters(expense_reduction=0.30),
    )

    result = ActionExecutor.execute(approved_action)

    assert unsafe_original.expense_reduction == pytest.approx(0.40)
    assert result["parameters"]["expense_reduction"] == pytest.approx(0.30)
    assert result["parameters"]["expense_reduction"] != unsafe_original.expense_reduction


def test_none_is_rejected():
    with pytest.raises(ActionExecutionError, match="cannot be None"):
        ActionExecutor.execute(None)


def test_dictionary_is_rejected():
    with pytest.raises(ActionExecutionError, match="only an Action instance"):
        ActionExecutor.execute(make_action().to_dict())


def test_scenario_object_is_rejected():
    scenario = Scenario(
        scenario_id="expense_reduction_0.1",
        name="Expense Reduction",
        description="test",
        expense_reduction=0.1,
        duration_months=6,
    )
    with pytest.raises(ActionExecutionError, match="only an Action instance"):
        ActionExecutor.execute(scenario)


def test_decision_like_object_is_rejected():
    class Decision:
        pass

    with pytest.raises(ActionExecutionError, match="only an Action instance"):
        ActionExecutor.execute(Decision())


def test_block_cannot_execute_even_if_validation_is_bypassed():
    blocked = forge_action(policy_status="BLOCK")

    with pytest.raises(ActionExecutionError, match="blocked actions cannot execute"):
        ActionExecutor.execute(blocked)


def test_invalid_policy_status_cannot_execute():
    invalid = forge_action(policy_status="PENDING")

    with pytest.raises(ActionExecutionError, match="policy_status must be APPROVE or MODIFY"):
        ActionExecutor.execute(invalid)


def test_unsupported_scenario_is_rejected():
    action = make_action(
        scenario_id="take_loan_100000",
        scenario_name="Take Loan",
    )

    with pytest.raises(ActionExecutionError, match="Unsupported executable scenario_id"):
        ActionExecutor.execute(action)


def test_baseline_is_rejected_as_non_executable():
    baseline = make_action(
        scenario_id="baseline",
        scenario_name="Baseline",
    )

    with pytest.raises(ActionExecutionError, match="Baseline is a no-op"):
        ActionExecutor.execute(baseline)


@pytest.mark.parametrize(
    "scenario_id,parameters",
    [
        (
            "revenue_growth_0.1",
            make_parameters(revenue_growth_adjustment=0.10, expense_reduction=0.0),
        ),
        (
            "expense_reduction_0.1",
            make_parameters(revenue_growth_adjustment=0.0, expense_reduction=0.10),
        ),
        (
            "combined_revenue_0.1_expense_reduction_0.1",
            make_parameters(revenue_growth_adjustment=0.10, expense_reduction=0.10),
        ),
    ],
)
def test_current_scenario_families_are_supported(scenario_id, parameters):
    result = ActionExecutor.execute(
        make_action(scenario_id=scenario_id, parameters=parameters)
    )
    assert result["status"] == "SIMULATED"
    assert result["scenario_id"] == scenario_id


def test_action_remains_unchanged_after_execution():
    action = make_action()
    before = action.to_dict()

    ActionExecutor.execute(action)

    assert action.to_dict() == before
    with pytest.raises(FrozenInstanceError):
        action.policy_status = "MODIFY"


def test_action_parameters_remain_unchanged_after_execution():
    action = make_action()
    before = action.parameters

    ActionExecutor.execute(action)

    assert action.parameters == before
    with pytest.raises(FrozenInstanceError):
        action.parameters.expense_reduction = 0.30


def test_scenario_id_is_not_used_to_reconstruct_parameter_values():
    action = make_action(
        scenario_id="expense_reduction_0.9",
        parameters=make_parameters(expense_reduction=0.17),
    )

    result = ActionExecutor.execute(action)

    assert result["parameters"]["expense_reduction"] == pytest.approx(0.17)


def test_result_is_json_serializable():
    result = ActionExecutor.execute(make_action())
    encoded = json.dumps(result)
    assert isinstance(encoded, str)


def test_result_contains_no_nan_or_infinity():
    result = ActionExecutor.execute(make_action())
    assert assert_finite_recursive(result)


def test_same_action_produces_deterministic_dry_run_result():
    action = make_action()
    assert ActionExecutor.execute(action) == ActionExecutor.execute(action)


def test_no_external_network_call_is_made(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", fail_network)
    result = ActionExecutor.execute(make_action())
    assert result["status"] == "SIMULATED"


def test_policy_engine_is_not_called(monkeypatch):
    def fail_policy(*args, **kwargs):
        raise AssertionError("PolicyEngine was called")

    monkeypatch.setattr(PolicyEngine, "evaluate", fail_policy)
    result = ActionExecutor.execute(make_action())
    assert result["status"] == "SIMULATED"


def test_scenario_engine_is_not_called(monkeypatch):
    def fail_scenario(*args, **kwargs):
        raise AssertionError("ScenarioEngine was called")

    monkeypatch.setattr(ScenarioEngine, "simulate", fail_scenario)
    result = ActionExecutor.execute(make_action())
    assert result["status"] == "SIMULATED"


def test_executor_contains_no_financial_calculation_contract_fields():
    result = ActionExecutor.execute(make_action())

    forbidden = {
        "cash",
        "revenue",
        "expenses",
        "burn",
        "runway",
        "survival_probability",
        "expected_impact",
        "decision_score",
        "action_id",
    }
    assert forbidden.isdisjoint(result)
    assert set(result) == {
        "status",
        "mode",
        "scenario_id",
        "policy_status",
        "parameters",
        "message",
    }


def test_malformed_action_is_rejected_explicitly():
    malformed = forge_action(parameters="not parameters")

    with pytest.raises(ActionExecutionError, match="ActionParameters instance"):
        ActionExecutor.execute(malformed)


def test_execution_failure_is_explicit(monkeypatch):
    def fail_build(cls, action):
        raise RuntimeError("synthetic executor failure")

    monkeypatch.setattr(
        ActionExecutor,
        "_build_dry_run_result",
        classmethod(fail_build),
    )

    with pytest.raises(
        ActionExecutionError,
        match="Dry-run execution failed explicitly: synthetic executor failure",
    ):
        ActionExecutor.execute(make_action())