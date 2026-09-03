# FinSight

### Financial Decision Intelligence with a Safety-Gated Action Layer

## 🚀 Live Demo

**[Open the Live FinSight Prototype](https://fin-sight-nu-weld.vercel.app)**

> Upload financial data → simulate interventions → rank decisions → apply safety policy → execute or block.






> **FinSight doesn't just tell you what looks best. It decides whether that action is safe enough to take.**

FinSight is a financial decision-intelligence prototype that transforms financial data into **ranked, simulated, policy-constrained actions**.

The core idea is simple:

> **The best financial action is not always a safe action.**

Instead of stopping at dashboards, risk alerts, or unrestricted AI recommendations, FinSight creates a controlled decision pipeline:

**Observe → Detect → Simulate → Rank → Safety Gate → Act → Verify**

---

## 1. Why FinSight?

Financial automation has an important asymmetry:

> **A bad automated financial decision can make an already fragile situation worse.**

Imagine a company with rapidly increasing expenses and limited liquidity.

An optimizer might discover an intervention that:

- improves projected ending cash by approximately **₹11.57 lakh**
- improves projected downside by approximately **₹11.6 lakh**
- delays projected failure by approximately **0.97 months**

It may therefore look like the "best" option.

But if the probability of cash shortfall remains **100%**, should an autonomous system execute it?

**FinSight says no.**

It deliberately separates two questions:

| Question | Component |
|---|---|
| **What performs best in simulation?** | Decision Optimizer |
| **Is it safe enough to execute?** | Safety + Policy Gate |

This creates a deliberate **decision boundary between financial intelligence and financial action**.

---

# 2. What FinSight Does

FinSight takes financial history and builds an operating picture of the business.

It then:

1. **Builds financial state**
2. **Detects financial risks**
3. **Surfaces detected drivers**
4. **Generates intervention scenarios**
5. **Simulates financial trajectories**
6. **Ranks interventions**
7. **Applies policy and safety constraints**
8. **Creates only bounded actions that pass**
9. **Verifies execution integrity**
10. **Maintains an auditable decision trail**

### The core flow

```text
                 FINANCIAL DATA
                       │
                       ▼
              ┌─────────────────┐
              │ Financial State  │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Risk Detector  │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ Detected Drivers│
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ Scenario Engine │
              └────────┬────────┘
                       ▼
              ┌──────────────────┐
              │ Decision Optimizer│
              └────────┬─────────┘
                       ▼
              ┌─────────────────┐
              │ SAFETY + POLICY │
              │      GATE       │
              └───────┬─────────┘
                      / \
                     /   \
                  SAFE   UNSAFE
                   │       │
                   ▼       ▼
                 ACTION   BLOCK
                   │
                   ▼
                VERIFY
                   │
                   ▼
               AUDIT TRAIL
```

---

# 3. System Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                    FINANCIAL INPUTS                      │
│                                                          │
│  Cash • Revenue • Expenses • Historical Financial Data  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                 FINANCIAL STATE ENGINE                   │
│                                                          │
│ Burn Rate • Runway • Growth • Expense Trends • Ratios   │
│                     Data Confidence                      │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                     RISK DETECTOR                         │
│                                                          │
│ Liquidity Risk • Operating Deficit                       │
│ Expense Acceleration • Growth Instability                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                  DETECTED DRIVER ENGINE                   │
│                                                          │
│ Surfaces financial signals associated with detected risk │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                     SCENARIO ENGINE                      │
│                                                          │
│ Baseline • Revenue Growth • Expense Reduction • Combined │
│                 Monte Carlo Simulation                   │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                  DECISION OPTIMIZER                      │
│                                                          │
│ Survival • Downside • Ending Cash • Survival Horizon     │
│                    → Rank Actions                        │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                 POLICY + SAFETY GATE                     │
│                                                          │
│ Policy Limits • Confidence • Capital Constraints          │
│              Cash-Shortfall Safety Check                 │
└──────────────────────────┬───────────────────────────────┘
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
              ┌──────┐           ┌───────┐
              │ SAFE │           │UNSAFE │
              └───┬──┘           └───┬───┘
                  ▼                  ▼
           ACTION EXECUTOR        BLOCK
                  │                  │
                  ▼                  ▼
              DRY_RUN          NO ACTION
                  │
                  ▼
           OUTCOME VERIFIER
                  │
                  ▼
             AUDIT TRAIL
```

---

# 4. The Decision Boundary

This is the central architectural idea behind FinSight.

```text
              BEST AVAILABLE ACTION
                       │
                       ▼
             ┌────────────────────┐
             │ FINANCIAL SAFETY   │
             │       GATE         │
             └─────────┬──────────┘
                       │
                 ┌─────┴─────┐
                 ▼           ▼
               SAFE        UNSAFE
                 │           │
                 ▼           ▼
              EXECUTE       BLOCK
                 │           │
                 ▼           ▼
              VERIFY      NO ACTION
```

The optimizer and safety gate have **different responsibilities**.

### Decision Optimizer

> **"What looks best?"**

Ranks interventions using multiple financial dimensions.

### Safety Gate

> **"What is safe enough to do?"**

Determines whether the selected intervention satisfies explicit financial and policy constraints.

This prevents the system from turning:

**"better than baseline"**

into:

**"safe to automate."**

---

# 5. Core Pipeline

## 1. Financial State

Raw financial inputs are converted into an operating state containing:

- Current cash
- Monthly revenue
- Monthly expenses
- Net burn
- Average net burn
- Runway
- Revenue growth
- Expense growth
- Revenue-to-expense ratio
- Burn multiple
- Data confidence

---

## 2. Risk Detection

FinSight evaluates the financial state for conditions including:

- Operating deficit
- Liquidity pressure
- Expense acceleration
- Growth instability

Risks are surfaced with severity so that downstream decisions can prioritize them.

---

## 3. Detected Drivers

The system surfaces the financial signals associated with detected risks.

FinSight deliberately avoids pretending to know granular causal explanations when the input data does not contain granular operational categories.

> **No invented causality.**

---

## 4. Scenario Simulation

Candidate interventions are evaluated against a baseline.

Current intervention classes:

| Scenario | Purpose |
|---|---|
| **Baseline** | No intervention |
| **Revenue Growth** | Improve revenue trajectory |
| **Expense Reduction** | Reduce expense trajectory |
| **Combined** | Apply both interventions |

The scenario engine simulates financial trajectories across the planning horizon.

Key outputs include:

- Ending cash
- P10 downside
- Survival probability
- Survival horizon
- Cash-shortfall probability

---

## 5. Decision Optimization

FinSight does not optimize against a single metric.

The current optimizer considers:

```text
Survival
   +
Downside
   +
Ending Cash
   +
Survival Horizon
   ↓
Decision Score
```

This produces a ranked set of available interventions.

---

# 6. Policy + Financial Safety Gate

After optimization, the selected intervention is evaluated against explicit constraints.

The safety layer considers:

- Policy limits
- Data confidence
- Capital requirements
- Financial safety conditions
- Cash-shortfall risk

### Critical safety rule

When the baseline has material cash-shortfall risk:

> **If the selected intervention does not reduce the probability of cash shortfall, the action can be blocked.**

This is the control boundary between:

**financial intelligence**

and

**financial automation.**

---

# 7. Action Execution

Only an approved decision can produce an executable action.

The current prototype uses:

```text
DRY_RUN
```

Actions are bounded by the policy layer rather than being unrestricted autonomous operations.

---

# 8. Outcome Verification

FinSight verifies **execution integrity**, not imaginary business outcomes.

This distinction is important:

```text
SIMULATED OUTCOME
       ≠
OBSERVED BUSINESS OUTCOME
```

A successful dry-run does **not** mean money was actually recovered or that the business actually improved.

FinSight intentionally refuses to fabricate that claim.

---

# 9. Safety Demonstration

The stressed-case prototype demonstrates why the safety gate exists.

### Optimizer result

The optimizer identifies **Combined** as the best available intervention:

| Metric | Improvement |
|---|---:|
| Decision score | **53.7** |
| Mean ending cash | **+₹11.57 lakh** |
| P10 downside | **~+₹11.6 lakh** |
| Survival horizon | **+0.97 months** |

At first glance, this looks like the obvious action.

But:

```text
Baseline shortfall probability
              ↓
             100%

Selected intervention shortfall probability
              ↓
             100%
```

Therefore:

```text
        OPTIMIZER
            │
            ▼
 Combined is best available
            │
            ▼
       SAFETY GATE
            │
            ▼
 Shortfall risk remains 100%
            │
            ▼
          BLOCK
            │
            ▼
   NO EXECUTABLE ACTION
```

### This is intentional.

FinSight prefers:

> **No action**

over:

> **an action that looks better but remains financially unsafe.**

---

# 10. Prototype Validation

The backend currently has an automated test suite covering:

- Financial state calculations
- Risk detection
- Scenario simulation
- Decision optimization
- Policy evaluation
- Safety gating
- Action creation
- Action execution
- Outcome verification
- End-to-end decision pipeline

### Current validation baseline

# **355 tests passing**

The prototype has also been validated across both healthy and stressed financial states.

###  Healthy financial state

```text
Risk assessment
      ↓
Scenario evaluation
      ↓
Policy PASS
      ↓
Action created
      ↓
DRY_RUN execution
      ↓
Execution verified
```

###  Stressed financial state

```text
Risk assessment
      ↓
Scenario evaluation
      ↓
Best available intervention
      ↓
Safety gate FAIL
      ↓
ACTION BLOCKED
      ↓
NO EXECUTABLE ACTION
```

---

# 11. Where This Architecture Can Be Useful

##  Payment & Transaction Businesses

High transaction volumes create a need to continuously identify financial pressure and prioritize interventions without allowing risky decisions to propagate automatically.

---

##  SMBs & Merchants

Smaller businesses often operate with tighter liquidity buffers.

An intervention that looks positive under average-case projections may still be dangerous if downside cash risk remains high.

---

##  Finance Operations

Move from:

> **"Here is the problem."**

to:

> **"Here are the available interventions, their simulated consequences, and the safest action we can authorize."**

---

##  Agentic Finance

As financial workflows become increasingly autonomous, FinSight provides a control layer between:

```text
AI / Optimization
        ↓
Decision
        ↓
Safety + Policy
        ↓
Authorized Action
```

This allows autonomy without making the system blindly autonomous.

---

# 12. Relevance to Payment-Finance Platforms

FinSight is designed around a problem naturally present in payment and financial infrastructure:

> **Turning financial signals into bounded actions while preserving control over financial risk.**

A payment-finance platform can potentially observe high-frequency operational and financial signals across merchants and businesses.

That creates an opportunity to move beyond:

```text
DATA
 ↓
DASHBOARD
 ↓
ALERT
```

toward:

```text
DATA
 ↓
DETECT
 ↓
SIMULATE
 ↓
QUANTIFY DOWNSIDE
 ↓
APPLY POLICY
 ↓
AUTHORIZE
 ↓
ACT
 ↓
VERIFY
```

Potential application areas include:

- Merchant financial health
- Cash-flow decisioning
- Payment operations
- Finance automation
- Business controls
- Treasury decision support

The architecture does **not** depend on one narrow workflow.

The central principle remains:

> **Financial intelligence can recommend. Policy decides whether automation is allowed.**

---

# 13. Why This Is Different

Traditional financial analytics often stop at:

```text
Data → Dashboard → Insight
```

Recommendation systems may go one step further:

```text
Data → Insight → Recommendation
```

FinSight introduces another layer:

```text
Data
 ↓
Insight
 ↓
Simulation
 ↓
Optimization
 ↓
Safety
 ↓
Action
 ↓
Verification
```

The difference is not simply adding another model.

It is establishing a **control boundary around automation**.

The system can identify a potentially attractive action while simultaneously deciding:

> **"This is the best option we found, but we are not allowed to execute it."**

That is a first-class system outcome, not an error state.

---

# 14. Repository Structure

```text
FinSight/
│
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   ├── action.py
│   │   │   ├── decision.py
│   │   │   ├── financial_state.py
│   │   │   └── intervention.py
│   │   │
│   │   ├── services/
│   │   │   ├── action_executor.py
│   │   │   ├── audit_logger.py
│   │   │   ├── decision_optimizer.py
│   │   │   ├── decision_pipeline.py
│   │   │   ├── financial_state.py
│   │   │   ├── intervention_engine.py
│   │   │   ├── outcome_verifier.py
│   │   │   ├── policy_engine.py
│   │   │   ├── risk_detector.py
│   │   │   ├── root_cause.py
│   │   │   └── scenario_engine.py
│   │   │
│   │   └── utils/
│   │
│   └── tests/
│
├── frontend/
│   └── React + TypeScript dashboard
│
├── sample_data/
│   ├── demo_startup.csv
│   └── failing_startup.csv
│
└── README.md
```

---

# 15. Testing

Run the complete backend test suite:

```bash
pytest -q
```

Expected validation baseline:

```text
355 passed
```

The suite covers the major decision layers:

```text
Financial State
      ↓
Risk Detection
      ↓
Scenario Simulation
      ↓
Decision Optimization
      ↓
Policy Evaluation
      ↓
Safety Gate
      ↓
Action
      ↓
Execution
      ↓
Verification
```

---

# 16. Getting Started

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm

---

## Backend

From the project root:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn backend.app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

### Health check

```text
GET /health
```

### Demo

```text
GET /demo
```

### Analysis

```text
POST /analyze
```

---

## Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at:

```text
http://localhost:5173
```

The Vite development server proxies `/api` requests to the FastAPI backend.

---

# 17. Future Direction

The current prototype establishes the decision-control architecture.

Future iterations can extend it with:

- More intervention types
- Richer financial datasets
- Merchant-level financial signals
- Real observed outcome feedback
- Human approval workflows
- More granular policy controls
- Continuous decision monitoring
- Learning from verified outcomes
- Integration with payment and finance infrastructure

The important constraint remains:

> **Additional automation should extend the system without removing the safety boundary.**

---

# 18. Design Philosophy

FinSight is built around five principles.

### 01 , Quantify before acting

Don't execute because an intervention sounds reasonable.

**Simulate its financial consequences first.**

### 02 , Optimize separately from authorization

The mathematically best option is not automatically an authorized action.

### 03 , Make safety measurable

Safety decisions should be based on explicit financial conditions and constraints.

### 04 , Fail closed

If an intervention cannot satisfy the safety requirements:

**create no executable action.**

### 05 , Never confuse simulation with reality

A simulated improvement is evidence for a decision.

It is **not proof of an actual financial outcome.**

---

# 19. What FinSight Does NOT Claim

FinSight is a prototype decision-intelligence system.

It does **not** claim:

- Real-world financial recovery from simulation alone
- Guaranteed financial outcomes
- Granular causal attribution when the input data cannot support it
- Unrestricted autonomous financial actions
- That the highest-scoring scenario is automatically safe
- That dry-run execution represents an actual external transaction

These limitations are intentional.

They make the system easier to:

**evaluate → audit → trust**

---

# 20. Final Takeaway

Financial automation should not be designed around:

> **"Can the system make a decision?"**

It should also answer:

> **"Should the system be allowed to act on that decision?"**

FinSight is built around that second question.

```text
                    FINANCIAL INTELLIGENCE
                             │
                             ▼
                        RECOMMEND
                             │
                             ▼
                    ┌─────────────────┐
                    │  SAFETY GATE    │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                  SAFE             UNSAFE
                    │                 │
                    ▼                 ▼
                 ACTION              BLOCK
                    │
                    ▼
                 VERIFY
```

> **FinSight is a safety-gated financial decision engine that turns financial signals into simulated, policy-constrained actions , and knows when not to act.**

---

      ## License

      Copyright (c) 2026 Yash Jindal

      All rights reserved.

      This project, including its source code, documentation, design, and associated materials, is the original work of Yash Jindal unless otherwise stated.

      No permission is granted to copy, modify, distribute, sublicense, or use this project or substantial portions of its source code for commercial or derivative purposes without prior written permission from the copyright holder.

      Third-party libraries, frameworks, datasets, and external components remain subject to their respective licenses.

      For permission requests, please contact the repository owner.
