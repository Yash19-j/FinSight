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
  { id: "risks", label: "Risks & Drivers", icon: AlertTriangle },
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

function confidenceLabel(value: unknown): string {
  const raw = String(value ?? "").toUpperCase();

  if (raw === "HIGH") return "High";
  if (raw === "MEDIUM") return "Medium";
  if (raw === "LOW") return "Low";

  const n = number(value, NaN);

  if (!Number.isFinite(n)) return "—";
  if (n >= 0.8) return "High";
  if (n >= 0.6) return "Medium";
  return "Low";
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

function displayName(
  object: AnyObject | null | undefined,
  fallback = "Unknown",
): string {
  if (!object) return fallback;

  const value =
    object.name ??
    object.scenario_name ??
    object.title ??
    object.scenario_id ??
    object.cause_id;

  const result = String(value ?? "").trim();

  return result ? titleCase(result) : fallback;
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

      shortfall: scenarioMetric(
        scenario,
        [
          "probability_of_cash_shortfall",
          "cash_shortfall_probability",
          "shortfall_probability",
        ],
        0,
      ),
    }));
  }, [scenarios]);

  const baselineScenario =
    scenarioRows.find((scenario: AnyObject) => scenario.baseline) ??
    scenarioRows.find(
      (scenario: AnyObject) => scenario.scenario_id === "baseline",
    );

  const baselineCash = baselineScenario?.endingCash ?? 0;

  const baselineShortfall = baselineScenario?.shortfall ?? 0;

  const selectedScenario = scenarioRows.find(
    (scenario: AnyObject) =>
      scenario.scenario_id === recommendedScenario.scenario_id,
  );

  const selectedShortfall =
    selectedScenario?.shortfall ??
    (recommendedScenario?.probability_of_cash_shortfall != null
      ? number(recommendedScenario.probability_of_cash_shortfall)
      : null);

  const isBlocked =
    String(policy.status ?? "").toUpperCase() === "BLOCK";

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
            <div className="brand-subtitle">
              Decision Intelligence
            </div>
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

              if (file) {
                uploadCsv(file);
              }
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
            <div className="eyebrow">
              FINANCIAL CONTROL CENTER
            </div>

            <h1>{pageTitle(activeView)}</h1>
          </div>

          <div className="topbar-actions">
            <div className="data-confidence">
              <span>Data confidence</span>

              <strong>
                {confidenceLabel(financialState.data_confidence)}
              </strong>
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
                scenarios={scenarioRows}
                decision={decision}
                policy={policy}
                recommendedScenario={recommendedScenario}
                highestRisk={highestRisk}
                isBlocked={isBlocked}
                onNavigate={setActiveView}
              />
            )}

            {activeView === "risks" && (
              <RisksView
                risks={risks}
                rootCauses={rootCauses}
              />
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
                baselineShortfall={baselineShortfall}
                selectedShortfall={selectedShortfall}
              />
            )}

            {activeView === "execution" && (
              <ExecutionView
                action={action}
                execution={execution}
                verification={verification}
                policy={policy}
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
      return "Risks & Detected Drivers";

    case "scenarios":
      return "Scenario Engine";

    case "decision":
      return "Decision Center";

    case "execution":
      return "Execution & Verification";
  }
}


