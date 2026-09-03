
# FinSight — Decision Logic

## 1. Purpose

FinSight follows a safety-first decision process:

```text
Financial History
      ↓
Financial State
      ↓
Risk Detection
      ↓
Root Causes
      ↓
Scenario Simulation
      ↓
Decision Optimization
      ↓
Policy / Safety Gate
      ↓
Action OR NO SAFE ACTION
      ↓
Execution
      ↓
Verification
````

The system deliberately separates **what is financially best** from **what is safe to execute**.

---

## 2. Step 1 — Financial State

The FinancialStateEngine derives the current operating position from historical financial data.

Important metrics include:

* Current cash
* Monthly revenue
* Monthly expenses
* Net burn
* Average net burn
* Runway
* Revenue growth
* Expense growth
* Revenue/expense ratio
* Burn multiple
* Data confidence

### Net Burn

```text
Net Burn = Expenses - Revenue
```

Positive net burn indicates that the business is consuming cash.

### Runway

Runway estimates how long current cash can support the observed burn rate.

The system also uses historical behavior rather than relying exclusively on the latest month.

---

## 3. Step 2 — Risk Detection

RiskDetector evaluates the financial state against operating thresholds.

Detected risks can include:

* Operating deficit
* Liquidity risk
* Expense acceleration
* Growth instability

Each risk receives a severity.

The highest-severity risks become the primary decision drivers.

The system does not generate a recommendation simply because a metric is weak. The risk layer establishes the financial problem that an intervention should address.

---

## 4. Step 3 — Root Causes

RootCauseEngine translates detected risks into measurable financial drivers.

For example:

```text
High expenses
      +
Weak revenue growth
      ↓
Persistent operating deficit
      ↓
Cash deterioration
```

The engine only claims drivers supported by the available financial history.

It does not invent detailed accounting categories that are not present in the input.

---

## 5. Step 4 — Scenario Generation

ScenarioEngine creates alternative forward-looking paths.

Current scenarios include:

### Baseline

No intervention.

This is the reference case.

### Revenue Growth

Applies a bounded revenue-growth adjustment.

### Expense Reduction

Applies a bounded expense-reduction adjustment.

### Combined

Applies both revenue growth and expense reduction.

---

## 6. Step 5 — Scenario Simulation

Each scenario is simulated over the configured forward horizon.

For each scenario, FinSight evaluates metrics including:

* Survival probability
* Survival month
* Ending cash
* Mean ending cash
* P10 ending cash
* Cash-shortfall probability

### Survival

A simulated path survives only if cash remains positive throughout the complete horizon.

### Survival Month

The first month where cash reaches zero or below is recorded as the failure point.

### Ending Cash

Ending cash always represents cash at the actual end of the simulation horizon.

If a path becomes insolvent earlier, the simulation does not freeze the cash value at the failure month.

This distinction prevents the downside statistics from being distorted by early termination.

---

## 7. Step 6 — Decision Optimization

DecisionOptimizer compares intervention scenarios against the baseline.

The current score combines four dimensions:

| Component               | Weight |
| ----------------------- | -----: |
| Survival improvement    |    40% |
| Downside improvement    |    25% |
| Ending cash improvement |    20% |
| Horizon improvement     |    15% |

The weighted result is converted into a bounded decision score from 0 to 100.

### Recommendation thresholds

```text
70–100  → RECOMMEND
50–69   → CONSIDER
0–49    → NO_ACTION
```

The optimizer also considers:

* Capital requirements
* Data confidence
* Material improvement
* Scenario feasibility

---

## 8. Financial Improvement

Scenario improvements are evaluated relative to the baseline.

For example:

```text
Ending Cash Improvement
=
Scenario Ending Cash - Baseline Ending Cash
```

Large improvements are normalized using the financial scale of both the baseline and resulting scenario.

This avoids treating every sufficiently large improvement as identical.

---

## 9. Important Separation: Optimization vs Safety

The optimizer answers:

> Which available scenario provides the strongest financial improvement?

The policy layer answers:

> Is that scenario safe and permitted to execute?

These questions must remain separate.

A scenario can therefore be:

```text
BEST AVAILABLE
```

while still being:

```text
NOT SAFE TO EXECUTE
```

---

## 10. Step 7 — Policy and Safety Gate

PolicyEngine evaluates the optimizer's selected scenario.

It checks:

* Scenario validity
* Required assumptions
* Capital limits
* Intervention limits
* Data confidence
* Financial safety

Only a policy-approved scenario can become an executable action.

---

## 11. Cash-Shortfall Safety Rule

The most important financial safety check compares the selected scenario with the baseline.

If baseline cash-shortfall probability is zero:

```text
No shortfall-risk reduction is required.
```

The intervention may proceed if other policy requirements are satisfied.

If baseline shortfall probability is greater than zero, the selected intervention must reduce that probability.

Formally:

```text
Baseline Shortfall > 0
AND
Selected Shortfall >= Baseline Shortfall
        ↓
