import math
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.decision_optimizer import DecisionOptimizer


def result(
    scenario_id,
    scenario_name,
    *,
    survival=0.40,
    mean_cash=500_000.0,
    p10_cash=-200_000.0,
    p90_cash=900_000.0,
    survival_month=7.0,
    horizon=12,
    runs=5_000,
    baseline=False,
    capital=0.0,
    data_confidence=None,
):
    value = {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "horizon_months": horizon,
        "simulation_runs": runs,
        "survival_probability": survival,
        "mean_ending_cash": mean_cash,
        "median_ending_cash": mean_cash,
        "p10_ending_cash": p10_cash,
        "p90_ending_cash": p90_cash,
        "mean_survival_month": survival_month,
        "probability_of_cash_shortfall": 1.0 - survival,
        "baseline": baseline,
        "assumptions": {
            "revenue_growth_adjustment": 0.0,
            "expense_growth_adjustment": 0.0,
            "one_time_cash_adjustment": capital,
            "duration_months": horizon,
        },
    }
    if data_confidence is not None:
        value["data_confidence"] = data_confidence
    return value


def baseline(**kwargs):
    return result("baseline", "Baseline", baseline=True, **kwargs)


def optimize(base=None, scenarios=None, confidence=None):
    return DecisionOptimizer(
        baseline_result=base or baseline(),
        scenario_results=scenarios or [],
        data_confidence=confidence,
    ).optimize()


def finite_recursive(value):
    if isinstance(value, dict):
        return all(finite_recursive(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_recursive(v) for v in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def test_healthy_scenario_with_no_intervention_advantage_is_no_action():
    scenario = result(
        "expense_reduction",
        "Expense Reduction",
        survival=0.40,
        mean_cash=500_000,
        p10_cash=-200_000,
        survival_month=7,
    )
    output = optimize(scenarios=[scenario])
    assert output["decision"]["classification"] == "NO_ACTION"
    assert output["recommended_scenario"]["scenario_id"] == "baseline"


def test_strong_expense_reduction_wins():
    scenario = result(
        "expense_reduction",
        "Expense Reduction",
        survival=0.80,
        mean_cash=900_000,
        p10_cash=150_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario])
    assert output["ranking"][0]["scenario_id"] == "expense_reduction"
    assert output["decision"]["classification"] == "RECOMMEND"


def test_strong_revenue_growth_wins_when_appropriate():
    scenario = result(
        "revenue_growth",
        "Revenue Growth",
        survival=0.78,
        mean_cash=850_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario])
    assert output["recommended_scenario"]["scenario_id"] == "revenue_growth"


def test_combined_scenario_can_win_when_it_has_best_outcomes():
    scenarios = [
        result(
            "revenue_growth",
            "Revenue Growth",
            survival=0.65,
            mean_cash=700_000,
            p10_cash=-50_000,
            survival_month=9,
        ),
        result(
            "combined",
            "Combined",
            survival=0.85,
            mean_cash=1_000_000,
            p10_cash=250_000,
            survival_month=11,
        ),
    ]
    output = optimize(scenarios=scenarios)
    assert output["ranking"][0]["scenario_id"] == "combined"


def test_baseline_relative_survival_improvement():
    base = baseline(survival=0.40)
    scenario = result("s1", "S1", survival=0.75)
    output = optimize(base, [scenario])
    assert output["ranking"][0]["survival_improvement"] == pytest.approx(0.35)


def test_p10_downside_improvement_is_baseline_relative():
    base = baseline(p10_cash=-200_000)
    scenario = result("s1", "S1", p10_cash=100_000)
    output = optimize(base, [scenario])
    assert output["ranking"][0]["downside_improvement"] == pytest.approx(300_000)


def test_mean_ending_cash_improvement_is_baseline_relative():
    base = baseline(mean_cash=500_000)
    scenario = result("s1", "S1", mean_cash=800_000)
    output = optimize(base, [scenario])
    assert output["ranking"][0]["ending_cash_improvement"] == pytest.approx(300_000)


