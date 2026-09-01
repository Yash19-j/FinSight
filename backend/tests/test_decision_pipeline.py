import copy
import json
import math
import socket
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.action import Action
from backend.app.services.action_executor import ActionExecutor
from backend.app.services.decision_optimizer import DecisionOptimizer
from backend.app.services.decision_pipeline import DecisionPipeline
from backend.app.services.financial_state import FinancialStateEngine
from backend.app.services.outcome_verifier import OutcomeVerifier
from backend.app.services.policy_engine import PolicyEngine
from backend.app.services.risk_detector import RiskDetector
from backend.app.services.root_cause import RootCauseEngine
from backend.app.services.scenario_engine import ScenarioEngine


def make_df():
    return pd.DataFrame(
        {
            "Month": [1, 2, 3, 4, 5, 6],
            "Revenue": [500000, 490000, 475000, 460000, 450000, 440000],
            "Expenses": [650000, 670000, 700000, 730000, 760000, 790000],
            "Cash": [5000000, 4820000, 4595000, 4325000, 4015000, 3665000],
        }
    )


def healthy_df():
    return pd.DataFrame(
        {
            "Month": [1, 2, 3, 4, 5, 6],
            "Revenue": [500000, 525000, 551250, 578812, 607753, 638141],
            "Expenses": [300000, 303000, 306030, 309090, 312181, 315303],
            "Cash": [2000000, 2200000, 2450000, 2730000, 3030000, 3350000],
        }
    )


def run_pipeline(df=None, **kwargs):
    defaults = {
        "simulation_runs": 100,
        "horizon_months": 6,
        "random_seed": 42,
    }
    defaults.update(kwargs)
    return DecisionPipeline(
        df if df is not None else make_df(),
        **defaults,
    ).run()


def finite_recursive(value):
    if isinstance(value, dict):
        return all(finite_recursive(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_recursive(v) for v in value)
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, np.integer)):
        return True
    if value is None or isinstance(value, (bool, str)):
        return True
    return False


def _run_pipeline_with_selected_scenario(
    monkeypatch,
    scenario_id,
    **kwargs,
):
    """Use real engines except for deterministic optimizer selection."""

    class SelectingOptimizer:
        def __init__(
            self,
            baseline_result,
            scenario_results,
            data_confidence,
        ):
            self.baseline_result = baseline_result
            self.scenario_results = scenario_results

        def optimize(self):
            all_results = [
                self.baseline_result,
                *self.scenario_results,
            ]
            selected = next(
                (
                    item
                    for item in all_results
                    if item["scenario_id"] == scenario_id
                ),
                None,
            )

            if selected is None:
                selected = {
                    "scenario_id": scenario_id,
                    "scenario_name": "Unknown",
                }

            return {
                "recommended_scenario": {
                    key: selected[key]
                    for key in ("scenario_id", "scenario_name")
                    if key in selected
                },
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "CONSIDER",
                },
                "reasoning": ["test selection"],
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        SelectingOptimizer,
    )

    return run_pipeline(**kwargs)


def test_healthy_dataframe_runs():
    output = run_pipeline(healthy_df())
    assert "financial_state" in output
    assert "decision" in output
    assert isinstance(output["risks"], list)
    assert isinstance(output["root_causes"], list)


def test_loss_making_dataframe_runs():
    output = run_pipeline()
    assert output["financial_state"]["net_burn"] > 0
    assert output["risks"]


def test_pipeline_returns_all_major_sections():
    output = run_pipeline()
    assert set(output) == {
        "financial_state",
        "risks",
        "root_causes",
        "scenarios",
        "decision",
        "policy",
        "action",
        "execution",
        "verification",
        "metadata",
    }


def test_exactly_one_baseline_and_three_interventions():
    scenarios = run_pipeline()["scenarios"]
    assert sum(bool(s["baseline"]) for s in scenarios) == 1
    ids = {s["scenario_id"] for s in scenarios}
    assert "baseline" in ids
    assert any(s.startswith("revenue_growth_") for s in ids)
    assert any(s.startswith("expense_reduction_") for s in ids)
    assert any(s.startswith("combined_revenue_") for s in ids)


