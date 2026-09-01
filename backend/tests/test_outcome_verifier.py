import copy
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
from backend.app.services.action_executor import ActionExecutor
from backend.app.services.decision_optimizer import DecisionOptimizer
from backend.app.services.outcome_verifier import (
    OutcomeVerificationError,
    OutcomeVerifier,
)
from backend.app.services.policy_engine import PolicyEngine
from backend.app.services.scenario_engine import ScenarioEngine


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


def make_execution_result(action=None, **overrides):
    action = action or make_action()

    result = {
        "status": "SIMULATED",
        "mode": "DRY_RUN",
        "scenario_id": action.scenario_id,
        "policy_status": action.policy_status,
        "parameters": {
            "revenue_growth_adjustment":
                action.parameters.revenue_growth_adjustment,
            "expense_growth_adjustment":
                action.parameters.expense_growth_adjustment,
            "one_time_cash_adjustment":
                action.parameters.one_time_cash_adjustment,
            "duration_months":
                action.parameters.duration_months,
            "expense_reduction":
                action.parameters.expense_reduction,
        },
        "message": (
            "Approved intervention validated in dry-run mode; "
            "no external system was modified."
        ),
    }

    result.update(overrides)

    return result


def forge_action(**overrides):
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
        object.__setattr__(
            action,
            field,
            value,
        )

    return action


def finite_recursive(value):
    if isinstance(value, dict):
        return all(
            finite_recursive(item)
            for item in value.values()
        )

    if isinstance(value, (list, tuple)):
        return all(
            finite_recursive(item)
            for item in value
        )

    if (
        isinstance(value, bool)
        or value is None
        or isinstance(value, str)
    ):
        return True

    if isinstance(value, (int, float)):
        return math.isfinite(float(value))

    return False


def test_valid_approve_dry_run_verifies():
    action = make_action(
        policy_status="APPROVE"
    )

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )

    assert result["status"] == "EXECUTION_VERIFIED"
    assert result["verified"] is True
    assert (
        result["verification_type"]
        == "DRY_RUN_EXECUTION"
    )


def test_valid_modify_dry_run_verifies():
    action = make_action(
        policy_status="MODIFY",
        parameters=make_parameters(
            expense_reduction=0.30
        ),
    )

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )

    assert result["status"] == "EXECUTION_VERIFIED"
    assert result["verified"] is True


def test_modify_verifies_using_approved_action_parameters():
    action = make_action(
        scenario_id="expense_reduction_0.4",
        policy_status="MODIFY",
        parameters=make_parameters(
            expense_reduction=0.30
        ),
    )

    execution = make_execution_result(action)

    result = OutcomeVerifier.verify(
        action,
        execution,
    )

    assert (
        execution["parameters"]["expense_reduction"]
        == pytest.approx(0.30)
    )

    assert result["verified"] is True


def test_original_scenario_assumptions_are_not_used():
    action = make_action(
        scenario_id="expense_reduction_0.4",
        policy_status="MODIFY",
        parameters=make_parameters(
            expense_reduction=0.30
        ),
    )

    execution = make_execution_result(action)

    assert OutcomeVerifier.verify(
        action,
        execution,
    )["verified"] is True

    assert (
        execution["parameters"]["expense_reduction"]
        != pytest.approx(0.40)
    )


def test_none_action_rejected():
    with pytest.raises(
        OutcomeVerificationError,
        match="Action cannot be None",
    ):
        OutcomeVerifier.verify(
            None,
            make_execution_result(),
        )


def test_non_action_rejected():
    with pytest.raises(
        OutcomeVerificationError,
        match="only an Action instance",
    ):
        OutcomeVerifier.verify(
            {"scenario_id": "x"},
            make_execution_result(),
        )


def test_none_execution_result_rejected():
    with pytest.raises(
        OutcomeVerificationError,
        match="execution_result cannot be None",
    ):
        OutcomeVerifier.verify(
            make_action(),
            None,
        )


