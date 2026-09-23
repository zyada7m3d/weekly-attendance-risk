"""
ATT Project — Data Analyst track
Step 5: Rule-based baseline + weekly feature engineering

Security review fixes applied (see docs/security_review_baseline.md):
  1. student_id is pseudonymized (SHA-256 hash) in the saved output file —
     the plain ID never reaches disk. The salt is read from an environment
     variable (ATT_HASH_SALT), not hardcoded in the script, so someone with
     only this file cannot brute-force the ~300 possible student_id values
     back to a hash the way they could if the salt were visible here too.
  2. Input file/sheet/column validation added, with clear errors instead
     of silent failure or a bare crash.
  3. Logging added (file + console) recording who ran the script, when,
     and against which input file — replacing print()-only output.
  4. File paths now use os.path.join so the script is not tied to one OS.

Run from the project root: python scripts/05_rule_based_flags.py

Before running for the first time, set the hash salt (any value works for
this demo dataset, but keep it the same across runs so the same student
always hashes to the same pseudonym):
    Windows (PowerShell):  $env:ATT_HASH_SALT = "some-long-random-value"
    Windows (cmd):         set ATT_HASH_SALT=some-long-random-value
    Mac/Linux:             export ATT_HASH_SALT="some-long-random-value"
"""

import getpass
import hashlib
import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (FIX 4: os.path.join instead of a hardcoded OS-specific separator)
# ---------------------------------------------------------------------------
IN_PATH = os.path.join("data", "processed", "ATT_demo_dataset_converted.xlsx")
OUT_PATH = os.path.join("outputs", "weekly_features_and_flags.xlsx")
LOG_PATH = os.path.join("logs", "rule_based_flags.log")

# ---- Baseline thresholds (deterministic, documented, defensible) ----------
LOW_ATTENDANCE_THRESHOLD = 0.75
REPEATED_FAILED_THRESHOLD = 2
STREAK_THRESHOLD = 2

# FIX 1 (hardened): the salt now comes from an environment variable instead
# of being a plain constant in the source file. With ~300 possible
# student_id values (STU00001..STU00300), a fixed in-file salt lets anyone
# holding this script brute-force every hash back to its student_id in a
# fraction of a second. Keeping the salt out of the script (and out of
# version control) means the output file's hashes cannot be reversed by
# someone who only has this code — they would also need the salt, which
# should be treated like a credential (set per-environment, not committed).
HASH_SALT = os.environ.get("ATT_HASH_SALT")
if not HASH_SALT:
    raise RuntimeError(
        "Environment variable ATT_HASH_SALT is not set. Set it before running "
        "this script (see the module docstring above for the command for "
        "your OS) — the script refuses to run with no salt rather than "
        "silently falling back to a hardcoded one."
    )

# ---------------------------------------------------------------------------
# Logging setup (FIX 3: durable record of who/when/what ran)
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)
log.info("Run started by user: %s", getpass.getuser())


def pseudonymize(student_id: str) -> str:
    """One-way hash of a student_id so the saved output never carries the
    plain ID. Deterministic so rows for the same student still join
    correctly across sheets and across runs. Uses the full 64-character
    SHA-256 digest (not truncated) to keep the ~300-value ID space from
    being trivially brute-forceable even if the salt ever leaked."""
    return hashlib.sha256(f"{HASH_SALT}:{student_id}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Load (FIX 2: validate the file, sheets, and required columns exist)
# ---------------------------------------------------------------------------
REQUIRED_SHEETS = {
    "Enrollment": {"student_id", "section_id"},
    "AttendanceSessions": {"session_id", "section_id", "week_number"},
    "AttendanceEvents": {"session_id", "student_id", "status"},
}

log.info("Run started. Input file: %s", os.path.abspath(IN_PATH))

if not os.path.exists(IN_PATH):
    log.error("Input file not found: %s", IN_PATH)
    raise FileNotFoundError(
        f"Expected input file at '{IN_PATH}' — check that data_validation.py "
        f"and build_fact_table.py have been run, or that the path is correct."
    )

try:
    all_sheets = pd.read_excel(IN_PATH, sheet_name=None)
except Exception as exc:
    log.error("Failed to open '%s' as an Excel workbook: %s", IN_PATH, exc)
    raise

for sheet_name, required_cols in REQUIRED_SHEETS.items():
    if sheet_name not in all_sheets:
        log.error("Missing required sheet '%s' in %s", sheet_name, IN_PATH)
        raise ValueError(f"Sheet '{sheet_name}' not found in {IN_PATH}")
    missing_cols = required_cols - set(all_sheets[sheet_name].columns)
    if missing_cols:
        log.error("Sheet '%s' is missing columns: %s", sheet_name, missing_cols)
        raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing_cols}")

enrollment = all_sheets["Enrollment"]
sessions = all_sheets["AttendanceSessions"]
events = all_sheets["AttendanceEvents"]

VALID_STATUSES = {"present", "late", "absent", "rejected_expired", "rejected_duplicate"}
bad_status_rows = events[~events["status"].isin(VALID_STATUSES)]
if not bad_status_rows.empty:
    log.error("%d rows in AttendanceEvents have an unrecognized status value", len(bad_status_rows))
    raise ValueError(
        f"Found {len(bad_status_rows)} rows with an unexpected 'status' value "
        f"(expected one of {sorted(VALID_STATUSES)}). Fix the source data before re-running."
    )

log.info(
    "Loaded and validated: Enrollment=%d rows, AttendanceSessions=%d rows, AttendanceEvents=%d rows",
    len(enrollment), len(sessions), len(events),
)

sessions = sessions.merge(events, on="session_id", how="left")

course_load = enrollment.groupby("student_id")["section_id"].nunique().rename("course_load")