def test_optimizer_receives_baseline_interventions_and_confidence(
    monkeypatch,
):
    captured = {}

    class SpyOptimizer:
        def __init__(
            self,
            baseline_result,
            scenario_results,
            data_confidence,
        ):
            captured["baseline"] = baseline_result
            captured["scenarios"] = scenario_results
            captured["confidence"] = data_confidence
            self.baseline_result = baseline_result

        def optimize(self):
            return {
                "recommended_scenario": self.baseline_result,
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "NO_ACTION",
                },
                "reasoning": ["test"],
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        SpyOptimizer,
    )

    output = run_pipeline()

    assert captured["baseline"]["baseline"] is True
    assert len(captured["scenarios"]) == 3
    assert all(item["baseline"] is False for item in captured["scenarios"])
    assert captured["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert output["decision"]["baseline"] == captured["baseline"]


def test_data_confidence_flows_from_state(monkeypatch):
    captured = {}
    original_build = FinancialStateEngine.build_state

    def build_with_known_confidence(self):
        state = original_build(self)
        state["data_confidence"] = "HIGH"
        return state

    class SpyOptimizer:
        def __init__(
            self,
            baseline_result,
            scenario_results,
            data_confidence,
        ):
            captured["confidence"] = data_confidence
            self.baseline_result = baseline_result

        def optimize(self):
            return {
                "recommended_scenario": self.baseline_result,
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "NO_ACTION",
                },
                "reasoning": [],
            }

    monkeypatch.setattr(
        FinancialStateEngine,
        "build_state",
        build_with_known_confidence,
    )
    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        SpyOptimizer,
    )

    run_pipeline()
    assert captured["confidence"] == "HIGH"


def test_same_seed_is_reproducible():
    assert run_pipeline() == run_pipeline()


def test_different_seed_can_change_stochastic_results():
    first = run_pipeline(random_seed=42)
    second = run_pipeline(random_seed=43)
    assert first["scenarios"] != second["scenarios"]


def test_severe_risk_business_produces_risks():
    df = make_df().copy()
    df["Cash"] = [500000, 400000, 300000, 200000, 100000, 50000]
    assert run_pipeline(df)["risks"]


def test_invalid_dataframe_input_is_rejected():
    with pytest.raises(TypeError, match="pandas DataFrame"):
        DecisionPipeline([1, 2, 3])


def test_missing_financial_columns_are_rejected():
    df = make_df().drop(columns=["Expenses"])
    with pytest.raises(RuntimeError, match="financial-state construction"):
        DecisionPipeline(
            df,
            simulation_runs=100,
            horizon_months=3,
        ).run()


def test_invalid_simulation_count_is_rejected():
    with pytest.raises(ValueError, match="between 100 and 50000"):
        DecisionPipeline(
            make_df(),
            simulation_runs=99,
            horizon_months=3,
        ).run()


def test_invalid_horizon_is_rejected():
    with pytest.raises(ValueError, match="between 3 and 60"):
        DecisionPipeline(
            make_df(),
            simulation_runs=100,
            horizon_months=2,
        ).run()


def test_pipeline_does_not_mutate_input_dataframe():
    df = make_df()
    before = df.copy(deep=True)
    run_pipeline(df)
    pd.testing.assert_frame_equal(df, before)


def test_output_contains_metadata():
    output = run_pipeline(
        simulation_runs=100,
        horizon_months=3,
        random_seed=77,
    )
    assert output["metadata"] == {
        "simulation_runs": 100,
        "horizon_months": 3,
        "random_seed": 77,
    }


def test_scenario_results_preserve_core_statistics():
    for scenario in run_pipeline()["scenarios"]:
        assert 0.0 <= scenario["survival_probability"] <= 1.0
        for field in (
            "mean_ending_cash",
            "median_ending_cash",
            "p10_ending_cash",
            "p90_ending_cash",
            "mean_survival_month",
        ):
            assert math.isfinite(float(scenario[field]))


def test_decision_contains_recommendation_and_reasoning():
    decision = run_pipeline()["decision"]
    assert isinstance(decision["ranking"], list)
    assert decision["recommended_scenario"] is not None
    assert isinstance(decision["reasoning"], list)


def test_empty_risk_and_root_cause_lists_are_handled(monkeypatch):
    monkeypatch.setattr(RiskDetector, "detect", lambda self: [])
    monkeypatch.setattr(RootCauseEngine, "analyze", lambda self: [])
    output = run_pipeline()
    assert output["risks"] == []
    assert output["root_causes"] == []


