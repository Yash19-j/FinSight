import json
import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.policy_engine import PolicyEngine


def action(
    scenario_id="expense_reduction_0.1",
    scenario_name="Expense Reduction",
    *,
    scenario_type=None,
    revenue_growth=0.0,
    expense_reduction=0.10,
    capital=0.0,
    duration=6,
    include_expense_reduction=True,
):
    assumptions = {
        "revenue_growth_adjustment": revenue_growth,
        "expense_growth_adjustment": 0.0,
        "one_time_cash_adjustment": capital,
        "duration_months": duration,
    }
    if include_expense_reduction:
        assumptions["expense_reduction"] = expense_reduction

    result = {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "assumptions": assumptions,
        "baseline": scenario_id == "baseline",
        "decision_score": 82.0,
    }
    if scenario_type is not None:
        result["scenario_type"] = scenario_type
    return result


def decision(selected):
    return {
        "recommended_scenario": selected,
        "ranking": [selected],
        "baseline": action(
            "baseline",
            "Baseline",
            expense_reduction=0.0,
            include_expense_reduction=True,
        ),
        "decision": {
            "score": 82.0,
            "confidence": 1.0,
            "classification": "RECOMMEND",
        },
        "reasoning": ["Test decision"],
    }


def evaluate(selected, confidence="HIGH", capital_limit=0.0):
    return PolicyEngine(
        decision(selected),
        data_confidence=confidence,
        max_capital_required=capital_limit,
    ).evaluate()


def test_valid_baseline_is_approved():
    result = evaluate(action("baseline", "Baseline"))
    assert result["status"] == "APPROVE"
    assert result["approved_action"]["scenario_id"] == "baseline"


def test_normal_revenue_growth_is_approved():
    selected = action(
        "revenue_growth_0.10",
        "Revenue Growth",
        scenario_type="REVENUE_GROWTH",
        revenue_growth=0.10,
        include_expense_reduction=False,
    )
    result = evaluate(selected)
    assert result["status"] == "APPROVE"
    assert result["approved_action"]["assumptions"]["revenue_growth_adjustment"] == pytest.approx(0.10)


def test_revenue_growth_exactly_at_20_percent_is_approved():
    selected = action(
        "revenue_growth_0.2",
        "Revenue Growth",
        scenario_type="REVENUE_GROWTH",
        revenue_growth=0.20,
        include_expense_reduction=False,
    )
    result = evaluate(selected)
    assert result["status"] == "APPROVE"
    rule = next(r for r in result["policy"]["rules_evaluated"] if r["rule"] == "MAX_REVENUE_GROWTH_ADJUSTMENT")
    assert rule["requested"] == pytest.approx(0.20)
    assert rule["limit"] == pytest.approx(0.20)


def test_revenue_growth_above_20_percent_is_modified_to_20():
    selected = action(
        "revenue_growth_0.3",
        "Revenue Growth",
        scenario_type="REVENUE_GROWTH",
        revenue_growth=0.30,
        include_expense_reduction=False,
    )
    result = evaluate(selected)
    assert result["status"] == "MODIFY"
    assert result["original_action"]["assumptions"]["revenue_growth_adjustment"] == pytest.approx(0.30)
    assert result["approved_action"]["assumptions"]["revenue_growth_adjustment"] == pytest.approx(0.20)
    assert result["original_action"] == selected


def test_expense_reduction_exactly_30_percent_is_approved():
    selected = action(expense_reduction=0.30)
    result = evaluate(selected)
    assert result["status"] == "APPROVE"
    assert result["approved_action"]["assumptions"]["expense_reduction"] == pytest.approx(0.30)


def test_expense_reduction_between_30_and_50_is_modified_to_30():
    selected = action(expense_reduction=0.40)
    result = evaluate(selected)
    assert result["status"] == "MODIFY"
    assert result["approved_action"]["assumptions"]["expense_reduction"] == pytest.approx(0.30)
    rule = next(r for r in result["policy"]["rules_evaluated"] if r["rule"] == "MAX_EXPENSE_REDUCTION")
    assert rule["requested"] == pytest.approx(0.40)
    assert rule["limit"] == pytest.approx(0.30)


def test_expense_reduction_exactly_50_percent_is_modified_to_30():
    result = evaluate(action(expense_reduction=0.50))
    assert result["status"] == "MODIFY"
    assert result["approved_action"]["assumptions"]["expense_reduction"] == pytest.approx(0.30)


def test_expense_reduction_above_50_percent_is_blocked():
    result = evaluate(action(expense_reduction=0.60))
    assert result["status"] == "BLOCK"
    assert result["approved_action"] is None
    assert any("50%" in item for item in result["policy"]["violations"])


def test_capital_within_limit_is_allowed():
    result = evaluate(action(capital=500_000), capital_limit=500_000)
    assert result["status"] == "APPROVE"
    assert result["capital_required"] == pytest.approx(500_000)
    assert result["capital_limit"] == pytest.approx(500_000)


def test_capital_above_limit_is_blocked():
    result = evaluate(action(capital=1_000_000), capital_limit=500_000)
    assert result["status"] == "BLOCK"
    assert result["approved_action"] is None
    rule = next(r for r in result["policy"]["rules_evaluated"] if r["rule"] == "MAX_CAPITAL_REQUIRED")
    assert rule["status"] == "BLOCK"
    assert rule["requested"] == pytest.approx(1_000_000)
    assert rule["limit"] == pytest.approx(500_000)


