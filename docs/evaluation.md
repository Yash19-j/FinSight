
# FinSight — Evaluation

## 1. Evaluation Goal

FinSight is evaluated as a financial decision system, not only as a prediction model.

The evaluation checks whether the system can:

1. Correctly derive financial state
2. Detect material financial risks
3. Generate forward-looking scenarios
4. Rank interventions consistently
5. Apply safety policies
6. Block unsafe actions
7. Execute approved actions in a controlled mode
8. Verify execution without fabricating financial outcomes

---

## 2. Evaluation Datasets

FinSight includes two deterministic demonstration datasets:

```text
sample_data/
├── demo_startup.csv
└── failing_startup.csv
````

### `demo_startup.csv`

Represents a comparatively healthy operating position.

It is used to verify that:

* Financial state can be derived correctly
* Risks remain proportionate to the financial condition
* Intervention scenarios can be evaluated
* A valid intervention can pass policy
* The approved action can proceed through execution and verification

### `failing_startup.csv`

Represents a financially distressed operating position.

It is used to verify that:

* Critical financial risk is detected
* Baseline cash-shortfall risk is identified
* Interventions can still be ranked by financial improvement
* The strongest available intervention is not automatically treated as safe
* The financial safety gate can block an intervention
* No unsafe action is executed

---

## 3. Evaluation Dimensions

### 3.1 Financial State

The evaluation checks derived metrics including:

* Cash
* Revenue
* Expenses
* Net burn
* Average net burn
* Runway
* Revenue growth
* Expense growth
* Revenue/expense ratio
* Burn multiple
* Data confidence

The calculations must remain deterministic for a fixed input dataset.

---

## 4. Risk Evaluation

Risk detection is evaluated against the expected financial condition.

For a healthy dataset, the system should avoid escalating ordinary operating variation into critical financial risk.

For a distressed dataset, the system should identify the material risks responsible for the deteriorating financial position.

The evaluation therefore checks both:

```text
Risk sensitivity
```

and:

```text
Risk proportionality
```

---

## 5. Scenario Evaluation

Each scenario is compared with the baseline.

The evaluation records:

* Mean ending cash
* P10 ending cash
* Survival probability
* Survival month
* Cash-shortfall probability

The important property is that scenario outputs are internally consistent.

For example:

```text
Scenario ending cash
=
cash at the end of the simulation horizon
```

rather than cash at the first point of insolvency.

---

## 6. Decision Evaluation

DecisionOptimizer evaluates intervention scenarios using:

| Component               | Weight |
| ----------------------- | -----: |
| Survival improvement    |    40% |
| Downside improvement    |    25% |
| Ending cash improvement |    20% |
| Horizon improvement     |    15% |

The final decision score is bounded between 0 and 100.

Recommendation thresholds are:

```text
Score >= 70  → RECOMMEND
Score >= 50  → CONSIDER
Score < 50   → NO_ACTION
```

The evaluation verifies that scenario ranking is consistent with these rules.

---

## 7. Safety Evaluation

Safety is evaluated independently from optimization.

This distinction is critical.

A scenario can have the highest financial score while still being blocked.

### Cash-shortfall gate

When the baseline has non-zero cash-shortfall probability:

```text
Selected shortfall >= Baseline shortfall
```

results in:

```text
POLICY = BLOCK
```

and:

```text
ACTION = NONE
EXECUTION = NONE
VERIFICATION = NONE
```

The final system state is:

```text
NO SAFE ACTION FOUND
```

---

## 8. Healthy Case Expected Behavior

For the healthy demonstration dataset:

```text
Baseline shortfall = 0%
```

The financial safety gate therefore does not require a reduction in shortfall probability.

If an intervention satisfies the remaining policy constraints:

```text
Optimizer
    ↓
Policy APPROVE
    ↓
Action created
    ↓
Dry-run execution
    ↓
Execution verification
```

The system must still distinguish simulated execution from real financial impact.

---

## 9. Distressed Case Expected Behavior

For the failing demonstration dataset, the baseline represents material cash-shortfall risk.

An intervention may improve:

* Ending cash
* Downside
* Survival horizon

while still leaving the shortfall probability unchanged.

In this situation:

```text
Optimizer
    ↓
Best available intervention
    ↓
Policy BLOCK
    ↓
NO SAFE ACTION FOUND
```

This is an intended safety outcome.

The system should not execute an intervention merely because it improves projected financial metrics.

---

## 10. Execution Evaluation

The current executor operates in controlled dry-run mode.

The evaluation therefore verifies:

* Action construction
* Valid action parameters
* Execution processing
* Execution status
* Verification status

It does **not** claim real-world revenue recovery.

---

## 11. Outcome Integrity

FinSight distinguishes three different states:

```text
Decision
   ↓
Execution
   ↓
Financial Outcome
```

A successful execution does not automatically imply a successful financial outcome.

For a dry-run:

```text
Execution verified = YES
Financial outcome available = NO
```

This prevents the evaluation from reporting simulated effects as measured real-world money recovered.

---

## 12. Automated Test Suite

The backend contains unit and integration tests covering:

* Action model
* Action executor
* API
* Financial state
* Risk detection
* Root causes
* Scenario engine
* Decision optimizer
* Policy engine
* Decision pipeline
* Outcome verification

Run the complete test suite with:

```bash
pytest -q
```

A successful evaluation requires all tests to pass.

---

## 13. Determinism

For a fixed dataset and fixed configuration, FinSight should produce reproducible decision behavior.

The evaluation should therefore record:

* Input dataset
* Simulation configuration
* Scenario parameters
* Decision score
* Selected scenario
* Policy result
* Action status

Randomized simulation should use controlled randomness where applicable so that evaluation results can be reproduced.

---

## 14. What FinSight Measures

FinSight currently measures:

### Financial state

```text
Cash
Burn
Runway
Growth
Expense acceleration
Financial ratios
```

### Scenario quality

```text
Survival
Ending cash
Downside
Shortfall probability
Failure horizon
```

### Decision quality

```text
Scenario ranking
Decision score
Recommendation
```

### Safety

```text
Policy approval/block
Unsafe-action prevention
```

### Execution integrity

```text
Action creation
Execution status
Verification status
```

---

## 15. What FinSight Does Not Claim

The current prototype does not claim:

* Real-world revenue recovery
* Real payment execution
* Guaranteed financial improvement
* Real customer behavior change
* Accounting-grade financial statements
* Actual money recovered from an external payment system

The current execution layer is intentionally simulated.

Therefore:

> Projected financial impact is simulation output, not measured real-world recovery.

---

## 16. Evaluation Philosophy

The system is evaluated on more than whether it produces a recommendation.

A strong result must demonstrate:

```text
Correct analysis
      +
Scenario comparison
      +
Decision quality
      +
Safety enforcement
      +
Controlled execution
      +
Honest verification
```

The most important failure mode FinSight is designed to prevent is:

```text
Financially attractive
        ≠
Safe to execute
```

The evaluation explicitly tests this boundary.

---

## 17. Reproducible Evaluation

The intended evaluation workflow is:

```text
1. Install dependencies
2. Run test suite
3. Run healthy dataset
4. Run distressed dataset
5. Inspect scenario ranking
6. Inspect policy decision
7. Inspect action/execution state
8. Verify that blocked unsafe actions are not executed
```

Commands:

```bash
pip install -r requirements.txt
pytest -q
```

The sample datasets provide deterministic demonstrations of both:

```text
APPROVE
```

and:

```text
NO SAFE ACTION FOUND
```

This allows reviewers to inspect both the system's ability to act and its ability to refuse unsafe action.

````