def test_existing_engines_are_invoked(monkeypatch):
    calls = []

    original_state = FinancialStateEngine.build_state
    original_risk = RiskDetector.detect
    original_root = RootCauseEngine.analyze
    original_simulate = ScenarioEngine.simulate
    original_optimize = DecisionOptimizer.optimize

    def state_spy(self):
        calls.append("state")
        return original_state(self)

    def risk_spy(self):
        calls.append("risk")
        return original_risk(self)

    def root_spy(self):
        calls.append("root")
        return original_root(self)

    def simulate_spy(self, *args, **kwargs):
        calls.append("simulate")
        return original_simulate(self, *args, **kwargs)

    def optimize_spy(self):
        calls.append("optimize")
        return original_optimize(self)

    monkeypatch.setattr(FinancialStateEngine, "build_state", state_spy)
    monkeypatch.setattr(RiskDetector, "detect", risk_spy)
    monkeypatch.setattr(RootCauseEngine, "analyze", root_spy)
    monkeypatch.setattr(ScenarioEngine, "simulate", simulate_spy)
    monkeypatch.setattr(DecisionOptimizer, "optimize", optimize_spy)

    run_pipeline()
    assert calls[0:3] == ["state", "risk", "root"]
    assert calls.count("simulate") == 4
    assert calls[-1] == "optimize"


def test_simulation_failure_is_wrapped(monkeypatch):
    def fail_simulate(*args, **kwargs):
        raise ValueError("synthetic simulation failure")

    monkeypatch.setattr(ScenarioEngine, "simulate", fail_simulate)

    with pytest.raises(
        RuntimeError,
        match="scenario simulation.*synthetic simulation failure",
    ):
        run_pipeline()


def test_pipeline_output_has_no_nan_or_inf():
    assert finite_recursive(run_pipeline())


def test_custom_scenario_assumptions_are_configurable():
    output = run_pipeline(
        revenue_growth_adjustment=0.05,
        expense_reduction=0.20,
        scenario_duration_months=3,
    )
    assumptions = {
        s["scenario_id"]: s["assumptions"]
        for s in output["scenarios"]
    }

    assert assumptions["revenue_growth_0.05"][
        "revenue_growth_adjustment"
    ] == pytest.approx(0.05)

    assert assumptions["expense_reduction_0.2"][
        "expense_reduction"
    ] == pytest.approx(0.20)

    assert assumptions[
        "combined_revenue_0.05_expense_reduction_0.2"
    ]["duration_months"] == 3


def test_none_seed_is_supported_and_reported():
    assert run_pipeline(random_seed=None)["metadata"]["random_seed"] is None


@pytest.mark.parametrize(
    ("scenario_id", "expected_status"),
    [
        ("baseline", "APPROVE"),
        ("revenue_growth_0.1", "APPROVE"),
        ("expense_reduction_0.1", "APPROVE"),
        ("combined_revenue_0.1_expense_reduction_0.1", "APPROVE"),
    ],
)
def test_policy_resolution_uses_authoritative_scenario_result(
    monkeypatch,
    scenario_id,
    expected_status,
):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        scenario_id,
    )
    selected = next(
        item
        for item in output["scenarios"]
        if item["scenario_id"] == scenario_id
    )

    assert output["policy"]["status"] == expected_status
    assert output["policy"]["original_action"] == selected
    assert output["policy"]["original_action"]["assumptions"] == selected[
        "assumptions"
    ]


