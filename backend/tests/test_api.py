from __future__ import annotations

import io

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


VALID_CSV = """Month,Revenue,Expenses,Cash
2025-01,400000,520000,5000000
2025-02,420000,530000,4890000
2025-03,445000,545000,4770000
2025-04,460000,555000,4675000
2025-05,480000,565000,4590000
2025-06,500000,580000,4510000
2025-07,525000,590000,4445000
2025-08,550000,605000,4390000
2025-09,570000,620000,4340000
2025-10,595000,635000,4300000
2025-11,620000,650000,4270000
2025-12,650000,665000,4250000
"""


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_endpoint_returns_complete_pipeline_contract() -> None:
    response = client.get("/demo")

    assert response.status_code == 200

    payload = response.json()

    expected_sections = {
        "financial_state",
        "risks",
        "root_causes",
        "scenarios",
        "decision",
        "policy",
        "action",
        "execution",
        "verification",
        "metadata",
    }

    assert set(payload) == expected_sections


def test_demo_endpoint_returns_approved_dry_run() -> None:
    response = client.get("/demo")

    assert response.status_code == 200

    payload = response.json()

    assert payload["policy"]["status"] == "APPROVE"
    assert payload["action"] is not None

    assert payload["execution"]["status"] == "SIMULATED"
    assert payload["execution"]["mode"] == "DRY_RUN"

    assert payload["verification"]["status"] == "EXECUTION_VERIFIED"
    assert payload["verification"]["verified"] is True
    assert payload["verification"]["outcome_available"] is False


def test_analyze_accepts_valid_csv() -> None:
    response = client.post(
        "/analyze",
        files={
            "file": (
                "financials.csv",
                io.BytesIO(VALID_CSV.encode("utf-8")),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert "financial_state" in payload
    assert "decision" in payload
    assert "policy" in payload
    assert "action" in payload
    assert "execution" in payload
    assert "verification" in payload


def test_analyze_rejects_non_csv_file() -> None:
    response = client.post(
        "/analyze",
        files={
            "file": (
                "financials.txt",
                io.BytesIO(b"Revenue,Expenses,Cash\n100,120,1000"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are supported."


def test_analyze_rejects_empty_csv() -> None:
    response = client.post(
        "/analyze",
        files={
            "file": (
                "empty.csv",
                io.BytesIO(b""),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded CSV is empty."


def test_analyze_rejects_malformed_financial_data() -> None:
    malformed_csv = """Month,Revenue,Expenses
2025-01,400000,520000
2025-02,420000,530000
"""

    response = client.post(
        "/analyze",
        files={
            "file": (
                "malformed.csv",
                io.BytesIO(malformed_csv.encode("utf-8")),
                "text/csv",
            )
        },
    )

    assert response.status_code == 422


def test_analyze_accepts_single_row_dataset() -> None:
    single_row_csv = """Month,Revenue,Expenses,Cash
    2025-01,400000,520000,5000000
    """

    response = client.post(
        "/analyze",
        files={
            "file": (
                "single_row.csv",
                io.BytesIO(single_row_csv.encode("utf-8")),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert "financial_state" in payload
    assert "risks" in payload
    assert "decision" in payload
    assert "policy" in payload


def test_api_response_is_json_serializable() -> None:
    response = client.get("/demo")

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_api_does_not_expose_pipeline_traceback() -> None:
    # A CSV with valid structure but invalid numeric data should produce
    # a controlled HTTP error rather than a Python traceback.
    invalid_numeric_csv = """Month,Revenue,Expenses,Cash
2025-01,abc,520000,5000000
2025-02,420000,530000,4890000
"""

    response = client.post(
        "/analyze",
        files={
            "file": (
                "invalid.csv",
                io.BytesIO(invalid_numeric_csv.encode("utf-8")),
                "text/csv",
            )
        },
    )

    assert response.status_code in {400, 422}

    body = response.text

    assert "Traceback" not in body
    assert "File \"" not in body