def test_survival_horizon_improvement_is_baseline_relative():
    base = baseline(survival_month=7)
    scenario = result("s1", "S1", survival_month=10)
    output = optimize(base, [scenario])
    assert output["ranking"][0]["survival_horizon_improvement"] == pytest.approx(3)


def test_decision_score_stays_between_zero_and_hundred():
    scenarios = [
        result("bad", "Bad", survival=0.0, mean_cash=-1_000_000, p10_cash=-2_000_000, survival_month=1),
        result("good", "Good", survival=1.0, mean_cash=2_000_000, p10_cash=1_000_000, survival_month=12),
    ]
    output = optimize(scenarios=scenarios)
    for item in output["ranking"]:
        assert 0 <= item["decision_score"] <= 100
        assert -1 <= item["raw_score"] <= 1
        assert 0 <= item["confidence_adjusted_score"] <= 100


def test_confidence_adjusted_score_is_calculated_correctly():
    scenario = result(
        "s1",
        "S1",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario], confidence="HIGH")
    item = output["ranking"][0]
    assert item["confidence_adjusted_score"] == pytest.approx(
        item["decision_score"]
    )


@pytest.mark.parametrize(
    "confidence,multiplier",
    [
        ("HIGH", 1.00),
        ("MEDIUM", 0.90),
        ("LOW", 0.75),
    ],
)
def test_confidence_multiplier(confidence, multiplier):
    scenario = result(
        "s1",
        "S1",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario], confidence=confidence)
    item = output["ranking"][0]
    assert item["confidence"] == pytest.approx(multiplier)
    assert item["confidence_adjusted_score"] == pytest.approx(
        item["decision_score"] * multiplier
    )


def test_capital_requirement_creates_transparent_penalty():
    scenario = result(
        "capital",
        "Capital Intensive",
        survival=0.80,
        mean_cash=900_000,
        p10_cash=100_000,
        survival_month=10,
        capital=1_000_000,
    )
    output = optimize(scenarios=[scenario])
    item = output["ranking"][0]
    assert item["capital_required"] == pytest.approx(1_000_000)
    assert item["capital_penalty"] == pytest.approx(1.0)
    assert item["confidence_adjusted_score"] == pytest.approx(
        item["decision_score"] * 0.80 * item["confidence"]
    )


def test_zero_capital_requirement_has_zero_penalty():
    scenario = result(
        "free",
        "No Capital",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
        capital=0,
    )
    output = optimize(scenarios=[scenario])
    item = output["ranking"][0]
    assert item["capital_penalty"] == pytest.approx(0.0)
    assert item["confidence_adjusted_score"] == pytest.approx(
        item["decision_score"] * item["confidence"]
    )


def test_no_action_when_all_interventions_are_weak():
    scenarios = [
        result("s1", "S1", survival=0.41, mean_cash=505_000, p10_cash=-199_000, survival_month=7.1),
        result("s2", "S2", survival=0.42, mean_cash=510_000, p10_cash=-198_000, survival_month=7.2),
    ]
    output = optimize(scenarios=scenarios)
    assert output["decision"]["classification"] == "NO_ACTION"
    assert output["recommended_scenario"]["scenario_id"] == "baseline"


def test_empty_scenario_list_returns_valid_no_action():
    output = optimize(scenarios=[])
    assert output["ranking"] == []
    assert output["decision"]["classification"] == "NO_ACTION"
    assert output["recommended_scenario"]["scenario_id"] == "baseline"


def test_baseline_in_scenario_results_is_not_ranked_as_intervention():
    base = baseline()
    intervention = result("s1", "S1", survival=0.75, mean_cash=800_000, p10_cash=100_000, survival_month=10)
    output = optimize(base, [base, intervention])
    assert [item["scenario_id"] for item in output["ranking"]] == ["s1"]