def test_non_mapping_execution_result_rejected():
    with pytest.raises(
        OutcomeVerificationError,
        match="must be a Mapping",
    ):
        OutcomeVerifier.verify(
            make_action(),
            ["SIMULATED"],
        )


@pytest.mark.parametrize(
    "missing_key",
    [
        "status",
        "mode",
        "scenario_id",
        "policy_status",
        "parameters",
    ],
)
def test_missing_required_execution_keys_rejected(
    missing_key,
):
    action = make_action()

    execution = make_execution_result(action)

    execution.pop(missing_key)

    with pytest.raises(
        OutcomeVerificationError,
        match="missing required keys",
    ):
        OutcomeVerifier.verify(
            action,
            execution,
        )


def test_wrong_status_fails_verification():
    action = make_action()

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(
            action,
            status="FAILED",
        ),
    )

    assert result["status"] == "VERIFICATION_FAILED"
    assert result["verified"] is False


def test_wrong_mode_fails_verification():
    action = make_action()

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(
            action,
            mode="LIVE",
        ),
    )

    assert result["status"] == "VERIFICATION_FAILED"
    assert result["verified"] is False


def test_scenario_mismatch_fails_verification():
    action = make_action()

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(
            action,
            scenario_id="revenue_growth_0.1",
        ),
    )

    assert result["verified"] is False
    assert "scenario_id" in result["reason"]


def test_policy_status_mismatch_fails_verification():
    action = make_action(
        policy_status="APPROVE"
    )

    result = OutcomeVerifier.verify(
        action,
        make_execution_result(
            action,
            policy_status="MODIFY",
        ),
    )

    assert result["verified"] is False
    assert "policy_status" in result["reason"]


def test_parameter_mismatch_fails_verification():
    action = make_action()

    execution = make_execution_result(action)

    execution["parameters"][
        "expense_reduction"
    ] = 0.20

    result = OutcomeVerifier.verify(
        action,
        execution,
    )

    assert result["verified"] is False
    assert "parameters" in result["reason"]


@pytest.mark.parametrize(
    "bad_value",
    [
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_non_finite_execution_values_rejected(
    bad_value,
):
    action = make_action()

    execution = make_execution_result(action)

    execution["parameters"][
        "expense_reduction"
    ] = bad_value

    with pytest.raises(
        OutcomeVerificationError,
        match="must be finite",
    ):
        OutcomeVerifier.verify(
            action,
            execution,
        )


def test_block_cannot_verify_even_if_action_validation_is_bypassed():
    blocked = forge_action(
        policy_status="BLOCK"
    )

    with pytest.raises(
        OutcomeVerificationError,
        match="BLOCK cannot be verified",
    ):
        OutcomeVerifier.verify(
            blocked,
            make_execution_result(),
        )


def test_baseline_action_is_rejected():
    baseline = make_action(
        scenario_id="baseline",
        scenario_name="Baseline",
    )

    with pytest.raises(
        OutcomeVerificationError,
        match="Baseline is a no-op",
    ):
        OutcomeVerifier.verify(
            baseline,
            make_execution_result(baseline),
        )


def test_malformed_action_is_rejected():
    malformed = forge_action(
        parameters="not parameters"
    )

    with pytest.raises(
        OutcomeVerificationError,
        match="ActionParameters instance",
    ):
        OutcomeVerifier.verify(
            malformed,
            make_execution_result(),
        )


def test_action_remains_unchanged():
    action = make_action()

    before = action.to_dict()

    OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )

    assert action.to_dict() == before

    with pytest.raises(FrozenInstanceError):
        action.policy_status = "MODIFY"


def test_action_parameters_remain_unchanged():
    action = make_action()

    before = action.parameters

    OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )

    assert action.parameters == before

    with pytest.raises(FrozenInstanceError):
        action.parameters.expense_reduction = 0.30


def test_execution_result_remains_unchanged():
    action = make_action()

    execution = make_execution_result(action)

    before = copy.deepcopy(execution)

    OutcomeVerifier.verify(
        action,
        execution,
    )

    assert execution == before


