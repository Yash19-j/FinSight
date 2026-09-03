from __future__ import annotations

import io
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .services.decision_pipeline import DecisionPipeline


app = FastAPI(
    title="FinSight API",
    version="1.0.0",
    description="Financial decision intelligence API for FinSight.",
)


# ---------------------------------------------------------------------------
# Demo dataset
# ---------------------------------------------------------------------------

DEMO_DATA = pd.DataFrame(
    {
        "Month": [
            "2025-01",
            "2025-02",
            "2025-03",
            "2025-04",
            "2025-05",
            "2025-06",
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
        ],
        "Revenue": [
            400000,
            420000,
            445000,
            460000,
            480000,
            500000,
            525000,
            550000,
            570000,
            595000,
            620000,
            650000,
        ],
        "Expenses": [
            520000,
            530000,
            545000,
            555000,
            565000,
            580000,
            590000,
            605000,
            620000,
            635000,
            650000,
            665000,
        ],
        "Cash": [
            5000000,
            4890000,
            4770000,
            4675000,
            4590000,
            4510000,
            4445000,
            4390000,
            4340000,
            4300000,
            4270000,
            4250000,
        ],
    }
)


# ---------------------------------------------------------------------------
# Internal pipeline boundary
# ---------------------------------------------------------------------------

def _run_pipeline(df: pd.DataFrame) -> dict[str, Any]:
    """
    Single application boundary for FinSight's decision intelligence.

    The API performs input handling only. All financial/business logic
    remains inside DecisionPipeline.
    """
    try:
        result = DecisionPipeline(df).run()

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        # Do not expose internal pipeline exception details to API clients.
        raise HTTPException(
            status_code=422,
            detail="Financial analysis could not be completed.",
        ) from exc

    return result


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Demo analysis
# ---------------------------------------------------------------------------

@app.get("/demo")
def demo() -> JSONResponse:
    """
    Run FinSight against the built-in demonstration company.
    """
    result = _run_pipeline(DEMO_DATA.copy())

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# CSV analysis
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Analyze an uploaded financial CSV.

    Required CSV columns:
        Revenue
        Expenses
        Cash

    Optional:
        Month
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A CSV file is required.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported.",
        )

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded CSV is empty.",
            )

        df = pd.read_csv(io.BytesIO(contents))

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to parse CSV file.",
        ) from exc

    result = _run_pipeline(df)

    return JSONResponse(content=result)