def test_duplicate_intervention_ids_are_rejected():
    s1 = result("duplicate", "S1", survival=0.60)
    s2 = result("duplicate", "S2", survival=0.70)
    with pytest.raises(ValueError, match="Duplicate intervention scenario_id"):
        DecisionOptimizer(baseline(), [s1, s2])


@pytest.mark.parametrize(
    "field,value",
    [
        ("survival_probability", -0.1),
        ("survival_probability", 1.1),
        ("probability_of_cash_shortfall", -0.1),
        ("probability_of_cash_shortfall", 1.1),
    ],
)
def test_invalid_probabilities_are_rejected(field, value):
    bad = result("bad", "Bad")
    bad[field] = value
    with pytest.raises(ValueError, match="between 0 and 1"):
        DecisionOptimizer(baseline(), [bad])


@pytest.mark.parametrize(
    "field",
    [
        "mean_ending_cash",
        "median_ending_cash",
        "p10_ending_cash",
        "p90_ending_cash",
        "mean_survival_month",
    ],
)
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinity_inputs_are_rejected(field, bad_value):
    bad = result("bad", "Bad")
    bad[field] = bad_value
    with pytest.raises(ValueError, match="finite"):
        DecisionOptimizer(baseline(), [bad])


def test_ranking_is_descending_by_confidence_adjusted_score():
    scenarios = [
        result("low", "Low", survival=0.50, mean_cash=550_000, p10_cash=-100_000, survival_month=8),
        result("high", "High", survival=0.80, mean_cash=900_000, p10_cash=100_000, survival_month=10),
        result("medium", "Medium", survival=0.65, mean_cash=700_000, p10_cash=0, survival_month=9),
    ]
    output = optimize(scenarios=scenarios)
    scores = [item["confidence_adjusted_score"] for item in output["ranking"]]
    assert scores == sorted(scores, reverse=True)


def test_deterministic_tie_breaking():
    scenarios = [
        result(
            "b",
            "B",
            survival=0.50,
            mean_cash=600_000,
            p10_cash=-100_000,
            survival_month=8,
        ),
        result(
            "a",
            "A",
            survival=0.50,
            mean_cash=600_000,
            p10_cash=-100_000,
            survival_month=8,
        ),
    ]
    output = optimize(scenarios=scenarios)
    assert [item["scenario_id"] for item in output["ranking"]] == ["a", "b"]


def test_recommended_scenario_matches_ranking_winner():
    scenario = result(
        "winner",
        "Winner",
        survival=0.80,
        mean_cash=900_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario])
    assert output["recommended_scenario"]["scenario_id"] == output["ranking"][0]["scenario_id"]


def test_no_action_recommendation_points_to_baseline():
    scenario = result(
        "weak",
        "Weak",
        survival=0.41,
        mean_cash=501_000,
        p10_cash=-199_000,
        survival_month=7.1,
    )
    output = optimize(scenarios=[scenario])
    assert output["decision"]["classification"] == "NO_ACTION"
    assert output["recommended_scenario"]["scenario_id"] == "baseline"


def test_reasoning_uses_actual_metrics():
    scenario = result(
        "s1",
        "S1",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario])
    reasoning = " ".join(output["ranking"][0]["reasoning"])
    assert "35.00 percentage points" in reasoning
    assert "₹300,000.00" in reasoning
    assert "3.00 months" in reasoning
    assert "MEDIUM data confidence" in reasoning


def test_output_contains_no_nan_or_infinity():
    scenario = result(
        "s1",
        "S1",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
    )
    output = optimize(scenarios=[scenario])
    assert finite_recursive(output)


def test_higher_mean_cash_but_materially_worse_p10_is_penalized():
    safer = result(
        "safer",
        "Safer",
        survival=0.70,
        mean_cash=650_000,
        p10_cash=0,
        survival_month=9,
    )
    riskier = result(
        "riskier",
        "Riskier",
        survival=0.78,
        mean_cash=1_200_000,
        p10_cash=-400_000,
        survival_month=10,
    )
    output = optimize(scenarios=[riskier, safer])
    assert output["ranking"][0]["scenario_id"] == "safer"
    assert output["ranking"][1]["downside_improvement"] < 0