BLOCK
```

The system returns:

```text
NO SAFE ACTION FOUND
```

rather than automatically executing the financially attractive scenario.

---

## 12. Why This Rule Matters

Consider:

```text
Baseline:
Shortfall probability = 100%

Combined intervention:
Shortfall probability = 100%
Mean ending cash improves significantly
Survival horizon improves
```

The combined intervention may be the **best available option**, but it has not actually reduced the probability of the critical failure event.

Therefore:

```text
Optimizer → selects Combined
PolicyEngine → blocks Combined
Final result → NO SAFE ACTION FOUND
```

The system preserves the useful evidence:

* Best available intervention
* Financial improvement
* Delay in failure
* Remaining shortfall risk

but refuses to represent the intervention as safe.

---

## 13. Action Creation

An Action is created only after policy approval.

```text
Policy = APPROVE
      ↓
Action created
```

For a blocked decision:

```text
Policy = BLOCK
      ↓
No Action
```

This prevents downstream execution from bypassing the safety layer.

---

## 14. Execution

Approved actions are passed to ActionExecutor.

The current implementation uses controlled simulated/dry-run execution.

This allows the entire decision workflow to be demonstrated without creating real financial side effects.

Execution success means:

> The execution layer successfully processed the requested action.

It does not mean:

> The business actually recovered money.

---

## 15. Outcome Verification

OutcomeVerifier validates the execution result.

FinSight distinguishes between:

### Execution Verification

Confirms that the requested action was successfully processed.

### Financial Outcome Verification

Confirms that a measurable real-world financial outcome occurred.

A dry-run can provide the first without providing the second.

Therefore FinSight does not claim recovered revenue or cash unless an actual outcome is available.

---

## 16. Confidence

Data confidence is propagated through the decision process.

Confidence reflects the quality and completeness of the financial evidence available to the system.

The system should communicate confidence explicitly rather than presenting uncertain analysis as fact.

---

## 17. Decision States

The final decision can be understood as:

```text
                    ┌───────────────┐
                    │   Scenarios   │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │   Optimizer   │
                    └───────┬───────┘
                            ↓
                    Best Available
                            ↓
                    ┌───────────────┐
                    │ Policy / Gate │
                    └───────┬───────┘
                       ┌────┴────┐
                       ↓         ↓
                    APPROVE     BLOCK
                       ↓         ↓
                    ACTION    NO SAFE
                       ↓        ACTION
                   EXECUTE
                       ↓
                  VERIFY
```

---

## 18. Example — Healthy Business

A healthy business may have:

```text
Baseline shortfall = 0%
```

Several interventions may improve projected ending cash.

Because there is no baseline cash-shortfall risk, the shortfall-reduction gate does not block the intervention.

The optimizer can therefore select the strongest scenario subject to the remaining policy limits.

---

## 19. Example — Distressed Business

A distressed business may have:

```text
Baseline shortfall = 100%
```

Suppose the combined intervention produces:

```text
Ending cash improvement → significant
Survival horizon → improved
Shortfall probability → still 100%
```

The optimizer can still identify Combined as the strongest available scenario.

However:

```text
Selected shortfall >= Baseline shortfall
```

therefore:

```text
Policy → BLOCK
Action → None
Execution → None
Verification → None
```

Final system state:

```text
NO SAFE ACTION FOUND
```

This is intentional behavior, not a failure of the optimizer.

---

## 20. Core Design Principle

FinSight follows:

```text
Analyze
  ↓
Simulate
  ↓
Optimize
  ↓
Constrain
  ↓
Act
  ↓
Verify
```

The system never treats optimization alone as authorization to act.

The central safety principle is:

> **The best financial scenario is not automatically a safe action.**

````