def test_policy_receives_complete_authoritative_scenario(monkeypatch):
    captured = {}

    class SpyPolicy:
        def __init__(self, decision, data_confidence):
            captured["decision"] = decision
            captured["confidence"] = data_confidence

        def evaluate(self):
            action = captured["decision"]["recommended_scenario"]
            return {
                "status": "APPROVE",
                "original_action": action,
                "approved_action": action,
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": [],
                "confidence": 1.0,
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        SpyPolicy,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    selected = next(
        item
        for item in output["scenarios"]
        if item["scenario_id"] == "expense_reduction_0.1"
    )
    received = captured["decision"]["recommended_scenario"]

    assert received == selected
    assert received["assumptions"] is selected["assumptions"]
    assert received["baseline"] is selected["baseline"]
    assert received["survival_probability"] == selected[
        "survival_probability"
    ]
    assert captured["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert output["policy"]["original_action"] == selected


def test_does_not_reconstruct_assumptions_from_scenario_id(monkeypatch):
    original_simulate = ScenarioEngine.simulate
    captured = {}

    def simulate_with_authoritative_assumption(
        self,
        scenario,
        *args,
        **kwargs,
    ):
        result = original_simulate(self, scenario, *args, **kwargs)
        if result["scenario_id"] == "expense_reduction_0.1":
            result["assumptions"]["expense_reduction"] = 0.12345
        return result

    class SpyPolicy:
        def __init__(self, decision, data_confidence):
            captured["action"] = decision["recommended_scenario"]

        def evaluate(self):
            return {
                "status": "APPROVE",
                "original_action": captured["action"],
                "approved_action": captured["action"],
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": [],
                "confidence": 1.0,
            }

    monkeypatch.setattr(
        ScenarioEngine,
        "simulate",
        simulate_with_authoritative_assumption,
    )
    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        SpyPolicy,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["policy"]["original_action"]["assumptions"][
        "expense_reduction"
    ] == pytest.approx(0.12345)


def test_missing_recommended_scenario_id_is_rejected(monkeypatch):
    class MissingIdOptimizer:
        def __init__(self, baseline_result, scenario_results, data_confidence):
            self.baseline_result = baseline_result

        def optimize(self):
            return {
                "recommended_scenario": {"scenario_name": "Missing ID"},
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "NO_ACTION",
                },
                "reasoning": [],
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        MissingIdOptimizer,
    )

    with pytest.raises(RuntimeError, match="scenario_id is missing or invalid"):
        run_pipeline()


def test_unknown_recommended_scenario_id_is_rejected(monkeypatch):
    class UnknownIdOptimizer:
        def __init__(self, baseline_result, scenario_results, data_confidence):
            self.baseline_result = baseline_result

        def optimize(self):
            return {
                "recommended_scenario": {
                    "scenario_id": "not_a_real_scenario",
                    "scenario_name": "Unknown",
                },
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "NO_ACTION",
                },
                "reasoning": [],
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        UnknownIdOptimizer,
    )

    with pytest.raises(
        RuntimeError,
        match="could not resolve recommended scenario_id",
    ):
        run_pipeline()


def test_duplicate_recommended_scenario_id_is_rejected(monkeypatch):
    original = DecisionPipeline._simulate_scenarios

    def duplicate(self, engine, scenarios):
        results = original(self, engine, scenarios)
        results.append(dict(results[1]))
        return results

    monkeypatch.setattr(
        DecisionPipeline,
        "_simulate_scenarios",
        duplicate,
    )

    class SelectingOptimizer:
        def __init__(self, baseline_result, scenario_results, data_confidence):
            self.baseline_result = baseline_result

        def optimize(self):
            return {
                "recommended_scenario": {
                    "scenario_id": "revenue_growth_0.1",
                    "scenario_name": "Revenue Growth",
                },
                "ranking": [],
                "baseline": self.baseline_result,
                "decision": {
                    "score": 50.0,
                    "confidence": 1.0,
                    "classification": "CONSIDER",
                },
                "reasoning": [],
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.DecisionOptimizer",
        SelectingOptimizer,
    )

    with pytest.raises(
        RuntimeError,
        match="found multiple ScenarioEngine results",
    ):
        run_pipeline()


def test_policy_modify_does_not_mutate_original_scenario(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.4",
        expense_reduction=0.4,
    )

    original = next(
        item
        for item in output["scenarios"]
        if item["scenario_id"] == "expense_reduction_0.4"
    )

    assert output["policy"]["status"] == "MODIFY"
    assert original["assumptions"]["expense_reduction"] == pytest.approx(0.4)
    assert output["policy"]["approved_action"]["assumptions"][
        "expense_reduction"
    ] == pytest.approx(0.3)


def test_policy_block_has_no_approved_action(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.6",
        expense_reduction=0.6,
    )

    assert output["policy"]["status"] == "BLOCK"
    assert output["policy"]["approved_action"] is None


