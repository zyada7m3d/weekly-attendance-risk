"""
ATT Project — API wrapper
Exposes each pipeline script as its own endpoint so it can be triggered
remotely (and shown in Swagger at /docs).

Order matters — run in this sequence:
  1. POST /validate-data       (data_validation.py)
  2. POST /build-fact-table    (build_fact_table.py)
  3. POST /dashboard-kpis      (dashboard_kpis.py)
  4. POST /baseline-flags      (baseline.py — needs ATT_HASH_SALT env var set)

Run locally: uvicorn main:app --reload
"""

import os
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="ATT Attendance Risk API", version="1.0")

SCRIPTS_DIR = "scripts"  # scripts must live in ./scripts relative to project root

# Only files under these folders can ever be downloaded — keeps /download from
# being able to serve arbitrary files off the server.
ALLOWED_DOWNLOAD_DIRS = ["outputs", "docs", os.path.join("data", "processed")]


def run_script(script_name: str, output_files=None):
    """Run a script and, on success, attach download links for the files it produces."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script not found: {script_path}")

    result = subprocess.run(
        ["python", script_path],
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={"stdout": result.stdout, "stderr": result.stderr},
        )

    downloads = []
    for f in output_files or []:
        if os.path.exists(f):
            downloads.append({"file": f, "download_url": f"/download?path={f}"})

    return {"stdout": result.stdout, "stderr": result.stderr, "downloads": downloads}


@app.get("/")
def root():
    return {"message": "ATT Attendance Risk API is running. Visit /docs for Swagger UI."}


@app.get("/download", summary="Download a file produced by one of the pipeline steps")
def download(path: str):
    """Pass the exact 'file' value returned in a previous step's 'downloads' list."""
    normalized = os.path.normpath(path)
    if not any(
        normalized == d or normalized.startswith(d + os.sep) for d in ALLOWED_DOWNLOAD_DIRS
    ):
        raise HTTPException(status_code=403, detail="That path is not downloadable.")
    if not os.path.exists(normalized):
        raise HTTPException(status_code=404, detail=f"File not found: {normalized}")
    return FileResponse(normalized, filename=os.path.basename(normalized))


@app.post("/validate-data", summary="Step 2: Data validation")
def validate_data():
    """Runs data_validation.py — checks the raw dataset and writes a data quality report."""
    return run_script(
        "data_validation.py",
        output_files=[
            os.path.join("docs", "data_quality_report.md"),
            os.path.join("data", "processed", "ATT_demo_dataset_converted.xlsx"),
        ],
    )


@app.post("/build-fact-table", summary="Step 3: Build fact table")
def build_fact_table():
    """Runs build_fact_table.py — joins events/sessions/sections/courses/students into one flat table."""
    return run_script(
        "build_fact_table.py",
        output_files=[os.path.join("data", "processed", "fact_attendance.csv")],
    )


@app.post("/dashboard-kpis", summary="Step 4: Dashboard KPIs")
def dashboard_kpis():
    """Runs dashboard_kpis.py — computes attendance/late rates, missing-data count, low-attendance warnings."""
    return run_script(
        "dashboard_kpis.py",
        output_files=[
            os.path.join("outputs", "kpi_by_section.csv"),
            os.path.join("outputs", "kpi_by_student.csv"),
            os.path.join("outputs", "low_attendance_warnings.csv"),
        ],
    )


@app.post("/baseline-flags", summary="Step 5: Rule-based baseline flags")
def baseline_flags():
    """Runs baseline.py — builds weekly features and rule-based risk flags.
    Requires the ATT_HASH_SALT environment variable to be set on the server."""
    return run_script(
        "baseline.py",
        output_files=[os.path.join("outputs", "weekly_features_and_flags.xlsx")],
    )