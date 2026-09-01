import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.scenario_engine import Scenario, ScenarioEngine


def make_state(**overrides):
    state = {
        "cash": 1_000_000.0,
        "monthly_revenue": 500_000.0,
        "monthly_expenses": 400_000.0,
        "net_burn": -100_000.0,
        "average_net_burn": -80_000.0,
        "runway_months": None,
        "revenue_growth": 0.05,
        "expense_growth": 0.03,
        "revenue_volatility": 0.04,
        "expense_volatility": 0.03,
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


def engine(**overrides):
    return ScenarioEngine(make_state(**overrides))


def assert_finite(value):
    if isinstance(value, dict):
        for item in value.values():
            assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_baseline_scenario_works():
    result = engine().simulate(
        ScenarioEngine.baseline(duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["baseline"] is True
    assert result["scenario_id"] == "baseline"


def test_expense_reduction_scenario_works():
    result = engine().simulate(
        ScenarioEngine.expense_reduction(0.10, duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["baseline"] is False
    assert result["assumptions"]["duration_months"] == 3
    assert result["assumptions"]["revenue_growth_adjustment"] == 0.0


def test_revenue_growth_scenario_works():
    result = engine().simulate(
        ScenarioEngine.revenue_growth(0.10, duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["assumptions"]["revenue_growth_adjustment"] == 0.10


def test_combined_scenario_works():
    scenario = ScenarioEngine.combined(0.10, 0.10, duration_months=3)
    result = engine().simulate(
        scenario,
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["assumptions"]["revenue_growth_adjustment"] == 0.10


def test_same_seed_produces_identical_result():
    scenario = ScenarioEngine.combined(0.10, 0.10, duration_months=6)
    first = engine().simulate(scenario, simulation_runs=500, horizon_months=6, seed=42)
    second = engine().simulate(scenario, simulation_runs=500, horizon_months=6, seed=42)
    assert first == second


def test_different_seeds_can_differ_when_stochastic():
    scenario = ScenarioEngine.baseline(duration_months=6)
    first = engine().simulate(scenario, simulation_runs=500, horizon_months=6, seed=42)
    second = engine().simulate(scenario, simulation_runs=500, horizon_months=6, seed=43)
    assert first != second


def test_survival_probability_is_bounded():
    result = engine().simulate(
        ScenarioEngine.baseline(duration_months=6),
        simulation_runs=500,
        horizon_months=6,
        seed=42,
    )
    assert 0.0 <= result["survival_probability"] <= 1.0


def test_shortfall_probability_complements_survival():
    result = engine().simulate(
        ScenarioEngine.baseline(duration_months=6),
        simulation_runs=500,
        horizon_months=6,
        seed=42,
    )
    assert result["probability_of_cash_shortfall"] == pytest.approx(
        1.0 - result["survival_probability"]
    )


def test_percentiles_are_ordered():
    result = engine().simulate(
        ScenarioEngine.baseline(duration_months=6),
        simulation_runs=500,
        horizon_months=6,
        seed=42,
    )
    assert result["p10_ending_cash"] <= result["median_ending_cash"]
    assert result["median_ending_cash"] <= result["p90_ending_cash"]


def test_simulated_revenue_never_becomes_negative():
    sim = engine(revenue_volatility=2.0)
    scenario = ScenarioEngine.baseline()
    _, _, revenue, _ = sim._simulate_paths(scenario, 500, 6, 42)
    assert np.all(revenue >= 0.0)


def test_simulated_expenses_never_become_negative():
    sim = engine(expense_volatility=2.0)
    scenario = ScenarioEngine.baseline(duration_months=6)
    _, _, _, expenses = sim._simulate_paths(scenario, 500, 6, 42)
    assert np.all(expenses >= 0.0)


def test_invalid_simulation_count_rejected():
    with pytest.raises(ValueError):
        engine().simulate(ScenarioEngine.baseline(), simulation_runs=99, horizon_months=3)
    with pytest.raises(ValueError):
        engine().simulate(ScenarioEngine.baseline(), simulation_runs=50_001, horizon_months=3)


def test_invalid_horizon_rejected():
    with pytest.raises(ValueError):
        engine().simulate(ScenarioEngine.baseline(), simulation_runs=100, horizon_months=2)
    with pytest.raises(ValueError):
        engine().simulate(ScenarioEngine.baseline(), simulation_runs=100, horizon_months=61)


def test_invalid_scenario_parameters_rejected():
    with pytest.raises(ValueError):
        Scenario(
            "bad",
            "Bad",
            "invalid",
            revenue_growth_adjustment=float("nan"),
        )
    with pytest.raises(ValueError):
        Scenario(
            "bad",
            "Bad",
            "invalid",
            expense_growth_adjustment=float("inf"),
        )


def test_zero_cash_is_handled():
    result = engine(cash=0.0).simulate(
        ScenarioEngine.baseline(duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["survival_probability"] == 0.0
    assert result["mean_survival_month"] == 0.0


def test_profitable_business_does_not_automatically_fail():
    result = engine(
        cash=1_000_000.0,
        monthly_revenue=500_000.0,
        monthly_expenses=400_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    ).simulate(
        ScenarioEngine.baseline(duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )
    assert result["survival_probability"] == 1.0


def test_high_burn_has_lower_survival_than_healthy_business():
    healthy = engine(
        cash=1_000_000.0,
        monthly_revenue=500_000.0,
        monthly_expenses=400_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    ).simulate(
        ScenarioEngine.baseline(duration_months=6), simulation_runs=500, horizon_months=6, seed=42
    )
    distressed = engine(
        cash=300_000.0,
        monthly_revenue=100_000.0,
        monthly_expenses=200_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    ).simulate(
        ScenarioEngine.baseline(duration_months=6), simulation_runs=500, horizon_months=6, seed=42
    )
    assert distressed["survival_probability"] < healthy["survival_probability"]


def test_scenario_assumptions_appear_in_output():
    scenario = ScenarioEngine.combined(0.10, 0.20, duration_months=6)
    result = engine().simulate(scenario, simulation_runs=100, horizon_months=6, seed=42)
    assert result["assumptions"] == {
        "revenue_growth_adjustment": 0.10,
        "expense_growth_adjustment": 0.0,
        "one_time_cash_adjustment": 0.0,
        "duration_months": 6,
        "expense_reduction": 0.20,
    }


def test_output_contains_no_nan_or_infinity():
    result = engine().simulate(
        ScenarioEngine.baseline(duration_months=6),
        simulation_runs=500,
        horizon_months=6,
        seed=42,
    )
    assert_finite(result)


def test_baseline_flag():
    assert ScenarioEngine.baseline().baseline is True
    assert ScenarioEngine.revenue_growth(0.10).baseline is False


def test_one_time_cash_adjustment_applied_exactly_once():
    base_engine = engine(
        cash=100_000.0,
        monthly_revenue=100_000.0,
        monthly_expenses=100_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    )
    scenario = Scenario(
        "cash_plus",
        "Cash Adjustment",
        "One-time cash injection.",
        one_time_cash_adjustment=100_000.0,
        duration_months=3,
    )
    result = base_engine.simulate(
        scenario, simulation_runs=100, horizon_months=3, seed=42
    )
    assert result["mean_ending_cash"] == pytest.approx(200_000.0)


def test_expense_reduction_only_applies_during_duration():
    sim = engine(
        cash=1_000_000.0,
        monthly_revenue=100_000.0,
        monthly_expenses=100_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    )
    scenario = ScenarioEngine.expense_reduction(0.50, duration_months=3)
    result = sim.simulate(scenario, simulation_runs=100, horizon_months=6, seed=42)

    # Months 1-3: +50k/month; months 4-6: 0/month.
    assert result["mean_ending_cash"] == pytest.approx(1_150_000.0)


def test_revenue_growth_only_applies_during_duration():
    sim = engine(
        cash=1_000_000.0,
        monthly_revenue=100_000.0,
        monthly_expenses=100_000.0,
        revenue_growth=0.0,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    )
    scenario = ScenarioEngine.revenue_growth(0.10, duration_months=3)
    result = sim.simulate(scenario, simulation_runs=100, horizon_months=6, seed=42)

    expected = 100_000 * 1.1 + 100_000 * 1.1**2 + 100_000 * 1.1**3 + 3 * (100_000 * 1.1**3)
    assert result["mean_ending_cash"] == pytest.approx(1_000_000 + expected - 600_000)


def test_after_duration_baseline_behavior_resumes():
    sim = engine(
        cash=1_000_000.0,
        monthly_revenue=100_000.0,
        monthly_expenses=100_000.0,
        revenue_growth=0.05,
        expense_growth=0.0,
        revenue_volatility=0.0,
        expense_volatility=0.0,
    )
    scenario = ScenarioEngine.revenue_growth(0.10, duration_months=3)
    result = sim.simulate(scenario, simulation_runs=100, horizon_months=6, seed=42)

    # Active months compound at 15%; after month 3, baseline 5% resumes.
    r1 = 100_000 * 1.15
    r2 = r1 * 1.15
    r3 = r2 * 1.15
    r4 = r3 * 1.05
    r5 = r4 * 1.05
    r6 = r5 * 1.05
    expected_ending = 1_000_000 + sum((r1, r2, r3, r4, r5, r6)) - 600_000
    assert result["mean_ending_cash"] == pytest.approx(expected_ending)


def test_invalid_expense_reduction_over_100_percent_rejected():
    with pytest.raises(ValueError):
        ScenarioEngine.expense_reduction(1.01)


def test_duration_longer_than_horizon_rejected():
    with pytest.raises(ValueError):
        engine().simulate(
            ScenarioEngine.expense_reduction(0.10, duration_months=6),
            simulation_runs=100,
            horizon_months=3,
        )


def test_extreme_volatility_never_creates_negative_expenses():
    sim = engine(
        expense_volatility=10.0,
        monthly_expenses=100_000.0,
    )
    scenario = ScenarioEngine.baseline(duration_months=6)
    _, _, _, expenses = sim._simulate_paths(scenario, 500, 6, 42)
    assert np.all(expenses >= 0.0)
    # The constrained multiplicative model is strictly non-negative by construction.
    result = sim.simulate(scenario, simulation_runs=500, horizon_months=6, seed=42)
    assert_finite(result)


def test_expense_growth_adjustment_is_supported_explicitly():
    scenario = Scenario(
        "expense_growth",
        "Expense Growth Adjustment",
        "Temporary expense growth-rate change.",
        expense_growth_adjustment=-0.05,
        duration_months=3,
    )
    result = engine().simulate(scenario, simulation_runs=100, horizon_months=3, seed=42)
    assert result["assumptions"]["expense_growth_adjustment"] == pytest.approx(-0.05)


def test_simulate_paths_validates_cash_before_return(monkeypatch):
    sim = engine()
    original_validator = ScenarioEngine._validate_simulation_outputs
    seen = {"cash": False}

    def validator(*, ending_cash, survival_month, revenue, expenses, cash=None):
        seen["cash"] = cash is not None
        return original_validator(
            ending_cash=ending_cash,
            survival_month=survival_month,
            revenue=revenue,
            expenses=expenses,
            cash=cash,
        )

    monkeypatch.setattr(
        ScenarioEngine, "_validate_simulation_outputs", staticmethod(validator)
    )

    sim._simulate_paths(
        ScenarioEngine.baseline(duration_months=3),
        simulation_runs=100,
        horizon_months=3,
        seed=42,
    )

    assert seen["cash"] is True


@pytest.mark.parametrize(
    "bad_output, output_name",
    [
        ("ending_cash", "ending_cash"),
        ("survival_month", "survival_month"),
        ("revenue", "simulated revenue paths"),
        ("expenses", "simulated expense paths"),
    ],
)
def test_non_finite_simulation_output_fails_loudly(bad_output, output_name, monkeypatch):
    original = ScenarioEngine._simulate_paths

    def corrupted_paths(self, scenario, simulation_runs, horizon_months, seed):
        ending_cash, survival_month, revenue, expenses = original(
            self, scenario, simulation_runs, horizon_months, seed
        )
        arrays = {
            "ending_cash": ending_cash,
            "survival_month": survival_month,
            "revenue": revenue,
            "expenses": expenses,
        }
        if bad_output == "survival_month":
            survival_month = survival_month.astype(float)
            survival_month[0] = np.nan
        else:
            arrays[bad_output][0] = np.nan
        return ending_cash, survival_month, revenue, expenses

    monkeypatch.setattr(ScenarioEngine, "_simulate_paths", corrupted_paths)

    with pytest.raises(RuntimeError, match=output_name):
        engine().simulate(
            ScenarioEngine.baseline(duration_months=3),
            simulation_runs=100,
            horizon_months=3,
            seed=42,
        )