def test_policy_failure_is_wrapped(monkeypatch):
    class FailingPolicy:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self):
            raise ValueError("synthetic policy failure")

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        FailingPolicy,
    )

    with pytest.raises(
        RuntimeError,
        match="policy evaluation.*synthetic policy failure",
    ):
        run_pipeline()


# ----------------------------- Step 13 ---------------------------------


def test_step13_full_approve_intervention_flow(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    approved = output["policy"]["approved_action"]

    assert output["policy"]["status"] == "APPROVE"
    assert output["action"] is not None
    assert output["action"]["scenario_id"] == approved["scenario_id"]
    assert output["action"]["parameters"] == approved["assumptions"]
    assert output["execution"]["status"] == "SIMULATED"
    assert output["execution"]["mode"] == "DRY_RUN"
    assert output["verification"]["status"] == "EXECUTION_VERIFIED"
    assert output["verification"]["verified"] is True


def test_step13_full_modify_flow_uses_approved_parameters(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.4",
        expense_reduction=0.4,
    )

    original = next(
        item
        for item in output["scenarios"]
        if item["scenario_id"] == "expense_reduction_0.4"
    )
    approved = output["policy"]["approved_action"]

    assert output["policy"]["status"] == "MODIFY"
    assert original["assumptions"]["expense_reduction"] == pytest.approx(0.4)
    assert approved["assumptions"]["expense_reduction"] == pytest.approx(0.3)
    assert output["action"]["parameters"]["expense_reduction"] == pytest.approx(
        0.3
    )
    assert output["execution"]["parameters"]["expense_reduction"] == pytest.approx(
        0.3
    )
    assert output["verification"]["status"] == "EXECUTION_VERIFIED"


def test_step13_modified_parameter_is_not_reconstructed_from_id(monkeypatch):
    original_simulate = ScenarioEngine.simulate

    def simulate_with_non_id_value(self, scenario, *args, **kwargs):
        result = original_simulate(self, scenario, *args, **kwargs)
        if result["scenario_id"] == "expense_reduction_0.4":
            result["assumptions"]["expense_reduction"] = 0.41
        return result

    monkeypatch.setattr(
        ScenarioEngine,
        "simulate",
        simulate_with_non_id_value,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.4",
        expense_reduction=0.4,
    )

    assert output["policy"]["approved_action"]["assumptions"][
        "expense_reduction"
    ] == pytest.approx(0.30)
    assert output["action"]["parameters"]["expense_reduction"] == pytest.approx(
        0.30
    )


def test_step13_block_skips_executor_and_verifier(monkeypatch):
    def fail_execute(*args, **kwargs):
        raise AssertionError("executor must not run on BLOCK")

    def fail_verify(*args, **kwargs):
        raise AssertionError("verifier must not run on BLOCK")

    monkeypatch.setattr(ActionExecutor, "execute", fail_execute)
    monkeypatch.setattr(OutcomeVerifier, "verify", fail_verify)

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.6",
        expense_reduction=0.6,
    )

    assert output["policy"]["status"] == "BLOCK"
    assert output["action"] is None
    assert output["execution"] is None
    assert output["verification"] is None


def test_step13_baseline_skips_executor_and_verifier(monkeypatch):
    def fail_execute(*args, **kwargs):
        raise AssertionError("executor must not run on baseline")

    def fail_verify(*args, **kwargs):
        raise AssertionError("verifier must not run on baseline")

    monkeypatch.setattr(ActionExecutor, "execute", fail_execute)
    monkeypatch.setattr(OutcomeVerifier, "verify", fail_verify)

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "baseline",
    )

    assert output["policy"]["status"] == "APPROVE"
    assert output["policy"]["approved_action"]["scenario_id"] == "baseline"
    assert output["action"] is None
    assert output["execution"] is None
    assert output["verification"] is None


