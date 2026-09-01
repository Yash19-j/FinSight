from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class FinancialStateEngine:
    """
    Build a normalized snapshot of a merchant's financial state from the
    repository's existing monthly financial DataFrame contract.

    Required columns:
        Revenue, Expenses, Cash

    The engine intentionally does not call FinancialEngine.compute_basic_metrics()
    because that method currently contains the known CAGR interval bug. CAGR is
    not part of this state contract.
    """

    REQUIRED_COLUMNS = {"Revenue", "Expenses", "Cash"}

    DATASET_SIGNATURES = {
        "payments": {
            "payment_id",
            "merchant_id",
            "timestamp",
            "amount",
            "currency",
            "status",
            "method",
            "customer_id",
        },
        "settlements": {
            "settlement_id",
            "merchant_id",
            "payment_id",
            "expected_amount",
            "settled_amount",
            "settlement_date",
            "status",
        },
        "receivables": {
            "invoice_id",
            "merchant_id",
            "customer_id",
            "invoice_date",
            "due_date",
            "amount",
            "paid_amount",
            "status",
        },
        "refunds": {
            "refund_id",
            "payment_id",
            "merchant_id",
            "refund_date",
            "amount",
            "reason",
            "status",
        },
        "payouts": {
            "payout_id",
            "merchant_id",
            "beneficiary_id",
            "date",
            "amount",
            "status",
            "purpose",
        },
    }

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._validate_and_prepare()

    def _validate_and_prepare(self) -> None:
        if not isinstance(self.df, pd.DataFrame):
            raise TypeError("FinancialStateEngine expects a pandas DataFrame.")

        missing = self.REQUIRED_COLUMNS - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Missing required financial columns: {sorted(missing)}"
            )

        if self.df.empty:
            raise ValueError("Financial data must contain at least one observation.")

        for column in self.REQUIRED_COLUMNS:
            self.df[column] = pd.to_numeric(self.df[column], errors="raise")

        required_values = self.df[list(self.REQUIRED_COLUMNS)].to_numpy(dtype=float)
        if not np.isfinite(required_values).all():
            raise ValueError(
                "Revenue, Expenses and Cash must contain only finite numeric values."
            )

        if "Month" in self.df.columns:
            self.df = self.df.sort_values("Month", kind="stable").reset_index(drop=True)
        else:
            self.df = self.df.reset_index(drop=True)

    @staticmethod
    def _safe_growth(series: pd.Series) -> List[float]:
        """
        Compute finite month-over-month growth observations.

        A period whose previous value is zero has undefined percentage growth and
        is therefore excluded rather than represented as NaN or +/-inf.
        """
        values = series.astype(float).to_numpy()
        growth: List[float] = []

        for previous, current in zip(values[:-1], values[1:]):
            if previous == 0:
                continue

            value = (current - previous) / previous
            if np.isfinite(value):
                growth.append(float(value))

        return growth

    @staticmethod
    def _latest_or_zero(values: List[float]) -> float:
        return float(values[-1]) if values else 0.0

    @staticmethod
    def _volatility(values: List[float]) -> float:
        # Sample standard deviation is defensible for observed historical growth.
        # One or zero observations are insufficient to estimate dispersion.
        if len(values) < 2:
            return 0.0

        result = float(np.std(values, ddof=1))
        return result if np.isfinite(result) else 0.0

    @staticmethod
    def _data_confidence(usable_growth_observations: int) -> str:
        if usable_growth_observations >= 6:
            return "HIGH"
        if usable_growth_observations >= 3:
            return "MEDIUM"
        return "LOW"

    def _available_data(self) -> Dict[str, bool]:
        columns = set(self.df.columns)
        has_rows = not self.df.empty

        availability = {
            "financial_history": bool(
                has_rows and self.REQUIRED_COLUMNS.issubset(columns)
            )
        }

        for dataset, signature in self.DATASET_SIGNATURES.items():
            availability[dataset] = bool(
                has_rows and signature.issubset(columns)
            )

        return availability

    def build_state(self) -> Dict[str, object]:
        revenue = self.df["Revenue"].astype(float)
        expenses = self.df["Expenses"].astype(float)
        cash = self.df["Cash"].astype(float)

        current_revenue = float(revenue.iloc[-1])
        current_expenses = float(expenses.iloc[-1])
        current_cash = float(cash.iloc[-1])

        net_burn_series = expenses - revenue
        current_net_burn = float(net_burn_series.iloc[-1])
        average_net_burn = float(net_burn_series.mean())

        runway_months: Optional[float]
        if average_net_burn > 0:
            runway_months = float(current_cash / average_net_burn)
        else:
            runway_months = None

        revenue_growth_values = self._safe_growth(revenue)
        expense_growth_values = self._safe_growth(expenses)

        revenue_growth = self._latest_or_zero(revenue_growth_values)
        expense_growth = self._latest_or_zero(expense_growth_values)

        revenue_volatility = self._volatility(revenue_growth_values)
        expense_volatility = self._volatility(expense_growth_values)

        revenue_expense_ratio: Optional[float]
        if current_expenses > 0:
            revenue_expense_ratio = float(current_revenue / current_expenses)
        else:
            revenue_expense_ratio = None

        # Preserve the existing repository's burn-multiple interpretation:
        # average net burn / net new revenue, but normalize undefined/non-finite
        # results to None instead of infinity.
        net_new_revenue = float(revenue.iloc[-1] - revenue.iloc[0])
        burn_multiple: Optional[float]
        if net_new_revenue > 0:
            value = average_net_burn / net_new_revenue
            burn_multiple = float(value) if np.isfinite(value) else None
        else:
            burn_multiple = None

        # Confidence is based on history usable for both growth dimensions.
        usable_growth_observations = min(
            len(revenue_growth_values),
            len(expense_growth_values),
        )

        state: Dict[str, object] = {
            "cash": current_cash,
            "monthly_revenue": current_revenue,
            "monthly_expenses": current_expenses,
            "net_burn": current_net_burn,
            "average_net_burn": average_net_burn,
            "runway_months": runway_months,
            "revenue_growth": revenue_growth,
            "expense_growth": expense_growth,
            "revenue_volatility": revenue_volatility,
            "expense_volatility": expense_volatility,
            "revenue_expense_ratio": revenue_expense_ratio,
            "burn_multiple": burn_multiple,
            "data_confidence": self._data_confidence(
                usable_growth_observations
            ),
            "available_data": self._available_data(),
        }

        return state
