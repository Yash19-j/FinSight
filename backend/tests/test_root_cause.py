import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.root_cause import RootCauseEngine


def make_state(**overrides):
    state = {
        "cash": 1_000_000.0,
        "monthly_revenue": 500_000.0,
        "monthly_expenses": 400_000.0,
        "net_burn": -100_000.0,
        "average_net_burn": -80_000.0,
        "runway_months": None,
        "revenue_growth": 0.08,
        "expense_growth": 0.0,
        "revenue_volatility": 0.03,
        "expense_volatility": 0.02,
        "revenue_expense_ratio": 1.25,
        "burn_multiple": None,
        "data_confidence": "HIGH",
        "available_data": {
            "financial_history": True,
            "payments": False,
            "settlements": False,
            "receivables": False,
            "refunds": False,
            "payouts": False,
        },
    }
    state.update(overrides)
    return state


def make_risk(
    risk_id="liquidity_high",
    category="LIQUIDITY",
    severity="HIGH",
    metric="runway_months",
    current_value=4.0,
    threshold=6.0,
    financial_impact=100_000.0,
    confidence=0.90,
):
    return {
        "risk_id": risk_id,
        "category": category,
        "severity": severity,
        "title": "Test risk",
        "metric": metric,
        "current_value": current_value,
        "threshold": threshold,
        "financial_impact": financial_impact,
        "confidence": confidence,
        "evidence": "Test evidence",
    }


def analyze(state=None, risks=None):
    return RootCauseEngine(
        state if state is not None else make_state(),
        risks if risks is not None else [],
    ).analyze()


