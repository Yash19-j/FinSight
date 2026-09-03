from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.decision_pipeline import DecisionPipeline


DATA_DIR = ROOT / "sample_data"

DATASETS = {
    "HEALTHY": DATA_DIR / "demo_startup.csv",
    "DISTRESSED": DATA_DIR / "failing_startup.csv",
}


def run_case(name: str, path: Path) -> dict:
    print("\n" + "=" * 72)
    print(f"{name} CASE")
    print("=" * 72)
    print(f"Dataset: {path.name}")

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    df = pd.read_csv(path)

    result = DecisionPipeline(
        df,
        simulation_runs=5_000,
        horizon_months=12,
        random_seed=42,
    ).run()

    state = result["financial_state"]
    decision = result["decision"]
    policy = result["policy"]

    recommended = decision.get(
        "recommended_scenario",
        {},
    )

    if not isinstance(recommended, dict):
        recommended = {}

    scenario_id = recommended.get(
        "scenario_id",
        "none",
    )

    decision_summary = decision.get("decision", {})

    if not isinstance(decision_summary, dict):
        decision_summary = {}

    score = decision_summary.get(
        "score",
        0,
    )

    recommendation = decision_summary.get(
        "classification",
        "UNKNOWN",
    )

    policy_status = policy.get(
        "status",
        "UNKNOWN",
    )

    action = result.get("action")
    execution = result.get("execution")
    verification = result.get("verification")

    baseline = next(
        scenario
        for scenario in result["scenarios"]
        if scenario.get("baseline") is True
    )

    selected = next(
        (
            scenario
            for scenario in result["scenarios"]
            if scenario.get("scenario_id")
            == scenario_id
        ),
        None,
    )

    baseline_shortfall = baseline.get(
        "probability_of_cash_shortfall"
    )

    selected_shortfall = (
        None
        if selected is None
        else selected.get(
            "probability_of_cash_shortfall"
        )
    )

    print("\nFINANCIAL STATE")
    print(f"  Cash:             {state.get('cash')}")
    print(f"  Monthly revenue:  {state.get('monthly_revenue')}")
    print(f"  Monthly expenses: {state.get('monthly_expenses')}")
    print(f"  Net burn:         {state.get('net_burn')}")
    print(f"  Runway:           {state.get('runway_months')}")
    print(f"  Confidence:       {state.get('data_confidence')}")

    print("\nDECISION")
    print(f"  Scenario:         {scenario_id}")
    print(f"  Score:            {score}")
    print(f"  Recommendation:   {recommendation}")

    print("\nSAFETY")
    print(f"  Baseline shortfall:  {baseline_shortfall}")
    print(f"  Selected shortfall:  {selected_shortfall}")
    print(f"  Policy:              {policy_status}")

    print("\nEXECUTION")
    print(
        f"  Action created:     {'YES' if action else 'NO'}"
    )
    print(
        f"  Execution:          "
        f"{execution.get('status') if execution else 'NONE'}"
    )
    print(
        f"  Verification:       "
        f"{verification.get('status') if verification else 'NONE'}"
    )

    if policy_status == "BLOCK":
        expected = (
            action is None
            and execution is None
            and verification is None
        )

        print(
            f"\n  Safety invariant:   "
            f"{'PASS' if expected else 'FAIL'}"
        )

    result["_evaluation"] = {
        "dataset": name,
        "file": path.name,
        "scenario": scenario_id,
        "score": score,
        "recommendation": recommendation,
        "policy": policy_status,
        "baseline_shortfall_probability": (
            baseline_shortfall
        ),
        "selected_shortfall_probability": (
            selected_shortfall
        ),
        "action_created": action is not None,
        "execution_status": (
            execution.get("status")
            if execution
            else None
        ),
        "verification_status": (
            verification.get("status")
            if verification
            else None
        ),
    }

    return result


def main() -> None:
    print("\nFINSight deterministic evaluation")
    print("Simulation runs: 5000")
    print("Horizon: 12 months")
    print("Random seed: 42")

    results = {}

    for name, path in DATASETS.items():
        results[name] = run_case(
            name,
            path,
        )

    healthy = results["HEALTHY"]["_evaluation"]
    distressed = results["DISTRESSED"]["_evaluation"]

    print("\n" + "=" * 72)
    print("EVALUATION SUMMARY")
    print("=" * 72)

    print(
        f"\nHealthy case:"
        f"\n  Policy: {healthy['policy']}"
        f"\n  Action: "
        f"{'CREATED' if healthy['action_created'] else 'NONE'}"
    )

    print(
        f"\nDistressed case:"
        f"\n  Policy: {distressed['policy']}"
        f"\n  Action: "
        f"{'CREATED' if distressed['action_created'] else 'NONE'}"
    )

    safety_test = (
        distressed["policy"] == "BLOCK"
        and not distressed["action_created"]
        and distressed["execution_status"] is None
        and distressed["verification_status"] is None
    )

    print(
        "\nSafety blocking test: "
        f"{'PASS' if safety_test else 'FAIL'}"
    )

    output = {
        "configuration": {
            "simulation_runs": 5000,
            "horizon_months": 12,
            "random_seed": 42,
        },
        "healthy": healthy,
        "distressed": distressed,
        "safety_test_passed": safety_test,
    }

    output_path = ROOT / "evaluation_results.json"

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            default=str,
        )

    print(
        f"\nResults written to: "
        f"{output_path.relative_to(ROOT)}"
    )

    if not safety_test:
        raise SystemExit(
            "Evaluation failed: distressed case "
            "did not satisfy the safety invariant."
        )

    print("\nEVALUATION PASSED")


if __name__ == "__main__":
    main()