def test_result_is_json_serializable():
    result = OutcomeVerifier.verify(
        make_action(),
        make_execution_result(),
    )

    assert isinstance(
        json.dumps(result),
        str,
    )


def test_result_contains_no_nan_or_infinity():
    result = OutcomeVerifier.verify(
        make_action(),
        make_execution_result(),
    )

    assert finite_recursive(result)


def test_verification_is_deterministic():
    action = make_action()

    execution = make_execution_result(action)

    assert (
        OutcomeVerifier.verify(
            action,
            execution,
        )
        ==
        OutcomeVerifier.verify(
            action,
            execution,
        )
    )


def test_action_executor_is_not_called(monkeypatch):
    monkeypatch.setattr(
        ActionExecutor,
        "execute",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "ActionExecutor was called"
                )
            ),
    )

    action = make_action()

    assert OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )["verified"]


def test_policy_engine_is_not_called(monkeypatch):
    monkeypatch.setattr(
        PolicyEngine,
        "evaluate",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "PolicyEngine was called"
                )
            ),
    )

    action = make_action()

    assert OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )["verified"]


def test_scenario_engine_is_not_called(monkeypatch):
    monkeypatch.setattr(
        ScenarioEngine,
        "simulate",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "ScenarioEngine was called"
                )
            ),
    )

    action = make_action()

    assert OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )["verified"]


def test_decision_optimizer_is_not_called(monkeypatch):
    monkeypatch.setattr(
        DecisionOptimizer,
        "optimize",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "DecisionOptimizer was called"
                )
            ),
    )

    action = make_action()

    assert OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )["verified"]


def test_no_network_call_is_made(monkeypatch):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs:
            (_ for _ in ()).throw(
                AssertionError(
                    "network access attempted"
                )
            ),
    )

    action = make_action()

    assert OutcomeVerifier.verify(
        action,
        make_execution_result(action),
    )["verified"]


def test_no_financial_outcome_claims_or_financial_fields():
    result = OutcomeVerifier.verify(
        make_action(),
        make_execution_result(),
    )

    forbidden_fields = {
        "expected_impact",
        "revenue",
        "expenses",
        "cash",
        "roi",
        "survival_probability",
        "decision_score",
        "action_id",
    }

    forbidden_claims = (
        "revenue improved",
        "expenses decreased",
        "cash increased",
        "financially successful",
        "merchant saved",
    )

    assert forbidden_fields.isdisjoint(result)

    assert all(
        claim not in result["reason"].lower()
        for claim in forbidden_claims
    )


def test_outcome_available_is_false():
    result = OutcomeVerifier.verify(
        make_action(),
        make_execution_result(),
    )

    assert result["outcome_available"] is False


def test_success_reason_explicitly_states_no_real_world_outcome_evaluated():
    result = OutcomeVerifier.verify(
        make_action(),
        make_execution_result(),
    )

    assert (
        "No real-world financial outcome was evaluated."
        in result["reason"]
    )


def test_scenario_id_is_not_parsed_to_reconstruct_parameters():
    action = make_action(
        scenario_id="expense_reduction_0.9",
        parameters=make_parameters(
            expense_reduction=0.17
        ),
    )

    execution = make_execution_result(action)

    assert (
        execution["parameters"]["expense_reduction"]
        == pytest.approx(0.17)
    )

    assert OutcomeVerifier.verify(
        action,
        execution,
    )["verified"] is True


def test_extra_execution_metadata_does_not_change_verification_contract():
    action = make_action()

    execution = make_execution_result(action)

    execution["message"] = (
        "arbitrary dry-run acknowledgement"
    )

    result = OutcomeVerifier.verify(
        action,
        execution,
    )

    assert result["verified"] is True

    assert set(result) == {
        "status",
        "verified",
        "verification_type",
        "scenario_id",
        "reason",
        "outcome_available",
    }