def test_negative_capital_requirement_becomes_zero_required_capital():
    selected = action(capital=-100_000)
    result = evaluate(selected)
    assert result["status"] == "APPROVE"
    assert result["capital_required"] == pytest.approx(0.0)
    assert result["approved_action"]["assumptions"]["one_time_cash_adjustment"] == pytest.approx(-100_000)


@pytest.mark.parametrize("confidence,expected", [("HIGH", 1.0), ("MEDIUM", 0.9), ("LOW", 0.75)])
def test_confidence_values(confidence, expected):
    result = evaluate(action(), confidence=confidence)
    assert result["confidence"] == pytest.approx(expected)


def test_medium_confidence_passes_with_warning():
    result = evaluate(action(), confidence="MEDIUM")
    assert result["status"] == "APPROVE"
    assert result["policy"]["warnings"]


def test_low_confidence_blocks_automatic_execution():
    result = evaluate(action(), confidence="LOW")
    assert result["status"] == "BLOCK"
    assert result["approved_action"] is None
    assert any("LOW" in item for item in result["policy"]["violations"])
    assert any("presented to the user" in item for item in result["reasoning"])


def test_unknown_confidence_is_rejected():
    with pytest.raises(ValueError, match="HIGH, MEDIUM, or LOW"):
        evaluate(action(), confidence="UNKNOWN")


def test_invalid_scenario_type_is_rejected():
    selected = action(scenario_type="FIRE_EMPLOYEES")
    with pytest.raises(ValueError, match="Unsupported scenario type"):
        evaluate(selected)


def test_missing_assumptions_are_rejected():
    selected = action()
    selected.pop("assumptions")
    with pytest.raises(ValueError, match="assumptions must be a dictionary"):
        evaluate(selected)


def test_missing_required_expense_assumption_is_rejected():
    selected = action(include_expense_reduction=False)
    with pytest.raises(ValueError, match="expense_reduction"):
        evaluate(selected)


def test_invalid_duration_is_rejected():
    selected = action(duration=0)
    with pytest.raises(ValueError, match="duration_months"):
        evaluate(selected)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numeric_inputs_are_rejected(bad):
    selected = action(capital=bad)
    with pytest.raises(ValueError, match="finite"):
        evaluate(selected)


def test_output_contains_no_nan_or_inf():
    result = evaluate(action(expense_reduction=0.40))

    def walk(value):
        if isinstance(value, dict):
            return all(walk(v) for v in value.values())
        if isinstance(value, list):
            return all(walk(v) for v in value)
        if isinstance(value, float):
            return math.isfinite(value)
        return True

    assert walk(result)


def test_approve_preserves_original_assumptions():
    selected = action(revenue_growth=0.10, expense_reduction=0.20, capital=0)
    result = evaluate(selected)
    assert result["status"] == "APPROVE"
    assert result["approved_action"]["assumptions"] == selected["assumptions"]


def test_modify_explicitly_returns_modified_assumptions():
    selected = action(revenue_growth=0.30, expense_reduction=0.40)
    selected["scenario_type"] = "COMBINED"
    result = evaluate(selected)
    assert result["status"] == "MODIFY"
    assert result["approved_action"]["assumptions"]["revenue_growth_adjustment"] == pytest.approx(0.20)
    assert result["approved_action"]["assumptions"]["expense_reduction"] == pytest.approx(0.30)


def test_block_returns_none_approved_action():
    result = evaluate(action(expense_reduction=0.60))
    assert result["approved_action"] is None


def test_policy_rules_are_machine_readable():
    result = evaluate(action(expense_reduction=0.40))
    assert all({"rule", "status"}.issubset(rule) for rule in result["policy"]["rules_evaluated"])
    assert any(rule["rule"] == "MAX_EXPENSE_REDUCTION" and rule["status"] == "MODIFY" for rule in result["policy"]["rules_evaluated"])


def test_policy_limits_are_exposed():
    result = evaluate(action(), capital_limit=2_000_000)
    assert result["policy_limits"] == {
        "max_revenue_growth_adjustment": pytest.approx(0.20),
        "max_expense_reduction_approve": pytest.approx(0.30),
        "max_expense_reduction_modify": pytest.approx(0.50),
        "max_capital_required": pytest.approx(2_000_000),
    }


def test_critical_risk_does_not_bypass_hard_safety_rules():
    selected = action(expense_reduction=0.60, capital=1_000_000)
    selected["risks"] = [{"severity": "CRITICAL", "risk_id": "liquidity_critical"}]
    result = evaluate(selected, capital_limit=0)
    assert result["status"] == "BLOCK"
    assert result["approved_action"] is None


def test_policy_does_not_change_decision_optimizer_score():
    selected = action(expense_reduction=0.40)
    result = evaluate(selected)
    assert result["original_action"]["decision_score"] == pytest.approx(82.0)
    assert result["approved_action"]["decision_score"] == pytest.approx(82.0)


def test_same_input_produces_identical_policy_result():
    selected = action(expense_reduction=0.40)
    first = evaluate(selected)
    second = evaluate(selected)
    assert first == second


def test_no_external_io_is_used(monkeypatch):
    called = []
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: called.append(args))
    result = evaluate(action())
    assert result["status"] == "APPROVE"
    assert called == []


def test_output_is_json_serializable():
    result = evaluate(action(expense_reduction=0.40))
    json.dumps(result, allow_nan=False)
