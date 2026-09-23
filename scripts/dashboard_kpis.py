"""
ATT Project — Data Analyst track
Step 4: Dashboard KPIs (ATT-FR-10)

Reads the fact table built in step 3 and computes:
  - attendance rate + late rate per section
  - attendance rate per student
  - missing-data count (expected events with no record)
  - low-attendance warnings (students below a threshold)

Saves everything to outputs/ so it's ready to feed the Dashboard.

Run from the project root: python scripts/04_dashboard_kpis.py
"""

import os

import pandas as pd

IN_PATH = "data/processed/fact_attendance.csv"
CONVERTED_XLSX = "data/processed/ATT_demo_dataset_converted.xlsx"
OUT_DIR = "outputs"

LOW_ATTENDANCE_THRESHOLD = 0.75  # below this rate -> low-attendance warning

# ---------------------------------------------------------------------
# 1. Load the fact table
# ---------------------------------------------------------------------
fact = pd.read_csv(IN_PATH)
fact["date"] = pd.to_datetime(fact["date"])

print("Fact table loaded:", fact.shape)

# ---------------------------------------------------------------------
# 2. Attendance rate + late rate per group (reused for section and student)
# ---------------------------------------------------------------------
def rate_table(group_col):
    g = fact.groupby(group_col)["status"]
    total = g.count()
    present = g.apply(lambda s: (s == "present").sum())
    late = g.apply(lambda s: (s == "late").sum())
    absent = g.apply(lambda s: (s == "absent").sum())
    out = pd.DataFrame({
        "total_events": total,
        "attendance_rate": ((present + late) / total).round(3),
        "late_rate": (late / total).round(3),
        "absent_count": absent,
    })
    return out.reset_index()

kpi_by_section = rate_table("section_id")
print("\n--- Attendance/Late rate by section ---")
print(kpi_by_section)

kpi_by_student = rate_table("student_id")
kpi_by_student = kpi_by_student.merge(
    fact[["student_id", "name"]].drop_duplicates(),
    on="student_id", how="left"
)

# ---------------------------------------------------------------------
# 3. Missing-data count
# ---------------------------------------------------------------------
enrollment = pd.read_excel(CONVERTED_XLSX, sheet_name="Enrollment")
sessions = pd.read_excel(CONVERTED_XLSX, sheet_name="AttendanceSessions")

expected = enrollment.merge(sessions, on="section_id")
expected_pairs = set(zip(expected["session_id"], expected["student_id"]))
actual_pairs = set(zip(fact["session_id"], fact["student_id"]))

missing_pairs = expected_pairs - actual_pairs
missing_data_count = len(missing_pairs)
print(f"\nMissing-data count: {missing_data_count}")

# ---------------------------------------------------------------------
# 4. Low-attendance warnings
# ---------------------------------------------------------------------
low_attendance_students = kpi_by_student[
    kpi_by_student["attendance_rate"] < LOW_ATTENDANCE_THRESHOLD
].sort_values("attendance_rate")

print(f"\nStudents below {LOW_ATTENDANCE_THRESHOLD:.0%} attendance: {len(low_attendance_students)}")
print(low_attendance_students[["student_id", "name", "attendance_rate"]])

# ---------------------------------------------------------------------
# 5. Save everything for the Dashboard
# ---------------------------------------------------------------------
os.makedirs(OUT_DIR, exist_ok=True)

kpi_by_section.to_csv(f"{OUT_DIR}/kpi_by_section.csv", index=False)
kpi_by_student.to_csv(f"{OUT_DIR}/kpi_by_student.csv", index=False)
low_attendance_students.to_csv(f"{OUT_DIR}/low_attendance_warnings.csv", index=False)

print("\nSaved: kpi_by_section.csv, kpi_by_student.csv, low_attendance_warnings.csv -> outputs/")