def test_step13_executor_and_verifier_receive_same_action(monkeypatch):
    captured = {}

    def spy_execute(self, action):
        captured["executor_action"] = action
        return {
            "status": "SIMULATED",
            "mode": "DRY_RUN",
            "scenario_id": action.scenario_id,
            "policy_status": action.policy_status,
            "parameters": action.to_dict()["parameters"],
            "message": "test dry run",
        }

    def spy_verify(self, action, execution):
        captured["verifier_action"] = action
        captured["verifier_execution"] = execution
        return {
            "status": "EXECUTION_VERIFIED",
            "verified": True,
            "verification_type": "DRY_RUN_EXECUTION",
            "scenario_id": action.scenario_id,
            "reason": "No real-world financial outcome was evaluated.",
            "outcome_available": False,
        }

    monkeypatch.setattr(ActionExecutor, "execute", spy_execute)
    monkeypatch.setattr(OutcomeVerifier, "verify", spy_verify)

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert captured["executor_action"] is captured["verifier_action"]
    assert captured["verifier_execution"] == output["execution"]
    assert output["action"] == captured["executor_action"].to_dict()


def test_step13_public_action_is_serialized(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "revenue_growth_0.1",
    )
    assert isinstance(output["action"], dict)
    assert not isinstance(output["action"], Action)
    assert isinstance(json.dumps(output), str)


def test_step13_downstream_does_not_mutate_policy(monkeypatch):
    captured = {}
    original = DecisionPipeline._build_action_from_policy

    def build_spy(policy):
        captured["before"] = copy.deepcopy(policy)
        action = original(policy)
        captured["after"] = copy.deepcopy(policy)
        return action

    monkeypatch.setattr(
        DecisionPipeline,
        "_build_action_from_policy",
        staticmethod(build_spy),
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.4",
        expense_reduction=0.4,
    )

    assert captured["before"] == captured["after"]
    assert output["policy"] == captured["before"]


def test_step13_full_pipeline_is_deterministic(monkeypatch):
    first = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
        random_seed=91,
    )
    second = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
        random_seed=91,
    )
    assert first == second


def test_step13_action_construction_failure_is_wrapped(monkeypatch):
    class BrokenPolicy:
        def __init__(self, decision, data_confidence):
            self.decision = decision

        def evaluate(self):
            selected = self.decision["recommended_scenario"]
            return {
                "status": "APPROVE",
                "original_action": selected,
                "approved_action": {
                    "scenario_id": selected["scenario_id"],
                    "scenario_name": selected["scenario_name"],
                    "assumptions": {},
                },
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": [],
                "confidence": 1.0,
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        BrokenPolicy,
    )

    with pytest.raises(RuntimeError, match="action construction"):
        _run_pipeline_with_selected_scenario(
            monkeypatch,
            "expense_reduction_0.1",
        )


def test_step13_executor_failure_is_wrapped(monkeypatch):
    def fail_execute(self, action):
        raise ValueError("synthetic executor failure")

    monkeypatch.setattr(ActionExecutor, "execute", fail_execute)

    with pytest.raises(
        RuntimeError,
        match="action execution.*synthetic executor failure",
    ):
        _run_pipeline_with_selected_scenario(
            monkeypatch,
            "expense_reduction_0.1",
        )


def test_step13_verifier_failure_is_wrapped(monkeypatch):
    def fail_verify(self, action, execution):
        raise ValueError("synthetic verifier failure")

    monkeypatch.setattr(OutcomeVerifier, "verify", fail_verify)

    with pytest.raises(
        RuntimeError,
        match="outcome verification.*synthetic verifier failure",
    ):
        _run_pipeline_with_selected_scenario(
            monkeypatch,
            "expense_reduction_0.1",
        )


