
# FinSight — System Architecture

## 1. Overview

FinSight is a financial decision intelligence system that converts historical financial data into:

1. A current financial state
2. Detected financial risks
3. Root-cause drivers
4. Forward-looking intervention scenarios
5. A ranked decision
6. A policy/safety decision
7. A bounded action
8. Execution verification

The system separates **analysis**, **decision-making**, **policy enforcement**, **execution**, and **outcome verification**.

The canonical application flow is:

```text
Financial Data
      │
      ▼
┌──────────────────────┐
│ FinancialStateEngine  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    RiskDetector      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    RootCauseEngine   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   ScenarioEngine     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  DecisionOptimizer   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    PolicyEngine      │
└──────────┬───────────┘
           │
      ┌────┴────┐
      │         │
   BLOCK      APPROVE
      │         │
      │         ▼
      │   ┌──────────────┐
      │   │    Action    │
      │   └──────┬───────┘
      │          │
      │          ▼
      │   ┌──────────────┐
      │   │ActionExecutor│
      │   └──────┬───────┘
      │          │
      │          ▼
      │   ┌──────────────┐
      │   │OutcomeVerifier│
      │   └──────────────┘
      │
      ▼
  No Safe Action
````

The `DecisionPipeline` orchestrates this flow.

---

## 2. Repository Architecture

```text
FinSight/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── models/
│   │   │   ├── action.py
│   │   │   └── __init__.py
│   │   │
│   │   └── services/
│   │       ├── action_executor.py
│   │       ├── decision_optimizer.py
│   │       ├── decision_pipeline.py
│   │       ├── financial_state.py
│   │       ├── outcome_verifier.py
│   │       ├── policy_engine.py
│   │       ├── risk_detector.py
│   │       ├── root_cause.py
│   │       └── scenario_engine.py
│   │
│   └── tests/
│       ├── test_action.py
│       ├── test_action_executor.py
│       ├── test_api.py
│       ├── test_decision_optimizer.py
│       ├── test_decision_pipeline.py
│       ├── test_financial_state.py
│       ├── test_outcome_verifier.py
│       ├── test_policy_engine.py
│       ├── test_risk_detector.py
│       ├── test_root_cause.py
│       └── test_scenario_engine.py
│
├── frontend/
│   └── React + TypeScript application
│
├── docs/
│   ├── architecture.md
│   ├── decision_logic.md
│   └── evaluation.md
│
├── sample_data/
│   ├── demo_startup.csv
│   └── failing_startup.csv
│
├── scripts/
│   └── run_evaluation.py
│
├── requirements.txt
└── README.md
```

---

## 3. Backend Layers

### 3.1 API Layer

`backend/app/main.py`

The API is the entry point for the frontend.

Its responsibility is to:

* Receive financial data
* Validate request inputs
* Invoke the canonical decision pipeline
* Return structured decision output

The API does not contain the financial decision logic itself.

This keeps the business logic independently testable.

---

## 4. Decision Pipeline

### `decision_pipeline.py`

`DecisionPipeline` is the canonical orchestration layer.

It coordinates the complete decision lifecycle:

```text
Input
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
Policy Evaluation
  ↓
Action
  ↓
Execution
  ↓
Verification
```

The pipeline is intentionally sequential because later stages depend on authoritative outputs from earlier stages.

For example:

* ScenarioEngine produces the authoritative scenario results.
* DecisionOptimizer ranks those scenarios.
* PolicyEngine evaluates the selected scenario against safety constraints.
* Action is created only if policy permits execution.

---

## 5. Financial State Engine

### `financial_state.py`

The FinancialStateEngine converts raw financial history into an operating snapshot.

Core outputs include:

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

The engine establishes the baseline state used by downstream components.

### Important distinction

The financial state is an **observed/derived state**.

It is not itself a recommendation.

---

## 6. Risk Detection

### `risk_detector.py`

RiskDetector evaluates the financial state and identifies material operating risks.

Examples include:

* Critical operating deficit
* Liquidity risk
* Expense acceleration
* Growth instability

Each risk has a severity and supporting financial evidence.

The risk layer provides the decision system with a prioritized description of what is going wrong.

---

## 7. Root Cause Engine

### `root_cause.py`

RootCauseEngine converts detected financial risks into measurable drivers.

For example:

```text
Operating deficit
      ↓
Revenue growth insufficient
+
Expense growth elevated
      ↓
Persistent net burn
```

The engine does not claim access to detailed accounting categories unless those categories are present in the supplied data.

This distinction is important:

> FinSight identifies financial drivers supported by the available history rather than inventing unsupported accounting explanations.

---

## 8. Scenario Engine

### `scenario_engine.py`

ScenarioEngine evaluates the financial consequences of candidate interventions.

Current scenario types include:

* Baseline
* Revenue growth
* Expense reduction
* Combined intervention

Each scenario is evaluated over a forward simulation horizon.

Key outputs include:

* Survival probability
* Survival month
* Ending cash
* Mean ending cash
* P10 ending cash
* Cash-shortfall probability
* Simulation statistics

### Baseline

The baseline represents what happens if no intervention is applied.

It is the reference point against which interventions are evaluated.

### Intervention scenarios

Intervention scenarios modify specific financial assumptions and simulate the resulting trajectory.

The scenario engine continues the financial trajectory through the full simulation horizon even when a simulated path becomes insolvent.

This ensures:

* `ending_cash` means actual horizon-end cash
* `survival_month` records when failure first occurred
* `survival_probability` measures whether the path remained solvent throughout the horizon

This prevents insolvency paths from being artificially frozen at the failure point.

---

## 9. Decision Optimizer

### `decision_optimizer.py`

DecisionOptimizer ranks available scenarios.

The current decision score combines:

| Component               | Weight |
| ----------------------- | -----: |
| Survival improvement    |    40% |
| Downside improvement    |    25% |
| Ending cash improvement |    20% |
| Horizon improvement     |    15% |

The resulting score is converted to a bounded 0–100 decision score.

The optimizer also considers:

* Required capital
* Data confidence
* Material improvement
* Scenario feasibility

Recommendation levels are:

```text
Score >= 70  → RECOMMEND
Score >= 50  → CONSIDER
Score < 50   → NO_ACTION
```

### Important separation

DecisionOptimizer answers:

> "Which available scenario is financially best?"

It does **not** answer:

> "Is it safe to execute?"

That responsibility belongs to PolicyEngine.

This separation prevents optimization from overriding safety constraints.

---

## 10. Policy Engine

### `policy_engine.py`

PolicyEngine is the safety and governance layer.

It evaluates whether the optimizer's selected intervention is permitted.

Policy checks include:

* Scenario validity
* Capital limits
* Intervention limits
* Required assumptions
* Data confidence
* Financial safety

### Financial safety gate

A key safety rule compares the selected intervention against baseline cash-shortfall risk.

If:

```text
baseline shortfall probability > 0
```

and:

```text
selected scenario shortfall probability
    >=