def assert_no_nan_or_inf(value):
    if isinstance(value, dict):
        for nested in value.values():
            assert_no_nan_or_inf(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_nan_or_inf(nested)
    elif isinstance(value, float):
        assert not math.isnan(value)
        assert not math.isinf(value)


def test_healthy_business_empty_risk_list():
    assert analyze() == []


def test_liquidity_caused_by_operating_deficit():
    state = make_state(
        average_net_burn=120_000.0,
        net_burn=140_000.0,
        runway_months=4.0,
        revenue_growth=0.02,
        expense_growth=0.01,
        revenue_expense_ratio=0.8,
    )
    result = analyze(state, [make_risk()])[0]

    assert "operating expenses exceed revenue" in result["root_cause"].lower()
    assert "Structural operating deficit" in result["contributing_factors"]
    assert result["estimated_monthly_impact"] == pytest.approx(120_000.0)


def test_liquidity_caused_by_revenue_decline():
    state = make_state(
        average_net_burn=100_000.0,
        net_burn=0.0,
        runway_months=5.0,
        revenue_growth=-0.08,
        expense_growth=0.0,
    )
    result = analyze(state, [make_risk()])[0]

    assert "Revenue contraction" in result["contributing_factors"]
    assert any(e["metric"] == "revenue_growth" for e in result["evidence"])


def test_liquidity_caused_by_expense_pressure():
    state = make_state(
        average_net_burn=90_000.0,
        net_burn=0.0,
        runway_months=5.5,
        revenue_growth=0.02,
        expense_growth=0.12,
    )
    result = analyze(state, [make_risk()])[0]

    assert "Expense growth outpacing revenue growth" in result["contributing_factors"]
    assert "outpacing revenue growth" in result["root_cause"]


def test_revenue_decline():
    risk = make_risk(
        risk_id="revenue_decline_high",
        category="REVENUE",
        metric="revenue_growth",
        current_value=-0.08,
        financial_impact=None,
    )
    state = make_state(revenue_growth=-0.08, revenue_volatility=0.03)
    result = analyze(state, [risk])[0]

    assert result["root_cause"] == "Recent revenue contraction is the primary observed driver."
    assert result["estimated_monthly_impact"] is None


def test_revenue_decline_with_instability():
    risk = make_risk(
        risk_id="revenue_decline_high",
        category="REVENUE",
        metric="revenue_growth",
        current_value=-0.08,
        financial_impact=None,
    )
    state = make_state(revenue_growth=-0.08, revenue_volatility=0.15)
    result = analyze(state, [risk])[0]

    assert "unstable month-to-month growth" in result["root_cause"]
    assert "Revenue growth instability" in result["contributing_factors"]


def test_expense_acceleration():
    risk = make_risk(
        risk_id="expense_acceleration_high",
        category="EXPENSE",
        metric="expense_growth",
        current_value=0.12,
        financial_impact=None,
    )
    state = make_state(expense_growth=0.12, revenue_growth=0.04)
    result = analyze(state, [risk])[0]

    assert result["root_cause"] == "Expenses are accelerating faster than revenue."
    assert result["estimated_monthly_impact"] is None


def test_revenue_decline_and_expense_acceleration():
    risk = make_risk(
        risk_id="expense_acceleration_high",
        category="EXPENSE",
        metric="expense_growth",
        current_value=0.12,
        financial_impact=None,
    )
    state = make_state(expense_growth=0.12, revenue_growth=-0.08)
    result = analyze(state, [risk])[0]

    assert "simultaneously with revenue contraction" in result["root_cause"]
    assert result["contributing_factors"] == [
        "Expense acceleration",
        "Revenue contraction",
    ]


def test_operating_deficit_with_both_contributors():
    risk = make_risk(
        risk_id="operating_deficit_high",
        category="OPERATING_DEFICIT",
        metric="net_burn",
        current_value=300_000.0,
        financial_impact=300_000.0,
    )
    state = make_state(
        monthly_revenue=700_000.0,
        monthly_expenses=1_000_000.0,
        net_burn=300_000.0,
        revenue_expense_ratio=0.7,
        revenue_growth=-0.08,
        expense_growth=0.12,
    )
    result = analyze(state, [risk])[0]

    assert "Revenue contraction" in result["contributing_factors"]
    assert "Expense acceleration" in result["contributing_factors"]
    assert result["estimated_monthly_impact"] == pytest.approx(300_000.0)


def test_growth_instability():
    risk = make_risk(
        risk_id="growth_instability_medium",
        category="GROWTH_STABILITY",
        severity="MEDIUM",
        metric="revenue_volatility",
        current_value=0.10,
        threshold=0.03,
        financial_impact=None,
    )
    state = make_state(revenue_growth=0.03, revenue_volatility=0.10, data_confidence="MEDIUM")
    result = analyze(state, [risk])[0]

    assert "more volatile than the latest growth rate" in result["root_cause"]


def test_efficiency_cause():
    risk = make_risk(
        risk_id="efficiency_deterioration_medium",
        category="EFFICIENCY",
        severity="MEDIUM",
        metric="revenue_expense_ratio",
        current_value=0.8,
        threshold=0.9,
        financial_impact=None,
    )
    state = make_state(
        monthly_revenue=80_000.0,
        monthly_expenses=100_000.0,
        revenue_expense_ratio=0.8,
        net_burn=0.0,
    )
    result = analyze(state, [risk])[0]

    assert "insufficient relative to operating expenses" in result["root_cause"]


def test_zero_revenue():
    risk = make_risk(
        risk_id="operating_deficit_critical",
        category="OPERATING_DEFICIT",
        severity="CRITICAL",
        metric="net_burn",
        current_value=50_000.0,
        financial_impact=50_000.0,
    )
    state = make_state(
        monthly_revenue=0.0,
        monthly_expenses=50_000.0,
        net_burn=50_000.0,
        revenue_expense_ratio=0.0,
    )
    result = analyze(state, [risk])[0]

    assert result["estimated_monthly_impact"] == pytest.approx(50_000.0)
    assert_no_nan_or_inf(result)


def test_missing_optional_metric():
    risk = make_risk(
        risk_id="revenue_decline_medium",
        category="REVENUE",
        metric="revenue_growth",
        current_value=-0.03,
        financial_impact=None,
    )
    state = make_state(revenue_growth=-0.03)
    state["revenue_volatility"] = None

    result = analyze(state, [risk])[0]
    assert result["root_cause"] == "Recent revenue contraction is the primary observed driver."


def test_low_confidence():
    risk = make_risk(
        risk_id="revenue_decline_medium",
        category="REVENUE",
        metric="revenue_growth",
        current_value=-0.03,
        financial_impact=None,
    )
    state = make_state(data_confidence="LOW", revenue_growth=-0.03)
    result = analyze(state, [risk])[0]

    assert result["confidence"] <= 0.50


def test_confidence_remains_between_zero_and_one():
    categories = ["LIQUIDITY", "REVENUE", "EXPENSE", "OPERATING_DEFICIT", "GROWTH_STABILITY", "EFFICIENCY", "UNKNOWN"]
    risks = [
        make_risk(risk_id=f"risk_{i}", category=category)
        for i, category in enumerate(categories)
    ]
    results = analyze(make_state(data_confidence="HIGH"), risks)

    assert all(0.0 <= result["confidence"] <= 1.0 for result in results)


def test_no_nan_or_inf_in_output():
    risks = [
        make_risk(),
        make_risk(
            risk_id="revenue_decline_high",
            category="REVENUE",
            metric="revenue_growth",
            current_value=-0.10,
            financial_impact=None,
        ),
    ]
    state = make_state(
        average_net_burn=100_000.0,
        net_burn=120_000.0,
        runway_months=4.0,
        revenue_growth=-0.10,
        expense_growth=0.12,
    )
    results = analyze(state, risks)

    assert_no_nan_or_inf(results)


def test_unknown_risk_category_does_not_crash():
    risk = make_risk(
        risk_id="unknown_test",
        category="SOMETHING_NEW",
        metric="cash",
        current_value=1_000_000.0,
        financial_impact=None,
    )
    result = analyze(make_state(), [risk])[0]

    assert result["risk_id"] == "unknown_test"
    assert "No deterministic root-cause rule" in result["root_cause"]


def test_risk_ordering_is_preserved():
    risks = [
        make_risk(risk_id="first", category="REVENUE", metric="revenue_growth", current_value=-0.08, financial_impact=None),
        make_risk(risk_id="second", category="LIQUIDITY"),
        make_risk(risk_id="third", category="EXPENSE", metric="expense_growth", current_value=0.12, financial_impact=None),
    ]
    state = make_state(
        average_net_burn=100_000.0,
        runway_months=4.0,
        revenue_growth=-0.08,
        expense_growth=0.12,
    )

    results = analyze(state, risks)
    assert [result["risk_id"] for result in results] == ["first", "second", "third"]