def test_capital_intensive_scenario_does_not_automatically_win():
    no_capital = result(
        "efficient",
        "Efficient",
        survival=0.78,
        mean_cash=750_000,
        p10_cash=50_000,
        survival_month=10,
        capital=0,
    )
    capital_intensive = result(
        "capital",
        "Capital",
        survival=0.90,
        mean_cash=760_000,
        p10_cash=60_000,
        survival_month=11,
        capital=2_000_000,
    )
    output = optimize(scenarios=[capital_intensive, no_capital])
    assert output["ranking"][0]["scenario_id"] == "efficient"


def test_same_inputs_always_produce_same_result():
    scenarios = [
        result("a", "A", survival=0.70, mean_cash=800_000, p10_cash=100_000, survival_month=10),
        result("b", "B", survival=0.65, mean_cash=750_000, p10_cash=50_000, survival_month=9),
    ]
    first = optimize(scenarios=scenarios)
    second = optimize(scenarios=scenarios)
    assert first == second


def test_confidence_can_be_derived_from_baseline_when_present():
    base = baseline()
    base["data_confidence"] = "LOW"
    scenario = result("s1", "S1", survival=0.75, mean_cash=800_000, p10_cash=100_000, survival_month=10)
    output = DecisionOptimizer(base, [scenario]).optimize()
    assert output["ranking"][0]["confidence"] == pytest.approx(0.75)


def test_unknown_confidence_is_rejected():
    with pytest.raises(ValueError, match="HIGH, MEDIUM, or LOW"):
        DecisionOptimizer(baseline(), [], data_confidence="UNKNOWN")


def test_non_dict_baseline_is_rejected():
    with pytest.raises(ValueError, match="baseline_result must be a dictionary"):
        DecisionOptimizer([], [])


def test_non_list_scenarios_are_rejected():
    with pytest.raises(ValueError, match="scenario_results must be a list"):
        DecisionOptimizer(baseline(), (result("s1", "S1"),))


def test_scenario_horizon_must_match_baseline():
    scenario = result("s1", "S1", horizon=6)
    with pytest.raises(ValueError, match="horizon_months must match"):
        DecisionOptimizer(baseline(), [scenario])


def test_negative_capital_requirement_is_treated_as_no_required_capital():
    scenario = result(
        "s1",
        "S1",
        survival=0.75,
        mean_cash=800_000,
        p10_cash=100_000,
        survival_month=10,
        capital=-100_000,
    )
    output = optimize(scenarios=[scenario])
    assert output["ranking"][0]["capital_required"] == pytest.approx(0.0)
    assert output["ranking"][0]["capital_penalty"] == pytest.approx(0.0)


def test_material_downside_improvement_can_qualify_without_survival_improvement():
    scenario = result(
        "downside",
        "Downside Improvement",
        survival=0.40,
        mean_cash=500_000,
        p10_cash=0,
        survival_month=7,
    )
    output = optimize(scenarios=[scenario])
    assert output["recommended_scenario"]["scenario_id"] == "downside"


def test_low_confidence_can_change_recommendation_threshold():
    scenario = result(
        "borderline",
        "Borderline",
        survival=0.62,
        mean_cash=650_000,
        p10_cash=-50_000,
        survival_month=8.5,
    )
    high = optimize(scenarios=[scenario], confidence="HIGH")
    low = optimize(scenarios=[scenario], confidence="LOW")
    assert high["ranking"][0]["confidence_adjusted_score"] > low["ranking"][0]["confidence_adjusted_score"]
    assert low["ranking"][0]["confidence_adjusted_score"] == pytest.approx(
        low["ranking"][0]["decision_score"] * 0.75
    )