# ---------------------------------------------------------------------------
# Build a per (student, section, week) attendance summary first
# ---------------------------------------------------------------------------
sessions["attended"] = sessions["status"].isin(["present", "late"]).astype(int)
sessions["rejected"] = sessions["status"].isin(["rejected_expired", "rejected_duplicate"]).astype(int)
sessions["absent"] = (sessions["status"] == "absent").astype(int)

weekly = (
    sessions.groupby(["student_id", "section_id", "week_number"])
    .agg(
        sessions_this_week=("status", "count"),
        attended_this_week=("attended", "sum"),
        rejected_this_week=("rejected", "sum"),
        absent_this_week=("absent", "sum"),
    )
    .reset_index()
    .sort_values(["student_id", "section_id", "week_number"])
)

# ---------------------------------------------------------------------------
# Roll up into cumulative / rolling features, week by week, per (student, section)
# ---------------------------------------------------------------------------
rows = []
for (student_id, section_id), grp in weekly.groupby(["student_id", "section_id"]):
    grp = grp.sort_values("week_number").reset_index(drop=True)
    cum_sessions = 0
    cum_attended = 0
    absence_streak = 0
    weekly_rates = []
    rejected_history = []

    for i, r in grp.iterrows():
        wk = r["week_number"]

        rate_this_week = r["attended_this_week"] / r["sessions_this_week"] if r["sessions_this_week"] else np.nan
        weekly_rates.append((wk, rate_this_week))
        rejected_history.append((wk, r["rejected_this_week"]))

        attendance_rate_to_date = (cum_attended / cum_sessions) if cum_sessions > 0 else np.nan
        sessions_to_date = cum_sessions

        trend_last_3 = np.nan
        past_rates = [rt for w, rt in weekly_rates if w < wk]
        if len(past_rates) >= 3:
            recent = past_rates[-3:]
            prior = past_rates[-6:-3] if len(past_rates) >= 6 else past_rates[:-3]
            if prior:
                trend_last_3 = np.mean(recent) - np.mean(prior)

        rejected_last_2 = sum(c for w, c in rejected_history if wk - 2 <= w < wk)

        rows.append({
            "student_id": student_id,
            "section_id": section_id,
            "week_number": wk,
            "sessions_to_date": sessions_to_date,
            "attendance_rate_to_date": attendance_rate_to_date,
            "trend_last_3": trend_last_3,
            "rejected_last_2": rejected_last_2,
            "consecutive_absences": absence_streak,
        })

        cum_sessions += r["sessions_this_week"]
        cum_attended += r["attended_this_week"]
        if r["sessions_this_week"] > 0 and r["attended_this_week"] == 0:
            absence_streak += 1
        else:
            absence_streak = 0

    rate_by_week = dict(weekly_rates)
    for row in rows[-len(grp):]:
        nxt = row["week_number"] + 1
        if nxt in rate_by_week:
            row["label_next_week_low"] = int(rate_by_week[nxt] < 0.5)
        else:
            row["label_next_week_low"] = np.nan

features = pd.DataFrame(rows)
features = features.merge(course_load, on="student_id", how="left")

# ---------------------------------------------------------------------------
# Deterministic rule-based flags (the baseline itself)
# ---------------------------------------------------------------------------
features["flag_low_attendance"] = features["attendance_rate_to_date"] < LOW_ATTENDANCE_THRESHOLD
features["flag_repeated_failed"] = features["rejected_last_2"] >= REPEATED_FAILED_THRESHOLD
features["flag_absence_streak"] = features["consecutive_absences"] >= STREAK_THRESHOLD
features["flag_any"] = (
    features["flag_low_attendance"]
    | features["flag_repeated_failed"]
    | features["flag_absence_streak"]
)

features_clean = features.dropna(subset=["attendance_rate_to_date"]).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Quick baseline sanity report
# ---------------------------------------------------------------------------
eval_df = features_clean.dropna(subset=["label_next_week_low"])
tp = ((eval_df["flag_any"]) & (eval_df["label_next_week_low"] == 1)).sum()
fp = ((eval_df["flag_any"]) & (eval_df["label_next_week_low"] == 0)).sum()
fn = ((~eval_df["flag_any"]) & (eval_df["label_next_week_low"] == 1)).sum()
tn = ((~eval_df["flag_any"]) & (eval_df["label_next_week_low"] == 0)).sum()
precision = tp / (tp + fp) if (tp + fp) else float("nan")
recall = tp / (tp + fn) if (tp + fn) else float("nan")

log.info("Baseline (rule-based) sanity check vs. next-week-low label:")
log.info("  rows evaluated: %d", len(eval_df))
log.info("  TP=%d  FP=%d  FN=%d  TN=%d", tp, fp, fn, tn)
log.info("  precision=%.3f  recall=%.3f", precision, recall)
log.info("  flagged rate overall: %.3f", features_clean["flag_any"].mean())

# ---------------------------------------------------------------------------
# Save (FIX 1: pseudonymize student_id before writing to disk)
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

features_out = features_clean.copy()
features_out["student_id"] = features_out["student_id"].apply(pseudonymize)
features_out = features_out.rename(columns={"student_id": "student_id_hash"})

with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
    features_out.to_excel(writer, sheet_name="WeeklyFeaturesAndFlags", index=False)

log.info("Saved: %s (%d rows, student_id pseudonymized)", OUT_PATH, len(features_out))
log.info("Run by: %s | finished at: %s", getpass.getuser(), datetime.now().isoformat(timespec="seconds"))

print(f"\nSaved: {OUT_PATH}")
print(f"Rows: {len(features_out)}")
print(f"Log written to: {LOG_PATH}")
print("NOTE: 'student_id' is now saved as 'student_id_hash' (pseudonymized).")