function CashTrajectory({
  scenarios,
  baselineCash,
  recommendedScenario,
}: {
  scenarios: AnyObject[];
  baselineCash: number;
  recommendedScenario: AnyObject;
}) {
  const baseline = scenarios.find(
    (scenario) =>
      scenario.scenario_id === "baseline" || scenario.baseline,
  );

  const selected = scenarios.find(
    (scenario) =>
      scenario.scenario_id === recommendedScenario?.scenario_id,
  );

  const baselineEnd = number(
    baseline?.endingCash,
    baselineCash,
  );

  const selectedEnd = number(
    selected?.endingCash,
    baselineEnd,
  );

  const values = [baselineCash, baselineEnd, selectedEnd];
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);

  const width = 760;
  const height = 250;
  const left = 52;
  const right = 24;
  const top = 24;
  const bottom = 42;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const x0 = left;
  const x1 = left + chartWidth;

  const y = (value: number) =>
    top + ((maxAbs - value) / (maxAbs * 2)) * chartHeight;

  const startY = y(baselineCash);
  const baselineEndY = y(baselineEnd);
  const selectedEndY = y(selectedEnd);
  const zeroY = y(0);

  const baselinePath = `
    M ${x0} ${startY}
    C ${x0 + chartWidth * 0.25} ${startY},
      ${x0 + chartWidth * 0.48} ${baselineEndY},
      ${x1} ${baselineEndY}
  `;

  const selectedPath = `
    M ${x0} ${startY}
    C ${x0 + chartWidth * 0.25} ${startY},
      ${x0 + chartWidth * 0.55} ${selectedEndY},
      ${x1} ${selectedEndY}
  `;

  return (
    <section className="trajectory-panel panel">
      <div className="panel-header">
        <div>
          <h3>Financial Trajectory</h3>
          <span>Current position vs. simulated endpoints</span>
        </div>

        <div className="trajectory-legend">
          <span>
            <i className="legend-dot baseline" />
            Baseline
          </span>
          {selected && (
            <span>
              <i className="legend-dot recommended" />
              Recommended
            </span>
          )}
        </div>
      </div>

      <div className="trajectory-chart">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Financial trajectory comparison"
        >
          <line
            x1={left}
            x2={x1}
            y1={top + chartHeight * 0.25}
            y2={top + chartHeight * 0.25}
            className="chart-grid-line"
          />
          <line
            x1={left}
            x2={x1}
            y1={top + chartHeight * 0.5}
            y2={top + chartHeight * 0.5}
            className="chart-grid-line"
          />
          <line
            x1={left}
            x2={x1}
            y1={top + chartHeight * 0.75}
            y2={top + chartHeight * 0.75}
            className="chart-grid-line"
          />

          <line
            x1={left}
            x2={x1}
            y1={zeroY}
            y2={zeroY}
            className="chart-zero-line"
          />

          <text x={left} y={zeroY - 8} className="chart-zero-label">
            ₹0 — cash shortfall
          </text>

          <path d={baselinePath} className="trajectory-line baseline-line" />

          {selected && (
            <path
              d={selectedPath}
              className="trajectory-line recommended-line"
            />
          )}

          <circle
            cx={x0}
            cy={startY}
            r="5"
            className="trajectory-point start-point"
          />

          <circle
            cx={x1}
            cy={baselineEndY}
            r="5"
            className="trajectory-point baseline-point"
          />

          {selected && (
            <circle
              cx={x1}
              cy={selectedEndY}
              r="6"
              className="trajectory-point recommended-point"
            />
          )}

          <text x={x0} y={height - 12} className="chart-axis-label">
            NOW
          </text>

          <text
            x={x1}
            y={height - 12}
            textAnchor="end"
            className="chart-axis-label"
          >
            SIMULATED HORIZON
          </text>

          <text
            x={x1 - 8}
            y={baselineEndY - 12}
            textAnchor="end"
            className="chart-value-label baseline-value"
          >
            {compactMoney(baselineEnd)}
          </text>

          {selected && (
            <text
              x={x1 - 8}
              y={selectedEndY + 22}
              textAnchor="end"
              className="chart-value-label recommended-value"
            >
              {compactMoney(selectedEnd)}
            </text>
          )}
        </svg>
      </div>

      <div className="trajectory-footer">
        <div>
          <span>Starting cash</span>
          <strong>{compactMoney(baselineCash)}</strong>
        </div>

        <div>
          <span>Baseline endpoint</span>
          <strong>{compactMoney(baselineEnd)}</strong>
        </div>

        {selected && (
          <div>
            <span>Recommended endpoint</span>
            <strong className="trajectory-positive">
              {compactMoney(selectedEnd)}
            </strong>
          </div>
        )}
      </div>

      <p className="trajectory-note">
        The curve connects observed simulation endpoints; it does not
        invent month-by-month simulation values.
      </p>
    </section>
  );
}

