import math
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.financial_state import FinancialStateEngine


def build_state(rows):
    return FinancialStateEngine(pd.DataFrame(rows)).build_state()


def assert_no_nan_or_inf(value):
    if isinstance(value, dict):
        for nested in value.values():
            assert_no_nan_or_inf(nested)
    elif isinstance(value, float):
        assert not math.isnan(value)
        assert not math.isinf(value)


def test_normal_profitable_growing_dataset():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 80.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 110.0, "Expenses": 82.0, "Cash": 528.0},
            {"Month": 3, "Revenue": 121.0, "Expenses": 84.0, "Cash": 565.0},
            {"Month": 4, "Revenue": 133.1, "Expenses": 86.0, "Cash": 612.1},
        ]
    )

    assert state["cash"] == pytest.approx(612.1)
    assert state["monthly_revenue"] == pytest.approx(133.1)
    assert state["monthly_expenses"] == pytest.approx(86.0)
    assert state["net_burn"] < 0
    assert state["average_net_burn"] < 0
    assert state["runway_months"] is None
    assert state["revenue_growth"] > 0
    assert state["expense_growth"] > 0
    assert state["data_confidence"] == "MEDIUM"


def test_negative_cash_flow_dataset():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 140.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 105.0, "Expenses": 150.0, "Cash": 455.0},
            {"Month": 3, "Revenue": 110.0, "Expenses": 165.0, "Cash": 400.0},
        ]
    )

    assert state["net_burn"] == pytest.approx(55.0)
    assert state["average_net_burn"] > 0
    assert state["runway_months"] is not None


def test_zero_revenue_edge_case_does_not_create_infinity():
    state = build_state(
        [
            {"Month": 1, "Revenue": 0.0, "Expenses": 100.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 50.0, "Expenses": 100.0, "Cash": 450.0},
            {"Month": 3, "Revenue": 75.0, "Expenses": 100.0, "Cash": 425.0},
        ]
    )

    # 0 -> 50 is undefined percentage growth and is skipped;
    # the latest valid growth is 50 -> 75 = +50%.
    assert state["revenue_growth"] == pytest.approx(0.5)
    assert state["revenue_volatility"] == 0.0
    assert_no_nan_or_inf(state)


def test_zero_expense_edge_case():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 0.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 110.0, "Expenses": 0.0, "Cash": 610.0},
        ]
    )

    assert state["expense_growth"] == 0.0
    assert state["expense_volatility"] == 0.0
    assert state["revenue_expense_ratio"] is None
    assert state["runway_months"] is None
    assert_no_nan_or_inf(state)


def test_only_two_months_of_data():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 120.0, "Cash": 300.0},
            {"Month": 2, "Revenue": 110.0, "Expenses": 125.0, "Cash": 285.0},
        ]
    )

    assert state["revenue_growth"] == pytest.approx(0.10)
    assert state["expense_growth"] == pytest.approx(5.0 / 120.0)
    assert state["revenue_volatility"] == 0.0
    assert state["expense_volatility"] == 0.0
    assert state["data_confidence"] == "LOW"


def test_insufficient_history_single_observation():
    state = build_state(
        [{"Month": 1, "Revenue": 100.0, "Expenses": 90.0, "Cash": 250.0}]
    )

    assert state["revenue_growth"] == 0.0
    assert state["expense_growth"] == 0.0
    assert state["revenue_volatility"] == 0.0
    assert state["expense_volatility"] == 0.0
    assert state["data_confidence"] == "LOW"


def test_missing_required_column():
    df = pd.DataFrame(
        [{"Month": 1, "Revenue": 100.0, "Cash": 250.0}]
    )

    with pytest.raises(ValueError, match="Expenses"):
        FinancialStateEngine(df)


def test_no_nan_or_inf_values_in_returned_state():
    state = build_state(
        [
            {"Month": 1, "Revenue": 0.0, "Expenses": 0.0, "Cash": 100.0},
            {"Month": 2, "Revenue": 0.0, "Expenses": 0.0, "Cash": 100.0},
        ]
    )

    assert_no_nan_or_inf(state)


def test_correct_runway_uses_average_net_burn():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 140.0, "Cash": 600.0},
            {"Month": 2, "Revenue": 100.0, "Expenses": 160.0, "Cash": 550.0},
            {"Month": 3, "Revenue": 100.0, "Expenses": 150.0, "Cash": 500.0},
        ]
    )

    # Average burn = (40 + 60 + 50) / 3 = 50
    assert state["average_net_burn"] == pytest.approx(50.0)
    assert state["runway_months"] == pytest.approx(10.0)


def test_correct_growth_direction():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 100.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 120.0, "Expenses": 110.0, "Cash": 510.0},
            {"Month": 3, "Revenue": 108.0, "Expenses": 121.0, "Cash": 497.0},
        ]
    )

    assert state["revenue_growth"] < 0
    assert state["expense_growth"] > 0


def test_data_confidence_thresholds():
    medium = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 100.0, "Cash": 500.0},
            {"Month": 2, "Revenue": 101.0, "Expenses": 101.0, "Cash": 500.0},
            {"Month": 3, "Revenue": 102.0, "Expenses": 102.0, "Cash": 500.0},
            {"Month": 4, "Revenue": 103.0, "Expenses": 103.0, "Cash": 500.0},
        ]
    )
    high = build_state(
        [
            {"Month": i, "Revenue": 100.0 + i, "Expenses": 90.0 + i, "Cash": 500.0}
            for i in range(1, 8)
        ]
    )

    assert medium["data_confidence"] == "MEDIUM"
    assert high["data_confidence"] == "HIGH"


def test_current_sample_shape_marks_nonfinancial_datasets_unavailable():
    state = build_state(
        [
            {"Month": 1, "Revenue": 100.0, "Expenses": 120.0, "Cash": 300.0},
            {"Month": 2, "Revenue": 110.0, "Expenses": 125.0, "Cash": 285.0},
        ]
    )

    assert state["available_data"] == {
        "financial_history": True,
        "payments": False,
        "settlements": False,
        "receivables": False,
        "refunds": False,
        "payouts": False,
    }