baseline shortfall probability
```

the intervention is blocked.

The system therefore distinguishes between:

```text
Best available intervention
```

and:

```text
Safe intervention
```

These are not necessarily the same thing.

For example, an intervention may improve ending cash and delay insolvency while still leaving the probability of cash shortfall unchanged.

In that situation FinSight can identify it as the strongest available scenario while correctly returning:

```text
NO SAFE ACTION FOUND
```

rather than automatically executing it.

---

## 11. Action Layer

### `action.py`

An Action represents the bounded intervention approved by policy.

It contains the selected scenario and relevant execution parameters.

An action is created only when the policy layer permits execution.

Blocked decisions therefore do not produce executable actions.

---

## 12. Action Executor

### `action_executor.py`

ActionExecutor handles execution of approved actions.

The current implementation supports controlled simulation/dry-run execution.

This allows the complete decision loop to be demonstrated without causing real financial side effects.

Execution output records whether the requested action was successfully processed by the execution layer.

---

## 13. Outcome Verification

### `outcome_verifier.py`

OutcomeVerifier verifies the integrity of the execution step.

It distinguishes:

```text
Execution verification
```

from:

```text
Financial outcome verification
```

A successful dry-run means that the system successfully processed the requested action.

It does **not** mean that real-world revenue or cash was recovered.

This distinction prevents FinSight from making unsupported claims about financial impact.

---

## 14. Safety-First Execution Flow

The system follows:

```text
Optimize
   ↓
Policy Check
   ↓
 ┌───────────────┐
 │               │
BLOCK          APPROVE
 │               │
 ▼               ▼
No Action      Action
                 ↓
             Execution
                 ↓
             Verification
```

The optimizer cannot bypass the policy layer.

This is a deliberate architectural boundary.

---

## 15. Frontend Architecture

The frontend is a React + TypeScript dashboard.

Its primary responsibilities are:

* Present the financial state
* Explain detected risks
* Show scenario comparisons
* Display the selected decision
* Explain policy outcomes
* Show execution status
* Clearly distinguish simulated execution from real financial outcomes

The frontend consumes structured backend results rather than implementing financial decision logic independently.

### Main dashboard views

```text
Overview
Risks
Scenarios
Decision
Execution
```

The Decision view exposes:

* Recommendation
* Decision score
* Financial impact
* Safety comparison
* Policy result
* Action status

The Execution view exposes:

* Execution mode
* Execution status
* Verification status
* Whether an actual financial outcome is available

---

## 16. Data Flow

The complete data flow is:

```text
CSV / Uploaded Financial History
              │
              ▼
       FinancialState
              │
              ▼
          Risk List
              │
              ▼
        Root Causes
              │
              ▼
      Scenario Results
              │
              ▼
       Ranked Decisions
              │
              ▼
       Policy Evaluation
          │         │
       BLOCK      APPROVE
          │         │
          ▼         ▼
     No Action    Action
                       │
                       ▼
                   Execution
                       │
                       ▼
                  Verification
```

---

## 17. Testing Architecture

FinSight uses pytest-based unit and integration tests.

The test suite covers:

* Action creation
* Action execution
* API behavior
* Financial state calculation
* Risk detection
* Root-cause detection
* Scenario simulation
* Decision optimization
* Policy enforcement
* Decision pipeline orchestration
* Outcome verification

The canonical backend currently passes the complete test suite.

---

## 18. Design Principles

### 18.1 Separation of concerns

Each component has one primary responsibility.

### 18.2 Optimize before execute

The system first evaluates alternatives before selecting an intervention.

### 18.3 Policy is independent of optimization

A financially attractive scenario is not automatically safe to execute.

### 18.4 Evidence before explanation

Root causes and recommendations are derived from available financial evidence.

### 18.5 No fabricated outcomes

Simulation results are not presented as real-world financial outcomes.

### 18.6 Bounded execution

Actions are subject to explicit policy constraints before execution.

### 18.7 Auditability

The pipeline produces structured outputs describing:

* Financial state
* Risks
* Scenarios
* Decision
* Policy result
* Action
* Execution
* Verification

This makes the decision path inspectable end-to-end.

---

## 19. Architectural Boundary

The most important architectural boundary in FinSight is:

```text
Decision Quality
       ≠
Execution Permission
```

DecisionOptimizer determines the best available financial scenario.

PolicyEngine determines whether that scenario is safe and permitted.

Only after policy approval can execution occur.

This prevents the system from turning an optimization model into an unrestricted financial-action agent.

````
