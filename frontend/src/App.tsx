import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  FileSpreadsheet,
  Gauge,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  Wallet,
  X,
  Zap,
} from "lucide-react";

type AnyObject = Record<string, any>;

type View =
  | "overview"
  | "risks"
  | "scenarios"
  | "decision"
  | "execution";

const NAV_ITEMS: { id: View; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "risks", label: "Risks & Causes", icon: AlertTriangle },
  { id: "scenarios", label: "Scenarios", icon: BarChart3 },
  { id: "decision", label: "Decision", icon: Target },
  { id: "execution", label: "Execution", icon: Zap },
];

function number(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function money(value: unknown): string {
  const n = number(value);

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}

function compactMoney(value: unknown): string {
  const n = number(value);

  if (Math.abs(n) >= 10_000_000) {
    return `₹${(n / 10_000_000).toFixed(1)}Cr`;
  }

  if (Math.abs(n) >= 100_000) {
    return `₹${(n / 100_000).toFixed(1)}L`;
  }

  if (Math.abs(n) >= 1_000) {
    return `₹${(n / 1_000).toFixed(1)}K`;
  }

  return money(n);
}

function percent(value: unknown): string {
  return `${(number(value) * 100).toFixed(1)}%`;
}

function months(value: unknown): string {
  const n = number(value);

  if (n === 0) return "0";

  return `${n.toFixed(1)} mo`;
}

function titleCase(value: unknown): string {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function severityClass(severity: string): string {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
      return "severity critical";
    case "HIGH":
      return "severity high";
    case "MEDIUM":
      return "severity medium";
    default:
      return "severity low";
  }
}

function scenarioMetric(
  scenario: AnyObject,
  keys: string[],
  fallback = 0,
): number {
  for (const key of keys) {
    if (scenario[key] !== undefined && scenario[key] !== null) {
      return number(scenario[key], fallback);
    }
  }

  return fallback;
}

function App() {
  const [activeView, setActiveView] = useState<View>("overview");
  const [data, setData] = useState<AnyObject | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDemo = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/demo");

      if (!response.ok) {
        throw new Error("Unable to load the FinSight demo.");
      }

      const payload = await response.json();
      setData(payload);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the FinSight API.",
      );
    } finally {
      setLoading(false);
    }
  };

  const uploadCsv = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a CSV file.");
      return;
    }

    setUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "FinSight could not analyze this file.",
        );
      }

      setData(payload);
      setActiveView("overview");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze the uploaded file.",
      );
    } finally {
      setUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  useEffect(() => {
    loadDemo();
  }, []);

  const financialState = data?.financial_state ?? {};
  const risks: AnyObject[] = data?.risks ?? [];
  const rootCauses: AnyObject[] = data?.root_causes ?? [];
  const scenarios: AnyObject[] = data?.scenarios ?? [];
  const decision: AnyObject = data?.decision ?? {};
  const policy: AnyObject = data?.policy ?? {};
  const action: AnyObject | null = data?.action ?? null;
  const execution: AnyObject | null = data?.execution ?? null;
  const verification: AnyObject | null = data?.verification ?? null;

  const recommendedScenario =
    decision?.recommended_scenario ?? policy?.approved_action ?? {};

  const highestRisk = risks[0];

  const scenarioRows: AnyObject[] = useMemo(() => {
    return scenarios.map((scenario: AnyObject) => ({
      ...scenario,
      displayName:
        scenario.name ??
        scenario.scenario_name ??
        titleCase(scenario.scenario_id),
      survival: scenarioMetric(
        scenario,
        [
          "survival_probability",
          "probability_of_survival",
          "survival_rate",
        ],
        0,
      ),
      endingCash: scenarioMetric(
        scenario,
        [
          "median_ending_cash",
          "ending_cash_median",
          "ending_cash",
          "p50_ending_cash",
          "median_cash",
        ],
        0,
      ),
      p10: scenarioMetric(
        scenario,
        ["ending_cash_p10", "p10_ending_cash", "p10_cash"],
        0,
      ),
      p90: scenarioMetric(
        scenario,
        ["ending_cash_p90", "p90_ending_cash", "p90_cash"],
        0,
      ),
    }));
  }, [scenarios]);

  const baselineCash =
    scenarioRows.find((scenario: AnyObject) => scenario.baseline)?.endingCash ?? 0;

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-mark">
          <Sparkles size={25} />
        </div>
        <h1>FinSight</h1>
        <p>Building your financial decision brief...</p>
        <Loader2 className="spin" size={22} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={19} />
          </div>

          <div>
            <div className="brand-name">FinSight</div>
            <div className="brand-subtitle">Decision Intelligence</div>
          </div>
        </div>

        <div className="workspace">
          <span className="workspace-dot" />
          Demo workspace
        </div>

        <nav className="navigation">
          <div className="nav-label">COMMAND CENTER</div>

          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeView === item.id;

            return (
              <button
                key={item.id}
                className={`nav-item ${active ? "active" : ""}`}
                onClick={() => setActiveView(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>

                {item.id === "risks" && risks.length > 0 && (
                  <span className="nav-count">{risks.length}</span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <button
            className="upload-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 size={18} className="spin" />
            ) : (
              <Upload size={18} />
            )}
            {uploading ? "Analyzing..." : "Analyze CSV"}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) uploadCsv(file);
            }}
          />

          <div className="system-status">
            <span className="status-dot" />
            Pipeline operational
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">FINANCIAL CONTROL CENTER</div>
            <h1>{pageTitle(activeView)}</h1>
          </div>

          <div className="topbar-actions">
            <div className="data-confidence">
              <span>Data confidence</span>
              <strong>{financialState.data_confidence ?? "—"}</strong>
            </div>

            <button
              className="icon-button"
              onClick={loadDemo}
              title="Reset to demo"
            >
              <Activity size={18} />
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {!data ? (
          <EmptyState onRetry={loadDemo} />
        ) : (
          <>
            {activeView === "overview" && (
              <Overview
                state={financialState}
                risks={risks}
                decision={decision}
                policy={policy}
                recommendedScenario={recommendedScenario}
                highestRisk={highestRisk}
                onNavigate={setActiveView}
              />
            )}

            {activeView === "risks" && (
              <RisksView risks={risks} rootCauses={rootCauses} />
            )}

            {activeView === "scenarios" && (
              <ScenariosView
                scenarios={scenarioRows}
                baselineCash={baselineCash}
                recommendedScenario={recommendedScenario}
              />
            )}

            {activeView === "decision" && (
              <DecisionView
                decision={decision}
                policy={policy}
                action={action}
                recommendedScenario={recommendedScenario}
              />
            )}

            {activeView === "execution" && (
              <ExecutionView
                action={action}
                execution={execution}
                verification={verification}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function pageTitle(view: View): string {
  switch (view) {
    case "overview":
      return "Financial Overview";
    case "risks":
      return "Risks & Root Causes";
    case "scenarios":
      return "Scenario Engine";
    case "decision":
      return "Decision Center";
    case "execution":
      return "Execution & Verification";
  }
}

function Overview({
  state,
  risks,
  decision,
  policy,
  recommendedScenario,
  highestRisk,
  onNavigate,
}: {
  state: AnyObject;
  risks: AnyObject[];
  decision: AnyObject;
  policy: AnyObject;
  recommendedScenario: AnyObject;
  highestRisk?: AnyObject;
  onNavigate: (view: View) => void;
}) {
  const runway = state.runway_months;
  const netBurn = state.net_burn;
  const revenue = state.monthly_revenue;
  const expenses = state.monthly_expenses;
  const revenueGrowth = state.revenue_growth;
  const expenseGrowth = state.expense_growth;

  return (
    <div className="page">
      <section className="hero">
        <div>
          <div className="hero-kicker">
            <span className="live-dot" />
            AI FINANCIAL BRIEF
          </div>

          <h2>
            Your next financial move,
            <br />
            <span>already evaluated.</span>
          </h2>

          <p>
            FinSight converts raw financial history into a risk-aware,
            policy-gated action.
          </p>
        </div>

        <div className="hero-decision">
          <div className="mini-label">CURRENT DECISION</div>
          <div className="decision-status">
            <span className="status-pulse" />
            {policy.status ?? decision.status ?? "ANALYZED"}
          </div>

          <button onClick={() => onNavigate("decision")}>
            View decision
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Cash on hand"
          value={compactMoney(state.cash)}
          icon={<Wallet size={18} />}
        />

        <MetricCard
          label="Monthly net burn"
          value={compactMoney(netBurn)}
          icon={<CircleDollarSign size={18} />}
          negative={number(netBurn) > 0}
        />

        <MetricCard
          label="Runway"
          value={months(runway)}
          icon={<Clock3 size={18} />}
          warning={number(runway) <= 6}
        />

        <MetricCard
          label="Revenue / expense"
          value={number(state.revenue_expense_ratio).toFixed(2)}
          icon={<Activity size={18} />}
          warning={number(state.revenue_expense_ratio) < 1}
        />
      </section>

      <section className="grid-two">
        <div className="panel">
          <PanelHeader
            title="Operating position"
            subtitle="Latest financial state"
          />

          <div className="position-list">
            <PositionRow
              label="Monthly revenue"
              value={money(revenue)}
              trend={number(revenueGrowth)}
              trendLabel="MoM"
            />

            <PositionRow
              label="Monthly expenses"
              value={money(expenses)}
              trend={number(expenseGrowth)}
              trendLabel="MoM"
              inverse
            />

            <PositionRow
              label="Average net burn"
              value={money(state.average_net_burn)}
            />

            <PositionRow
              label="Burn multiple"
              value={
                state.burn_multiple === null
                  ? "N/A"
                  : number(state.burn_multiple).toFixed(2)
              }
            />
          </div>
        </div>

        <div className="panel risk-panel">
          <PanelHeader
            title="Priority risk"
            subtitle={`${risks.length} detected risk${risks.length === 1 ? "" : "s"}`}
            action={
              <button
                className="text-button"
                onClick={() => onNavigate("risks")}
              >
                View all
              </button>
            }
          />

          {highestRisk ? (
            <div className="priority-risk">
              <div className="risk-heading">
                <span className={severityClass(highestRisk.severity)}>
                  {highestRisk.severity}
                </span>
                <span className="risk-category">
                  {titleCase(highestRisk.category)}
                </span>
              </div>

              <h3>{highestRisk.title}</h3>
              <p>{highestRisk.evidence}</p>

              <div className="risk-footer">
                <span>
                  Confidence{" "}
                  <strong>{percent(highestRisk.confidence)}</strong>
                </span>

                {highestRisk.financial_impact != null && (
                  <span>
                    Impact{" "}
                    <strong>
                      {compactMoney(highestRisk.financial_impact)}
                    </strong>
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="no-risk">
              <ShieldCheck size={30} />
              <strong>No material risks detected</strong>
              <span>The current financial state is within thresholds.</span>
            </div>
          )}
        </div>
      </section>

      <section className="decision-strip">
        <div className="decision-strip-icon">
          <Target size={22} />
        </div>

        <div className="decision-strip-content">
          <div className="mini-label">RECOMMENDED PATH</div>
          <h3>
            {recommendedScenario.name ??
              recommendedScenario.scenario_name ??
              titleCase(recommendedScenario.scenario_id) ??
              "No intervention"}
          </h3>
          <p>
            {recommendedScenario.description ??
              "FinSight evaluated the available intervention scenarios."}
          </p>
        </div>

        <div className="decision-strip-meta">
          <div>
            <span>Policy</span>
            <strong>{policy.status ?? "—"}</strong>
          </div>

          <div>
            <span>Confidence</span>
            <strong>
              {decision.confidence != null
                ? percent(decision.confidence)
                : "—"}
            </strong>
          </div>

          <button onClick={() => onNavigate("decision")}>
            Inspect
            <ChevronRight size={17} />
          </button>
        </div>
      </section>
    </div>
  );
}

function RisksView({
  risks,
  rootCauses,
}: {
  risks: AnyObject[];
  rootCauses: AnyObject[];
}) {
  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">DETECTION LAYER</div>
          <h2>What could hurt the business?</h2>
          <p>
            Deterministic risk signals are ranked by severity, financial
            impact and confidence.
          </p>
        </div>

        <div className="big-count">
          <strong>{risks.length}</strong>
          <span>signals</span>
        </div>
      </div>

      <div className="risk-list">
        {risks.length === 0 ? (
          <div className="empty-panel">
            <ShieldCheck size={28} />
            <h3>No material risks detected</h3>
          </div>
        ) : (
          risks.map((risk, index) => (
            <div className="risk-card" key={risk.risk_id ?? index}>
              <div className="risk-card-index">
                {(index + 1).toString().padStart(2, "0")}
              </div>

              <div className="risk-card-main">
                <div className="risk-heading">
                  <span className={severityClass(risk.severity)}>
                    {risk.severity}
                  </span>
                  <span className="risk-category">
                    {titleCase(risk.category)}
                  </span>
                </div>

                <h3>{risk.title}</h3>
                <p>{risk.evidence}</p>

                <div className="risk-details">
                  <span>
                    Metric <strong>{titleCase(risk.metric)}</strong>
                  </span>

                  {risk.current_value != null && (
                    <span>
                      Current{" "}
                      <strong>
                        {risk.metric?.includes("growth") ||
                        risk.metric?.includes("volatility")
                          ? percent(risk.current_value)
                          : number(risk.current_value).toFixed(2)}
                      </strong>
                    </span>
                  )}

                  <span>
                    Confidence <strong>{percent(risk.confidence)}</strong>
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <section className="panel root-cause-panel">
        <PanelHeader
          title="Root cause analysis"
          subtitle="Why these signals exist"
        />

        {rootCauses.length === 0 ? (
          <div className="muted-block">
            No root causes were returned by the analysis pipeline.
          </div>
        ) : (
          <div className="cause-grid">
            {rootCauses.map((cause, index) => (
              <div className="cause-card" key={cause.cause_id ?? index}>
                <div className="cause-number">{index + 1}</div>
                <div>
                  <h3>
                    {cause.title ??
                      cause.name ??
                      titleCase(cause.cause_id) ??
                      "Root cause"}
                  </h3>
                  <p>
                    {cause.explanation ??
                      cause.description ??
                      cause.evidence ??
                      cause.reason ??
                      "The pipeline identified this as a contributing factor."}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ScenariosView({
  scenarios,
  baselineCash,
  recommendedScenario,
}: {
  scenarios: AnyObject[];
  baselineCash: number;
  recommendedScenario: AnyObject;
}) {
  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">COUNTERFACTUAL ENGINE</div>
          <h2>Don't guess. Compare.</h2>
          <p>
            FinSight simulates explicit intervention assumptions before
            recommending a path.
          </p>
        </div>

        <div className="simulation-badge">
          <Activity size={15} />
          Monte Carlo
        </div>
      </div>

      <div className="scenario-grid">
        {scenarios.map((scenario, index) => {
          const recommended =
            scenario.scenario_id === recommendedScenario.scenario_id;

          const delta =
            scenario.endingCash - baselineCash;

          return (
            <div
              className={`scenario-card ${recommended ? "recommended" : ""}`}
              key={scenario.scenario_id ?? index}
            >
              {recommended && (
                <div className="recommended-tag">
                  <Check size={13} />
                  RECOMMENDED
                </div>
              )}

              <div className="scenario-top">
                <div className="scenario-icon">
                  {scenario.baseline ? (
                    <Activity size={19} />
                  ) : (
                    <Zap size={19} />
                  )}
                </div>

                <div>
                  <h3>{scenario.displayName}</h3>
                  <span>
                    {scenario.duration_months
                      ? `${scenario.duration_months}-month intervention`
                      : scenario.baseline
                        ? "No intervention"
                        : "Intervention scenario"}
                  </span>
                </div>
              </div>

              <p className="scenario-description">
                {scenario.description ??
                  "Scenario outcome generated from the financial state."}
              </p>

              <div className="scenario-main-metric">
                <span>Median ending cash</span>
                <strong>{compactMoney(scenario.endingCash)}</strong>
              </div>

              <div className="scenario-stats">
                <div>
                  <span>Survival</span>
                  <strong>{percent(scenario.survival)}</strong>
                </div>

                <div>
                  <span>vs baseline</span>
                  <strong className={delta >= 0 ? "positive" : "negative"}>
                    {delta >= 0 ? "+" : ""}
                    {compactMoney(delta)}
                  </strong>
                </div>
              </div>

              <div className="range">
                <div className="range-label">
                  <span>10th percentile</span>
                  <span>90th percentile</span>
                </div>

                <div className="range-line">
                  <span
                    className="range-fill"
                    style={{
                      width: `${Math.max(
                        8,
                        Math.min(
                          92,
                          scenario.survival * 100,
                        ),
                      )}%`,
                    }}
                  />
                </div>

                <div className="range-values">
                  <span>{compactMoney(scenario.p10)}</span>
                  <span>{compactMoney(scenario.p90)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="method-note">
        <ShieldCheck size={17} />
        <span>
          Scenario outputs are probabilistic estimates conditional on the
          current financial state and explicit assumptions — not guaranteed
          forecasts.
        </span>
      </div>
    </div>
  );
}

function DecisionView({
  decision,
  policy,
  action,
  recommendedScenario,
}: {
  decision: AnyObject;
  policy: AnyObject;
  action: AnyObject | null;
  recommendedScenario: AnyObject;
}) {
  const reasoning: string[] =
    decision.reasoning ??
    policy.reasoning ??
    action?.reasoning ??
    [];

  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">DECISION LAYER</div>
          <h2>What should happen next?</h2>
          <p>
            The optimizer chooses a scenario; the policy engine decides
            whether that action is allowed.
          </p>
        </div>

        <div className={`policy-pill ${String(policy.status).toLowerCase()}`}>
          <span />
          {policy.status ?? "UNKNOWN"}
        </div>
      </div>

      <section className="decision-main">
        <div className="decision-recommendation">
          <div className="recommendation-icon">
            <Target size={28} />
          </div>

          <div className="mini-label">RECOMMENDED SCENARIO</div>

          <h2>
            {recommendedScenario.name ??
              recommendedScenario.scenario_name ??
              titleCase(recommendedScenario.scenario_id)}
          </h2>

          <p>
            {recommendedScenario.description ??
              "The optimizer selected this scenario based on simulated outcomes."}
          </p>

          <div className="recommendation-metrics">
            <div>
              <span>Decision confidence</span>
              <strong>
                {decision.confidence != null
                  ? percent(decision.confidence)
                  : action?.confidence != null
                    ? percent(action.confidence)
                    : "—"}
              </strong>
            </div>

            <div>
              <span>Policy status</span>
              <strong>{policy.status ?? "—"}</strong>
            </div>
          </div>
        </div>

        <div className="reasoning-panel">
          <PanelHeader
            title="Decision reasoning"
            subtitle="Traceable recommendation"
          />

          {reasoning.length === 0 ? (
            <div className="muted-block">
              No explicit reasoning items were returned.
            </div>
          ) : (
            <div className="reasoning-list">
              {reasoning.map((item, index) => (
                <div className="reasoning-item" key={index}>
                  <span>{index + 1}</span>
                  <p>{item}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="panel action-panel">
        <PanelHeader
          title="Approved action"
          subtitle="Policy-gated intervention"
        />

        {action ? (
          <div className="action-content">
            <div className="action-summary">
              <div className="action-icon">
                <Play size={19} />
              </div>

              <div>
                <h3>
                  {action.scenario_name ??
                    action.scenario_id ??
                    "Approved intervention"}
                </h3>

                <p>
                  This action was constructed from the policy engine's
                  approved action.
                </p>
              </div>
            </div>

            <div className="parameter-grid">
              {Object.entries(action.parameters ?? {}).map(
                ([key, value]) => (
                  <div className="parameter" key={key}>
                    <span>{titleCase(key)}</span>
                    <strong>
                      {typeof value === "number"
                        ? key.includes("adjustment") ||
                          key.includes("reduction")
                          ? percent(value)
                          : key.includes("cash")
                            ? money(value)
                            : value
                        : String(value)}
                    </strong>
                  </div>
                ),
              )}
            </div>
          </div>
        ) : (
          <div className="blocked-action">
            <ShieldCheck size={25} />
            <div>
              <strong>No external action approved</strong>
              <p>
                The policy engine did not produce an executable intervention.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ExecutionView({
  action,
  execution,
  verification,
}: {
  action: AnyObject | null;
  execution: AnyObject | null;
  verification: AnyObject | null;
}) {
  const verified = verification?.verified === true;

  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">CONTROLLED EXECUTION</div>
          <h2>From recommendation to action.</h2>
          <p>
            FinSight currently operates in dry-run mode. Nothing external is
            modified.
          </p>
        </div>

        <div className="dry-run-badge">
          <span />
          DRY RUN
        </div>
      </div>

      <section className="execution-timeline">
        <TimelineStep
          number="01"
          title="Decision approved"
          description="The policy engine produced an approved intervention."
          complete={Boolean(action)}
        />

        <TimelineStep
          number="02"
          title="Action constructed"
          description="Execution parameters were taken directly from the approved action."
          complete={Boolean(action)}
        />

        <TimelineStep
          number="03"
          title="Dry-run executed"
          description="The executor validated the action without modifying an external system."
          complete={Boolean(execution)}
        />

        <TimelineStep
          number="04"
          title="Execution verified"
          description="The verifier checked that the dry-run matches the approved action."
          complete={verified}
          last
        />
      </section>

      <section className="verification-card">
        <div
          className={`verification-icon ${verified ? "verified" : "failed"}`}
        >
          {verified ? <Check size={30} /> : <AlertTriangle size={30} />}
        </div>

        <div className="verification-copy">
          <div className="mini-label">VERIFICATION RESULT</div>
          <h2>
            {verification?.status ??
              (action ? "Awaiting execution" : "No action")}
          </h2>

          <p>
            {verification?.reason ??
              "No execution verification is available for this decision."}
          </p>

          {verification && (
            <div className="verification-meta">
              <span>
                Verification type{" "}
                <strong>
                  {titleCase(verification.verification_type)}
                </strong>
              </span>

              <span>
                Financial outcome{" "}
                <strong>
                  {verification.outcome_available ? "Available" : "Not evaluated"}
                </strong>
              </span>
            </div>
          )}
        </div>
      </section>

      <div className="important-note">
        <AlertTriangle size={18} />
        <div>
          <strong>Important distinction</strong>
          <p>
            Execution verification confirms that the dry-run matched the
            approved action. It does <strong>not</strong> claim that money was
            actually recovered or that a real-world financial outcome occurred.
          </p>
        </div>
      </div>
    </div>
  );
}

function TimelineStep({
  number: stepNumber,
  title,
  description,
  complete,
  last = false,
}: {
  number: string;
  title: string;
  description: string;
  complete: boolean;
  last?: boolean;
}) {
  return (
    <div className={`timeline-step ${complete ? "complete" : ""}`}>
      <div className="timeline-marker">
        {complete ? <Check size={16} /> : stepNumber}
      </div>

      {!last && <div className="timeline-line" />}

      <div className="timeline-content">
        <span className="step-number">STEP {stepNumber}</span>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
  negative,
  warning,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  negative?: boolean;
  warning?: boolean;
}) {
  return (
    <div className={`metric-card ${negative ? "negative" : ""}`}>
      <div className="metric-card-top">
        <span>{label}</span>
        <div className={`metric-icon ${warning ? "warning" : ""}`}>
          {icon}
        </div>
      </div>

      <strong>{value}</strong>
    </div>
  );
}

function PositionRow({
  label,
  value,
  trend,
  trendLabel,
  inverse = false,
}: {
  label: string;
  value: string;
  trend?: number;
  trendLabel?: string;
  inverse?: boolean;
}) {
  return (
    <div className="position-row">
      <span>{label}</span>

      <div className="position-value">
        <strong>{value}</strong>

        {trend !== undefined && (
          <span
            className={
              inverse
                ? trend > 0
                  ? "trend negative"
                  : "trend positive"
                : trend >= 0
                  ? "trend positive"
                  : "trend negative"
            }
          >
            {trend >= 0 ? (
              <ArrowUpRight size={13} />
            ) : (
              <ArrowDownRight size={13} />
            )}
            {Math.abs(trend * 100).toFixed(1)}% {trendLabel}
          </span>
        )}
      </div>
    </div>
  );
}

function PanelHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel-header">
      <div>
        <h3>{title}</h3>
        <span>{subtitle}</span>
      </div>

      {action}
    </div>
  );
}

function EmptyState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <FileSpreadsheet size={28} />
      </div>
      <h2>FinSight is waiting for data</h2>
      <p>Load the demo dataset or upload a financial CSV.</p>
      <button onClick={onRetry}>
        Load demo
        <ChevronRight size={17} />
      </button>
    </div>
  );
}

export default App;