"""
ATT Project — Data Analyst track
Step 3: Build the Fact Table

Joins AttendanceEvents + AttendanceSessions + Sections + Courses + Students
into one flat table: one row = one student's attendance event in one
session, with course/section/student details already attached.

Reads from the *converted* file (data_validation.py's output) so that
date/timestamp columns are already real datetimes.

Run from the project root: python scripts/build_fact_table.py
"""

import pandas as pd

IN_PATH = "data/processed/ATT_demo_dataset_converted.xlsx"
OUT_PATH = "data/processed/fact_attendance.csv"

# ---------------------------------------------------------------------
# 1. Load the sheets we need
# ---------------------------------------------------------------------
sheets = pd.read_excel(IN_PATH, sheet_name=None)

events = sheets["AttendanceEvents"]
sessions = sheets["AttendanceSessions"]
sections = sheets["Sections"]
courses = sheets["Courses"]
students = sheets["Students"]

# ---------------------------------------------------------------------
# 2. Join step by step
# ---------------------------------------------------------------------
fact = events.merge(sessions, on="session_id", suffixes=("", "_sess"))
fact = fact.merge(sections, on="section_id", suffixes=("", "_sec"))
fact = fact.merge(courses, on="course_code", how="left")
fact = fact.merge(students, on="student_id", how="left", suffixes=("", "_stu"))

# ---------------------------------------------------------------------
# 3. Sanity check the result
# ---------------------------------------------------------------------
print("Fact table shape:", fact.shape)
print("AttendanceEvents shape:", events.shape)
assert fact.shape[0] == events.shape[0], (
    "Row count changed after merging — check for duplicate keys in a "
    "joined table (e.g. a section_id or course_code appearing twice)."
)
print("\nRow count matches AttendanceEvents — no fan-out from the joins.\n")

print(fact[["event_id", "student_id", "section_id", "course_code", "course_name", "status", "date"]].head())

# ---------------------------------------------------------------------
# 4. Save for reuse by later scripts (KPIs, rule-based flags, etc.)
# ---------------------------------------------------------------------
import os

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
fact.to_csv(OUT_PATH, index=False)
print(f"\nSaved fact table to: {OUT_PATH}")