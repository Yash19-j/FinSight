from __future__ import annotations

import math
from typing import Dict, List, Optional


class RiskDetector:
    """
    Deterministic financial risk detector operating only on the normalized
    FinancialStateEngine.build_state() output.
    """

    SEVERITY_RANK = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    CONFIDENCE_BY_STATE = {
        "HIGH": 0.90,
        "MEDIUM": 0.75,
        "LOW": 0.50,
    }

    REQUIRED_KEYS = {
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
        "data_confidence",
        "available_data",
    }

    def __init__(self, financial_state: Dict[str, object]):
        if not isinstance(financial_state, dict):
            raise TypeError("RiskDetector expects a financial-state dictionary.")

        missing = self.REQUIRED_KEYS - set(financial_state.keys())
        if missing:
            raise ValueError(
                f"Financial state is missing required keys: {sorted(missing)}"
            )

        self.state = financial_state
        confidence_label = str(self.state["data_confidence"]).upper()
        if confidence_label not in self.CONFIDENCE_BY_STATE:
            raise ValueError(
                "data_confidence must be one of: LOW, MEDIUM, HIGH"
            )

        self.state_confidence = confidence_label
        self.base_confidence = self.CONFIDENCE_BY_STATE[confidence_label]

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
        """
        Rule confidence, not a model probability.
        strength should be <= 1 and is used only to discount borderline signals.
        """
        return round(
            self._clamp_confidence(self.base_confidence * strength),
            2,
        )

    def _risk(
        self,
        *,
        risk_id: str,
        category: str,
        severity: str,
        title: str,
        metric: str,
        current_value: Optional[float],
        threshold: Optional[float],
        financial_impact: Optional[float],
        confidence: float,
        evidence: str,
    ) -> Dict[str, object]:
        return {
            "risk_id": risk_id,
            "category": category,
            "severity": severity,
            "title": title,
            "metric": metric,
            "current_value": current_value,
            "threshold": threshold,
            "financial_impact": financial_impact,
            "confidence": self._clamp_confidence(confidence),
            "evidence": evidence,
        }

    def _liquidity_risk(self) -> Optional[Dict[str, object]]:
        runway = self._finite_float(self.state["runway_months"])
        if runway is None or runway > 12:
            return None

        average_burn = self._finite_float(self.state["average_net_burn"])
        impact = average_burn if average_burn is not None and average_burn > 0 else None

        if runway < 3:
            severity = "CRITICAL"
            threshold = 3.0
            risk_id = "liquidity_critical"
            strength = 1.0
        elif runway < 6:
            severity = "HIGH"
            threshold = 6.0
            risk_id = "liquidity_high"
            strength = 1.0
        else:
            severity = "MEDIUM"
            threshold = 12.0
            risk_id = "liquidity_medium"
            # Slightly discount the weakest part of the liquidity signal.
            strength = 0.9 if runway > 10 else 1.0

        return self._risk(
            risk_id=risk_id,
            category="LIQUIDITY",
            severity=severity,
            title="Short liquidity runway",
            metric="runway_months",
            current_value=runway,
            threshold=threshold,
            financial_impact=impact,
            confidence=self._confidence(strength),
            evidence=(
                f"Current average net burn implies approximately "
                f"{runway:.2f} months of runway."
            ),
        )

    def _revenue_decline_risk(self) -> Optional[Dict[str, object]]:
        growth = self._finite_float(self.state["revenue_growth"])
        if growth is None or growth >= 0:
            return None

        if growth < -0.15:
            severity = "CRITICAL"
            threshold = -0.15
            risk_id = "revenue_decline_critical"
            strength = 1.0
        elif growth < -0.05:
            severity = "HIGH"
            threshold = -0.05
            risk_id = "revenue_decline_high"
            strength = 1.0
        else:
            severity = "MEDIUM"
            threshold = 0.0
            risk_id = "revenue_decline_medium"
            # A very small negative movement is a weaker signal.
            strength = 0.85 if growth > -0.02 else 1.0

        return self._risk(
            risk_id=risk_id,
            category="REVENUE",
            severity=severity,
            title="Revenue declined in the latest period",
            metric="revenue_growth",
            current_value=growth,
            threshold=threshold,
            financial_impact=None,
            confidence=self._confidence(strength),
            evidence=(
                f"Latest month-over-month revenue growth is "
                f"{growth * 100:.2f}%."
            ),
        )

    def _expense_acceleration_risk(self) -> Optional[Dict[str, object]]:
        growth = self._finite_float(self.state["expense_growth"])
        if growth is None or growth <= 0:
            return None

        if growth > 0.20:
            severity = "CRITICAL"
            threshold = 0.20
            risk_id = "expense_acceleration_critical"
            strength = 1.0
        elif growth > 0.10:
            severity = "HIGH"
            threshold = 0.10
            risk_id = "expense_acceleration_high"
            strength = 1.0
        elif growth > 0.05:
            severity = "MEDIUM"
            threshold = 0.05
            risk_id = "expense_acceleration_medium"
            strength = 1.0
        else:
            severity = "LOW"
            threshold = 0.0
            risk_id = "expense_acceleration_low"
            strength = 0.8 if growth < 0.02 else 1.0

        return self._risk(
            risk_id=risk_id,
            category="EXPENSE",
            severity=severity,
            title="Expenses accelerated in the latest period",
            metric="expense_growth",
            current_value=growth,
            threshold=threshold,
            financial_impact=None,
            confidence=self._confidence(strength),
            evidence=(
                f"Latest month-over-month expense growth is "
                f"{growth * 100:.2f}%."
            ),
        )

    def _operating_deficit_risk(self) -> Optional[Dict[str, object]]:
        net_burn = self._finite_float(self.state["net_burn"])
        revenue = self._finite_float(self.state["monthly_revenue"])

        if net_burn is None or net_burn <= 0:
            return None

        if revenue is None or revenue <= 0:
            # With zero revenue, deficit/revenue is undefined but the deficit
            # itself is clearly severe.
            severity = "CRITICAL"
            threshold = 0.25
            ratio = None
        else:
            ratio = net_burn / revenue
            if ratio > 0.25:
                severity = "CRITICAL"
                threshold = 0.25
            elif ratio > 0.10:
                severity = "HIGH"
                threshold = 0.10
            else:
                severity = "MEDIUM"
                threshold = 0.10

        if ratio is None:
            evidence = (
                f"Latest period has a net operating deficit of {net_burn:.2f} "
                "with zero or unavailable revenue."
            )
        else:
            evidence = (
                f"Latest net burn is {net_burn:.2f}, equal to "
                f"{ratio * 100:.2f}% of current revenue."
            )

        return self._risk(
            risk_id=f"operating_deficit_{severity.lower()}",
            category="OPERATING_DEFICIT",
            severity=severity,
            title="Current expenses exceed revenue",
            metric="net_burn",
            current_value=net_burn,
            threshold=threshold,
            financial_impact=net_burn,
            confidence=self._confidence(),
            evidence=evidence,
        )

    def _growth_instability_risk(self) -> Optional[Dict[str, object]]:
        if self.state_confidence == "LOW":
            return None

        volatility = self._finite_float(self.state["revenue_volatility"])
        growth = self._finite_float(self.state["revenue_growth"])

        if volatility is None or growth is None:
            return None

        if volatility <= abs(growth):
            return None

        return self._risk(
            risk_id="growth_instability_medium",
            category="GROWTH_STABILITY",
            severity="MEDIUM",
            title="Revenue growth is unstable",
            metric="revenue_volatility",
            current_value=volatility,
            threshold=abs(growth),
            financial_impact=None,
            confidence=self._confidence(0.9),
            evidence=(
                f"Revenue-growth volatility ({volatility:.4f}) exceeds the "
                f"absolute latest revenue growth ({abs(growth):.4f})."
            ),
        )

    def _efficiency_deterioration_risk(
        self,
        operating_deficit_detected: bool,
    ) -> Optional[Dict[str, object]]:
        ratio = self._finite_float(self.state["revenue_expense_ratio"])
        if ratio is None or ratio >= 1:
            return None

        # Avoid duplicating the same current-period revenue-vs-expense condition.
        if operating_deficit_detected:
            return None

        # "Materially below 1" uses 0.90 as a simple transparent cutoff.
        if ratio >= 0.90:
            return None

        return self._risk(
            risk_id="efficiency_deterioration_medium",
            category="EFFICIENCY",
            severity="MEDIUM",
            title="Revenue is materially below current expenses",
            metric="revenue_expense_ratio",
            current_value=ratio,
            threshold=0.90,
            financial_impact=None,
            confidence=self._confidence(),
            evidence=(
                f"Current revenue-to-expense ratio is {ratio:.3f}, below "
                "the material-efficiency threshold of 0.90."
            ),
        )

    def detect(self) -> List[Dict[str, object]]:
        risks: List[Dict[str, object]] = []

        liquidity = self._liquidity_risk()
        if liquidity:
            risks.append(liquidity)

        revenue = self._revenue_decline_risk()
        if revenue:
            risks.append(revenue)

        expenses = self._expense_acceleration_risk()
        if expenses:
            risks.append(expenses)

        deficit = self._operating_deficit_risk()
        if deficit:
            risks.append(deficit)

        instability = self._growth_instability_risk()
        if instability:
            risks.append(instability)

        efficiency = self._efficiency_deterioration_risk(
            operating_deficit_detected=deficit is not None
        )
        if efficiency:
            risks.append(efficiency)

        def sort_key(risk: Dict[str, object]):
            impact = self._finite_float(risk["financial_impact"])
            return (
                -self.SEVERITY_RANK[str(risk["severity"])],
                -(impact if impact is not None else -1.0),
                -float(risk["confidence"]),
                str(risk["risk_id"]),
            )

        risks.sort(key=sort_key)
        return risks
