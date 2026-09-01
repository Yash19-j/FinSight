from __future__ import annotations

import math
from typing import Dict, List, Optional


class RootCauseEngine:
    """
    Deterministic, evidence-based root-cause analysis for risks emitted by
    RiskDetector. The engine consumes only normalized financial-state fields and
    supplied risk objects; it does not infer unsupported business explanations.
    """

    CONFIDENCE_BY_STATE = {
        "HIGH": 0.90,
        "MEDIUM": 0.75,
        "LOW": 0.50,
    }

    EXPECTED_RISK_FIELDS = {
        "risk_id",
        "category",
        "severity",
        "title",
        "metric",
        "current_value",
        "threshold",
        "financial_impact",
        "confidence",
        "evidence",
    }

    def __init__(self, financial_state: Dict[str, object], risks: List[Dict[str, object]]):
        if not isinstance(financial_state, dict):
            raise TypeError("RootCauseEngine expects financial_state to be a dictionary.")
        if not isinstance(risks, list):
            raise TypeError("RootCauseEngine expects risks to be a list.")

        self.state = financial_state
        self.risks = risks

        confidence_label = str(self.state.get("data_confidence", "LOW")).upper()
        if confidence_label not in self.CONFIDENCE_BY_STATE:
            confidence_label = "LOW"

        self.state_confidence = confidence_label
        self.base_confidence = self.CONFIDENCE_BY_STATE[confidence_label]

        self._validate_risks()
        self._validate_numeric_state_values()

    def _validate_risks(self) -> None:
        for index, risk in enumerate(self.risks):
            if not isinstance(risk, dict):
                raise TypeError(f"Risk at index {index} must be a dictionary.")

            missing = self.EXPECTED_RISK_FIELDS - set(risk.keys())
            if missing:
                raise ValueError(
                    f"Risk at index {index} is missing required fields: {sorted(missing)}"
                )

            for field in ("current_value", "threshold", "financial_impact", "confidence"):
                value = risk.get(field)
                if value is None:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Risk field '{field}' at index {index} must be numeric or None."
                    ) from exc
                if not math.isfinite(numeric):
                    raise ValueError(
                        f"Risk field '{field}' at index {index} must be finite when present."
                    )

    def _validate_numeric_state_values(self) -> None:
        numeric_fields = (
            "cash",
            "monthly_revenue",
            "monthly_expenses",
            "net_burn",
            "average_net_burn",
            "runway_months",
            "revenue_growth",
            "expense_growth",
            "revenue_volatility",
            "expense_volatility",
            "revenue_expense_ratio",
            "burn_multiple",
        )

        for field in numeric_fields:
            value = self.state.get(field)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric):
                raise ValueError(
                    f"Financial-state metric '{field}' must be finite when present."
                )

    @staticmethod
    def _finite_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    @staticmethod
    def _clamp_confidence(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _confidence(self, strength: float = 1.0) -> float:
        return round(
            self._clamp_confidence(self.base_confidence * strength),
            2,
        )

    @staticmethod
    def _evidence(metric: str, value: Optional[float], interpretation: str) -> Dict[str, object]:
        return {
            "metric": metric,
            "value": value,
            "interpretation": interpretation,
        }

    def _liquidity_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        average_burn = self._finite_float(self.state.get("average_net_burn"))
        net_burn = self._finite_float(self.state.get("net_burn"))
        revenue_growth = self._finite_float(self.state.get("revenue_growth"))
        expense_growth = self._finite_float(self.state.get("expense_growth"))
        ratio = self._finite_float(self.state.get("revenue_expense_ratio"))
        runway = self._finite_float(self.state.get("runway_months"))

        factors: List[str] = []
        evidence: List[Dict[str, object]] = []

        if average_burn is not None and average_burn > 0:
            evidence.append(
                self._evidence(
                    "average_net_burn",
                    average_burn,
                    f"Average monthly net burn is {average_burn:.2f}.",
                )
            )

        if runway is not None:
            evidence.append(
                self._evidence(
                    "runway_months",
                    runway,
                    f"Current runway is approximately {runway:.2f} months.",
                )
            )

        if net_burn is not None and net_burn > 0:
            factors.append("Structural operating deficit")
            evidence.append(
                self._evidence(
                    "net_burn",
                    net_burn,
                    f"Current operating expenses exceed revenue by {net_burn:.2f}.",
                )
            )

        if revenue_growth is not None and revenue_growth < 0:
            factors.append("Revenue contraction")
            evidence.append(
                self._evidence(
                    "revenue_growth",
                    revenue_growth,
                    f"Revenue declined {abs(revenue_growth) * 100:.2f}% month-over-month.",
                )
            )

        if (
            expense_growth is not None
            and expense_growth > 0
            and revenue_growth is not None
            and expense_growth > revenue_growth
        ):
            factors.append("Expense growth outpacing revenue growth")
            evidence.append(
                self._evidence(
                    "expense_growth",
                    expense_growth,
                    f"Expenses increased {expense_growth * 100:.2f}% month-over-month and are growing faster than revenue.",
                )
            )

        if ratio is not None:
            evidence.append(
                self._evidence(
                    "revenue_expense_ratio",
                    ratio,
                    f"Current revenue-to-expense ratio is {ratio:.3f}.",
                )
            )

        if "Revenue contraction" in factors and "Expense growth outpacing revenue growth" in factors:
            root_cause = "Revenue contraction and faster expense growth are jointly increasing liquidity pressure."
        elif "Structural operating deficit" in factors:
            root_cause = "Current operating expenses exceed revenue, creating recurring liquidity pressure."
        elif "Revenue contraction" in factors:
            root_cause = "Revenue contraction is contributing to liquidity pressure."
        elif "Expense growth outpacing revenue growth" in factors:
            root_cause = "Expense growth is outpacing revenue growth and contributing to liquidity pressure."
        else:
            root_cause = "Positive average net burn is reducing available liquidity."

        strength = 1.0 if factors or (average_burn is not None and average_burn > 0) else 0.8
        impact = average_burn if average_burn is not None and average_burn > 0 else None

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=impact,
            confidence=self._confidence(strength),
            explanation=root_cause,
        )

    def _revenue_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        growth = self._finite_float(self.state.get("revenue_growth"))
        volatility = self._finite_float(self.state.get("revenue_volatility"))

        factors: List[str] = []
        evidence: List[Dict[str, object]] = []

        if growth is not None:
            evidence.append(
                self._evidence(
                    "revenue_growth",
                    growth,
                    (
                        f"Revenue declined {abs(growth) * 100:.2f}% month-over-month."
                        if growth < 0
                        else f"Latest revenue growth is {growth * 100:.2f}% month-over-month."
                    ),
                )
            )

        unstable = (
            growth is not None
            and volatility is not None
            and volatility > abs(growth)
            and self.state_confidence != "LOW"
        )

        if volatility is not None:
            evidence.append(
                self._evidence(
                    "revenue_volatility",
                    volatility,
                    f"Historical revenue-growth volatility is {volatility:.4f}.",
                )
            )

        if growth is not None and growth < 0:
            factors.append("Revenue contraction")

        if unstable:
            factors.append("Revenue growth instability")
            root_cause = "Revenue performance is deteriorating with unstable month-to-month growth."
            explanation = (
                "The latest revenue contraction is accompanied by historical growth volatility that exceeds the magnitude of the latest growth rate."
            )
            strength = 1.0
        elif growth is not None and growth < 0:
            root_cause = "Recent revenue contraction is the primary observed driver."
            explanation = (
                "The available financial state shows a negative latest month-over-month revenue growth rate without evidence of another observable revenue driver."
            )
            strength = 1.0
        else:
            root_cause = "The supplied revenue risk has limited supporting state evidence."
            explanation = root_cause
            strength = 0.7

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=None,
            confidence=self._confidence(strength),
            explanation=explanation,
        )

    def _expense_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        expense_growth = self._finite_float(self.state.get("expense_growth"))
        revenue_growth = self._finite_float(self.state.get("revenue_growth"))
        net_burn = self._finite_float(self.state.get("net_burn"))
        ratio = self._finite_float(self.state.get("revenue_expense_ratio"))

        factors: List[str] = []
        evidence: List[Dict[str, object]] = []

        if expense_growth is not None:
            evidence.append(
                self._evidence(
                    "expense_growth",
                    expense_growth,
                    f"Expenses changed {expense_growth * 100:.2f}% month-over-month.",
                )
            )

        if revenue_growth is not None:
            evidence.append(
                self._evidence(
                    "revenue_growth",
                    revenue_growth,
                    f"Revenue changed {revenue_growth * 100:.2f}% month-over-month.",
                )
            )

        if net_burn is not None:
            evidence.append(
                self._evidence(
                    "net_burn",
                    net_burn,
                    f"Current net burn is {net_burn:.2f}.",
                )
            )

        if ratio is not None:
            evidence.append(
                self._evidence(
                    "revenue_expense_ratio",
                    ratio,
                    f"Current revenue-to-expense ratio is {ratio:.3f}.",
                )
            )

        if expense_growth is not None and expense_growth > 0:
            factors.append("Expense acceleration")
        if revenue_growth is not None and revenue_growth < 0:
            factors.append("Revenue contraction")

        if "Expense acceleration" in factors and "Revenue contraction" in factors:
            root_cause = "Expense acceleration is occurring simultaneously with revenue contraction."
            explanation = (
                "Expenses are increasing while revenue is declining, worsening the operating trajectory from both directions."
            )
            strength = 1.0
        elif (
            expense_growth is not None
            and expense_growth > 0
            and revenue_growth is not None
            and expense_growth > revenue_growth
        ):
            root_cause = "Expenses are accelerating faster than revenue."
            explanation = (
                "The latest expense growth rate exceeds the latest revenue growth rate."
            )
            strength = 1.0
        elif expense_growth is not None and expense_growth > 0:
            root_cause = "Recent expense acceleration is the primary observed driver."
            explanation = "The available state shows positive latest month-over-month expense growth."
            strength = 0.9
        else:
            root_cause = "The supplied expense risk has limited supporting state evidence."
            explanation = root_cause
            strength = 0.7

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=None,
            confidence=self._confidence(strength),
            explanation=explanation,
        )

    def _operating_deficit_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        net_burn = self._finite_float(self.state.get("net_burn"))
        revenue = self._finite_float(self.state.get("monthly_revenue"))
        expenses = self._finite_float(self.state.get("monthly_expenses"))
        ratio = self._finite_float(self.state.get("revenue_expense_ratio"))
        revenue_growth = self._finite_float(self.state.get("revenue_growth"))
        expense_growth = self._finite_float(self.state.get("expense_growth"))

        factors: List[str] = []
        evidence: List[Dict[str, object]] = []

        if revenue is not None:
            evidence.append(
                self._evidence(
                    "monthly_revenue",
                    revenue,
                    f"Current monthly revenue is {revenue:.2f}.",
                )
            )
        if expenses is not None:
            evidence.append(
                self._evidence(
                    "monthly_expenses",
                    expenses,
                    f"Current monthly expenses are {expenses:.2f}.",
                )
            )
        if net_burn is not None:
            evidence.append(
                self._evidence(
                    "net_burn",
                    net_burn,
                    f"Current monthly operating deficit is {net_burn:.2f}.",
                )
            )
        if ratio is not None:
            evidence.append(
                self._evidence(
                    "revenue_expense_ratio",
                    ratio,
                    f"Current revenue-to-expense ratio is {ratio:.3f}.",
                )
            )
        if revenue_growth is not None:
            evidence.append(
                self._evidence(
                    "revenue_growth",
                    revenue_growth,
                    f"Revenue changed {revenue_growth * 100:.2f}% month-over-month.",
                )
            )
        if expense_growth is not None:
            evidence.append(
                self._evidence(
                    "expense_growth",
                    expense_growth,
                    f"Expenses changed {expense_growth * 100:.2f}% month-over-month.",
                )
            )

        if net_burn is not None and net_burn > 0:
            factors.append("Revenue below operating expenses")
        if revenue_growth is not None and revenue_growth < 0:
            factors.append("Revenue contraction")
        if expense_growth is not None and expense_growth > 0:
            factors.append("Expense acceleration")

        if "Revenue contraction" in factors and "Expense acceleration" in factors:
            root_cause = "Revenue is below operating expenses while revenue is contracting and expenses are accelerating."
            explanation = (
                "The current deficit is being reinforced by both negative revenue growth and positive expense growth."
            )
        elif "Revenue contraction" in factors:
            root_cause = "Revenue is below operating expenses, with revenue contraction contributing to the deficit."
            explanation = "Current expenses exceed revenue and the latest revenue trend is negative."
        elif "Expense acceleration" in factors:
            root_cause = "Revenue is below operating expenses while expenses are accelerating."
            explanation = "Current expenses exceed revenue and the latest expense trend is positive."
        else:
            root_cause = "Current revenue is below operating expenses."
            explanation = "The latest financial state directly shows expenses exceeding revenue."

        impact = net_burn if net_burn is not None and net_burn > 0 else None
        strength = 1.0 if impact is not None else 0.8

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=impact,
            confidence=self._confidence(strength),
            explanation=explanation,
        )

    def _growth_instability_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        growth = self._finite_float(self.state.get("revenue_growth"))
        volatility = self._finite_float(self.state.get("revenue_volatility"))

        evidence: List[Dict[str, object]] = []
        factors: List[str] = []

        if growth is not None:
            evidence.append(
                self._evidence(
                    "revenue_growth",
                    growth,
                    f"Latest revenue growth is {growth * 100:.2f}% month-over-month.",
                )
            )
        if volatility is not None:
            evidence.append(
                self._evidence(
                    "revenue_volatility",
                    volatility,
                    f"Historical revenue-growth volatility is {volatility:.4f}.",
                )
            )

        supported = (
            growth is not None
            and volatility is not None
            and volatility > abs(growth)
            and self.state_confidence != "LOW"
        )

        if supported:
            factors.append("Revenue growth volatility")
            root_cause = "Historical revenue growth is more volatile than the latest growth rate."
            explanation = (
                "Observed revenue-growth volatility exceeds the magnitude of the latest revenue growth rate, indicating unstable historical growth."
            )
            strength = 1.0
        else:
            root_cause = "The supplied growth-instability risk has limited supporting state evidence."
            explanation = root_cause
            strength = 0.7

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=None,
            confidence=self._confidence(strength),
            explanation=explanation,
        )

    def _efficiency_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        ratio = self._finite_float(self.state.get("revenue_expense_ratio"))
        revenue = self._finite_float(self.state.get("monthly_revenue"))
        expenses = self._finite_float(self.state.get("monthly_expenses"))

        evidence: List[Dict[str, object]] = []
        factors: List[str] = []

        if ratio is not None:
            evidence.append(
                self._evidence(
                    "revenue_expense_ratio",
                    ratio,
                    f"Current revenue-to-expense ratio is {ratio:.3f}.",
                )
            )
        if revenue is not None:
            evidence.append(
                self._evidence(
                    "monthly_revenue",
                    revenue,
                    f"Current monthly revenue is {revenue:.2f}.",
                )
            )
        if expenses is not None:
            evidence.append(
                self._evidence(
                    "monthly_expenses",
                    expenses,
                    f"Current monthly expenses are {expenses:.2f}.",
                )
            )

        if ratio is not None and ratio < 1:
            factors.append("Revenue insufficient relative to expenses")
            root_cause = "Current revenue generation is insufficient relative to operating expenses."
            explanation = (
                "The current revenue-to-expense ratio is below 1, showing that revenue does not fully cover operating expenses."
            )
            strength = 1.0
        else:
            root_cause = "The supplied efficiency risk has limited supporting state evidence."
            explanation = root_cause
            strength = 0.7

        return self._build_result(
            risk=risk,
            root_cause=root_cause,
            factors=factors,
            evidence=evidence,
            impact=None,
            confidence=self._confidence(strength),
            explanation=explanation,
        )

    def _unknown_analysis(self, risk: Dict[str, object]) -> Dict[str, object]:
        metric_name = str(risk.get("metric", "unknown_metric"))
        metric_value = self._finite_float(self.state.get(metric_name))
        evidence: List[Dict[str, object]] = []

        if metric_name in self.state:
            evidence.append(
                self._evidence(
                    metric_name,
                    metric_value,
                    "Metric is present in the financial state, but no deterministic root-cause rule is defined for this risk category.",
                )
            )

        return self._build_result(
            risk=risk,
            root_cause="No deterministic root-cause rule is defined for this risk category.",
            factors=[],
            evidence=evidence,
            impact=None,
            confidence=self._confidence(0.6),
            explanation=(
                "The risk is preserved, but the engine does not invent a cause for an unsupported category."
            ),
        )

    def _build_result(
        self,
        *,
        risk: Dict[str, object],
        root_cause: str,
        factors: List[str],
        evidence: List[Dict[str, object]],
        impact: Optional[float],
        confidence: float,
        explanation: str,
    ) -> Dict[str, object]:
        finite_impact = self._finite_float(impact)
        return {
            "risk_id": str(risk["risk_id"]),
            "root_cause": root_cause,
            "contributing_factors": factors,
            "evidence": evidence,
            "estimated_monthly_impact": finite_impact,
            "confidence": self._clamp_confidence(confidence),
            "explanation": explanation,
        }

    def analyze(self) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []

        for risk in self.risks:
            category = str(risk.get("category", "")).upper()

            if category == "LIQUIDITY":
                result = self._liquidity_analysis(risk)
            elif category == "REVENUE":
                result = self._revenue_analysis(risk)
            elif category == "EXPENSE":
                result = self._expense_analysis(risk)
            elif category == "OPERATING_DEFICIT":
                result = self._operating_deficit_analysis(risk)
            elif category == "GROWTH_STABILITY":
                result = self._growth_instability_analysis(risk)
            elif category == "EFFICIENCY":
                result = self._efficiency_analysis(risk)
            else:
                result = self._unknown_analysis(risk)

            results.append(result)

        return results
