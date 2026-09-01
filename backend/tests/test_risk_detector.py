import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.risk_detector import RiskDetector


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


def detect(**overrides):
    return RiskDetector(make_state(**overrides)).detect()


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


def test_no_risks_for_healthy_business():
    assert detect() == []


def test_critical_liquidity_risk():
    risks = detect(
        runway_months=2.4,
        average_net_burn=310_000.0,
        net_burn=0.0,
        monthly_revenue=500_000.0,
        monthly_expenses=500_000.0,
    )

    liquidity = next(r for r in risks if r["category"] == "LIQUIDITY")
    assert liquidity["severity"] == "CRITICAL"
    assert liquidity["current_value"] == pytest.approx(2.4)
    assert liquidity["financial_impact"] == pytest.approx(310_000.0)


def test_high_liquidity_risk():
    risks = detect(
        runway_months=4.5,
        average_net_burn=100_000.0,
        net_burn=0.0,
        monthly_revenue=500_000.0,
        monthly_expenses=500_000.0,
    )

    liquidity = next(r for r in risks if r["category"] == "LIQUIDITY")
    assert liquidity["severity"] == "HIGH"


def test_revenue_decline():
    risks = detect(revenue_growth=-0.04)
    decline = next(r for r in risks if r["category"] == "REVENUE")

    assert decline["severity"] == "MEDIUM"
    assert decline["current_value"] == pytest.approx(-0.04)


def test_severe_revenue_decline():
    risks = detect(revenue_growth=-0.20)
    decline = next(r for r in risks if r["category"] == "REVENUE")

    assert decline["severity"] == "CRITICAL"


def test_expense_acceleration():
    risks = detect(expense_growth=0.12)
    acceleration = next(r for r in risks if r["category"] == "EXPENSE")

    assert acceleration["severity"] == "HIGH"
    assert acceleration["current_value"] == pytest.approx(0.12)


def test_operating_deficit():
    risks = detect(
        monthly_revenue=100_000.0,
        monthly_expenses=120_000.0,
        net_burn=20_000.0,
        revenue_expense_ratio=100_000.0 / 120_000.0,
    )
    deficit = next(r for r in risks if r["category"] == "OPERATING_DEFICIT")

    assert deficit["severity"] == "HIGH"
    assert deficit["financial_impact"] == pytest.approx(20_000.0)
    assert not any(r["category"] == "EFFICIENCY" for r in risks)


def test_growth_instability():
    risks = detect(
        revenue_growth=0.03,
        revenue_volatility=0.08,
        data_confidence="MEDIUM",
    )
    instability = next(r for r in risks if r["category"] == "GROWTH_STABILITY")

    assert instability["severity"] == "MEDIUM"


def test_low_confidence_suppresses_growth_instability():
    risks = detect(
        revenue_growth=0.03,
        revenue_volatility=0.50,
        data_confidence="LOW",
    )

    assert not any(r["category"] == "GROWTH_STABILITY" for r in risks)


def test_zero_revenue_does_not_crash():
    risks = detect(
        monthly_revenue=0.0,
        monthly_expenses=50_000.0,
        net_burn=50_000.0,
        revenue_expense_ratio=0.0,
    )

    deficit = next(r for r in risks if r["category"] == "OPERATING_DEFICIT")
    assert deficit["severity"] == "CRITICAL"
    assert_no_nan_or_inf(risks)


def test_no_nan_or_inf_in_output():
    risks = detect(
        runway_months=5.0,
        average_net_burn=50_000.0,
        revenue_growth=-0.08,
        expense_growth=0.15,
        revenue_volatility=0.20,
        monthly_revenue=0.0,
        monthly_expenses=50_000.0,
        net_burn=50_000.0,
        revenue_expense_ratio=None,
    )

    assert_no_nan_or_inf(risks)


def test_multiple_risks_sort_correctly():
    risks = detect(
        runway_months=2.0,
        average_net_burn=100_000.0,
        revenue_growth=-0.10,
        expense_growth=0.07,
        monthly_revenue=100_000.0,
        monthly_expenses=130_000.0,
        net_burn=30_000.0,
        revenue_expense_ratio=100_000.0 / 130_000.0,
    )

    severities = [r["severity"] for r in risks]
    ranks = [RiskDetector.SEVERITY_RANK[s] for s in severities]
    assert ranks == sorted(ranks, reverse=True)
    assert risks[0]["severity"] == "CRITICAL"


def test_confidence_stays_between_zero_and_one():
    for confidence in ("LOW", "MEDIUM", "HIGH"):
        risks = detect(
            data_confidence=confidence,
            runway_months=2.0,
            average_net_burn=100_000.0,
            revenue_growth=-0.20,
            expense_growth=0.30,
        )
        assert risks
        assert all(0.0 <= risk["confidence"] <= 1.0 for risk in risks)


def test_profitable_none_runway_has_no_liquidity_risk():
    risks = detect(
        runway_months=None,
        average_net_burn=-50_000.0,
        net_burn=-60_000.0,
    )

    assert not any(r["category"] == "LIQUIDITY" for r in risks)


def test_efficiency_risk_only_when_not_duplicate_of_operating_deficit():
    risks = detect(
        revenue_expense_ratio=0.80,
        net_burn=0.0,
        monthly_revenue=80_000.0,
        monthly_expenses=100_000.0,
    )

    efficiency = next(r for r in risks if r["category"] == "EFFICIENCY")
    assert efficiency["severity"] == "MEDIUM"