def test_step13_verification_failure_result_is_preserved(monkeypatch):
    def failed_verify(self, action, execution):
        return {
            "status": "VERIFICATION_FAILED",
            "verified": False,
            "verification_type": "DRY_RUN_EXECUTION",
            "scenario_id": action.scenario_id,
            "reason": (
                "synthetic mismatch; no real-world financial outcome "
                "was evaluated."
            ),
            "outcome_available": False,
        }

    monkeypatch.setattr(
        OutcomeVerifier,
        "verify",
        failed_verify,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["verification"]["status"] == "VERIFICATION_FAILED"
    assert output["verification"]["verified"] is False


def test_step13_no_external_network_call(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", fail_network)

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["execution"]["mode"] == "DRY_RUN"


def test_step13_scenario_engine_runs_only_for_generation(monkeypatch):
    calls = {"simulate": 0}
    original = ScenarioEngine.simulate

    def spy(self, *args, **kwargs):
        calls["simulate"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ScenarioEngine, "simulate", spy)

    _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert calls["simulate"] == 4


def test_step13_policy_engine_runs_exactly_once(monkeypatch):
    calls = {"policy": 0}
    original = PolicyEngine.evaluate

    def spy(self):
        calls["policy"] += 1
        return original(self)

    monkeypatch.setattr(PolicyEngine, "evaluate", spy)

    _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert calls["policy"] == 1


def test_step13_executor_result_is_in_public_output(monkeypatch):
    execution = {
        "status": "SIMULATED",
        "mode": "DRY_RUN",
        "scenario_id": "expense_reduction_0.1",
        "policy_status": "APPROVE",
        "parameters": {},
        "message": "test",
    }

    def spy_execute(self, action):
        return execution

    monkeypatch.setattr(ActionExecutor, "execute", spy_execute)

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["execution"] is execution


def test_step13_policy_object_is_not_reconstructed_from_decision(monkeypatch):
    captured = {}

    class SpyPolicy:
        def __init__(self, decision, data_confidence):
            captured["recommended"] = decision["recommended_scenario"]

        def evaluate(self):
            return {
                "status": "APPROVE",
                "original_action": captured["recommended"],
                "approved_action": captured["recommended"],
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": [],
                "confidence": 1.0,
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        SpyPolicy,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    selected = next(
        s for s in output["scenarios"]
        if s["scenario_id"] == "expense_reduction_0.1"
    )
    assert captured["recommended"] == selected


def test_step13_action_confidence_comes_from_policy(monkeypatch):
    captured = {}

    class SpyPolicy:
        def __init__(self, decision, data_confidence):
            self.decision = decision

        def evaluate(self):
            selected = self.decision["recommended_scenario"]
            captured["selected"] = selected
            return {
                "status": "APPROVE",
                "original_action": selected,
                "approved_action": selected,
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": ["policy reason"],
                "confidence": 0.87,
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        SpyPolicy,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["action"]["confidence"] == pytest.approx(0.87)
    assert output["action"]["reasoning"] == ["policy reason"]


def test_step13_policy_approved_scenario_name_is_used(monkeypatch):
    class SpyPolicy:
        def __init__(self, decision, data_confidence):
            self.decision = decision

        def evaluate(self):
            selected = dict(self.decision["recommended_scenario"])
            selected["scenario_name"] = "Authoritative Policy Name"
            return {
                "status": "APPROVE",
                "original_action": self.decision["recommended_scenario"],
                "approved_action": selected,
                "policy": {
                    "rules_evaluated": [],
                    "violations": [],
                    "warnings": [],
                },
                "reasoning": [],
                "confidence": 1.0,
            }

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        SpyPolicy,
    )

    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )

    assert output["action"]["scenario_name"] == "Authoritative Policy Name"


def test_step13_policy_result_must_be_dictionary(monkeypatch):
    class BadPolicy:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self):
            return []

    monkeypatch.setattr(
        "backend.app.services.decision_pipeline.PolicyEngine",
        BadPolicy,
    )

    with pytest.raises(
        RuntimeError,
        match="non-dictionary policy result",
    ):
        run_pipeline()


def test_step13_executor_result_must_be_dictionary(monkeypatch):
    def bad_execute(self, action):
        return []

    monkeypatch.setattr(ActionExecutor, "execute", bad_execute)

    with pytest.raises(
        RuntimeError,
        match="executor returned a non-dictionary result",
    ):
        _run_pipeline_with_selected_scenario(
            monkeypatch,
            "expense_reduction_0.1",
        )


def test_step13_verifier_result_must_be_dictionary(monkeypatch):
    def bad_verify(self, action, execution):
        return []

    monkeypatch.setattr(OutcomeVerifier, "verify", bad_verify)

    with pytest.raises(
        RuntimeError,
        match="verifier returned a non-dictionary result",
    ):
        _run_pipeline_with_selected_scenario(
            monkeypatch,
            "expense_reduction_0.1",
        )


def test_step13_final_result_is_json_serializable(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )
    assert isinstance(json.dumps(output), str)


def test_step13_final_result_has_no_nonfinite_numbers(monkeypatch):
    output = _run_pipeline_with_selected_scenario(
        monkeypatch,
        "expense_reduction_0.1",
    )
    assert finite_recursive(output)