function Overview({
  state,
  risks,
  scenarios,
  decision,
  policy,
  recommendedScenario,
  highestRisk,
  isBlocked,
  onNavigate,
}: {
  state: AnyObject;
  risks: AnyObject[];
  scenarios: AnyObject[];
  decision: AnyObject;
  policy: AnyObject;
  recommendedScenario: AnyObject;
  highestRisk?: AnyObject;
  isBlocked: boolean;
  onNavigate: (view: View) => void;
}) {
  const runway = state.runway_months;
  const netBurn = state.net_burn;
  const revenue = state.monthly_revenue;
  const expenses = state.monthly_expenses;
  const revenueGrowth = state.revenue_growth;
  const expenseGrowth = state.expense_growth;
  const ratio = number(state.revenue_expense_ratio);
  const averageBurn = state.average_net_burn;
  const burnMultiple = state.burn_multiple;

  const selectedScenario = scenarios.find(
    (scenario: AnyObject) =>
      scenario.scenario_id === recommendedScenario?.scenario_id,
  );

  const baselineScenario = scenarios.find(
    (scenario: AnyObject) =>
      scenario.scenario_id === "baseline" || scenario.baseline,
  );

  const baselineEndingCash = number(
    baselineScenario?.endingCash,
    number(state.cash),
  );

  const selectedEndingCash = number(
    selectedScenario?.endingCash,
    baselineEndingCash,
  );

  const endingCashImprovement =
    selectedEndingCash - baselineEndingCash;


  const selectedShortfall = number(
    selectedScenario?.shortfall,
    number(recommendedScenario?.probability_of_cash_shortfall),
  );

  const baselineShortfall = number(
    baselineScenario?.shortfall,
  );

  const shortfallReduced = selectedShortfall < baselineShortfall;
  const monthlyGap = number(revenue) - number(expenses);

  const riskHeadline = isBlocked
    ? "Cash protection is not yet safe to automate."
    : highestRisk
      ? "Financial pressure has been evaluated before action."
      : "Financial position has been evaluated for action.";

  return (
    <div className="page overview-page">
      <section className={`hero overview-hero ${isBlocked ? "hero-blocked" : ""}`}>
        <div className="overview-hero-copy">
          <div className="hero-kicker">
            <span className="live-dot" />
            AI FINANCIAL BRIEF
          </div>

          <h2>
            {isBlocked ? (
              <>
                Cash protection comes
                <br />
                <span>before automation.</span>
              </>
            ) : (
              <>
                Your next financial move,
                <br />
                <span>already evaluated.</span>
              </>
            )}
          </h2>

          <p>
            {riskHeadline} FinSight converts financial history into a
            risk-aware, policy-gated decision.
          </p>

          <div className="hero-facts">
            <div>
              <span>Cash</span>
              <strong>{compactMoney(state.cash)}</strong>
            </div>

            <div>
              <span>Monthly position</span>
              <strong className={monthlyGap < 0 ? "fact-negative" : "fact-positive"}>
                {monthlyGap >= 0 ? "+" : "−"}
                {compactMoney(Math.abs(monthlyGap))}
              </strong>
            </div>

            <div>
              <span>Runway</span>
              <strong>{months(runway)}</strong>
            </div>
          </div>
        </div>

        <div className={`hero-decision ${isBlocked ? "hero-decision-blocked" : ""}`}>
          <div className="mini-label">CURRENT DECISION</div>

          <div
            className={`decision-status ${
              isBlocked ? "blocked-status" : ""
            }`}
          >
            <span className="status-pulse" />

            {isBlocked
              ? "BLOCKED"
              : policy.status ??
                decision.status ??
                "ANALYZED"}
          </div>

          <div className="hero-decision-meta">
            <span>Data confidence</span>
            <strong>
              {confidenceLabel(
                state.data_confidence ?? decision.confidence,
              )}
            </strong>
          </div>

          <button onClick={() => onNavigate("decision")}>
            View decision
            <ChevronRight size={16} />
          </button>
        </div>
      </section>

      <section className="metric-grid overview-metrics">
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
          warning={number(runway) > 0 && number(runway) <= 6}
        />

        <MetricCard
          label="Revenue / expense"
          value={ratio.toFixed(2)}
          icon={<Activity size={18} />}
          warning={ratio < 1}
        />
      </section>

      <FinancialPulse
        revenue={revenue}
        expenses={expenses}
        monthlyGap={monthlyGap}
        revenueGrowth={revenueGrowth}
        expenseGrowth={expenseGrowth}
        averageBurn={averageBurn}
        burnMultiple={burnMultiple}
        ratio={ratio}
      />

      <CashTrajectory
        scenarios={scenarios}
        baselineCash={number(state.cash)}
        recommendedScenario={recommendedScenario}
      />

      <section className="grid-two overview-detail-grid">
        <div className="panel overview-operating-panel">
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
              value={money(averageBurn)}
            />

            <PositionRow
              label="Burn multiple"
              value={
                burnMultiple === null || burnMultiple === undefined
                  ? "N/A"
                  : number(burnMultiple).toFixed(2)
              }
            />
          </div>

          <div className="operating-signal">
            <div className="operating-signal-label">MONTHLY CASH FLOW SIGNAL</div>
            <div className={monthlyGap < 0 ? "signal-negative" : "signal-positive"}>
              {monthlyGap < 0 ? "Deficit" : "Surplus"}
              <strong>
                {monthlyGap >= 0 ? "+" : "−"}
                {compactMoney(Math.abs(monthlyGap))}
              </strong>
            </div>
            <p>
              Revenue currently covers {ratio.toFixed(2)}× of monthly expenses.
            </p>
          </div>
        </div>

        <div className="panel risk-panel overview-risk-panel">
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

              <div className="risk-evidence-grid">
                <div>
                  <span>Metric</span>
                  <strong>{titleCase(highestRisk.metric)}</strong>
                </div>

                {highestRisk.current_value != null && (
                  <div>
                    <span>Current</span>
                    <strong>
                      {highestRisk.metric?.includes("growth") ||
                      highestRisk.metric?.includes("volatility")
                        ? percent(highestRisk.current_value)
                        : number(highestRisk.current_value).toFixed(2)}
                    </strong>
                  </div>
                )}

                <div>
                  <span>Confidence</span>
                  <strong>
                    {confidenceLabel(highestRisk.confidence)}
                  </strong>
                </div>

                {highestRisk.financial_impact != null && (
                  <div>
                    <span>Impact</span>
                    <strong>
                      {compactMoney(highestRisk.financial_impact)}
                    </strong>
                  </div>
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

      <section className={`decision-strip overview-decision-strip ${isBlocked ? "blocked" : ""}`}>
        <div className="decision-strip-icon">
          {isBlocked ? <ShieldCheck size={22} /> : <Target size={22} />}
        </div>

        <div className="decision-strip-content">
          <div className="mini-label">
            {isBlocked ? "NO SAFE ACTION FOUND" : "RECOMMENDED PATH"}
          </div>

          <h3>
            {isBlocked
              ? "Automatic execution blocked"
              : displayName(recommendedScenario, "No intervention")}
          </h3>

          <p>
            {isBlocked
              ? policy?.policy?.violations?.[0] ??
                "The selected intervention does not satisfy the financial safety policy."
              : recommendedScenario.description ??
                "FinSight evaluated the available intervention scenarios."}
          </p>
        </div>

        <div className="decision-strip-metrics">
          <div>
            <span>Ending cash delta</span>
            <strong className={endingCashImprovement >= 0 ? "positive" : "negative"}>
              {endingCashImprovement >= 0 ? "+" : "−"}
              {compactMoney(Math.abs(endingCashImprovement))}
            </strong>
          </div>

          <div>
            <span>Shortfall risk</span>
            <strong className={shortfallReduced ? "positive" : "negative"}>
              {percent(selectedShortfall)}
            </strong>
          </div>

          <div>
            <span>Policy</span>
            <strong>{policy.status ?? "—"}</strong>
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

function FinancialPulse({
  revenue,
  expenses,
  monthlyGap,
  revenueGrowth,
  expenseGrowth,
  averageBurn,
  burnMultiple,
  ratio,
}: {
  revenue: unknown;
  expenses: unknown;
  monthlyGap: number;
  revenueGrowth: unknown;
  expenseGrowth: unknown;
  averageBurn: unknown;
  burnMultiple: unknown;
  ratio: number;
}) {
  const deficit = monthlyGap < 0;
  const expensePressure = number(expenseGrowth) > number(revenueGrowth);

  return (
    <section className={`panel financial-pulse ${deficit ? "pulse-deficit" : "pulse-surplus"}`}>
      <div className="financial-pulse-header">
        <div>
          <div className="pulse-eyebrow">FINANCIAL PULSE</div>
          <h3>What is driving the current position?</h3>
        </div>

        <div className={`pulse-state ${deficit ? "negative" : "positive"}`}>
          <span />
          {deficit ? "CASH OUTFLOW" : "CASH GENERATIVE"}
        </div>
      </div>

      <div className="financial-pulse-main">
        <div className="cash-flow-block">
          <span className="pulse-label">MONTHLY REVENUE</span>
          <strong>{money(revenue)}</strong>

          <div className="pulse-bar revenue-bar">
            <span style={{ width: `${Math.min(100, Math.max(8, (number(revenue) / Math.max(number(revenue), number(expenses), 1)) * 100))}%` }} />
          </div>
        </div>

        <div className="cash-flow-block">
          <span className="pulse-label">MONTHLY EXPENSES</span>
          <strong>{money(expenses)}</strong>

          <div className="pulse-bar expense-bar">
            <span style={{ width: `${Math.min(100, Math.max(8, (number(expenses) / Math.max(number(revenue), number(expenses))) * 100))}%` }} />
          </div>
        </div>

        <div className="cash-flow-gap">
          <span className="pulse-label">CURRENT GAP</span>
          <strong className={deficit ? "negative" : "positive"}>
            {monthlyGap >= 0 ? "+" : "−"}
            {compactMoney(Math.abs(monthlyGap))}
          </strong>
          <span>{deficit ? "monthly deficit" : "monthly surplus"}</span>
        </div>
      </div>

      <div className="pulse-diagnostics">
        <div>
          <span>Revenue growth</span>
          <strong className={number(revenueGrowth) >= 0 ? "positive" : "negative"}>
            {percent(revenueGrowth)} MoM
          </strong>
        </div>

        <div>
          <span>Expense growth</span>
          <strong className={expensePressure ? "negative" : "positive"}>
            {percent(expenseGrowth)} MoM
          </strong>
        </div>

        <div>
          <span>Average net burn</span>
          <strong>{money(averageBurn)}</strong>
        </div>

        <div>
          <span>Burn multiple</span>
          <strong>
            {burnMultiple === null || burnMultiple === undefined
              ? "N/A"
              : number(burnMultiple).toFixed(2)}
          </strong>
        </div>

        <div>
          <span>Revenue / expense</span>
          <strong className={ratio >= 1 ? "positive" : "negative"}>
            {ratio.toFixed(2)}×
          </strong>
        </div>
      </div>
    </section>
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
            Deterministic risk signals are ranked by
            severity, financial impact and confidence.
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
            <div
              className="risk-card"
              key={risk.risk_id ?? index}
            >
              <div className="risk-card-index">
                {(index + 1)
                  .toString()
                  .padStart(2, "0")}
              </div>

              <div className="risk-card-main">
                <div className="risk-heading">
                  <span
                    className={severityClass(
                      risk.severity,
                    )}
                  >
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
                    Metric{" "}
                    <strong>
                      {titleCase(risk.metric)}
                    </strong>
                  </span>

                  {risk.current_value != null && (
                    <span>
                      Current{" "}
                      <strong>
                        {risk.metric?.includes(
                          "growth",
                        ) ||
                        risk.metric?.includes(
                          "volatility",
                        )
                          ? percent(
                              risk.current_value,
                            )
                          : number(
                              risk.current_value,
                            ).toFixed(2)}
                      </strong>
                    </span>
                  )}

                  <span>
                    Confidence{" "}
                    <strong>
                      {confidenceLabel(
                        risk.confidence,
                      )}
                    </strong>
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <section className="panel root-cause-panel">
        <PanelHeader
          title="Detected drivers"
          subtitle="Evidence behind the identified risks"
        />

        {rootCauses.length === 0 ? (
          <div className="muted-block">
            No detected drivers were returned by
            the analysis pipeline.
          </div>
        ) : (
          <div className="cause-grid">
            {rootCauses.map((cause, index) => (
              <div
                className="cause-card"
                key={cause.cause_id ?? index}
              >
                <div className="cause-number">
                  {index + 1}
                </div>

                <div>
                  <h3>
                    {cause.title ??
                      cause.name ??
                      titleCase(
                        cause.cause_id,
                      ) ??
                      "Detected driver"}
                  </h3>

                  <p>
                    {cause.explanation ??
                      cause.description ??
                      cause.root_cause ??
                      cause.evidence ??
                      cause.reason ??
                      "The pipeline identified this as a contributing financial factor."}
                  </p>

                  {cause.contributing_factors
                    ?.length > 0 && (
                    <div className="factor-list">
                      {cause.contributing_factors.map(
                        (
                          factor: string,
                          factorIndex: number,
                        ) => (
                          <span
                            key={factorIndex}
                          >
                            {factor}
                          </span>
                        ),
                      )}
                    </div>
                  )}
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
          <div className="eyebrow">
            COUNTERFACTUAL ENGINE
          </div>

          <h2>Don't guess. Compare.</h2>

          <p>
            FinSight simulates explicit intervention
            assumptions before recommending a path.
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
            scenario.scenario_id ===
            recommendedScenario.scenario_id;

          const delta =
            scenario.endingCash - baselineCash;

          return (
            <div
              className={`scenario-card ${
                recommended ? "recommended" : ""
              }`}
              key={scenario.scenario_id ?? index}
            >
              {recommended && (
                <div className="recommended-tag">
                  <Check size={13} />
                  BEST AVAILABLE
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

                <strong>
                  {compactMoney(
                    scenario.endingCash,
                  )}
                </strong>
              </div>

              <div className="scenario-stats">
                <div>
                  <span>Survival</span>

                  <strong>
                    {percent(scenario.survival)}
                  </strong>
                </div>

                <div>
                  <span>Shortfall risk</span>

                  <strong
                    className={
                      scenario.shortfall >= 0.5
                        ? "negative"
                        : "positive"
                    }
                  >
                    {percent(scenario.shortfall)}
                  </strong>
                </div>

                <div>
                  <span>vs baseline</span>

                  <strong
                    className={
                      delta >= 0
                        ? "positive"
                        : "negative"
                    }
                  >
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
                          scenario.survival *
                            100,
                        ),
                      )}%`,
                    }}
                  />
                </div>

                <div className="range-values">
                  <span>
                    {compactMoney(scenario.p10)}
                  </span>

                  <span>
                    {compactMoney(scenario.p90)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="method-note">
        <ShieldCheck size={17} />

        <span>
          Scenario outputs are probabilistic
          estimates conditional on the current
          financial state and explicit assumptions —
          not guaranteed forecasts.
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
  baselineShortfall,
  selectedShortfall,
}: {
  decision: AnyObject;
  policy: AnyObject;
  action: AnyObject | null;
  recommendedScenario: AnyObject;
  baselineShortfall: number;
  selectedShortfall: number | null;
}) {
  const isBlocked =
    String(policy.status ?? "").toUpperCase() ===
    "BLOCK";

  const reasoning: string[] =
    decision.reasoning ??
    policy.reasoning ??
    action?.reasoning ??
    [];

  const violation =
    policy?.policy?.violations?.[0] ??
    (isBlocked
      ? "Automatic execution is blocked under the configured policy."
      : null);

  const survivalImprovement =
    recommendedScenario?.survival_improvement ?? 0;

  const downsideImprovement =
    recommendedScenario?.downside_improvement ?? 0;

  const endingCashImprovement =
    recommendedScenario?.ending_cash_improvement ?? 0;

  const survivalHorizonImprovement =
    recommendedScenario?.survival_horizon_improvement ??
    0;

  const shortfallImprovement =
    baselineShortfall -
    number(selectedShortfall, baselineShortfall);

  const shortfallReduced =
    selectedShortfall != null &&
    selectedShortfall < baselineShortfall;

  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">DECISION LAYER</div>

          <h2>
            {isBlocked
              ? "The safest decision is to stop."
              : "What should happen next?"}
          </h2>

          <p>
            The optimizer chooses a scenario; the policy
            engine decides whether that action is allowed.
          </p>
        </div>

        <div
          className={`policy-pill ${
            isBlocked ? "block" : "approve"
          }`}
        >
          <span />
          {policy.status ?? "UNKNOWN"}
        </div>
      </div>

      {isBlocked && (
        <section className="safe-action-banner">
          <div className="safe-action-icon">
            <ShieldCheck size={30} />
          </div>

          <div>
            <div className="mini-label">
              FINANCIAL SAFETY GATE
            </div>

            <h2>NO SAFE ACTION FOUND</h2>

            <p>
              The optimizer found a best available
              intervention, but the selected intervention
              does not adequately mitigate the current
              financial risk. Automatic execution has
              therefore been blocked.
            </p>
          </div>
        </section>
      )}

      <section className="decision-main">
        <div
          className={`decision-recommendation ${
            isBlocked ? "blocked-recommendation" : ""
          }`}
        >
          <div className="recommendation-icon">
            {isBlocked ? (
              <ShieldCheck size={28} />
            ) : (
              <Target size={28} />
            )}
          </div>

          <div className="mini-label">
            {isBlocked
              ? "BEST AVAILABLE INTERVENTION"
              : "RECOMMENDED SCENARIO"}
          </div>

          <h2>
            {displayName(
              recommendedScenario,
              "No intervention",
            )}
          </h2>

          <p>
            {recommendedScenario.description ??
              "The optimizer selected this scenario based on simulated outcomes."}
          </p>

          <div className="recommendation-metrics">
            <div>
              <span>Decision score</span>

              <strong>
                {recommendedScenario.decision_score !=
                null
                  ? number(
                      recommendedScenario.decision_score,
                    ).toFixed(1)
                  : "—"}
              </strong>
            </div>

            <div>
              <span>Classification</span>

              <strong>
                {recommendedScenario.classification ??
                  "—"}
              </strong>
            </div>

            <div>
              <span>Data confidence</span>

              <strong>
                {confidenceLabel(
                  recommendedScenario.data_confidence ??
                    decision.data_confidence ??
                    recommendedScenario.confidence,
                )}
              </strong>
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
                <div
                  className="reasoning-item"
                  key={index}
                >
                  <span>{index + 1}</span>

                  <p>{item}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="panel decision-replay-panel">
        <PanelHeader
          title="Decision replay"
          subtitle="How FinSight moved from evidence to a controlled decision"
        />

        <div className="decision-replay">
          <div className="replay-step">
            <div className="replay-node">01</div>
            <div>
              <span>FINANCIAL STATE</span>
              <strong>Position assessed</strong>
              <p>Cash, revenue, expenses, burn and runway establish the starting state.</p>
            </div>
          </div>

          <div className="replay-step">
            <div className="replay-node">02</div>
            <div>
              <span>RISK DETECTION</span>
              <strong>Material risks ranked</strong>
              <p>Financial signals are evaluated for liquidity, burn, growth and expense pressure.</p>
            </div>
          </div>

          <div className="replay-step">
            <div className="replay-node">03</div>
            <div>
              <span>SCENARIO SIMULATION</span>
              <strong>Interventions compared</strong>
              <p>Candidate scenarios are evaluated through seeded Monte Carlo simulation.</p>
            </div>
          </div>

          <div className="replay-step">
            <div className="replay-node">04</div>
            <div>
              <span>OPTIMIZATION</span>
              <strong>Best available path selected</strong>
              <p>Scenario outcomes are ranked using survival, downside, cash and horizon impact.</p>
            </div>
          </div>

          <div className={`replay-step ${isBlocked ? "replay-blocked" : ""}`}>
            <div className="replay-node">05</div>
            <div>
              <span>SAFETY GATE</span>
              <strong>{isBlocked ? "Automatic execution blocked" : "Policy requirement satisfied"}</strong>
              <p>
                {isBlocked
                  ? "The selected intervention does not reduce cash-shortfall probability relative to baseline."
                  : "The selected intervention passes the configured financial safety policy."}
              </p>
            </div>
          </div>

          <div className={`replay-final ${isBlocked ? "replay-final-blocked" : ""}`}>
            {isBlocked ? <ShieldCheck size={20} /> : <Check size={20} />}
            <div>
              <span>FINAL DECISION</span>
              <strong>
                {isBlocked ? "NO SAFE ACTION FOUND" : "ACTION CLEARED FOR EXECUTION"}
              </strong>
            </div>
          </div>
        </div>
      </section>

      <section className="panel impact-panel">
        <PanelHeader
          title="Intervention impact"
          subtitle={
            isBlocked
              ? "Best available improvement — not sufficient for safe execution"
              : "Expected financial effect of the selected path"
          }
        />

        <div className="impact-grid">
          <ImpactMetric
            label="P10 cash improvement"
            value={
              downsideImprovement > 0
                ? `+${compactMoney(
                    downsideImprovement,
                  )}`
                : compactMoney(
                    downsideImprovement,
                  )
            }
            positive={downsideImprovement > 0}
          />

          <ImpactMetric
            label="Mean cash improvement"
            value={
              endingCashImprovement > 0
                ? `+${compactMoney(
                    endingCashImprovement,
                  )}`
                : compactMoney(
                    endingCashImprovement,
                  )
            }
            positive={endingCashImprovement > 0}
          />

          <ImpactMetric
            label="Survival horizon"
            value={`${
              survivalHorizonImprovement >= 0
                ? "+"
                : ""
            }${number(
              survivalHorizonImprovement,
            ).toFixed(2)} mo`}
            positive={survivalHorizonImprovement > 0}
          />

          <ImpactMetric
            label="Survival probability"
            value={percent(survivalImprovement)}
            positive={survivalImprovement > 0}
          />
        </div>
      </section>

      <section
        className={`panel safety-comparison ${
          isBlocked ? "safety-blocked" : ""
        }`}
      >
        <PanelHeader
          title="Financial safety check"
          subtitle="Does the selected intervention actually reduce cash-shortfall risk?"
        />

        <div className="safety-grid">
          <div className="safety-column baseline-column">
            <span>BASELINE</span>

            <strong>
              {percent(baselineShortfall)}
            </strong>

            <small>
              Probability of cash shortfall
            </small>
          </div>

          <div className="safety-arrow">
            <ChevronRight size={22} />
          </div>

          <div
            className={`safety-column ${
              shortfallReduced
                ? "safety-improved"
                : "safety-failed"
            }`}
          >
            <span>SELECTED INTERVENTION</span>

            <strong>
              {selectedShortfall != null
                ? percent(selectedShortfall)
                : "—"}
            </strong>

            <small>
              Probability of cash shortfall
            </small>
          </div>
        </div>

        <div
          className={`safety-result ${
            shortfallReduced
              ? "safety-result-pass"
              : "safety-result-fail"
          }`}
        >
          {shortfallReduced ? (
            <Check size={18} />
          ) : (
            <AlertTriangle size={18} />
          )}

          <div>
            <strong>
              {shortfallReduced
                ? "Safety requirement satisfied"
                : "Safety requirement not satisfied"}
            </strong>

            <p>
              {shortfallReduced
                ? `Cash-shortfall probability improves by ${percent(
                    shortfallImprovement,
                  )}.`
                : violation ??
                  "The selected intervention does not reduce the probability of cash shortfall relative to baseline."}
            </p>
          </div>
        </div>
      </section>

      <section className="panel action-panel">
        <PanelHeader
          title={
            isBlocked ? "Action gate" : "Approved action"
          }
          subtitle={
            isBlocked
              ? "Policy prevented executable action creation"
              : "Policy-gated intervention"
          }
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
                  This action was constructed from the
                  policy engine's approved action.
                </p>
              </div>
            </div>

            <div className="parameter-grid">
              {Object.entries(
                action.parameters ?? {},
              ).map(([key, value]) => (
                <div
                  className="parameter"
                  key={key}
                >
                  <span>{titleCase(key)}</span>

                  <strong>
                    {typeof value === "number"
                      ? key.includes(
                          "adjustment",
                        ) ||
                        key.includes(
                          "reduction",
                        )
                        ? percent(value)
                        : key.includes("cash")
                          ? money(value)
                          : value
                      : String(value)}
                  </strong>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div
            className={`blocked-action ${
              isBlocked
                ? "safety-block"
                : ""
            }`}
          >
            {isBlocked ? (
              <ShieldCheck size={25} />
            ) : (
              <AlertTriangle size={25} />
            )}

            <div>
              <strong>
                {isBlocked
                  ? "NO EXECUTABLE ACTION CREATED"
                  : "No external action approved"}
              </strong>

              <p>
                {isBlocked
                  ? violation
                  : "The policy engine did not produce an executable intervention."}
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ImpactMetric({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive: boolean;
}) {
  return (
    <div
      className={`impact-metric-card ${
        positive ? "impact-positive" : ""
      }`}
    >
      <span>{label}</span>

      <strong>{value}</strong>

      <div className="impact-indicator">
        {positive ? (
          <ArrowUpRight size={13} />
        ) : (
          <ArrowDownRight size={13} />
        )}

        <span>
          {positive
            ? "Improvement"
            : "No improvement"}
        </span>
      </div>
    </div>
  );
}

function ExecutionView({
  action,
  execution,
  verification,
  policy,
}: {
  action: AnyObject | null;
  execution: AnyObject | null;
  verification: AnyObject | null;
  policy: AnyObject;
}) {
  const isBlocked =
    String(policy.status ?? "").toUpperCase() ===
    "BLOCK";

  const verified =
    verification?.verified === true;

  if (isBlocked || !action) {
    return (
      <div className="page">
        <div className="section-intro">
          <div>
            <div className="eyebrow">
              CONTROLLED EXECUTION
            </div>

            <h2>
              Execution stopped by policy.
            </h2>

            <p>
              FinSight will not construct or execute
              an action when the financial safety gate
              blocks the selected intervention.
            </p>
          </div>

          <div className="policy-pill block">
            <span />
            BLOCKED
          </div>
        </div>

        <section className="execution-blocked-card">
          <div className="execution-blocked-icon">
            <ShieldCheck size={34} />
          </div>

          <div>
            <div className="mini-label">
              EXECUTION CONTROL
            </div>

            <h2>NO ACTION WAS EXECUTED</h2>

            <p>
              The optimizer identified the best
              available scenario, but the policy engine
              rejected automatic execution because the
              intervention did not reduce
              cash-shortfall probability.
            </p>

            <div className="execution-blocked-reason">
              <AlertTriangle size={17} />

              <span>
                {policy?.policy?.violations?.[0] ??
                  "Automatic execution is blocked under the configured policy."}
              </span>
            </div>
          </div>
        </section>

        <section className="execution-timeline">
          <TimelineStep
            number="01"
            title="Decision evaluated"
            description="The optimizer compared the available intervention scenarios."
            complete
          />

          <TimelineStep
            number="02"
            title="Policy evaluated"
            description="The financial safety gate rejected automatic execution."
            complete
          />

          <TimelineStep
            number="03"
            title="Action construction"
            description="Skipped because no approved action exists."
            complete={false}
          />

          <TimelineStep
            number="04"
            title="Execution"
            description="Skipped. No external system was modified."
            complete={false}
            last
          />
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="section-intro">
        <div>
          <div className="eyebrow">
            CONTROLLED EXECUTION
          </div>

          <h2>
            From recommendation to action.
          </h2>

          <p>
            FinSight currently operates in dry-run
            mode. Nothing external is modified.
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
          className={`verification-icon ${
            verified ? "verified" : "failed"
          }`}
        >
          {verified ? (
            <Check size={30} />
          ) : (
            <AlertTriangle size={30} />
          )}
        </div>

        <div className="verification-copy">
          <div className="mini-label">
            VERIFICATION RESULT
          </div>

          <h2>
            {verification?.status ??
              (action
                ? "Awaiting execution"
                : "No action")}
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
                  {titleCase(
                    verification.verification_type,
                  )}
                </strong>
              </span>

              <span>
                Financial outcome{" "}
                <strong>
                  {verification.outcome_available
                    ? "Available"
                    : "Not evaluated"}
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
            Execution verification confirms that the
            dry-run matched the approved action. It does
            <strong> not</strong> claim that money was
            actually recovered or that a real-world
            financial outcome occurred.
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
    <div
      className={`timeline-step ${
        complete ? "complete" : ""
      }`}
    >
      <div className="timeline-marker">
        {complete ? (
          <Check size={16} />
        ) : (
          stepNumber
        )}
      </div>

      {!last && <div className="timeline-line" />}

      <div className="timeline-content">
        <span className="step-number">
          STEP {stepNumber}
        </span>

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
    <div
      className={`metric-card ${
        negative ? "negative" : ""
      }`}
    >
      <div className="metric-card-top">
        <span>{label}</span>

        <div
          className={`metric-icon ${
            warning ? "warning" : ""
          }`}
        >
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

            {Math.abs(trend * 100).toFixed(1)}%{" "}
            {trendLabel}
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

function EmptyState({
  onRetry,
}: {
  onRetry: () => void;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <FileSpreadsheet size={28} />
      </div>

      <h2>FinSight is waiting for data</h2>

      <p>
        Load the demo dataset or upload a financial
        CSV.
      </p>

      <button onClick={onRetry}>
        Load demo
        <ChevronRight size={17} />
      </button>
    </div>
  );
}

export default App;